package com.turkbey.goktungu.veri

import android.content.Context
import android.content.SharedPreferences
import java.util.UUID

/**
 * Kalici ayarlar.
 *
 * ## Kimlik bilgisi saklama
 *
 * Kullanici adi saklanir, **sifre saklanmaz**.  Merkezden alinan oturum
 * belirteci (token) saklanir; boylece uygulama her acilista sifre
 * sormadan baglanabilir ama sifre cihazda durmaz.
 *
 * `EncryptedSharedPreferences` kullanilmadi cunku saklanan tek hassas
 * deger belirtec ve o da merkezde sureli.  Bu karar bilincli olarak
 * belgelenmistir; sifre saklanmaya baslanirsa sifreleme ZORUNLU olur.
 */
object Ayarlar {

    private const val DOSYA = "goktungu_ayar"

    private const val A_SUNUCU = "sunucu"
    private const val A_PORT = "port"
    private const val A_TLS = "tls"
    private const val A_KULLANICI = "kullanici"
    private const val A_BELIRTEC = "belirtec"
    private const val A_CIHAZ = "cihaz_kimlik"
    private const val A_OTO = "oto_baglan"

    /** Sunucu tarafi `dji_kopru.py` varsayilan dinleme portu. */
    const val VARSAYILAN_PORT = 8790

    data class Deger(
        val sunucu: String,
        val port: Int,
        val tls: Boolean,
        val kullanici: String,
        val belirtec: String,
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
        // arac seri numarasi okunamadiginda sysid esleme dayanagi olur.
        var cihaz = s.getString(A_CIHAZ, "") ?: ""
        if (cihaz.isBlank()) {
            cihaz = "AND-" + UUID.randomUUID().toString()
                .replace("-", "").take(10).uppercase()
            s.edit().putString(A_CIHAZ, cihaz).apply()
        }
        return Deger(
            sunucu = s.getString(A_SUNUCU, "") ?: "",
            port = s.getInt(A_PORT, VARSAYILAN_PORT),
            tls = s.getBoolean(A_TLS, false),
            kullanici = s.getString(A_KULLANICI, "") ?: "",
            belirtec = s.getString(A_BELIRTEC, "") ?: "",
            cihazKimlik = cihaz,
            otoBaglan = s.getBoolean(A_OTO, false)
        )
    }

    fun yaz(
        baglam: Context,
        sunucu: String,
        port: Int,
        tls: Boolean,
        kullanici: String,
        otoBaglan: Boolean
    ) {
        p(baglam).edit()
            .putString(A_SUNUCU, sunucu.trim())
            .putInt(A_PORT, port)
            .putBoolean(A_TLS, tls)
            .putString(A_KULLANICI, kullanici.trim())
            .putBoolean(A_OTO, otoBaglan)
            .apply()
    }

    fun belirtecYaz(baglam: Context, belirtec: String) {
        p(baglam).edit().putString(A_BELIRTEC, belirtec).apply()
    }

    fun belirtecSil(baglam: Context) {
        p(baglam).edit().remove(A_BELIRTEC).apply()
    }
}
