package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.dji.DjiKopru

/**
 * DJI MOBILE SDK STRATEJISI (Faz 2 baglamasi).
 *
 * Faz 1'de gommeli olarak eklenen [DjiKopruCekirdegi] artik arayuzden
 * (sol menu → "DJI Mobile SDK") tetiklenir. Bu strateji cekirdege ince
 * bir sarmalayicidir: `kur()` MSDK'yi baslatir (ancak burada, secilene
 * kadar MSDK BASLAMAZ; mevcut MAVLink davranisi korunur), `baslat()`
 * ajani ve telemetri dongusunu calistirir.
 *
 * DJI UX SDK kullanilmaz; yalniz MSDK v5 cekirdegi.
 */
class DjiStrateji(private val baglam: Context) : KopruStrateji {

    override val tip = KopruTipi.DJI

    override val ajan: KopruAjan? get() = DjiKopruCekirdegi.ajan

    override fun kur(baglam: Context) = DjiKopruCekirdegi.kur(baglam)

    override fun kuruldu(): Boolean = DjiKopruCekirdegi.kuruldu()

    override fun baslat(): Boolean {
        DjiKopruCekirdegi.kur(baglam)
        return DjiKopruCekirdegi.baslat()
    }

    override fun durdur() = DjiKopruCekirdegi.durdur()

    override fun calisiyorMu(): Boolean = DjiKopruCekirdegi.calisiyorMu()

    override fun bagliMi(): Boolean = DjiKopruCekirdegi.ajan?.bagliMi() == true

    override fun etkinKanalSayi(): Int = DjiKopruCekirdegi.kanallar?.etkinSayi() ?: 0

    override fun kanalOzet(): String {
        val n = etkinKanalSayi()
        return if (n > 0) "DJI GDP oturumu acik" else ""
    }

    override fun aracSatiri(baglam: Context): Pair<String, Int>? {
        val d = DjiKopruCekirdegi.dji
        return if (d != null && d.urunBagli.value) {
            baglam.getString(R.string.durum_arac_bagli, d.urunModeli()) to R.color.iyi
        } else {
            baglam.getString(R.string.dji_arac_yok) to R.color.soluk
        }
    }

    override fun telemetriMetni(baglam: Context): String {
        val d = DjiKopruCekirdegi.dji
            ?: return baglam.getString(R.string.dji_msdk_baslamadi)
        val yok = baglam.getString(R.string.tel_deger_yok)
        val kayit = when (d.kayit.value) {
            DjiKopru.KayitDurum.KAYITLI -> baglam.getString(R.string.dji_kayit_ok)
            DjiKopru.KayitDurum.BASLIYOR -> baglam.getString(R.string.dji_kayit_basliyor)
            DjiKopru.KayitDurum.HATA ->
                baglam.getString(R.string.dji_kayit_hata, d.kayitHata.value)
            else -> baglam.getString(R.string.dji_kayit_yok)
        }
        val t = d.telemetri.value
        return buildString {
            appendLine(kayit)
            val konum = t.konum
            if (konum == null) {
                appendLine(baglam.getString(R.string.tel_konum_yok))
            } else {
                appendLine(
                    "%s  %.6f, %.6f".format(
                        baglam.getString(R.string.tel_konum), konum.enlem, konum.boylam
                    )
                )
            }
            appendLine("%s  %.1f m".format(baglam.getString(R.string.tel_irtifa), t.altRel))
            appendLine("%s  %.0f".format(baglam.getString(R.string.tel_yon), t.heading))
            appendLine(
                "%s  %d%%  %.1f V".format(
                    baglam.getString(R.string.tel_batarya), t.bataryaPct, t.bataryaV
                )
            )
            append(
                "%s  %s".format(
                    baglam.getString(R.string.tel_mod), t.mod.ifBlank { yok }
                )
            )
        }
    }
}
