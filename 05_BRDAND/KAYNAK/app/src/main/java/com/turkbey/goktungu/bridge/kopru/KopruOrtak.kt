package com.turkbey.goktungu.bridge.kopru

import android.os.Build
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * Kopru stratejilerinin paylastigi merkez-protokolu yardimci parcalari.
 *
 * `sistem_bilgi` ve `konsol` gibi islevlerin yaniti kopru tipinden
 * BAGIMSIZDIR (merkez `kopru/uygulama.py::_ajan_islevleri` ile ayni
 * bicim). Tekrari onlemek icin burada tek yerde uretilir.
 */
object KopruOrtak {

    fun makineAdi(): String = (Build.MANUFACTURER + " " + Build.MODEL).trim()

    fun platform(): String = "android-" + Build.VERSION.RELEASE

    fun sistemBilgi(baslamaTs: Long): JSONObject = JSONObject()
        .put("surum", BuildConfig.VERSION_NAME)
        .put("platform", platform())
        .put("makine_adi", makineAdi())
        .put("urun", "kopru")
        .put("calisma_sn", (System.currentTimeMillis() - baslamaTs) / 1000)
        .put("panel_port", JSONObject.NULL)

    /** `konsol` islevi: `dron` servisinin gunluk satirlarini doner. */
    fun konsol(v: JSONObject): JSONObject {
        val ad = v.optString("servis")
        if (ad != "dron") return JSONObject().put("hata", "Bilinmeyen servis: $ad")
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
        return JSONObject().put("servis", "dron").put("satirlar", satirlar)
    }
}
