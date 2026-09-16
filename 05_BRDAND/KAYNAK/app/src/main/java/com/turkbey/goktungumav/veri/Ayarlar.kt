package com.turkbey.goktungumav.veri

import android.content.Context
import android.content.SharedPreferences
import java.util.UUID

/**
 * Kalici ayarlar.
 *
 * ## Neden kimlik bilgisi saklanmiyor
 *
 * DJI koprusu GDP el sikismasi yaptigi icin kullanici adi ve oturum
 * belirteci saklardi.  MAVLink koprusu **seffaf borudur**: uygulama
 * duzeyinde oturum acmaz, yalnizca MAVLink cercevelerini tasir.
 * Erisim denetimi ag katmaninda saglanir (yalniz ozel ag adreslerine
 * gonderim; bkz. [AgKisiti]).
 *
 * Bu yuzden burada saklanan hicbir hassas deger yoktur ve
 * `EncryptedSharedPreferences` gerekmez.  Sifre veya belirtec
 * saklanmaya baslanirsa sifreleme ZORUNLU olur.
 */
object Ayarlar {

    private const val DOSYA = "goktungumav_ayar"

    private const val A_SUNUCU = "sunucu"
    private const val A_PORT = "port"
    private const val A_HIZ = "hiz"
    private const val A_CIHAZ = "cihaz_kimlik"
    private const val A_OTO = "oto_baglan"

    /**
     * `mavutil` varsayilan MAVLink UDP portu.  Merkezdeki `udp` turu
     * baglanti kaydinin `port` alani bu degeri tasir.
     */
    const val VARSAYILAN_PORT = 14550

    /** ArduPilot USB dogrudan baglantida 115200 kullanir. */
    const val VARSAYILAN_HIZ = 115200

    data class Deger(
        val sunucu: String,
        val port: Int,
        val hiz: Int,
        val cihazKimlik: String,
        val otoBaglan: Boolean
    ) {
        /** Baglanmak icin yeterli bilgi var mi. */
        fun eksiksizMi(): Boolean =
            sunucu.isNotBlank() && port in 1..65535
    }

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
            sunucu = s.getString(A_SUNUCU, "") ?: "",
            port = s.getInt(A_PORT, VARSAYILAN_PORT),
            hiz = s.getInt(A_HIZ, VARSAYILAN_HIZ),
            cihazKimlik = cihaz,
            otoBaglan = s.getBoolean(A_OTO, false)
        )
    }

    fun yaz(
        baglam: Context,
        sunucu: String,
        port: Int,
        hiz: Int,
        otoBaglan: Boolean
    ) {
        p(baglam).edit()
            .putString(A_SUNUCU, sunucu.trim())
            .putInt(A_PORT, port)
            .putInt(A_HIZ, hiz)
            .putBoolean(A_OTO, otoBaglan)
            .apply()
    }
}
