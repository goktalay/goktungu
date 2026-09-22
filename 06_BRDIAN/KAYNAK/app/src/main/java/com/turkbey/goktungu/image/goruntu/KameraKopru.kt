package com.turkbey.goktungu.image.goruntu

import android.content.Context
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.turkbey.goktungu.image.veri.Ayarlar
import com.turkbey.goktungu.image.veri.Gunluk
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * KAMERA CEKIRDEGI — cihaz kamerasini CameraX ile yakalar.
 *
 * BRDIMG masaustu koprusunun `video_vekil.py::_oku_opencv` yolunun
 * Android karsiligidir: orada USB/donanim kamera OpenCV ile acilir ve
 * kareler JPEG'e kodlanip yerel fan-out'a beslenir. Burada ayni gorevi
 * CameraX ustlenir:
 *
 *   - [Preview] : arayuzdeki `PreviewView`'e canli onizleme.
 *   - [ImageAnalysis] : her kareyi (YUV_420_888) JPEG'e cevirip
 *     [MjpegSunucu.kareYayinla] ile yerel MJPEG akisina besler.
 *
 * ## Kareler yerelde kalir
 *
 * Kodlanan JPEG merkeze GONDERILMEZ; yalniz yerel MJPEG sunucusuna
 * (`http://<telefon-ip>:8801`) verilir. Merkeze giden tek sey akis-meta
 * ve durumdur (bkz. [com.turkbey.goktungu.image.kopru.GoruntuKanallari]).
 *
 * ## Iskele notu (kodlama)
 *
 * Simdilik YUV->JPEG (YuvImage.compressToJpeg) kullanilir; her kare tek
 * bir bagimsiz JPEG'dir (MJPEG). Tam H.264/RTSP donanim kodlama sonraki
 * fazda [ImageAnalysis] yerine `VideoCapture` + `MediaCodec` ile
 * eklenebilir; kaynak soyutlamasi (fan-out) ayni kalir.
 */
class KameraKopru(private val baglam: Context) {

    private var saglayici: ProcessCameraProvider? = null
    private var onizlemeKullanim: Preview? = null
    private val analizIsi = Executors.newSingleThreadExecutor { r ->
        Thread(r, "kamera-analiz").apply { isDaemon = true }
    }

    @Volatile
    var bagli = false
        private set

    @Volatile
    var sonHata = ""
        private set

    @Volatile
    var cozunurluk = ""
        private set

    val uretilenKare = AtomicLong(0)

    private var jpgKalite = 80
    private var fpsTavan = 15
    private var sonKareZaman = 0L

    /**
     * Kamerayi verilen yasam dongusune baglar (analiz + onizleme).
     *
     * Yasam dongusu genellikle on plan hizmetidir (arka planda da yakalama
     * surer); onizleme yuzeyi arayuz gorunur oldugunda [onizlemeAyarla]
     * ile SONRADAN takilir. Boylece kamera bir kez baglanir, onizleme
     * gelip gider.
     *
     * @param sahip Yasam dongusu (LifecycleService ya da Activity).
     * @param mjpeg Kodlanan karelerin beslenecegi yerel sunucu.
     */
    fun bagla(sahip: LifecycleOwner, mjpeg: MjpegSunucu) {
        val gelecek = ProcessCameraProvider.getInstance(baglam)
        gelecek.addListener({
            try {
                val cp = gelecek.get()
                saglayici = cp

                val onizleme = Preview.Builder().build()
                onizlemeKullanim = onizleme

                val analiz = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                analiz.setAnalyzer(analizIsi) { imge ->
                    kareyiIsle(imge, mjpeg)
                }

                val secici = if (Ayarlar.oku(baglam).mercek == Ayarlar.MERCEK_ON) {
                    CameraSelector.DEFAULT_FRONT_CAMERA
                } else {
                    CameraSelector.DEFAULT_BACK_CAMERA
                }

                cp.unbindAll()
                cp.bindToLifecycle(sahip, secici, onizleme, analiz)
                bagli = true
                sonHata = ""
                Gunluk.yaz("KAMERA", "Kamera baglandi (mercek: ${Ayarlar.oku(baglam).mercek})")
            } catch (e: Exception) {
                bagli = false
                sonHata = e.message ?: e.javaClass.simpleName
                Gunluk.hata("KAMERA", "Kamera baglanamadi: $sonHata")
            }
        }, ContextCompat.getMainExecutor(baglam))
    }

    /** Arayuz onizleme yuzeyini takar/kaldirir (kamera bagli kalir). */
    fun onizlemeAyarla(saglayan: Preview.SurfaceProvider?) {
        onizlemeKullanim?.setSurfaceProvider(saglayan)
    }

    fun coz() {
        runCatching { saglayici?.unbindAll() }
        onizlemeKullanim = null
        bagli = false
        Gunluk.yaz("KAMERA", "Kamera cozuldu")
    }

    // ------------------------------------------------------------------
    private fun kareyiIsle(imge: ImageProxy, mjpeg: MjpegSunucu) {
        try {
            // FPS tavani: analiz ipligi hizli beslerse yerel aga gereksiz
            // yuk binmesin (video_vekil.py fps sinirlama deseni).
            val simdi = System.currentTimeMillis()
            if (simdi - sonKareZaman < 1000L / fpsTavan) return
            sonKareZaman = simdi

            val jpg = jpgeCevir(imge) ?: return
            cozunurluk = "${imge.width}x${imge.height}"
            uretilenKare.incrementAndGet()
            mjpeg.kareYayinla(jpg)
        } finally {
            imge.close()
        }
    }

    /** YUV_420_888 ImageProxy -> NV21 -> JPEG. */
    private fun jpgeCevir(imge: ImageProxy): ByteArray? {
        return try {
            val nv21 = yuv420ToNv21(imge)
            val yuv = YuvImage(nv21, ImageFormat.NV21, imge.width, imge.height, null)
            val cikti = ByteArrayOutputStream()
            val ok = yuv.compressToJpeg(Rect(0, 0, imge.width, imge.height), jpgKalite, cikti)
            if (ok) cikti.toByteArray() else null
        } catch (e: Exception) {
            sonHata = "kare kodlanamadi: ${e.message}"
            null
        }
    }

    /**
     * YUV_420_888 duzlemlerini NV21'e (Y + araya gecmis VU) donusturur.
     * pixelStride/rowStride hesaba katilir (aygitlar arasi farkli olur).
     */
    private fun yuv420ToNv21(imge: ImageProxy): ByteArray {
        val g = imge.width
        val y = imge.height
        val nv21 = ByteArray(g * y * 3 / 2)

        val yD = imge.planes[0]
        val uD = imge.planes[1]
        val vD = imge.planes[2]

        val yTampon = yD.buffer
        val uTampon = uD.buffer
        val vTampon = vD.buffer

        // Y duzlemi
        var cikti = 0
        val ySatir = yD.rowStride
        val yPiksel = yD.pixelStride
        for (satir in 0 until y) {
            var pos = satir * ySatir
            for (sutun in 0 until g) {
                nv21[cikti++] = yTampon.get(pos)
                pos += yPiksel
            }
        }

        // UV duzlemleri (yariya inmis): NV21 = VUVU...
        val uvSatir = uD.rowStride
        val uvPiksel = uD.pixelStride
        val yUv = y / 2
        val gUv = g / 2
        for (satir in 0 until yUv) {
            var uPos = satir * uvSatir
            var vPos = satir * vD.rowStride
            for (sutun in 0 until gUv) {
                nv21[cikti++] = vTampon.get(vPos)
                nv21[cikti++] = uTampon.get(uPos)
                uPos += uvPiksel
                vPos += vD.pixelStride
            }
        }
        return nv21
    }

    fun durumJson(): org.json.JSONObject = org.json.JSONObject()
        .put("bagli", bagli)
        .put("cozunurluk", cozunurluk)
        .put("uretilen_kare", uretilenKare.get())
        .put("son_hata", sonHata)
}
