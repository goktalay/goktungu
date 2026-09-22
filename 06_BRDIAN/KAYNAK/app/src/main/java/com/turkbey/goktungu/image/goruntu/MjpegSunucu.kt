package com.turkbey.goktungu.image.goruntu

import com.turkbey.goktungu.image.veri.Gunluk
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * YEREL MJPEG SUNUCUSU — kamera karelerini yerel agda HTTP ile sunar.
 *
 * BRDIMG masaustu koprusunun `kopru/video_vekil.py` desenini Android'e
 * tasir. Oradaki tasarim karari BURADA DA gecerlidir:
 *
 *   > Kullanicinin kamerasi SAHADAKI yerel agda durur; merkez sunucu bir
 *   > veri merkezindedir ve o adrese erisemez. Akisi merkezde acmak
 *   > tanim geregi basarisizdir.
 *
 * Bu yuzden KARELER YERELDE KALIR: telefon kendi kamerasini yakalar,
 * MJPEG'i yerel agda `http://<telefon-ip>:8801/kamera/<id>` adresinde
 * sunar. Merkeze (GRCON/GRCOFF) yalniz DURUM/akis-meta gider
 * ([com.turkbey.goktungu.image.kopru.KopruAjan] uzerinden); ham kareler
 * WebSocket'e KONMAZ.
 *
 * Tek kaynak (cihaz kamerasi) icin tek yayin vardir; en son kareyi
 * bekleyen tum HTTP istemcilerine dagitan basit bir fan-out yapisi
 * kurulur (video_vekil.py `_Yayin` ile ayni fikir).
 *
 * ## Iskele notu
 *
 * multipart/x-mixed-replace ile MJPEG sunumu tam islevseldir. Ileride
 * gercek RTSP/donanim kodlama (H.264) eklenirse bu sinif kaynak
 * soyutlamasini korur; kamera karesini besleyen [kareYayinla]
 * arayuzu degismez.
 */
class MjpegSunucu(private val port: Int = VARSAYILAN_PORT) {

    @Volatile
    private var sunucu: ServerSocket? = null

    @Volatile
    var calisiyor = false
        private set

    // Son kare + kare numarasi; istemci iplikleri bunu bekler.
    private val kilit = Object()

    @Volatile
    private var sonKare: ByteArray? = null
    private var kareNo = 0L

    val gonderilenKare = AtomicLong(0)
    val izleyici = AtomicLong(0)

    private val istemciler = CopyOnWriteArrayList<Socket>()
    private val havuz = Executors.newCachedThreadPool { r ->
        Thread(r, "mjpeg-istemci").apply { isDaemon = true }
    }
    private var kabulIpligi: Thread? = null

    fun baslat(): Boolean {
        if (calisiyor) return true
        return try {
            sunucu = ServerSocket().apply {
                reuseAddress = true
                bind(InetSocketAddress("0.0.0.0", port))
            }
            calisiyor = true
            kabulIpligi = Thread({ kabulDongusu() }, "mjpeg-kabul").apply {
                isDaemon = true
                start()
            }
            Gunluk.yaz("MJPEG", "Yerel MJPEG sunucusu basladi (port $port)")
            true
        } catch (e: Exception) {
            Gunluk.hata("MJPEG", "Sunucu baslatilamadi (port $port): ${e.message}")
            calisiyor = false
            false
        }
    }

    fun durdur() {
        calisiyor = false
        runCatching { sunucu?.close() }
        sunucu = null
        istemciler.forEach { runCatching { it.close() } }
        istemciler.clear()
        izleyici.set(0)
        Gunluk.yaz("MJPEG", "Yerel MJPEG sunucusu durdu")
    }

    /** Kamera cekirdegi her yeni JPEG kareyi buraya besler (fan-out). */
    fun kareYayinla(jpg: ByteArray) {
        synchronized(kilit) {
            sonKare = jpg
            kareNo++
            gonderilenKare.incrementAndGet()
            kilit.notifyAll()
        }
    }

    fun kareVar(): Boolean = sonKare != null

    // ------------------------------------------------------------------
    private fun kabulDongusu() {
        val s = sunucu ?: return
        while (calisiyor) {
            val istemci = try {
                s.accept()
            } catch (e: Exception) {
                if (calisiyor) Gunluk.uyari("MJPEG", "Kabul hatasi: ${e.message}")
                break
            }
            havuz.execute { istemciyiIsle(istemci) }
        }
    }

    private fun istemciyiIsle(istemci: Socket) {
        istemciler.add(istemci)
        izleyici.incrementAndGet()
        try {
            istemci.tcpNoDelay = true
            val giris = BufferedReader(InputStreamReader(istemci.getInputStream()))
            // Istek satirini oku (yol onemli degil; tek kaynak var).
            val istekSatiri = giris.readLine() ?: return
            // Kalan basliklari yut.
            while (true) {
                val satir = giris.readLine() ?: break
                if (satir.isEmpty()) break
            }
            val cikis = istemci.getOutputStream()
            if (!istekSatiri.startsWith("GET")) {
                hataYaz(cikis, 400, "yalniz GET desteklenir")
                return
            }
            mjpegAkisi(cikis)
        } catch (e: Exception) {
            // Baglanti koptu; sessizce kapat.
        } finally {
            istemciler.remove(istemci)
            izleyici.decrementAndGet()
            runCatching { istemci.close() }
        }
    }

    private fun hataYaz(cikis: OutputStream, kod: Int, gerekce: String) {
        val govde = "{\"hata\":\"$gerekce\"}".toByteArray(Charsets.UTF_8)
        val bas = buildString {
            append("HTTP/1.1 $kod TAMAM\r\n")
            append("Content-Type: application/json\r\n")
            append("Content-Length: ${govde.size}\r\n")
            append("Access-Control-Allow-Origin: *\r\n")
            append("Connection: close\r\n\r\n")
        }
        runCatching {
            cikis.write(bas.toByteArray(Charsets.US_ASCII))
            cikis.write(govde)
            cikis.flush()
        }
    }

    private fun mjpegAkisi(cikis: OutputStream) {
        // Ilk kare gelene kadar bekle (video_vekil.py ilk_kare_bekle deseni):
        // bos govdeli 200 yaniti tarayicida "YAYIN ALINAMIYOR" uretirdi.
        val bitis = System.currentTimeMillis() + ILK_KARE_MS
        while (sonKare == null && calisiyor && System.currentTimeMillis() < bitis) {
            synchronized(kilit) { kilit.wait(200) }
        }
        if (sonKare == null) {
            hataYaz(cikis, 503, "kaynak henuz kare uretmedi")
            return
        }
        val bas = buildString {
            append("HTTP/1.1 200 TAMAM\r\n")
            append("Content-Type: multipart/x-mixed-replace; boundary=$SINIR\r\n")
            append("Cache-Control: no-cache, private\r\n")
            append("Pragma: no-cache\r\n")
            append("Access-Control-Allow-Origin: *\r\n")
            append("Connection: close\r\n\r\n")
        }
        cikis.write(bas.toByteArray(Charsets.US_ASCII))
        cikis.flush()

        var sonGonderilen = -1L
        while (calisiyor) {
            val kare: ByteArray?
            synchronized(kilit) {
                if (kareNo == sonGonderilen) kilit.wait(2000)
                kare = sonKare
                sonGonderilen = kareNo
            }
            val k = kare ?: continue
            val parcaBas = "--$SINIR\r\nContent-Type: image/jpeg\r\n" +
                "Content-Length: ${k.size}\r\n\r\n"
            cikis.write(parcaBas.toByteArray(Charsets.US_ASCII))
            cikis.write(k)
            cikis.write("\r\n".toByteArray(Charsets.US_ASCII))
            cikis.flush()
        }
    }

    companion object {
        const val VARSAYILAN_PORT = 8801
        const val SINIR = "goktunguframe"
        const val ILK_KARE_MS = 12_000L
    }
}
