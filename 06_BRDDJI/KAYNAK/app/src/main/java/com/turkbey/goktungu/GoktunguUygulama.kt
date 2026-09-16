package com.turkbey.goktungu

import android.app.Application
import android.content.Context
import androidx.multidex.MultiDex
import com.turkbey.goktungu.veri.Gunluk

/**
 * Uygulama girisi.
 *
 * MSDK buyuk oldugu icin multidex zorunludur; [attachBaseContext]
 * icinde kurulmali.
 *
 * DIKKAT: MSDK kaydi burada BASLATILMAZ.  DJI'nin `SDKManager`
 * cagrisi, kayit geri bildirimi icin uzun surebilir ve kullaniciya
 * durum gostermek gerekir; bu yuzden kayit `DjiKayit` uzerinden
 * arayuz hazir olduktan sonra baslatilir.
 */
class GoktunguUygulama : Application() {

    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        MultiDex.install(this)
    }

    override fun onCreate() {
        super.onCreate()
        ornek = this
        Gunluk.yaz("UYG", "GOKTUNGU DJI Koprusu baslatildi " +
            "(surum ${BuildConfig.VERSION_NAME})")
    }

    companion object {
        @Volatile
        lateinit var ornek: GoktunguUygulama
            private set
    }
}
