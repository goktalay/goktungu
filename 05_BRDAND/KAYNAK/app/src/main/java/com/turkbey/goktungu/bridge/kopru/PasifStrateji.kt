package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * PASIF (ISKELE) STRATEJI — Elektro-Optik telemetri ve Radar.
 *
 * Bu kopru tipleri Faz 2'de SECILEBILIR ve CAGRILABILIR ama backend'i
 * henuz tam entegre DEGILDIR. Iskele: derlenir, ajan merkeze baglanip
 * dogru kopru tipini bildirir ([KopruTipi.yetenek]) fakat veri kaynagi
 * yoktur; arayuz "baglanti bekleniyor / pasif" gosterir. Ileride bu
 * sinifin yerine gercek EO/Radar surucusu gelir; sozlesme (KopruStrateji)
 * ayni kalir, cagri yerleri degismez.
 */
class PasifStrateji(
    private val baglam: Context,
    override val tip: KopruTipi
) : KopruStrateji {

    private var _ajan: KopruAjan? = null
    override val ajan: KopruAjan? get() = _ajan

    private val baslamaTs = System.currentTimeMillis()

    @Volatile
    private var kuruldu = false

    override fun kur(baglam: Context) {
        if (kuruldu) return
        kuruldu = true
        _ajan = KopruAjan(
            kimlikOku = { KopruKimlik.oku(baglam) },
            surum = BuildConfig.VERSION_NAME,
            platform = KopruOrtak.platform(),
            makineAdi = KopruOrtak.makineAdi(),
            islevler = islevler(),
            akisYaz = { _, _ -> },
            yetenekler = ::yetenekler,
            dronSayisi = { 0 },
            nabizEk = {
                JSONObject().put("servisler", servisler()).put("kanallar", JSONArray())
            }
        )
        Gunluk.yaz("KOPRU", "${tip.etiket} (iskele) stratejisi kuruldu")
    }

    override fun kuruldu(): Boolean = kuruldu

    override fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("KOPRU", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        // Ajan baglanir; merkez bu koprunun tipini gorur. Veri yok.
        _ajan?.baslat()
        Gunluk.uyari(
            "KOPRU",
            "${tip.etiket}: backend henuz entegre degil (iskele) — baglanti bekleniyor"
        )
        return true
    }

    override fun durdur() {
        _ajan?.durdur()
    }

    override fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    override fun bagliMi(): Boolean = _ajan?.bagliMi() == true

    override fun etkinKanalSayi(): Int = 0

    override fun kanalOzet(): String = ""

    override fun aracSatiri(baglam: Context): Pair<String, Int>? =
        baglam.getString(R.string.iskele_pasif) to R.color.uyari

    override fun telemetriMetni(baglam: Context): String =
        baglam.getString(R.string.iskele_govde, tip.etiket)

    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", "kopru")
        .put("platform", "android")
        .put("kopru_tipi", tip.id)
        .put(tip.yetenek, true)
        .put("hazir", false)
        .put("servis", true)
        .put("telemetri", false)

    private fun servisler(): JSONArray {
        val dron = JSONObject()
            .put("ad", "dron")
            .put("baslik", "${tip.etiket} (iskele)")
            .put("aciklama", "Backend henuz entegre degil; baglanti bekleniyor")
            .put("calisiyor", false)
            .put("pid", JSONObject.NULL)
            .put("baslama_ts", baslamaTs / 1000.0)
            .put("bitis_ts", JSONObject.NULL)
            .put("cikis_kodu", JSONObject.NULL)
            .put("son_hata", "pasif (iskele)")
            .put("konsol_satir", Gunluk.kayitlar.value.size)
            .put("olcumler", JSONObject().put("hazir", false))
            .put("surum", BuildConfig.VERSION_NAME)
        return JSONArray().put(dron)
    }

    private fun islevler(): Map<String, (JSONObject) -> JSONObject> {
        val servisDurum: (JSONObject) -> JSONObject = { _ ->
            JSONObject().put("servisler", servisler()).put("kanallar", JSONArray())
        }
        return mapOf(
            "sistem_bilgi" to { _ -> KopruOrtak.sistemBilgi(baslamaTs) },
            "servis_durum" to servisDurum,
            "durum" to servisDurum,
            "yetenekler" to { _ -> yetenekler() },
            "dron_sayisi" to { _ -> JSONObject().put("sonuc", 0) },
            "konsol" to { v -> KopruOrtak.konsol(v) },
            "seri_portlar" to { _ -> JSONObject().put("portlar", JSONArray()) },
            "akis_ac" to { _ ->
                JSONObject().put("tamam", false).put(
                    "hata", "${tip.etiket} kopru tipi henuz entegre degil (iskele)."
                )
            },
            "akis_kapat" to { _ -> JSONObject().put("tamam", true).put("vardi", false) },
            "akis_yaz" to { _ -> JSONObject().put("yazilan", 0) },
            "akis_durum" to { _ -> JSONObject().put("kanallar", JSONArray()) }
        )
    }
}
