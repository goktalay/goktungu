package com.turkbey.goktungu.bridge

import android.app.Application
import android.content.Context
import androidx.multidex.MultiDex
import com.turkbey.goktungu.bridge.veri.Gunluk

/**
 * Uygulama girisi.
 *
 * ## Multidex (DJI MSDK gommeli)
 *
 * DJI MSDK v5 cekirdegi gomulunce yontem sayisi 64K DEX sinirinin
 * uzerine cikar; bu yuzden `multiDexEnabled true` ZORUNLUDUR ve MSDK
 * buyuk oldugu icin [attachBaseContext] icinde `MultiDex.install`
 * cagrilmalidir (BRDDJI `GoktunguUygulama` deseni). Bu, saf-JVM MAVLink
 * yolunun davranisini DEGISTIRMEZ; yalnizca ikincil dex dosyalarinin
 * eski surumlerde de yuklenmesini saglar.
 *
 * ## Kopru cekirdekleri burada BASLATILMAZ
 *
 * MAVLink cekirdegi `AnaEtkinlik` icinde kurulur cunku USB erisimi icin
 * etkinlik baglami ve kullanici izni gerekir. DJI cekirdegi
 * ([com.turkbey.goktungu.bridge.kopru.DjiKopruCekirdegi]) da ancak
 * arayuzden DJI kopru tipi secilince (Faz 2) `kur()` ile tetiklenir;
 * boylece cagrilmadan MSDK BASLAMAZ ve mevcut MAVLink davranisi
 * korunur.
 */
class GoktunguMavUygulama : Application() {

    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        // DJI MSDK gommeli oldugundan yontem sayisi 64K'yi asar;
        // ikincil dex'ler burada yuklenir.
        MultiDex.install(this)
    }

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
