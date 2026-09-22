package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.betaflight.MspOturumu
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * BETAFLIGHT (MSP) STRATEJISI — SALT-OKUNUR.
 *
 * USB seri (VCP) uzerinden BetaFlight ucus kontrolcusune yalniz izinli
 * MSP v1 sorgulari gonderir ve telemetri OKUR ([MspOturumu]). Hicbir
 * kumanda/ayar yazilmaz. Cozulen telemetri arayuzde gosterilir ve
 * merkeze `servisler` olcumleriyle bildirilir.
 *
 * MSP query/response yereldir; ham byte merkeze role EDILMEZ (aksi
 * merkezin FC'ye MSP yazmasina yol acardi). Bu yuzden `akis_ac` bu
 * strateji icin ret doner: telemetri servis durumundan okunur.
 */
class BetaflightStrateji(
    private val baglam: Context,
    private val usb: UsbSeri
) : KopruStrateji {

    override val tip = KopruTipi.BETAFLIGHT

    private var _ajan: KopruAjan? = null
    override val ajan: KopruAjan? get() = _ajan

    private var oturum: MspOturumu? = null
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
            akisYaz = { _, _ -> },            // salt-okunur: ham yazma yok
            yetenekler = ::yetenekler,
            dronSayisi = { if (oturum?.bagliMi() == true) 1 else 0 },
            nabizEk = {
                JSONObject().put("servisler", servisler()).put("kanallar", JSONArray())
            }
        )
        Gunluk.yaz("BETAFLIGHT", "BetaFlight (MSP) stratejisi kuruldu")
    }

    override fun kuruldu(): Boolean = kuruldu

    override fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("BETAFLIGHT", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        _ajan?.baslat()
        oturumBaslat()
        return true
    }

    /** Ilk uygun USB seri cihazda MSP oturumu acar. */
    private fun oturumBaslat() {
        if (oturum?.calisiyorMu() == true) return
        val cihazlar = usb.cihazlariListele()
        if (cihazlar.isEmpty()) {
            Gunluk.uyari("BETAFLIGHT", "USB seri cihaz yok; kabloyu takip TARA yapin")
            return
        }
        val hedef = cihazlar.firstOrNull { usb.izinVarMi(it) } ?: cihazlar.first()
        val o = MspOturumu(usb, hedef)
        oturum = o
        o.baslat()
    }

    override fun durdur() {
        oturum?.durdur()
        oturum = null
        _ajan?.durdur()
    }

    override fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    override fun bagliMi(): Boolean = _ajan?.bagliMi() == true

    override fun etkinKanalSayi(): Int = if (oturum?.bagliMi() == true) 1 else 0

    override fun kanalOzet(): String {
        val d = oturum?.durum?.value ?: return ""
        return when (d.faz) {
            "bagli" -> "MSP oturumu bagli" + (if (d.fcTuru.isNotBlank()) " · ${d.fcTuru}" else "")
            "baglaniyor" -> "MSP baglaniyor…"
            "hata" -> "MSP: ${d.hata}"
            else -> ""
        }
    }

    override fun aracSatiri(baglam: Context): Pair<String, Int>? {
        val d = oturum?.durum?.value
        return if (d != null && d.faz == "bagli" && d.yanitSayisi > 0) {
            val ad = d.fcTuru.ifBlank { "BetaFlight" } +
                (if (d.fcSurumu.isNotBlank()) " ${d.fcSurumu}" else "")
            baglam.getString(R.string.durum_arac_bagli, ad) to R.color.iyi
        } else {
            baglam.getString(R.string.bf_fc_yok) to R.color.soluk
        }
    }

    override fun telemetriMetni(baglam: Context): String {
        val d = oturum?.durum?.value ?: return baglam.getString(R.string.bf_oturum_yok)
        if (d.faz == "hata") return baglam.getString(R.string.bf_hata, d.hata)
        if (d.faz != "bagli" || d.yanitSayisi == 0L) {
            return baglam.getString(R.string.bf_bekleniyor)
        }
        val yok = baglam.getString(R.string.tel_deger_yok)
        return buildString {
            appendLine(baglam.getString(R.string.bf_salt_okunur))
            appendLine(
                "FC  %s %s".format(
                    d.fcTuru.ifBlank { "?" },
                    if (d.fcSurumu.isNotBlank()) d.fcSurumu else ""
                ).trim()
            )
            if (d.api.isNotBlank()) appendLine("MSP API  ${d.api}")
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_tutum),
                    if (d.rollDeg != null && d.pitchDeg != null) {
                        "roll %.1f°  pitch %.1f°".format(d.rollDeg, d.pitchDeg)
                    } else yok
                )
            )
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_yon),
                    d.headingDeg?.let { "$it°" } ?: yok
                )
            )
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_irtifa),
                    d.irtifaCm?.let { "%.2f m".format(it / 100.0) } ?: yok
                )
            )
            append(
                "%s  %s".format(
                    baglam.getString(R.string.tel_batarya),
                    if (d.gerilimV != null) {
                        "%.2f V%s".format(
                            d.gerilimV,
                            d.hucreSayisi?.let { " · ${it}S" } ?: ""
                        )
                    } else yok
                )
            )
        }
    }

    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", "kopru")
        .put("platform", "android")
        .put("kopru_tipi", tip.id)
        .put("msp", true)
        .put("salt_okunur", true)
        .put("servis", true)
        .put("konsol", true)
        .put("telemetri", true)

    private fun servisler(): JSONArray {
        val d = oturum?.durum?.value
        val olcumler = JSONObject()
            .put("msp_bagli", oturum?.bagliMi() == true)
            .put("fc_turu", d?.fcTuru ?: "")
            .put("fc_surumu", d?.fcSurumu ?: "")
            .put("msp_api", d?.api ?: "")
            .put("yanit_sayisi", d?.yanitSayisi ?: 0)
            .put("hatali_checksum", d?.hataliChecksum ?: 0)
            .put("gerilim_v", d?.gerilimV ?: JSONObject.NULL)
        val dron = JSONObject()
            .put("ad", "dron")
            .put("baslik", "Dron Servisi (BetaFlight MSP, salt-okunur)")
            .put("aciklama", "USB seri MSP telemetri okuma")
            .put("calisiyor", calisiyorMu())
            .put("pid", JSONObject.NULL)
            .put("baslama_ts", baslamaTs / 1000.0)
            .put("bitis_ts", JSONObject.NULL)
            .put("cikis_kodu", JSONObject.NULL)
            .put("son_hata", d?.hata ?: "")
            .put("konsol_satir", Gunluk.kayitlar.value.size)
            .put("olcumler", olcumler)
            .put("bilgi", oturum?.bilgiKopyasi() ?: JSONObject())
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
            "dron_sayisi" to { _ ->
                JSONObject().put("sonuc", if (oturum?.bagliMi() == true) 1 else 0)
            },
            "konsol" to { v -> KopruOrtak.konsol(v) },
            "servis_baslat" to { v ->
                if (v.optString("servis") == "dron") {
                    oturumBaslat()
                    JSONObject().put("tamam", true).put("hata", "")
                } else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis")
            },
            "servis_durdur" to { v ->
                if (v.optString("servis") == "dron") {
                    oturum?.durdur()
                    JSONObject().put("tamam", true).put("hata", "")
                } else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis")
            },
            "seri_portlar" to { _ ->
                val portlar = JSONArray()
                usb.portEnvanteri().forEach { p -> portlar.put(JSONObject(p)) }
                JSONObject().put("portlar", portlar)
            },
            "akis_ac" to { _ ->
                // Salt-okunur MSP: ham role kanali ACILMAZ (merkezin FC'ye
                // MSP yazmasini onlemek icin). Telemetri servis durumundan
                // okunur.
                JSONObject().put("tamam", false).put(
                    "hata",
                    "BetaFlight koprusu salt-okunurdur; ham MSP kanali acilmaz. " +
                        "Telemetri servis durumundan okunur."
                )
            },
            "akis_kapat" to { _ -> JSONObject().put("tamam", true).put("vardi", false) },
            "akis_yaz" to { _ -> JSONObject().put("yazilan", 0) },
            "akis_durum" to { _ -> JSONObject().put("kanallar", JSONArray()) },
            "protokol_algila" to { _ ->
                val d = oturum?.durum?.value
                if (d != null && d.faz == "bagli" && d.api.isNotBlank()) {
                    JSONObject().put("tamam", true).put("protokol", "betaflight")
                        .put("kanit", "msp_api_version").put("msp_api", d.api)
                } else {
                    JSONObject().put("tamam", true).put("protokol", "msp")
                        .put("kanit", "BetaFlight MSP koprusu (salt-okunur)")
                }
            }
        )
    }
}
