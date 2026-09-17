package com.turkbey.goktungumav.kopru

import android.util.Base64
import com.turkbey.goktungumav.veri.Gunluk
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.net.URI
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * KOPRU AJANI — merkeze kalici TERS WebSocket baglantisi (Kotlin).
 *
 * Masaustu koprunun `kopru/ajan.py` sinifiyla AYNI protokolu konusur;
 * merkez tarafinda (GRCON `mk_role.py`, GRCOFF `kopru_kabul.py`) ikinci
 * bir protokol uygulamasi gerekmez:
 *
 * ```
 * Telefon --- WSS connect ---> Merkez (/kopru)
 *         --- {"tur":"merhaba", kurulum_uid, gizli, ...} -->
 *         <-- {"tur":"merhaba_tamam", ornek_id, kanal} ---
 *         --- {"tur":"nabiz"} (25 sn) -->  <-- {"tur":"nabiz_tamam"}
 *         <-- {"tur":"istek", istek_id, eylem, veri} ---
 *         --- {"tur":"yanit", istek_id, veri|hata} -->
 *         <-> {"tur":"akis", kanal_id, veri(b64)}        (ham byte)
 * ```
 *
 * ## Tasarim kararlari
 *
 * 1. Baglantiyi HER ZAMAN saha acar; telefon NAT/mobil sebeke
 *    arkasindadir ve merkez ona ulasamaz. Ayni soket uzerinden merkez
 *    istek gonderir. Telefonda hicbir dinleyen port yoktur.
 * 2. Ustel geri cekilme (3 sn -> 60 sn): merkez bakimdayken binlerce
 *    cihazin selle merkezi bogmasini onler.
 * 3. Islev haritasi disaridan verilir; ajan uygulamanin ic yapisini
 *    (USB, DJI SDK) BILMEZ. Boylece MAVLink ve DJI kopruleri ayni
 *    ajani paylasir.
 * 4. `akis` paketleri ATESLE-UNUT: yanit uretilmez, kuyruga alinmaz.
 *    Kopmus baglantida biriken telemetri, baglanti dondugunde eski
 *    konumu "guncel" gibi gosterirdi.
 * 5. Merkezden gelen `akis` yazimlari TEK is parcaciginda, sirayla
 *    yapilir: MAVLink byte sirasi bozulursa cerceve ayristirici
 *    kopar.
 */
class KopruAjan(
    private val kimlikOku: () -> KopruKimlik.Deger?,
    private val surum: String,
    private val platform: String,
    private val makineAdi: String,
    private val islevler: Map<String, (JSONObject) -> JSONObject>,
    private val akisYaz: (Int, ByteArray) -> Unit,
    private val yetenekler: () -> JSONObject,
    private val dronSayisi: () -> Int,
    private val nabizEk: () -> JSONObject
) {

    enum class Durum { KAPALI, BAGLANIYOR, BAGLI, HATA }

    data class Bilgi(
        val adres: String = "",
        val ornekId: Int = 0,
        val ad: String = "",
        val kanal: String = "",
        val baglanmaTs: Long = 0L,
        val sonNabizTs: Long = 0L,
        val gidenAkisByte: Long = 0L,
        val gelenAkisByte: Long = 0L,
        val deneme: Int = 0
    )

    private val _durum = MutableStateFlow(Durum.KAPALI)
    val durum: StateFlow<Durum> = _durum.asStateFlow()

    private val _sonHata = MutableStateFlow("")
    val sonHata: StateFlow<String> = _sonHata.asStateFlow()

    private val _bilgi = MutableStateFlow(Bilgi())
    val bilgi: StateFlow<Bilgi> = _bilgi.asStateFlow()

    private val calisiyor = AtomicBoolean(false)
    private var kapsam: CoroutineScope? = null

    @Volatile
    private var soket: WebSocket? = null

    @Volatile
    private var elSikismaTamam = false

    private val yazici = Executors.newSingleThreadExecutor { r ->
        Thread(r, "kopru-akis-yazici").apply { isDaemon = true }
    }

    private val istemci = OkHttpClient.Builder()
        .connectTimeout(EL_SIKISMA_SN, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .build()

    fun calisiyorMu(): Boolean = calisiyor.get()

    fun bagliMi(): Boolean = elSikismaTamam && soket != null

    fun baslat() {
        if (!calisiyor.compareAndSet(false, true)) return
        val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        kapsam = k
        k.launch { anaDongu() }
        Gunluk.yaz("AJAN", "Kopru ajani baslatildi")
    }

    fun durdur() {
        if (!calisiyor.compareAndSet(true, false)) return
        runCatching { soket?.close(1000, "durdur") }
        kapsam?.cancel()
        kapsam = null
        soket = null
        elSikismaTamam = false
        _durum.value = Durum.KAPALI
        Gunluk.yaz("AJAN", "Kopru ajani durduruldu")
    }

    // ------------------------------------------------------------------
    // Ana dongu: baglan, kopunca geri cekil, yeniden dene
    // ------------------------------------------------------------------
    private suspend fun anaDongu() {
        var bekleme = YENIDEN_TABAN_MS
        var deneme = 0
        while (calisiyor.get()) {
            val k = kimlikOku()
            if (k == null || !k.eksiksizMi()) {
                _durum.value = Durum.KAPALI
                _sonHata.value = "Kurulum kimligi yok (API kodu girilmedi)"
                delay(3000)
                continue
            }
            deneme++
            _bilgi.value = _bilgi.value.copy(deneme = deneme)
            var basarili = false
            for (adres in adayAdresler(k.merkezAdres)) {
                if (!calisiyor.get()) break
                _durum.value = Durum.BAGLANIYOR
                Gunluk.yaz("AJAN", "Merkeze baglaniliyor: $adres")
                val sonuc = birOturum(adres, k)
                if (sonuc.elSikismaOldu) {
                    basarili = true
                    break
                }
                // Kimlik reddi KALICIDIR; port degistirmek cozmez.
                if (sonuc.kalici) break
            }
            if (!calisiyor.get()) break
            if (basarili) {
                bekleme = YENIDEN_TABAN_MS
                deneme = 0
                _durum.value = Durum.KAPALI
                Gunluk.uyari("AJAN", "Merkez baglantisi koptu; yeniden denenecek")
            } else {
                _durum.value = Durum.HATA
                Gunluk.uyari(
                    "AJAN",
                    "Baglanamadi: ${_sonHata.value} (${bekleme / 1000} sn sonra yeniden)"
                )
            }
            delay(bekleme)
            bekleme = (bekleme * 2).coerceAtMost(YENIDEN_ENUST_MS)
        }
    }

    private class OturumSonucu(val elSikismaOldu: Boolean, val kalici: Boolean)

    private suspend fun birOturum(adres: String, k: KopruKimlik.Deger): OturumSonucu {
        val kapandi = CompletableDeferred<Unit>()
        var elSikismaOldu = false
        var kalici = false
        var nabizIsi: Job? = null
        elSikismaTamam = false

        val dinleyici = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(merhaba(k).toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val m = try {
                    JSONObject(text)
                } catch (e: Exception) {
                    return
                }
                val tur = m.optString("tur")
                if (!elSikismaTamam) {
                    if (tur == "merhaba_tamam") {
                        elSikismaTamam = true
                        elSikismaOldu = true
                        _sonHata.value = ""
                        _bilgi.value = _bilgi.value.copy(
                            adres = adres,
                            ornekId = m.optInt("ornek_id", 0),
                            ad = m.optString("ad"),
                            kanal = m.optString("kanal"),
                            baglanmaTs = System.currentTimeMillis(),
                            sonNabizTs = System.currentTimeMillis()
                        )
                        _durum.value = Durum.BAGLI
                        Gunluk.yaz(
                            "AJAN",
                            "Merkeze baglandi: ${m.optString("ad")} " +
                                "(ornek ${m.optInt("ornek_id")})"
                        )
                        nabizIsi = kapsam?.launch { nabizDongusu(webSocket) }
                    } else {
                        val neden = m.optString("mesaj").ifBlank {
                            "Merkez baglantiyi kabul etmedi"
                        }
                        _sonHata.value = neden
                        kalici = true
                        Gunluk.hata("AJAN", "Merkez reddetti: $neden")
                        webSocket.close(1000, "ret")
                    }
                    return
                }
                mesajIsle(webSocket, m, tur)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (!elSikismaOldu) {
                    _sonHata.value = t.message ?: t.javaClass.simpleName
                }
                kapandi.complete(Unit)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                kapandi.complete(Unit)
            }
        }

        val ws = istemci.newWebSocket(Request.Builder().url(adres).build(), dinleyici)
        soket = ws
        try {
            kapandi.await()
        } catch (e: CancellationException) {
            throw e
        } finally {
            nabizIsi?.cancel()
            elSikismaTamam = false
            if (soket === ws) soket = null
            runCatching { ws.cancel() }
        }
        return OturumSonucu(elSikismaOldu, kalici)
    }

    // ------------------------------------------------------------------
    // Protokol
    // ------------------------------------------------------------------
    private fun merhaba(k: KopruKimlik.Deger): JSONObject = JSONObject().apply {
        put("tur", "merhaba")
        put("kurulum_uid", k.kurulumUid)
        put("gizli", k.gizli)
        put("surum", surum)
        put("platform", platform)
        put("makine_adi", makineAdi)
        put("yetenekler", guvenli { yetenekler() } ?: JSONObject())
        put("dron_sayisi", guvenli { dronSayisi() } ?: 0)
    }

    private suspend fun nabizDongusu(ws: WebSocket) {
        while (true) {
            delay(NABIZ_MS)
            if (!elSikismaTamam) return
            val paket = JSONObject().apply {
                put("tur", "nabiz")
                put("dron_sayisi", guvenli { dronSayisi() } ?: 0)
                put("yetenekler", guvenli { yetenekler() } ?: JSONObject())
            }
            guvenli { nabizEk() }?.let { ek ->
                val anahtarlar = ek.keys()
                while (anahtarlar.hasNext()) {
                    val a = anahtarlar.next()
                    paket.put(a, ek.get(a))
                }
            }
            ws.send(paket.toString())
        }
    }

    private fun mesajIsle(ws: WebSocket, m: JSONObject, tur: String) {
        when (tur) {
            "akis" -> {
                val kid = m.optInt("kanal_id", 0)
                val veri = try {
                    Base64.decode(m.optString("veri"), Base64.DEFAULT)
                } catch (e: Exception) {
                    return
                }
                if (veri.isEmpty()) return
                _bilgi.value = _bilgi.value.copy(
                    gelenAkisByte = _bilgi.value.gelenAkisByte + veri.size
                )
                // Sira korunur: tek iplik, kuyruk.
                yazici.execute {
                    try {
                        akisYaz(kid, veri)
                    } catch (e: Exception) {
                        Gunluk.hata("AJAN", "Akis yazma (kanal $kid): ${e.message}")
                    }
                }
            }

            "istek" -> {
                val eylem = m.optString("eylem")
                val istekId = m.opt("istek_id")
                val veri = m.optJSONObject("veri") ?: JSONObject()
                kapsam?.launch {
                    val yanit = JSONObject().put("tur", "yanit").put("istek_id", istekId)
                    val islev = islevler[eylem]
                    if (islev == null) {
                        yanit.put("hata", "Bu kurulum '$eylem' eylemini desteklemiyor")
                    } else {
                        try {
                            yanit.put("veri", islev(veri))
                        } catch (e: Exception) {
                            yanit.put("hata", "${e.javaClass.simpleName}: ${e.message}")
                        }
                    }
                    ws.send(yanit.toString())
                }
            }

            "kapat" -> {
                Gunluk.uyari("AJAN", "Merkez baglantiyi kapatmak istedi")
                ws.close(1000, "merkez")
            }

            "nabiz_tamam" -> {
                _bilgi.value = _bilgi.value.copy(sonNabizTs = System.currentTimeMillis())
            }

            "hata" -> {
                val neden = m.optString("mesaj").ifBlank { "Merkez hata bildirdi" }
                _sonHata.value = neden
                Gunluk.uyari("AJAN", "Merkez hatasi: $neden")
            }

            else -> {
                // kamera_kaynaklari, ucus_tamam vb.: bu kopru icin anlamsiz,
                // sessizce yok sayilir.
            }
        }
    }

    /**
     * Ham byte'i merkeze yollar (atesle-unut). Baglanti yoksa `false`.
     */
    fun akisGonder(kanalId: Int, veri: ByteArray): Boolean {
        val ws = soket ?: return false
        if (!elSikismaTamam || veri.isEmpty()) return false
        val paket = JSONObject()
            .put("tur", "akis")
            .put("kanal_id", kanalId)
            .put("veri", Base64.encodeToString(veri, Base64.NO_WRAP))
        val ok = ws.send(paket.toString())
        if (ok) {
            _bilgi.value = _bilgi.value.copy(
                gidenAkisByte = _bilgi.value.gidenAkisByte + veri.size
            )
        }
        return ok
    }

    // ------------------------------------------------------------------
    /**
     * Denenecek adresler (443 once, sonra 9443). Kullanici/API kodu acik
     * bir port verdiyse ona DOKUNULMAZ.
     */
    private fun adayAdresler(ham: String): List<String> = try {
        val u = URI(ham)
        val konak = u.host ?: return listOf(ham)
        if (u.port != -1) {
            listOf(ham)
        } else {
            val yol = if (u.path.isNullOrBlank()) "/kopru" else u.path
            listOf("${u.scheme}://$konak$yol", "${u.scheme}://$konak:9443$yol")
        }
    } catch (e: Exception) {
        listOf(ham)
    }

    private inline fun <T> guvenli(blok: () -> T): T? = try {
        blok()
    } catch (e: Exception) {
        null
    }

    companion object {
        const val NABIZ_MS = 25_000L
        const val YENIDEN_TABAN_MS = 3_000L
        const val YENIDEN_ENUST_MS = 60_000L
        const val EL_SIKISMA_SN = 20L
    }
}
