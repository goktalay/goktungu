package com.turkbey.goktungumav.kopru

import android.content.Context
import android.hardware.usb.UsbDevice
import com.turkbey.goktungumav.mavlink.MavlinkKopru
import com.turkbey.goktungumav.veri.Gunluk

/**
 * Kopru cekirdegine tek erisim noktasi.
 *
 * ## Neden tek ornek (singleton)
 *
 * USB cihazi ayni anda yalniz bir kez acilabilir.  Iki [MavlinkKopru]
 * ornegi ayni cihazi almaya kalksa ikincisi `claimInterface`
 * basarisizligiyla doner ve kullanici nedenini anlamaz.  Ayrica
 * arayuz ile on plan hizmetinin AYNI kopru ornegini gormesi
 * zorunludur; yoksa bildirimde gosterilen durum ekrandakinden farkli
 * olur.
 */
object KopruYonetici {

    private var _kopru: MavlinkKopru? = null
    val kopru: MavlinkKopru? get() = _kopru

    @Volatile
    private var kuruldu = false

    /** Uygulama acilisinda bir kez cagrilir. */
    fun kur(baglam: Context) {
        if (kuruldu) return
        kuruldu = true
        _kopru = MavlinkKopru(baglam.applicationContext)
        Gunluk.yaz("KOPRU", "Kopru cekirdegi kuruldu")
    }

    /**
     * Kopruyu baslatir.
     *
     * @return hata iletisi, basarili ise `null`
     */
    fun baglan(
        cihaz: UsbDevice, hiz: Int, sunucu: String, port: Int
    ): String? {
        val k = _kopru ?: run {
            Gunluk.hata("KOPRU", "Cekirdek kurulmadan baglanti denendi")
            return "Kopru cekirdegi kurulmadi"
        }
        return k.baslat(cihaz, hiz, sunucu, port)
    }

    fun kes() {
        _kopru?.durdur()
    }

    fun calisiyorMu(): Boolean =
        _kopru?.durum?.value?.let {
            it == MavlinkKopru.Durum.CALISIYOR ||
                it == MavlinkKopru.Durum.ARAC_BEKLENIYOR
        } == true
}
