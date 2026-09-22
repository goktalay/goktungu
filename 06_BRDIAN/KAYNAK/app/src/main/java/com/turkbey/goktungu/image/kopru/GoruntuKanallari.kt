package com.turkbey.goktungu.image.kopru

import com.turkbey.goktungu.image.goruntu.KameraKopru
import com.turkbey.goktungu.image.goruntu.MjpegSunucu
import com.turkbey.goktungu.image.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject
import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * GORUNTU KANALLARI — merkezin actigi yerel MJPEG akislari.
 *
 * BRDAND'in `AkisKanallari` sinifinin GORUNTU karsiligidir. BRDAND'da
 * kanal, ham MAVLink byte'larini merkeze TASIYORDU. Burada tasarim
 * BRDIMG `video_vekil.py` desenini izler: KARELER MERKEZE GITMEZ.
 *
 * Merkezdeki Baglanti Yoneticisi bir goruntu kaydini oynatinca kopruye
 * `akis_ac` gelir; kopru cihaz kamerasini + yerel MJPEG sunucusunu acar
 * ve merkeze YALNIZ akis-meta doner:
 *
 *   {
 *     "kanal_id": 0,
 *     "tur": "goruntu",
 *     "yerel_url": "http://192.168.1.42:8801/kamera/0",  // saha aginda
 *     "cozunurluk": "1280x720",
 *     "uretilen_kare": 1234,
 *     "izleyici": 1
 *   }
 *
 * Merkez bu URL'yi kendi izleyicisine (saha aginda) verir; ham video
 * WebSocket'e KONMAZ (merkez veri merkezindedir, saha agina erisemez).
 *
 * ## Kamera baglama nerede
 *
 * CameraX yasam dongusu (LifecycleOwner) gerektirir; baglama arayuz ya
 * da on plan hizmeti tarafindan [GoruntuYonetici.kameraBagla] ile
 * yapilir. Bu sinif yalniz MJPEG sunucusunu ve mantiksal kanal durumunu
 * yonetir.
 */
class GoruntuKanallari(
    private val kamera: KameraKopru,
    private val mjpeg: MjpegSunucu
) {

    /** Merkezin actigi mantiksal kanallar (kanal_id -> tanim). */
    private val kanallar = LinkedHashMap<Int, JSONObject>()

    @Synchronized
    fun ac(kanalId: Int, tanim: JSONObject): Pair<JSONObject?, String?> {
        if (!mjpeg.calisiyor && !mjpeg.baslat()) {
            return null to "Yerel MJPEG sunucusu baslatilamadi"
        }
        kanallar[kanalId] = tanim
        Gunluk.yaz("GORUNTU", "Kanal $kanalId acildi (yerel MJPEG)")
        return durum(kanalId) to null
    }

    @Synchronized
    fun kapat(kanalId: Int): Boolean {
        val vardi = kanallar.remove(kanalId) != null
        if (kanallar.isEmpty()) {
            // Son izleyici kalmadiginda sunucuyu ayakta tutmak zararsizdir
            // (kamera zaten yasam dongusune bagli); yalniz gunluge yaz.
            Gunluk.yaz("GORUNTU", "Kanal $kanalId kapatildi (aktif kanal kalmadi)")
        } else {
            Gunluk.yaz("GORUNTU", "Kanal $kanalId kapatildi")
        }
        return vardi
    }

    @Synchronized
    fun tumunuKapat() {
        kanallar.clear()
    }

    fun etkinSayi(): Int = kanallar.size

    fun ozet(): String = if (kanallar.isEmpty()) "" else
        "yerel MJPEG · ${kamera.cozunurluk.ifBlank { "kare bekleniyor" }}"

    /** Tek kanalin akis-meta JSON'u (merkez bu bicimi bekler). */
    fun durum(kanalId: Int): JSONObject = JSONObject().apply {
        put("kanal_id", kanalId)
        put("tur", "goruntu")
        put("etiket", "yerel MJPEG kamera")
        put("calisiyor", mjpeg.calisiyor && kamera.bagli)
        put("yerel_url", yerelUrl(kanalId))
        put("cozunurluk", kamera.cozunurluk)
        put("uretilen_kare", kamera.uretilenKare.get())
        put("izleyici", mjpeg.izleyici.get())
        put("kamera_bagli", kamera.bagli)
        put("son_hata", kamera.sonHata)
    }

    fun durum(): JSONArray = JSONArray().apply {
        if (kanallar.isEmpty()) {
            // Kanal acilmamis olsa da kamera durumu gorunsun.
            put(durum(0))
        } else {
            kanallar.keys.sorted().forEach { put(durum(it)) }
        }
    }

    private fun yerelUrl(kanalId: Int): String {
        val ip = yerelIp() ?: return ""
        return "http://$ip:${MjpegSunucu.VARSAYILAN_PORT}/kamera/$kanalId"
    }

    /** Cihazin saha agindaki IPv4 adresini bulur (yerel URL icin). */
    private fun yerelIp(): String? = try {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .filterIsInstance<Inet4Address>()
            .firstOrNull { !it.isLoopbackAddress }
            ?.hostAddress
    } catch (e: Exception) {
        null
    }
}
