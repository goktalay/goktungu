package com.gokkubbetech.goktungu.kopru

import com.gokkubbetech.goktungu.veri.AgKisiti
import com.gokkubbetech.goktungu.veri.GdpMesaj
import com.gokkubbetech.goktungu.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean

/**
 * GDP (GOKTUNGU DJI Kopru Protokolu) TCP istemcisi.
 *
 * Sozlesme: `goktungu/dji_kopru.py`.  Tasima satir-ayrilmis JSON (NDJSON).
 * Varsayilan sunucu portu **8790**.
 *
 * ## Sunucunun bekledigi davranis (koddan dogrulandi)
 *
 * - Sunucu soketi 30 sn veri gelmezse duser (`settimeout(30.0)`).
 *   Bu yuzden arac bagli olmasa bile **5 sn'de bir `kalp`** gonderilir.
 * - `merhaba` ilk mesaj olmali; sunucu `sn` alanini kalici sysid
 *   eslemesi icin kullanir (ayni arac -> ayni sysid -> gecmis korunur).
 * - Sunucu ilk `telemetri` gelene kadar dron kartini olusturmaz.
 *   Arac RC'ye bagli degilse `kalp` icinde `urun=false` gonderilir.
 * - Tek mesajdaki hata baglantiyi dusurmez; sunucu tarafi da boyle
 *   davranir.
 */
class GdpIstemci(
    private val kapsam: CoroutineScope
) {

    enum class Durum { KOPUK, BAGLANIYOR, BAGLI, HATA }

    private val _durum = MutableStateFlow(Durum.KOPUK)
    val durum: StateFlow<Durum> = _durum.asStateFlow()

    private val _sonHata = MutableStateFlow("")
    val sonHata: StateFlow<String> = _sonHata.asStateFlow()

    /** Sunucudan gelen komutlari isleyen geri cagri. */
    var komutIsleyici: ((GdpMesaj.GelenKomut) -> Unit)? = null

    /** Arac (urun) RC'ye bagli mi; `kalp` mesajinda bildirilir. */
    @Volatile
    var urunBagli: Boolean = false

    /** `merhaba` mesajini ureten geri cagri; her yeniden baglanmada
     *  cagrilir cunku arac degismis olabilir. */
    var merhabaUretici: (() -> JSONObject)? = null

    private var soket: Socket? = null
    private var cikis: OutputStream? = null
    private val gonderKilit = Any()
    private var dongu: Job? = null
    private val calisiyor = AtomicBoolean(false)

    /**
     * Baglantiyi baslatir ve kopma halinde yeniden dener.
     *
     * @param tls Ileride TLS destegi icin ayrilmis; su an `false`.
     */
    fun baslat(adres: String, port: Int, tls: Boolean = false) {
        if (!calisiyor.compareAndSet(false, true)) {
            Gunluk.uyari("GDP", "Istemci zaten calisiyor")
            return
        }
        dongu = kapsam.launch(Dispatchers.IO) {
            var bekleme = 1000L
            while (isActive && calisiyor.get()) {
                // Duz metin kisiti: genel internet adresine TLS'siz
                // baglanti reddedilir (bkz. AgKisiti).
                if (!AgKisiti.duzMetinIzinliMi(adres, tls)) {
                    val n = AgKisiti.redNedeni(adres)
                    Gunluk.hata("GDP", n)
                    _sonHata.value = n
                    _durum.value = Durum.HATA
                    calisiyor.set(false)
                    return@launch
                }
                try {
                    _durum.value = Durum.BAGLANIYOR
                    baglanVeOku(adres, port)
                    bekleme = 1000L   // basarili baglanti sonrasi sifirla
                } catch (e: Exception) {
                    _sonHata.value = e.message ?: e.javaClass.simpleName
                    Gunluk.uyari("GDP", "Baglanti koptu: ${_sonHata.value}")
                } finally {
                    kapat()
                    if (calisiyor.get()) _durum.value = Durum.KOPUK
                }
                if (!calisiyor.get()) break
                // Ustel geri cekilme, 30 sn ust sinir
                delay(bekleme)
                bekleme = (bekleme * 2).coerceAtMost(30_000L)
            }
        }
    }

    fun durdur() {
        calisiyor.set(false)
        dongu?.cancel()
        kapat()
        _durum.value = Durum.KOPUK
        Gunluk.yaz("GDP", "Istemci durduruldu")
    }

    private suspend fun baglanVeOku(adres: String, port: Int) {
        val s = Socket()
        // Sunucu 30 sn veri gelmezse duser; okuma zaman asimi daha uzun
        // olmali ki kendi tarafimiz once kopmasin.
        s.soTimeout = 45_000
        s.tcpNoDelay = true
        s.connect(InetSocketAddress(adres, port), 10_000)
        soket = s
        cikis = s.getOutputStream()
        _durum.value = Durum.BAGLI
        _sonHata.value = ""
        Gunluk.yaz("GDP", "Merkeze baglandi: $adres:$port")

        // El sikisma: merhaba ILK mesaj olmali
        val m = merhabaUretici?.invoke()
        if (m == null) {
            Gunluk.hata("GDP", "merhaba uretici tanimli degil; " +
                "sunucu bu istemciyi tanimlayamaz")
            throw IllegalStateException("merhaba uretilemedi")
        }
        gonder(m)

        val kalpIsi = kapsam.launch(Dispatchers.IO) { kalpDongusu() }
        try {
            val okuyucu = BufferedReader(
                InputStreamReader(s.getInputStream(), Charsets.UTF_8)
            )
            while (calisiyor.get()) {
                val satir = withContext(Dispatchers.IO) {
                    okuyucu.readLine()
                } ?: break
                if (satir.isBlank()) continue
                isle(satir)
            }
        } finally {
            kalpIsi.cancel()
        }
    }

    private fun isle(satir: String) {
        val nesne = try {
            JSONObject(satir)
        } catch (e: Exception) {
            // Bozuk satir baglantiyi dusurmemeli
            Gunluk.uyari("GDP", "Cozulemeyen satir atlandi " +
                "(${satir.take(60)})")
            return
        }
        val komut = GdpMesaj.komutAyristir(nesne)
        if (komut == null) {
            Gunluk.uyari("GDP", "Bilinmeyen mesaj: " +
                nesne.optString("tip", "?"))
            return
        }
        try {
            komutIsleyici?.invoke(komut)
        } catch (e: Exception) {
            // Tek komuttaki hata baglantiyi dusurmez
            Gunluk.hata("GDP", "Komut isleme hatasi " +
                "(${komut.ad}): ${e.message}")
            gonder(GdpMesaj.yanit(komut.id, false,
                "istemci hatasi: ${e.message}"))
        }
    }

    /**
     * Kalp atisi.  Sunucu 30 sn sessizlikte soketi duser; 5 sn aralik
     * comert bir paydir.
     */
    private suspend fun kalpDongusu() {
        while (calisiyor.get() && _durum.value == Durum.BAGLI) {
            delay(5_000)
            if (_durum.value != Durum.BAGLI) break
            gonder(GdpMesaj.kalp(urunBagli))
        }
    }

    /**
     * Mesaji gonderir.  Yazma islemi kilitlidir: telemetri, yanit ve
     * kalp farkli is parcalarindan gelebilir ve satirlar birbirine
     * karisirsa protokol bozulur.
     */
    fun gonder(m: JSONObject): Boolean {
        val c = cikis ?: return false
        return try {
            val bayt = (m.toString() + "\n").toByteArray(Charsets.UTF_8)
            synchronized(gonderKilit) {
                c.write(bayt)
                c.flush()
            }
            true
        } catch (e: Exception) {
            Gunluk.uyari("GDP", "Gonderilemedi: ${e.message}")
            false
        }
    }

    private fun kapat() {
        try { cikis?.close() } catch (_: Exception) {}
        try { soket?.close() } catch (_: Exception) {}
        cikis = null
        soket = null
    }
}
