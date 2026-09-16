package com.turkbey.goktungu.kopru

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.turkbey.goktungu.R
import com.turkbey.goktungu.arayuz.AnaEtkinlik
import com.turkbey.goktungu.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * On plan hizmeti: ucus surerken koprunun isletim sistemi tarafindan
 * oldurulmesini engeller.
 *
 * Android 14+ `connectedDevice` hizmet turu ister; manifestte bildirildi.
 * Bildirim govdesi arac ve merkez durumunu canli gosterir — pilot
 * uygulamayi one almadan koprunun ayakta oldugunu gorur.
 */
class KopruHizmeti : Service() {

    private var kapsam: CoroutineScope? = null
    private var guncelleyici: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        kanalKur()
        startForeground(
            BILDIRIM_ID,
            bildirimKur(
                getString(R.string.durum_arac_yok),
                getString(R.string.durum_merkez_kopuk)
            )
        )
        Gunluk.yaz("HIZMET", "Kopru hizmeti basladi")
        durumuIzle()
    }

    override fun onStartCommand(
        intent: Intent?, bayraklar: Int, baslatmaId: Int
    ): Int = START_STICKY

    override fun onDestroy() {
        guncelleyici?.cancel()
        kapsam?.cancel()
        kapsam = null
        Gunluk.yaz("HIZMET", "Kopru hizmeti durdu")
        super.onDestroy()
    }

    /**
     * Bildirimi iki saniyede bir tazeler.  Akislari `collect` etmek
     * yerine yoklama kullanildi: uc ayri akisi (arac, merkez, ornek)
     * birlestirmek bildirim icin gereksiz karmasa olurdu.
     */
    private fun durumuIzle() {
        val k = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        kapsam = k
        guncelleyici = k.launch {
            var oncekiArac = ""
            var oncekiMerkez = ""
            while (true) {
                val dji = KopruYonetici.dji
                val arac = if (dji?.urunBagli?.value == true) {
                    dji.urunModeli()
                } else {
                    getString(R.string.durum_arac_yok)
                }
                val ist = KopruYonetici.istemci
                val merkez = when (ist?.durum?.value) {
                    GdpIstemci.Durum.BAGLI ->
                        getString(R.string.hizmet_merkez_bagli) + " " +
                            KopruYonetici.ornekSayisi.value
                    GdpIstemci.Durum.BAGLANIYOR ->
                        getString(R.string.durum_merkez_baglaniyor)
                    GdpIstemci.Durum.HATA ->
                        getString(R.string.hizmet_merkez_hata)
                    else -> getString(R.string.durum_merkez_kopuk)
                }
                // Yalniz degisince bildirim tazele: gereksiz tazeleme
                // pil tuketir ve bildirim golgesinde titreme yapar.
                if (arac != oncekiArac || merkez != oncekiMerkez) {
                    oncekiArac = arac
                    oncekiMerkez = merkez
                    runCatching {
                        (getSystemService(NotificationManager::class.java))
                            .notify(BILDIRIM_ID, bildirimKur(arac, merkez))
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
            (getSystemService(NotificationManager::class.java))
                .createNotificationChannel(k)
        }
    }

    private fun bildirimKur(arac: String, merkez: String): Notification {
        val niyet = PendingIntent.getActivity(
            this, 0,
            Intent(this, AnaEtkinlik::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, KANAL_ID)
            .setContentTitle(getString(R.string.hizmet_bildirim_baslik))
            .setContentText(
                getString(R.string.hizmet_bildirim_govde, arac, merkez)
            )
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentIntent(niyet)
            .setOngoing(true)
            .setShowWhen(false)
            .build()
    }

    companion object {
        const val KANAL_ID = "goktungu_kopru"
        const val BILDIRIM_ID = 1001
    }
}
