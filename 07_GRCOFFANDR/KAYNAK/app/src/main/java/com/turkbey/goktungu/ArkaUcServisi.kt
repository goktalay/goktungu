package com.turkbey.goktungu

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.turkbey.goktungu.usb.UsbMavKoprusu
import java.io.File
import kotlin.concurrent.thread

/**
 * Gömülü GRCOFF Python arka ucunu tutan ön plan servisi.
 *
 * Chaquopy Python 3.11 yorumlayıcısını başlatır ve `android_sunucu`
 * modülünün `baslat(veri_koku, port)` fonksiyonunu çağırır. Bu modül
 * mevcut GRCOFF sunucusunu (goktungu paketi) Android'e uyarlanmış
 * biçimde ayağa kaldırır: PostgreSQL yerine SQLite, kök dizin olarak
 * uygulamanın özel veri klasörü.
 */
class ArkaUcServisi : Service() {

    companion object {
        const val PORT = 8770
        private const val KANAL = "grcoff_arka_uc"
        private const val BILDIRIM_ID = 1
    }

    @Volatile private var calisiyor = false
    private var usbKoprusu: UsbMavKoprusu? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, id: Int): Int {
        if (!calisiyor) {
            calisiyor = true
            onPlanaGec()
            arkaUcuBaslat()
            // USB seri (uçuş kontrolcüsü) -> yerel TCPköprüsü; pymavlink
            // tcp:127.0.0.1:5760 ile bağlanır (android_sunucu bu bağlantıyı
            // otomatik kaydeder).
            usbKoprusu = UsbMavKoprusu(this).also { it.baslat() }
        }
        return START_STICKY
    }

    private fun onPlanaGec() {
        val ym = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val kanal = NotificationChannel(
                KANAL, "GÖKTUNGU arka uç",
                NotificationManager.IMPORTANCE_LOW
            )
            ym.createNotificationChannel(kanal)
        }
        val bildirim: Notification = NotificationCompat.Builder(this, KANAL)
            .setContentTitle("GÖKTUNGU")
            .setContentText("Uçuş yer istasyonu arka ucu çalışıyor")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .build()
        startForeground(BILDIRIM_ID, bildirim)
    }

    private fun arkaUcuBaslat() = thread(name = "grcoff-python") {
        try {
            val veriKoku = filesDir.absolutePath // özel, harici erişime kapalı
            // Web arayüzü (Cesium + js/css) APK içinde assets/web altında
            // taşınır; Chaquopy veri dosyalarını gerçek dosya yoluna
            // çıkarmadığı için HTTP sunucusunun okuyabilmesi adına
            // filesDir/web'e ayıklanır (sürüm anahtarlı, bir kez).
            val webKoku = webVarliklariniAyikla()

            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(this))
            }
            val py = Python.getInstance()
            // android_sunucu.baslat(veri_koku, web_koku, port)
            py.getModule("android_sunucu")
                .callAttr("baslat", veriKoku, webKoku, PORT)
        } catch (e: Throwable) {
            android.util.Log.e("GRCOFF", "Arka uç başlatılamadı", e)
        }
    }

    /**
     * APK `assets/web` içeriğini `filesDir/web`'e ayıklar. Uygulama sürümü
     * değişmedikçe yeniden kopyalamaz (sürüm imzası dosyasıyla ölçülür).
     * @return ayıklanan web kökünün mutlak yolu
     */
    private fun webVarliklariniAyikla(): String {
        val hedef = File(filesDir, "web")
        val imza = File(hedef, ".surum")
        val simdiki = BuildConfig.VERSION_CODE.toString()
        if (imza.exists() && imza.readText() == simdiki) {
            return hedef.absolutePath
        }
        if (hedef.exists()) hedef.deleteRecursively()
        hedef.mkdirs()
        varlikKopyala("web", hedef)
        try { imza.writeText(simdiki) } catch (_: Throwable) {}
        return hedef.absolutePath
    }

    /** Bir asset dizinini özyinelemeli kopyalar. */
    private fun varlikKopyala(kaynakDizin: String, hedefDizin: File) {
        val liste = assets.list(kaynakDizin) ?: return
        if (liste.isEmpty()) {
            // Dosya (dizin değil): kopyala.
            assets.open(kaynakDizin).use { girdi ->
                hedefDizin.outputStream().use { girdi.copyTo(it) }
            }
            return
        }
        hedefDizin.mkdirs()
        for (ad in liste) {
            val altKaynak = "$kaynakDizin/$ad"
            val altListe = assets.list(altKaynak)
            if (altListe.isNullOrEmpty()) {
                assets.open(altKaynak).use { girdi ->
                    File(hedefDizin, ad).outputStream().use { girdi.copyTo(it) }
                }
            } else {
                varlikKopyala(altKaynak, File(hedefDizin, ad))
            }
        }
    }

    override fun onDestroy() {
        calisiyor = false
        runCatching { usbKoprusu?.durdur() }
        usbKoprusu = null
        super.onDestroy()
    }
}
