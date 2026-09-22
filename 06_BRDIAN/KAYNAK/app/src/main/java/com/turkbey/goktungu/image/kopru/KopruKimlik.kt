package com.turkbey.goktungu.image.kopru

import android.content.Context
import android.content.SharedPreferences

/**
 * Kopru kurulum kimligi (API kodundan yazilir).
 *
 * Masaustu koprunun `kimlik.json` + `ayar.json` ciftinin karsiligi:
 * kurulum kimligi, sir, merkez adresi ve secim turu tek yerde durur.
 *
 * ## Sir cihazda tutulur
 *
 * `gizli` merkezle el sikismada her baglantida gonderilir; kaybolursa
 * merkezdeki kayit ancak "Kodu yenile" ile canlanir. Uygulama ozel
 * depolamasinda (`MODE_PRIVATE`) tutulur ve `allowBackup=false`
 * oldugu icin bulut yedegine gitmez. Sifre DEGILDIR (kullaniciya ait
 * bir parola saklanmaz); kaybi yalniz yeniden eslestirme gerektirir.
 */
object KopruKimlik {

    private const val DOSYA = "goktungu_kopru_kimlik"
    private const val A_UID = "kurulum_uid"
    private const val A_GIZLI = "gizli"
    private const val A_ADRES = "merkez_adres"
    private const val A_HTTP = "merkez_http"
    private const val A_AD = "ad"
    private const val A_ORNEK = "ornek_id"
    private const val A_TUR = "tur"
    private const val A_TS = "kurulum_ts"

    data class Deger(
        val kurulumUid: String,
        val gizli: String,
        val merkezAdres: String,
        val merkezHttp: String,
        val ad: String,
        val ornekId: Int,
        val tur: String,
        val kurulumTs: Long
    ) {
        fun eksiksizMi(): Boolean =
            kurulumUid.isNotBlank() && gizli.isNotBlank() && merkezAdres.isNotBlank()

        fun turEtiketi(): String = if (tur == "grcoff") "GRCOFF" else "GRCON"
    }

    private fun p(baglam: Context): SharedPreferences =
        baglam.getSharedPreferences(DOSYA, Context.MODE_PRIVATE)

    fun oku(baglam: Context): Deger? {
        val s = p(baglam)
        val uid = s.getString(A_UID, "") ?: ""
        if (uid.isBlank()) return null
        return Deger(
            kurulumUid = uid,
            gizli = s.getString(A_GIZLI, "") ?: "",
            merkezAdres = s.getString(A_ADRES, "") ?: "",
            merkezHttp = s.getString(A_HTTP, "") ?: "",
            ad = s.getString(A_AD, "") ?: "",
            ornekId = s.getInt(A_ORNEK, 0),
            tur = s.getString(A_TUR, "") ?: "",
            kurulumTs = s.getLong(A_TS, 0L)
        )
    }

    fun var_(baglam: Context): Boolean = oku(baglam)?.eksiksizMi() == true

    fun yaz(baglam: Context, kod: KimlikKodu.ApiKod, secim: String) {
        p(baglam).edit()
            .putString(A_UID, kod.kurulumUid)
            .putString(A_GIZLI, kod.gizli)
            .putString(A_ADRES, kod.merkezAdres)
            .putString(A_HTTP, kod.merkezHttp)
            .putString(A_AD, kod.ad)
            .putInt(A_ORNEK, kod.ornekId)
            .putString(A_TUR, kod.tur.ifBlank { secim })
            .putLong(A_TS, System.currentTimeMillis())
            .apply()
    }

    fun sil(baglam: Context) {
        p(baglam).edit().clear().apply()
    }
}
