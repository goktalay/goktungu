package com.turkbey.goktungu.image.kopru

import android.util.Base64
import org.json.JSONObject

/**
 * API kodu cozumu (GTK1.<base64url(JSON)>).
 *
 * Kod, merkezin (GRCON) ya da yerel Merkez Uygulamasinin (GRCOFF)
 * "Destek > Kopruler" panelinde uretilir ve koprunun baglanmak icin
 * bilmesi gereken HER SEYI tasir: kurulum kimligi (u), sir (g), merkez
 * WebSocket adresi (m), istege bagli HTTP adresi (h), kayit adi (a),
 * ornek kimligi (o) ve hedef turu (t: "grcon" | "grcoff").
 *
 * Masaustu kopru (`kopru/kimlik_kodu.py`) ile AYNI sozlesme; iki
 * cozucu ayrismasin diye alan adlari ve dogrulama kurallari birebir
 * korunur.
 */
object KimlikKodu {

    const val ONEK = "GTK1."

    data class ApiKod(
        val kurulumUid: String,
        val gizli: String,
        val merkezAdres: String,
        val merkezHttp: String,
        val ad: String,
        val ornekId: Int,
        val tur: String,
        /** Kaydin urunu: "kopru" (saha koprusu) ya da "gcs" (Merkezi Yazilim / GRCOFF). */
        val urun: String
    )

    sealed class Sonuc {
        data class Gecerli(val kod: ApiKod) : Sonuc()
        data class Gecersiz(val neden: String) : Sonuc()
    }

    fun coz(ham: String?): Sonuc {
        val kod = (ham ?: "").filterNot { it.isWhitespace() }
        if (kod.isEmpty()) return Sonuc.Gecersiz("API kodu bos")
        if (!kod.startsWith(ONEK)) {
            return Sonuc.Gecersiz("API kodu '$ONEK' ile baslamali")
        }
        var govde = kod.substring(ONEK.length)
        val eksik = (4 - govde.length % 4) % 4
        govde += "=".repeat(eksik)
        val d = try {
            val bayt = Base64.decode(govde, Base64.URL_SAFE or Base64.NO_WRAP)
            JSONObject(String(bayt, Charsets.UTF_8))
        } catch (e: Exception) {
            return Sonuc.Gecersiz("API kodu cozulemedi (eksik veya bozuk kopyalanmis)")
        }
        val u = d.optString("u")
        val g = d.optString("g")
        val m = d.optString("m")
        if (u.isBlank() || g.isBlank() || m.isBlank()) {
            return Sonuc.Gecersiz("API kodu eksik alan iceriyor")
        }
        if (!(m.startsWith("ws://") || m.startsWith("wss://"))) {
            return Sonuc.Gecersiz("API kodundaki merkez adresi ws:// veya wss:// olmali")
        }
        val h = d.optString("h")
        if (h.isNotBlank() && !(h.startsWith("http://") || h.startsWith("https://"))) {
            return Sonuc.Gecersiz("API kodundaki HTTP adresi http(s):// olmali")
        }
        val urun = d.optString("p", "kopru")
        if (urun.isNotBlank() && urun != "kopru") {
            return Sonuc.Gecersiz(
                "Bu API kodu bir kopru kaydina degil '$urun' kaydina ait " +
                    "(Merkezi Yazilim kodu koprude kullanilamaz)"
            )
        }
        return Sonuc.Gecerli(
            ApiKod(
                kurulumUid = u,
                gizli = g,
                merkezAdres = m,
                merkezHttp = h,
                ad = d.optString("a"),
                ornekId = d.optInt("o", 0),
                tur = d.optString("t"),
                urun = urun.ifBlank { "kopru" }
            )
        )
    }
}
