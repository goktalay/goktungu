package com.turkbey.goktungu.image

import android.app.Application
import com.turkbey.goktungu.image.veri.Gunluk

/**
 * Uygulama girisi (GOKTUNGU Goruntu Koprusu / BRDIAN).
 *
 * ## BRDAND'dan fark: multidex YOK
 *
 * BRDAND'da DJI MSDK v5 gomulu oldugundan `MultiDex.install` zorunluydu.
 * BRDIAN yalniz AndroidX + CameraX + OkHttp tasir; yontem sayisi 64K DEX
 * sinirinin altindadir, bu yuzden multidex gerekmez.
 *
 * ## Cekirdek burada BASLATILMAZ
 *
 * Kamera ve kopru ajani [com.turkbey.goktungu.image.arayuz.AnaEtkinlik]
 * icinden [com.turkbey.goktungu.image.kopru.GoruntuYonetici] ile kurulur;
 * kamera erisimi kullanici izni ve yasam dongusu (LifecycleOwner)
 * gerektirdigi icin uygulama acilisinda otomatik baslatilmaz.
 */
class GoktunguGoruntuUygulama : Application() {

    override fun onCreate() {
        super.onCreate()
        ornek = this
        Gunluk.yaz("UYGULAMA", "GOKTUNGU Goruntu Koprusu baslatildi")
    }

    companion object {
        @Volatile
        var ornek: GoktunguGoruntuUygulama? = null
            private set
    }
}
