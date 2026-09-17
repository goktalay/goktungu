package com.turkbey.goktungumav.veri

import android.content.Context
import android.content.SharedPreferences
import java.util.UUID

/**
 * Kalici uygulama ayarlari (kimlik DISINDA).
 *
 * Kurulum kimligi (API kodundan gelen uid/sir/adres) ayri dosyada
 * durur: `kopru/KopruKimlik.kt`. Burada yalniz tercihler vardir.
 *
 * 1.1.0: merkez adresi/portu ve hat hizi alanlari KALKTI. Adres API
 * kodunun icinde gelir; hat hizi merkezdeki Baglanti Yoneticisi'nden
 * (`akis_ac` tanimindaki `baud`) belirlenir, telefonda elle secilmez.
 */
object Ayarlar {

    private const val DOSYA = "goktungumav_ayar"

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
        // Cihaz kimligi ilk okumada uretilir ve bir daha degismez;
        // gunlukte kopruyu ayirt etmeye yarar.
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
