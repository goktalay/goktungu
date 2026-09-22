package com.turkbey.goktungu.image.kopru

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungu.image.R
import com.turkbey.goktungu.image.arayuz.AnaEtkinlik
import com.turkbey.goktungu.image.veri.Gunluk
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * On plan hizmeti: yayin surerken koprunun ve kamera yakalamanin isletim
 * sistemi tarafindan oldurulmesini engeller.
 *
 * BRDAND'daki `KopruHizmeti`nin GORUNTU karsiligidir. Iki onemli fark:
 *
 *  1. [LifecycleService]'tir: CameraX'in yasam dongusu (LifecycleOwner)
 *     olarak hizmet kullanilir; boylece arayuz kapali olsa da kamera
 *     yakalama ve yerel MJPEG sunumu surer. [GoruntuYonetici.kameraBagla]
 *     bu hizmete baglar; arayuz yalniz onizleme yuzeyini takar/kaldirir.
 *  2. On plan turu `camera`'dir (Android 14+ icin FOREGROUND_SERVICE_CAMERA
 *     izni ile).
 */
class KopruHizmeti : LifecycleService() {

    private var guncelleyici: Job? = null

    override fun onCreate() {
        super.onCreate()
        kanalKur()
        val tur = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA
        } else 0
        ServiceCompat.startForeground(
            this,
            BILDIRIM_ID,
            bildirimKur(
                getString(R.string.durum_kamera_yok),
                getString(R.string.durum_merkez_kopuk)
            ),
            tur
        )
        // Kamerayi bu hizmetin yasam dongusune bagla (arka planda da surer).
        GoruntuYonetici.kur(applicationContext)
        GoruntuYonetici.kameraBagla(this)
        Gunluk.yaz("HIZMET", "Goruntu koprusu hizmeti basladi")
        durumuIzle()
    }

    override fun onStartCommand(intent: Intent?, bayraklar: Int, baslatmaId: Int): Int {
        super.onStartCommand(intent, bayraklar, baslatmaId)
        return START_STICKY
    }

    override fun onDestroy() {
        guncelleyici?.cancel()
        GoruntuYonetici.kameraCoz()
        Gunluk.yaz("HIZMET", "Goruntu koprusu hizmeti durdu")
        super.onDestroy()
    }

    private fun durumuIzle() {
        guncelleyici = lifecycleScope.launch {
            var oncekiKamera = ""
            var oncekiMerkez = ""
            while (true) {
                val kam = GoruntuYonetici.kamera
                val kamera = when {
                    kam?.bagli == true -> getString(
                        R.string.hizmet_kamera_bagli,
                        kam.cozunurluk.ifBlank { "…" }, kam.uretilenKare.get()
                    )
                    else -> getString(R.string.durum_kamera_yok)
                }
                val ajan = GoruntuYonetici.ajan
                val merkez = when (ajan?.durum?.value) {
                    KopruAjan.Durum.BAGLI -> getString(
                        R.string.hizmet_merkez_bagli, ajan.bilgi.value.ad
                    )
                    KopruAjan.Durum.BAGLANIYOR -> getString(R.string.durum_merkez_baglaniyor)
                    KopruAjan.Durum.HATA -> getString(R.string.hizmet_merkez_hata)
                    else -> getString(R.string.durum_merkez_kopuk)
                }
                if (kamera != oncekiKamera || merkez != oncekiMerkez) {
                    oncekiKamera = kamera
                    oncekiMerkez = merkez
                    runCatching {
                        (getSystemService(NotificationManager::class.java))
                            .notify(BILDIRIM_ID, bildirimKur(kamera, merkez))
                    }
                }
                delay(2000)
            }
        }
    }

    private fun kanalKur() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val k = NotificationChannel(
                KANAL_ID,
                getString(R.string.hizmet_kanal_adi),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.hizmet_kanal_aciklama)
            }
            (getSystemService(NotificationManager::class.java)).createNotificationChannel(k)
        }
    }

    private fun bildirimKur(kamera: String, merkez: String): Notification {
        val niyet = PendingIntent.getActivity(
            this, 0,
            Intent(this, AnaEtkinlik::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, KANAL_ID)
            .setContentTitle(getString(R.string.hizmet_bildirim_baslik))
            .setContentText(getString(R.string.hizmet_bildirim_govde, kamera, merkez))
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentIntent(niyet)
            .setOngoing(true)
            .setShowWhen(false)
            .build()
    }

    companion object {
        const val KANAL_ID = "goktungu_goruntu_kopru"
        const val BILDIRIM_ID = 1001
    }
}
