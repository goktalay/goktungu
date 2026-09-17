package com.turkbey.goktungu.veri

import android.content.Context
import android.content.SharedPreferences
import java.util.UUID

/**
 * Kalici uygulama ayarlari (kimlik DISINDA).
 *
 * 1.1.0: sunucu adresi, port, e-posta ve belirtec alanlari KALKTI.
 * Kimlik ve merkez adresi API kodundan gelir (`kopru/KopruKimlik.kt`);
 * belirtec gerekmez cunku kopru el sikismasi kimligi zaten dogrular ve
 * DJI GDP oturumu merkezde 127.0.0.1 uzerinden acilir.
 */
object Ayarlar {

    private const val DOSYA = "goktungu_ayar"

    private const val A_CIHAZ = "cihaz_kimlik"
    private const val A_OTO = "oto_baslat"

    data class Deger(
        val cihazKimlik: String,
        val otoBaslat: Boolean
    )

    private fun p(baglam: Context): SharedPreferences =
        baglam.getSharedPreferences(DOSYA, Context.MODE_PRIVATE)

    fun oku(baglam: Context): Deger {
        val s = p(baglam)
        // Cihaz kimligi ilk okumada uretilir ve bir daha degismez; arac
        // seri numarasi okunamadiginda sysid esleme dayanagi olur.
        var cihaz = s.getString(A_CIHAZ, "") ?: ""
        if (cihaz.isBlank()) {
            cihaz = "AND-" + UUID.randomUUID().toString()
                .replace("-", "").take(10).uppercase()
            s.edit().putString(A_CIHAZ, cihaz).apply()
        }
        return Deger(
            cihazKimlik = cihaz,
            otoBaslat = s.getBoolean(A_OTO, true)
        )
    }

    fun otoBaslatYaz(baglam: Context, deger: Boolean) {
        p(baglam).edit().putBoolean(A_OTO, deger).apply()
    }
}
