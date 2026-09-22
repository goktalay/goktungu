package com.turkbey.goktungu

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.webkit.JavascriptInterface
import androidx.core.app.NotificationCompat
import java.util.concurrent.atomic.AtomicInteger

/**
 * WebView (GRCOFF arayüzü) → Android bildirim köprüsü.
 *
 * Arayüzdeki Uyarılar sistemi (uyari_merkezi.js) yeni bir uyarı aldığında
 * `window.AndroidBildirim.bildir(baslik, metin)` çağırır; bu sınıf onu
 * native Android bildirimine çevirir. Böylece uygulama arka plandayken
 * bile uyarılar cihazın bildirim panelinde görünür.
 *
 * Yalnız Android tarafında tanımlıdır; masaüstü GRCOFF arayüzünde
 * `window.AndroidBildirim` yoktur ve JS tarafı varlık denetimi yapar.
 */
class BildirimKopru(private val baglam: Context) {

    @JavascriptInterface
    fun bildir(baslik: String?, metin: String?) {
        try {
            gonder(baslik ?: "GÖKTUNGU", metin ?: "")
        } catch (_: Throwable) {
        }
    }

    private fun gonder(baslik: String, metin: String) {
        val ym = baglam.getSystemService(Context.NOTIFICATION_SERVICE)
            as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val kanal = NotificationChannel(
                KANAL, "GÖKTUNGU Uyarıları",
                NotificationManager.IMPORTANCE_HIGH
            ).apply { description = "Uçuş, radar ve sistem uyarıları" }
            ym.createNotificationChannel(kanal)
        }

        // Bildirime dokununca uygulamayı öne getir.
        val niyet = Intent(baglam, AnaEtkinlik::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val bayrak = PendingIntent.FLAG_UPDATE_CURRENT or
            (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
                PendingIntent.FLAG_IMMUTABLE else 0)
        val pi = PendingIntent.getActivity(baglam, 0, niyet, bayrak)

        val bildirim: Notification = NotificationCompat.Builder(baglam, KANAL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(baslik)
            .setContentText(metin)
            .setStyle(NotificationCompat.BigTextStyle().bigText(metin))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .build()

        ym.notify(SAYAC.incrementAndGet(), bildirim)
    }

    companion object {
        private const val KANAL = "grcoff_uyari"
        // Her uyarı ayrı bildirim (üst üste binmesin) — artan kimlik.
        private val SAYAC = AtomicInteger(1000)
    }
}
