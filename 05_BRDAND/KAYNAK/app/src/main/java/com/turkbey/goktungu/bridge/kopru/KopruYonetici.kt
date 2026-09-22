package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import com.turkbey.goktungu.bridge.mavlink.MavGozlemci
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Ayarlar
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Kopru cekirdegine tek erisim noktasi (Faz 2: COK-KOPRU koordinatoru).
 *
 * ## Mimari
 *
 * 1.1.x'te bu nesne dogrudan MAVLink yolunu yonetiyordu. Faz 2 ile
 * strateji desenine gecildi: her kopru tipi ([KopruTipi]) kendi
 * [KopruStrateji] gerceklemesine sahiptir ve bu koordinator ayni anda
 * TEK bir stratejiyi etkin tutar (bir cihaz, bir kurulum kimligi,
 * merkeze bir baglanti). Kullanici sol menuden tip secince
 * [secTip] cagrilir; onceki tip durdurulur, yenisi kurulur.
 *
 * ## Neden tek ornek ve paylasimli USB
 *
 * USB cihazi ayni anda yalniz bir kez acilabilir; on plan hizmeti ve
 * arayuz AYNI cekirdegi gormelidir. `usb` ve `gozlemci` burada
 * sahiplenip seri kullanan stratejilere ([ArduPilotStrateji],
 * [BetaflightStrateji]) verilir; arayuz cihaz taramasi icin tek bir
 * [UsbSeri] ornegi gorur.
 *
 * ## Regresyon
 *
 * Varsayilan tip [KopruTipi.ARDUPILOT]'tur ve mevcut MAVLink davranisi
 * (USB seri, `akis` kanallari, gozlemci) BIREBIR korunur.
 */
object KopruYonetici {

    private lateinit var baglam: Context

    private var _usb: UsbSeri? = null
    val usb: UsbSeri? get() = _usb

    /** ArduPilot MAVLink telemetrisi (arayuz + on plan hizmeti okur). */
    val gozlemci = MavGozlemci()

    private val stratejiler = LinkedHashMap<KopruTipi, KopruStrateji>()

    private val _aktifTip = MutableStateFlow(KopruTipi.ARDUPILOT)
    val aktifTip: StateFlow<KopruTipi> = _aktifTip.asStateFlow()

    /** Kullanilabilir tum kopru tipleri (menu sirasi). */
    val tipler: List<KopruTipi> get() = KopruTipi.entries

    val aktif: KopruStrateji
        get() = stratejiler[_aktifTip.value]
            ?: error("KopruYonetici.kur() cagrilmadi")

    val ajan: KopruAjan? get() = stratejiler[_aktifTip.value]?.ajan

    @Volatile
    private var kuruldu = false

    /** Uygulama acilisinda bir kez cagrilir. */
    fun kur(b: Context) {
        if (kuruldu) return
        kuruldu = true
        baglam = b.applicationContext
        val u = UsbSeri(baglam)
        _usb = u
        stratejiler[KopruTipi.ARDUPILOT] = ArduPilotStrateji(baglam, u, gozlemci)
        stratejiler[KopruTipi.BETAFLIGHT] = BetaflightStrateji(baglam, u)
        stratejiler[KopruTipi.DJI] = DjiStrateji(baglam)
        stratejiler[KopruTipi.ELEKTRO_OPTIK] = PasifStrateji(baglam, KopruTipi.ELEKTRO_OPTIK)
        stratejiler[KopruTipi.RADAR] = PasifStrateji(baglam, KopruTipi.RADAR)

        // Kullanicinin en son sectigi tip geri yuklenir (varsayilan
        // ArduPilot). DJI'nin MSDK'si secilmedikce BASLAMAZ.
        _aktifTip.value = KopruTipi.idden(Ayarlar.oku(baglam).kopruTip)
        aktif.kur(baglam)
        Gunluk.yaz("KOPRU", "Kopru cekirdegi kuruldu (cok-tipli; aktif: ${aktif.tip.etiket})")
    }

    /**
     * Etkin kopru tipini degistirir. Onceki tip durdurulur (yalniz bir
     * ajan merkeze baglanir), yenisi kurulur. Baslatma cagri yerine
     * (arayuz) birakilir.
     */
    fun secTip(tip: KopruTipi) {
        if (_aktifTip.value == tip) {
            aktif.kur(baglam)
            return
        }
        stratejiler[_aktifTip.value]?.durdur()
        _aktifTip.value = tip
        Ayarlar.kopruTipYaz(baglam, tip.id)
        aktif.kur(baglam)
        Gunluk.yaz("KOPRU", "Kopru tipi secildi: ${tip.etiket}")
    }

    fun baslat(): Boolean {
        aktif.kur(baglam)
        return aktif.baslat()
    }

    fun durdur() = aktif.durdur()

    fun calisiyorMu(): Boolean = stratejiler[_aktifTip.value]?.calisiyorMu() == true

    fun bagliMi(): Boolean = stratejiler[_aktifTip.value]?.bagliMi() == true

    fun etkinKanalSayi(): Int = stratejiler[_aktifTip.value]?.etkinKanalSayi() ?: 0

    fun kanalOzet(): String = stratejiler[_aktifTip.value]?.kanalOzet() ?: ""
}
