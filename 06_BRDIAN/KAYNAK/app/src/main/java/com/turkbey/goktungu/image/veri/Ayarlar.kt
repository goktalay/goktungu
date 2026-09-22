package com.turkbey.goktungu.image.veri

import android.content.Context
import android.content.SharedPreferences
import java.util.UUID

/**
 * Kalici uygulama ayarlari (kimlik DISINDA).
 *
 * Kurulum kimligi (API kodundan gelen uid/sir/adres/tur) ayri dosyada
 * durur: `kopru/KopruKimlik.kt`. Burada yalniz tercihler vardir.
 *
 * BRDAND'daki `kopru_tip` alani (cok-kopru secimi) BRDIAN'da yoktur:
 * bu uygulama tek amaclidir (goruntu koprusu). Onun yerine kamera
 * mercek secimi (on/arka) saklanir.
 */
object Ayarlar {

    private const val DOSYA = "goktungu_goruntu_ayar"

    private const val A_CIHAZ = "cihaz_kimlik"
    private const val A_OTO = "oto_baslat"
    private const val A_MERCEK = "mercek"          // "arka" | "on"

    const val MERCEK_ARKA = "arka"
    const val MERCEK_ON = "on"

    data class Deger(
        val cihazKimlik: String,
        val otoBaslat: Boolean,
        val mercek: String
    )

    private fun p(baglam: Context): SharedPreferences =
        baglam.getSharedPreferences(DOSYA, Context.MODE_PRIVATE)

    fun oku(baglam: Context): Deger {
        val s = p(baglam)
        // Cihaz kimligi ilk okumada uretilir ve bir daha degismez;
        // gunlukte kopruyu ayirt etmeye yarar.
        var cihaz = s.getString(A_CIHAZ, "") ?: ""
        if (cihaz.isBlank()) {
            cihaz = "IMG-" + UUID.randomUUID().toString()
                .replace("-", "").take(10).uppercase()
            s.edit().putString(A_CIHAZ, cihaz).apply()
        }
        return Deger(
            cihazKimlik = cihaz,
            otoBaslat = s.getBoolean(A_OTO, true),
            mercek = s.getString(A_MERCEK, MERCEK_ARKA) ?: MERCEK_ARKA
        )
    }

    fun otoBaslatYaz(baglam: Context, deger: Boolean) {
        p(baglam).edit().putBoolean(A_OTO, deger).apply()
    }

    fun mercekYaz(baglam: Context, mercek: String) {
        p(baglam).edit().putString(A_MERCEK, mercek).apply()
    }
}
