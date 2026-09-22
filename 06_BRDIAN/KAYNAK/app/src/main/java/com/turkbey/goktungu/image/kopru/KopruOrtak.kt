package com.turkbey.goktungu.image.kopru

import android.os.Build
import com.turkbey.goktungu.image.BuildConfig
import com.turkbey.goktungu.image.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * Kopru ajaninin paylastigi merkez-protokolu yardimci parcalari.
 *
 * `sistem_bilgi` ve `konsol` gibi islevlerin yaniti merkez
 * `kopru/uygulama.py::_ajan_islevleri` ile ayni bicimdedir; boylece
 * merkez tarafinda (GRCON/GRCOFF) ikinci bir uyarlama gerekmez.
 *
 * BRDAND'dan tek fark: `urun` alani "kopru" degil "goruntu"dur -- bu
 * kayit bir GORUNTU koprusudur.
 */
object KopruOrtak {

    const val URUN = "goruntu"

    fun makineAdi(): String = (Build.MANUFACTURER + " " + Build.MODEL).trim()

    fun platform(): String = "android-" + Build.VERSION.RELEASE

    fun sistemBilgi(baslamaTs: Long): JSONObject = JSONObject()
        .put("surum", BuildConfig.VERSION_NAME)
        .put("platform", platform())
        .put("makine_adi", makineAdi())
        .put("urun", URUN)
        .put("calisma_sn", (System.currentTimeMillis() - baslamaTs) / 1000)
        .put("panel_port", JSONObject.NULL)

    /** `konsol` islevi: `goruntu` servisinin gunluk satirlarini doner. */
    fun konsol(v: JSONObject): JSONObject {
        val ad = v.optString("servis")
        if (ad != "goruntu" && ad != "dron") {
            return JSONObject().put("hata", "Bilinmeyen servis: $ad")
        }
        val sonrasi = v.optInt("sonrasi", 0)
        val satirlar = JSONArray()
        Gunluk.kayitlar.value.forEachIndexed { i, s ->
            val no = i + 1
            if (no > sonrasi) {
                satirlar.put(
                    JSONObject()
                        .put("no", no)
                        .put("ts", s.zaman / 1000.0)
                        .put("kaynak", s.etiket)
                        .put("metin", "[${s.etiket}] ${s.ileti}")
                )
            }
        }
        return JSONObject().put("servis", ad).put("satirlar", satirlar)
    }
}
