package com.turkbey.goktungu.bridge.kopru

import com.turkbey.goktungu.bridge.veri.GdpMesaj
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.ConcurrentHashMap

/**
 * GDP KANALLARI — DJI telemetrisi/komutlari kopru role kanalindan.
 *
 * 1.0.x'te GDP (NDJSON) dogrudan merkezin 8790 TCP portuna gidiyordu.
 * 1.1.0 ile GRCON'a dogrudan baglanti yoktur: merkezin Baglanti
 * Yoneticisi "DJI" turu kaydi `play` yapinca kopruye `akis_ac`
 * (tanim.tur = "dji") gelir; bu sinif o kanal icin bir GDP oturumu acar
 * ve satirlari `{"tur":"akis"}` paketleriyle tasir. Merkezde
 * `dji_role.py` adaptoru bu byte'lari yerel DJI TCP dinleyicisine
 * (`dji_kopru.py`) verir; sunucu mantigi DEGISMEZ.
 *
 * Sunucu 30 sn veri gelmezse istemciyi duser; bu yuzden arac bagli
 * olmasa da 5 sn'de bir `kalp` gonderilir. `merhaba` ILK satirdir.
 */
class GdpKanal(
    private val gonder: (Int, ByteArray) -> Boolean,
    private val merhabaUretici: () -> JSONObject,
    private val komutIsle: (GdpMesaj.GelenKomut, (JSONObject) -> Unit) -> Unit,
    private val urunBagli: () -> Boolean
) {

    inner class Oturum(val kanalId: Int, val tanim: JSONObject) {
        @Volatile
        var calisiyor = false
            private set
        val acilmaTs = System.currentTimeMillis() / 1000.0

        @Volatile
        var sonVeriTs = 0.0

        @Volatile
        var gidenByte = 0L

        @Volatile
        var gelenByte = 0L

        @Volatile
        var sonHata = ""
        private val tampon = ByteArrayOutputStream()
        private var kapsam: CoroutineScope? = null
        private var kalpIsi: Job? = null

        fun ac(): String? {
            calisiyor = true
            val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
            kapsam = k
            // El sikisma: merhaba ILK satir olmali.
            if (!satirGonder(merhabaUretici())) {
                sonHata = "merhaba gonderilemedi (merkez baglantisi yok)"
                calisiyor = false
                return sonHata
            }
            kalpIsi = k.launch {
                while (calisiyor) {
                    delay(5_000)
                    if (!calisiyor) break
                    satirGonder(GdpMesaj.kalp(urunBagli()))
                }
            }
            Gunluk.yaz("GDP", "Kanal $kanalId acildi (DJI GDP oturumu)")
            return null
        }

        /** Bir GDP mesajini NDJSON satiri olarak kanala yazar. */
        fun satirGonder(m: JSONObject): Boolean {
            if (!calisiyor) return false
            val bayt = (m.toString() + "\n").toByteArray(Charsets.UTF_8)
            val ok = gonder(kanalId, bayt)
            if (ok) gidenByte += bayt.size
            return ok
        }

        /** Merkezden gelen byte'lar: satirlara bolunup komut olarak islenir. */
        @Synchronized
        fun yaz(v: ByteArray): Int {
            if (!calisiyor) return 0
            gelenByte += v.size
            sonVeriTs = System.currentTimeMillis() / 1000.0
            tampon.write(v, 0, v.size)
            val hepsi = tampon.toByteArray()
            var bas = 0
            for (i in hepsi.indices) {
                if (hepsi[i] == '\n'.code.toByte()) {
                    val satir = String(hepsi, bas, i - bas, Charsets.UTF_8).trim()
                    bas = i + 1
                    if (satir.isNotEmpty()) satirIsle(satir)
                }
            }
            tampon.reset()
            if (bas < hepsi.size) tampon.write(hepsi, bas, hepsi.size - bas)
            if (tampon.size() > 256 * 1024) {
                // Satir sonu gelmeyen bozuk akis: bellek sinirsiz buyumesin.
                tampon.reset()
                Gunluk.uyari("GDP", "Kanal $kanalId: satir tamponu tasti, sifirlandi")
            }
            return v.size
        }

        private fun satirIsle(satir: String) {
            val nesne = try {
                JSONObject(satir)
            } catch (e: Exception) {
                Gunluk.uyari("GDP", "Cozulemeyen satir atlandi (${satir.take(60)})")
                return
            }
            if (nesne.optString("tip") == "hata") {
                sonHata = nesne.optString("mesaj")
                Gunluk.hata("GDP", "Merkez DJI sunucusu: $sonHata")
                return
            }
            val komut = GdpMesaj.komutAyristir(nesne)
            if (komut == null) {
                Gunluk.uyari("GDP", "Bilinmeyen mesaj: ${nesne.optString("tip", "?")}")
                return
            }
            try {
                komutIsle(komut) { yanit -> satirGonder(yanit) }
            } catch (e: Exception) {
                Gunluk.hata("GDP", "Komut isleme hatasi (${komut.ad}): ${e.message}")
                satirGonder(GdpMesaj.yanit(komut.id, false, "istemci hatasi: ${e.message}"))
            }
        }

        fun kapat() {
            calisiyor = false
            kalpIsi?.cancel()
            kapsam?.cancel()
            kapsam = null
        }

        fun durum(): JSONObject = JSONObject().apply {
            put("kanal_id", kanalId)
            put("tur", "dji")
            put("etiket", "DJI GDP (" + tanim.optString("isim") + ")")
            put("calisiyor", calisiyor)
            put("acilma_ts", acilmaTs)
            put("son_veri_ts", sonVeriTs)
            put("giden_byte", gidenByte)
            put("gelen_byte", gelenByte)
            put("son_hata", sonHata)
            put("merkez_kesik", false)
            put("kesinti_byte", 0)
            put("kesinti_dosya_sayi", 0)
            put("kesinti_dusen_byte", 0)
        }
    }

    private val oturumlar = ConcurrentHashMap<Int, Oturum>()

    fun ac(kanalId: Int, tanim: JSONObject): Pair<JSONObject?, String?> {
        val tur = tanim.optString("tur", "dji").lowercase()
        if (tur != "dji") {
            return null to "DJI koprusu yalniz 'dji' turu baglanti acar (istenen: $tur). " +
                "Baglanti Yoneticisi'nde DJI turu kayit kullanin."
        }
        oturumlar.remove(kanalId)?.kapat()
        val o = Oturum(kanalId, tanim)
        val hata = o.ac()
        if (hata != null) return null to hata
        oturumlar[kanalId] = o
        return o.durum() to null
    }

    fun kapat(kanalId: Int): Boolean {
        val o = oturumlar.remove(kanalId) ?: return false
        o.kapat()
        Gunluk.yaz("GDP", "Kanal $kanalId kapatildi")
        return true
    }

    fun yaz(kanalId: Int, veri: ByteArray): Int = oturumlar[kanalId]?.yaz(veri) ?: 0

    /** Telemetri gibi yayinlar TUM acik oturumlara gider (normalde tek). */
    fun yayinla(m: JSONObject): Int {
        var n = 0
        oturumlar.values.forEach { if (it.satirGonder(m)) n++ }
        return n
    }

    fun tumunuKapat() {
        val hepsi = oturumlar.values.toList()
        oturumlar.clear()
        hepsi.forEach { runCatching { it.kapat() } }
    }

    fun etkinSayi(): Int = oturumlar.values.count { it.calisiyor }

    fun durum(): JSONArray = JSONArray().apply {
        oturumlar.values.sortedBy { it.kanalId }.forEach { put(it.durum()) }
    }
}
