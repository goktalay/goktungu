package com.turkbey.goktungu.bridge.kopru

import android.hardware.usb.UsbDevice
import com.turkbey.goktungu.bridge.mavlink.MavCerceve
import com.turkbey.goktungu.bridge.mavlink.MavGozlemci
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketAddress
import java.net.SocketTimeoutException
import java.util.concurrent.ConcurrentHashMap

/**
 * AKIS KANALLARI — merkezin actigi ham MAVLink kanallari.
 *
 * Masaustu koprunun `kopru/akis.py` modulunun karsiligi. Merkezdeki
 * Baglanti Yoneticisi bir kaydi `play` yapinca kopruye `akis_ac`
 * istegi gelir; tanim kaydin kendi turudur:
 *
 * | tur  | kaynak                                  |
 * |------|-----------------------------------------|
 * | seri | USB seri cihaz (`port` = cihaz adi)     |
 * | udp  | UDP dinleyici (`port`), udpin semantigi |
 * | tcp  | TCP istemci (`host`:`port`)             |
 *
 * Byte'lar COZULMEZ; oldugu gibi merkeze tasinir (cozumleme merkezdeki
 * `dron.py`de kalir). Yalniz USB kanalinda cerceveler SALT OKUMA
 * gozlemciye kopyalanir ki telefonda arac durumu gorunsun.
 *
 * ## Partileme
 *
 * 10 Hz MAVLink ~50-100 kucuk paket/sn uretir; her birini ayri WSS
 * mesaji yapmak JSON+base64 yukunu faydali yukun onune gecirir. Okunan
 * byte'lar 20 ms pencerede (en cok 8 KB) biriktirilip tek pakette
 * gider; 20 ms komut gecikmesi icin fark edilmezdir.
 */
class AkisKanallari(
    private val usb: UsbSeri,
    private val gonder: (Int, ByteArray) -> Boolean,
    private val gozlemci: MavGozlemci
) {

    class Tanim(t: JSONObject) {
        val tur: String = t.optString("tur", "seri").lowercase()
        val port: String = t.optString("port")
        val baud: Int = t.optInt("baud", 57600).let { if (it <= 0) 57600 else it }
        val host: String = t.optString("host")
        val isim: String = t.optString("isim")
        fun etiket(): String = when (tur) {
            "seri" -> "seri $port @$baud"
            "udp" -> "udpin:0.0.0.0:$port"
            "tcp" -> "tcp:$host:$port"
            else -> tur
        }
    }

    inner class Kanal(val kanalId: Int, val tanim: Tanim) {
        @Volatile
        var calisiyor = false
            private set

        @Volatile
        var gidenByte = 0L

        @Volatile
        var gelenByte = 0L

        @Volatile
        var sonHata = ""
        val acilmaTs = System.currentTimeMillis() / 1000.0

        @Volatile
        var sonVeriTs = 0.0

        private var iplik: Thread? = null
        private var udp: DatagramSocket? = null

        @Volatile
        private var udpEs: SocketAddress? = null
        private var tcp: Socket? = null
        private var cihaz: UsbDevice? = null
        private val cerceveci = MavCerceve()

        /** Kaynagi acar ve okuma ipligini baslatir; hata metni doner. */
        fun ac(): String? {
            when (tanim.tur) {
                "seri" -> {
                    val d = usb.cihazBul(tanim.port)
                        ?: return "USB seri cihaz bulunamadi: ${tanim.port}. " +
                            "Kabloyu takip uygulamada TARA yapin."
                    if (!usb.izinVarMi(d)) {
                        usb.izinIste(d)
                        return "USB izni verilmedi (${usb.cihazEtiketi(d)}). " +
                            "Telefonda izin istemini onaylayip yeniden baslatin."
                    }
                    usb.ac(d, tanim.baud)?.let { return it }
                    cihaz = d
                }

                "udp" -> {
                    val p = tanim.port.toIntOrNull()
                        ?: return "UDP portu gecersiz: ${tanim.port}"
                    try {
                        udp = DatagramSocket(null).apply {
                            reuseAddress = true
                            soTimeout = 200
                            bind(InetSocketAddress("0.0.0.0", p))
                        }
                    } catch (e: Exception) {
                        return "UDP $p acilamadi: ${e.message}"
                    }
                }

                "tcp" -> {
                    val p = tanim.port.toIntOrNull()
                        ?: return "TCP portu gecersiz: ${tanim.port}"
                    if (tanim.host.isBlank()) return "TCP konak adresi bos"
                    try {
                        tcp = Socket().apply {
                            tcpNoDelay = true
                            connect(InetSocketAddress(tanim.host, p), 5000)
                            soTimeout = 200
                        }
                    } catch (e: Exception) {
                        return "TCP ${tanim.host}:$p baglanamadi: ${e.message}"
                    }
                }

                else -> return "Desteklenmeyen kanal turu: ${tanim.tur}"
            }
            calisiyor = true
            iplik = Thread({ okumaDongusu() }, "akis-kanal-$kanalId").apply {
                isDaemon = true
                start()
            }
            Gunluk.yaz("AKIS", "Kanal $kanalId acildi: ${tanim.etiket()}")
            return null
        }

        private fun okumaDongusu() {
            val tampon = ByteArray(OKUMA_TAMPON)
            val parti = ByteArrayOutputStream(PARTI_ENUST)
            var partiBas = 0L
            var sonCihazDenetim = System.currentTimeMillis()
            while (calisiyor) {
                val n = try {
                    oku(tampon)
                } catch (e: Exception) {
                    sonHata = e.message ?: e.javaClass.simpleName
                    -1
                }
                if (n < 0) {
                    if (sonHata.isBlank()) sonHata = "kaynak kapandi"
                    Gunluk.hata("AKIS", "Kanal $kanalId okuma hatasi: $sonHata")
                    break
                }
                val simdi = System.currentTimeMillis()
                if (n > 0) {
                    parti.write(tampon, 0, n)
                    gelenByte += n
                    sonVeriTs = simdi / 1000.0
                    if (partiBas == 0L) partiBas = simdi
                    if (tanim.tur == "seri") {
                        for (c in cerceveci.besle(tampon, n)) gozlemci.gozlemle(c)
                    }
                }
                if (parti.size() > 0 &&
                    (parti.size() >= PARTI_ENUST || simdi - partiBas >= PARTI_PENCERE_MS)
                ) {
                    val v = parti.toByteArray()
                    parti.reset()
                    partiBas = 0L
                    if (gonder(kanalId, v)) gidenByte += v.size
                }
                // USB cikarildi mi? bulkTransfer sessizce 0 dondurur.
                if (tanim.tur == "seri" && simdi - sonCihazDenetim > 2000) {
                    sonCihazDenetim = simdi
                    if (usb.cihazBul(tanim.port) == null) {
                        sonHata = "USB cihaz cikarildi"
                        Gunluk.hata("AKIS", "Kanal $kanalId: $sonHata")
                        break
                    }
                }
            }
            calisiyor = false
            kaynakKapat()
        }

        private fun oku(t: ByteArray): Int = when (tanim.tur) {
            "seri" -> usb.oku(t)
            "udp" -> {
                val s = udp ?: return -1
                try {
                    val p = DatagramPacket(t, t.size)
                    s.receive(p)
                    udpEs = p.socketAddress
                    p.length
                } catch (e: SocketTimeoutException) {
                    0
                }
            }

            "tcp" -> {
                val s = tcp ?: return -1
                try {
                    s.getInputStream().read(t)
                } catch (e: SocketTimeoutException) {
                    0
                }
            }

            else -> -1
        }

        /** Merkezden gelen byte'i donanima yazar; yazilan sayiyi doner. */
        fun yaz(v: ByteArray): Int {
            if (!calisiyor) return 0
            return when (tanim.tur) {
                "seri" -> if (usb.yaz(v, v.size)) v.size else 0
                "udp" -> {
                    val s = udp ?: return 0
                    val es = udpEs ?: return 0   // arac henuz yazmadi
                    s.send(DatagramPacket(v, v.size, es))
                    v.size
                }

                "tcp" -> {
                    val s = tcp ?: return 0
                    s.getOutputStream().write(v)
                    s.getOutputStream().flush()
                    v.size
                }

                else -> 0
            }
        }

        fun kapat() {
            calisiyor = false
            iplik?.let { runCatching { it.join(600) } }
            iplik = null
            kaynakKapat()
        }

        @Synchronized
        private fun kaynakKapat() {
            runCatching { udp?.close() }
            runCatching { tcp?.close() }
            udp = null
            tcp = null
            if (tanim.tur == "seri" && cihaz != null) {
                usb.kapat()
                cihaz = null
            }
        }

        fun durum(): JSONObject = JSONObject().apply {
            put("kanal_id", kanalId)
            put("tur", tanim.tur)
            put("etiket", tanim.etiket())
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

    private val kanallar = ConcurrentHashMap<Int, Kanal>()

    /** `akis_ac`: ayni kanal yeniden aciliyorsa eskisi kapatilir. */
    fun ac(kanalId: Int, tanimJson: JSONObject): Pair<JSONObject?, String?> {
        kanallar.remove(kanalId)?.kapat()
        if (kanallar.size >= ENUST_KANAL) {
            return null to "Es zamanli kanal siniri asildi ($ENUST_KANAL)"
        }
        val tanim = Tanim(tanimJson)
        if (tanim.tur == "seri" && kanallar.values.any { it.tanim.tur == "seri" && it.calisiyor }) {
            val acik = kanallar.values.first { it.tanim.tur == "seri" && it.calisiyor }
            return null to "USB seri kanal zaten acik (kanal ${acik.kanalId}); " +
                "telefon tek USB cihaz tasir"
        }
        val k = Kanal(kanalId, tanim)
        val hata = k.ac()
        if (hata != null) {
            Gunluk.hata("AKIS", "Kanal $kanalId acilamadi: $hata")
            return null to hata
        }
        kanallar[kanalId] = k
        return k.durum() to null
    }

    fun kapat(kanalId: Int): Boolean {
        val k = kanallar.remove(kanalId) ?: return false
        k.kapat()
        Gunluk.yaz("AKIS", "Kanal $kanalId kapatildi")
        return true
    }

    fun yaz(kanalId: Int, veri: ByteArray): Int {
        val k = kanallar[kanalId] ?: return 0
        return k.yaz(veri)
    }

    fun tumunuKapat() {
        val hepsi = kanallar.values.toList()
        kanallar.clear()
        hepsi.forEach { runCatching { it.kapat() } }
    }

    fun temizleOlu() {
        kanallar.entries.filter { !it.value.calisiyor }.forEach {
            kanallar.remove(it.key)?.kapat()
        }
    }

    fun etkinSayi(): Int = kanallar.values.count { it.calisiyor }

    fun durum(): JSONArray = JSONArray().apply {
        kanallar.values.sortedBy { it.kanalId }.forEach { put(it.durum()) }
    }

    fun ozet(): String = kanallar.values.joinToString(", ") {
        "#${it.kanalId} ${it.tanim.etiket()}" + if (it.calisiyor) "" else " (durdu)"
    }

    companion object {
        const val OKUMA_TAMPON = 4096
        const val PARTI_ENUST = 8192
        const val PARTI_PENCERE_MS = 20L
        const val ENUST_KANAL = 8
    }
}
