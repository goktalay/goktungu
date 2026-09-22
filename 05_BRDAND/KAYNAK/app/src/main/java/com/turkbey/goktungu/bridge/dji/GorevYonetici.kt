package com.turkbey.goktungu.bridge.dji

import android.content.Context
import com.turkbey.goktungu.bridge.veri.GdpKoordinat
import com.turkbey.goktungu.bridge.veri.Gunluk
import dji.v5.common.callback.CommonCallbacks
import dji.v5.common.error.IDJIError
import dji.v5.manager.aircraft.waypoint3.WaypointMissionManager
import java.io.File

/**
 * DJI dalga hatti (waypoint) gorev yoneticisi.
 *
 * MSDK v5'te tek noktaya gitme komutu olmadigi icin (bkz.
 * `BULGU_msdk_api.md`) hem `goto` hem `gorev_yukle` KMZ uzerinden
 * yurutulur:
 *
 * 1. [KmzUretici] ile KMZ dosyasi uretilir
 * 2. `pushKMZFileToAircraft` ile araca yuklenir (ilerleme bildirilir)
 * 3. `startMission` ile baslatilir
 *
 * Gorev adi dosya adiyla ayni olmak zorundadir; `startMission` dosya
 * adini ister, yolu degil.
 */
class GorevYonetici(
    baglam: Context,
    /** Gorev durumunu sunucuya bildirmek icin. */
    private val durumBildir: (durum: String, nokta: Int) -> Unit,
    /** Yukleme ilerlemesini sunucuya bildirmek icin. */
    private val yuklemeBildir: (
        yuklenen: Int, toplam: Int, durum: String, mesaj: String
    ) -> Unit
) {

    /** KMZ dosyalari uygulama ozel deposunda tutulur. */
    private val dizin: File =
        File(baglam.filesDir, "gorev").apply { mkdirs() }

    /** Araca yuklenmis en son gorevin adi (uzantisiz). */
    @Volatile
    private var yuklenmisAd: String? = null

    private val wm: WaypointMissionManager
        get() = WaypointMissionManager.getInstance()

    fun baslatModulu() {
        try {
            wm.init()
            Gunluk.yaz("GOREV", "Gorev yoneticisi hazir")
        } catch (e: Exception) {
            Gunluk.hata("GOREV", "Gorev yoneticisi baslatilamadi: " +
                "${e.message}")
        }
    }

    /**
     * Tek noktaya gitme.  GDP `goto` komutunun karsiligi.
     *
     * Uretilen gorev her seferinde ayni adi kullanir (`goktungu_goto`);
     * boylece araca birikmis dosya kalmaz.
     */
    fun tekNoktayaGit(
        hedef: GdpKoordinat,
        irtifa: Double,
        hiz: Double,
        geri: (Boolean, String) -> Unit
    ) {
        val dosya = KmzUretici.uret(
            dizin, "goktungu_goto",
            listOf(KmzUretici.Nokta(hedef, irtifa)),
            hiz,
            // Tek noktaya gidiste arac hedefte beklemeli; otomatik eve
            // donmek pilotun beklentisini bozar.
            KmzUretici.BitisEylemi.BEKLE
        )
        if (dosya == null) {
            geri(false, "gorev dosyasi uretilemedi")
            return
        }
        yukleVeBaslat(dosya, 1, geri)
    }

    /**
     * Cok noktali gorev yukler ve baslatir.
     */
    fun gorevYukle(
        noktalar: List<KmzUretici.Nokta>,
        hiz: Double,
        geri: (Boolean, String) -> Unit
    ) {
        val dosya = KmzUretici.uret(
            dizin, "goktungu_gorev", noktalar, hiz,
            KmzUretici.BitisEylemi.BEKLE
        )
        if (dosya == null) {
            geri(false, "gorev dosyasi uretilemedi")
            return
        }
        yukleVeBaslat(dosya, noktalar.size, geri)
    }

    private fun yukleVeBaslat(
        dosya: File,
        noktaSayisi: Int,
        geri: (Boolean, String) -> Unit
    ) {
        val ad = dosya.nameWithoutExtension
        yuklemeBildir(0, noktaSayisi, "basladi", "")
        try {
            wm.pushKMZFileToAircraft(dosya.absolutePath,
                object : CommonCallbacks.CompletionCallbackWithProgress<Double> {
                    override fun onProgressUpdate(oran: Double?) {
                        val o = ((oran ?: 0.0) * noktaSayisi).toInt()
                        yuklemeBildir(o, noktaSayisi, "suruyor", "")
                    }

                    override fun onSuccess() {
                        yuklenmisAd = ad
                        yuklemeBildir(noktaSayisi, noktaSayisi, "tamam", "")
                        Gunluk.basari("GOREV", "KMZ araca yuklendi: $ad")
                        baslat(geri)
                    }

                    override fun onFailure(hata: IDJIError) {
                        val a = hata.description() ?: hata.toString()
                        yuklemeBildir(0, noktaSayisi, "hata", a)
                        Gunluk.hata("GOREV", "KMZ yuklenemedi: $a")
                        geri(false, "gorev yuklenemedi: $a")
                    }
                })
        } catch (e: Exception) {
            yuklemeBildir(0, noktaSayisi, "hata", e.message ?: "istisna")
            geri(false, "gorev yuklenemedi: ${e.message}")
        }
    }

    fun baslat(geri: (Boolean, String) -> Unit) {
        val ad = yuklenmisAd
        if (ad == null) {
            geri(false, "araca yuklenmis gorev yok")
            return
        }
        try {
            wm.startMission(ad, object : CommonCallbacks.CompletionCallback {
                override fun onSuccess() {
                    Gunluk.basari("GOREV", "Gorev basladi: $ad")
                    durumBildir("basladi", 0)
                    geri(true, "gorev basladi")
                }

                override fun onFailure(hata: IDJIError) {
                    val a = hata.description() ?: hata.toString()
                    Gunluk.hata("GOREV", "Gorev baslatilamadi: $a")
                    durumBildir("hata", 0)
                    geri(false, "gorev baslatilamadi: $a")
                }
            })
        } catch (e: Exception) {
            geri(false, "gorev baslatilamadi: ${e.message}")
        }
    }

    fun durdur(geri: (Boolean, String) -> Unit) {
        val ad = yuklenmisAd
        if (ad == null) {
            geri(false, "yurutulen gorev yok")
            return
        }
        try {
            wm.stopMission(ad, basitGeri("gorev durduruldu", geri) {
                durumBildir("durduruldu", 0)
            })
        } catch (e: Exception) {
            geri(false, "gorev durdurulamadi: ${e.message}")
        }
    }

    fun duraklat(geri: (Boolean, String) -> Unit) {
        try {
            wm.pauseMission(basitGeri("gorev duraklatildi", geri) {
                durumBildir("duraklatildi", 0)
            })
        } catch (e: Exception) {
            geri(false, "gorev duraklatilamadi: ${e.message}")
        }
    }

    fun devam(geri: (Boolean, String) -> Unit) {
        try {
            wm.resumeMission(basitGeri("gorev suruyor", geri) {
                durumBildir("suruyor", 0)
            })
        } catch (e: Exception) {
            geri(false, "gorev surdurulemedi: ${e.message}")
        }
    }

    private fun basitGeri(
        basariMesaji: String,
        geri: (Boolean, String) -> Unit,
        basaridaYap: () -> Unit
    ) = object : CommonCallbacks.CompletionCallback {
        override fun onSuccess() {
            Gunluk.basari("GOREV", basariMesaji)
            basaridaYap()
            geri(true, basariMesaji)
        }

        override fun onFailure(hata: IDJIError) {
            val a = hata.description() ?: hata.toString()
            Gunluk.hata("GOREV", "$basariMesaji basarisiz: $a")
            geri(false, a)
        }
    }
}
