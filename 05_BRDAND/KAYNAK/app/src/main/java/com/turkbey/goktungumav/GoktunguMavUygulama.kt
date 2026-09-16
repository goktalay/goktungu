package com.turkbey.goktungumav

import android.app.Application
import com.turkbey.goktungumav.veri.Gunluk

/**
 * Uygulama girisi.
 *
 * ## Neden multidex yok
 *
 * DJI koprusu MSDK'nin buyuklugu nedeniyle `multiDexEnabled true`
 * kullanmak ZORUNDAYDI.  MAVLink koprusunun hicbir agir bagimliligi
 * yoktur (kendi seri surucusu ve kendi cerceve ayristiricisi var), bu
 * yuzden yontem sayisi 64K sinirinin cok altinda kalir ve multidex
 * gereksizdir.  Multidex'i kaldirmak acilis suresini kisaltir.
 *
 * Kopru cekirdegi burada kurulmaz; `AnaEtkinlik` icinde kurulur cunku
 * USB erisimi icin etkinlik baglami ve kullanici izni gerekir.
 */
class GoktunguMavUygulama : Application() {

    override fun onCreate() {
        super.onCreate()
        ornek = this
        Gunluk.yaz("UYGULAMA", "GOKTUNGU MAVLink Koprusu baslatildi")
    }

    companion object {
        @Volatile
        var ornek: GoktunguMavUygulama? = null
            private set
    }
}
