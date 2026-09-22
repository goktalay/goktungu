package com.turkbey.goktungu

import android.app.Application
import android.content.Context
import androidx.multidex.MultiDex
import com.turkbey.goktungu.veri.Gunluk

/**
 * Uygulama girisi (GRCOFFANDR Faz 4).
 *
 * DJI MSDK cok buyuk oldugundan (arm64 jni ~257 MB) uygulamanin metod
 * sayisi 64K sinirini asar; Chaquopy'nin gomulu Python sinifları da
 * eklenince multidex ZORUNLUDUR. [attachBaseContext] icinde kurulur.
 *
 * DIKKAT — REGRESYONSUZLUK:
 *  - Chaquopy burada BASLATILMAZ. Gomulu Python arka uc, mevcut
 *    davranista oldugu gibi [ArkaUcServisi] icinde
 *    `Python.start(AndroidPlatform(...))` ile elle baslatilir. Bu
 *    Application yalnizca MultiDex.install ekler; Chaquopy/WebView/MAVLink
 *    yoluna DOKUNMAZ.
 *  - DJI MSDK kaydi da burada baslatilmaz: `SDKManager.init` kayit geri
 *    bildirimi icin uzun surebilir ve arka uc hazir olduktan sonra
 *    [ArkaUcServisi] -> [com.turkbey.goktungu.kopru.YerelDjiKopru]
 *    uzerinden baslatilir (127.0.0.1:8790 yerel Python sunucusuna baglanir).
 */
class GoktunguUygulama : Application() {

    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        // minSdk 24'te ART yerel multidex destekler; kutuphane cagrisi
        // guvenli (no-op benzeri) ve daha dusuk API'lerde de dogru calisir.
        MultiDex.install(this)
    }

    override fun onCreate() {
        super.onCreate()
        ornek = this
        Gunluk.yaz("UYG", "GOKTUNGU (GRCOFFANDR) baslatildi " +
            "(surum ${BuildConfig.VERSION_NAME})")
    }

    companion object {
        @Volatile
        lateinit var ornek: GoktunguUygulama
            private set
    }
}
