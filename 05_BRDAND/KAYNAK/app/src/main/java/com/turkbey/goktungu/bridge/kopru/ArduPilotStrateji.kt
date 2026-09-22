package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import android.util.Base64
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.mavlink.MavGozlemci
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * ARDUPILOT (MAVLink) STRATEJISI.
 *
 * BRDAND'in 1.1.x MAVLink yolunun BIREBIR karsiligidir: USB seri
 * cihazlardan gecen ham MAVLink cerceveleri merkeze [KopruAjan] `akis`
 * kanallariyla tasinir. Faz 2'de bu mantik [KopruYonetici] icinden
 * cikarilip stratejiye alindi; davranis DEGISMEDI (regresyon yok).
 *
 * `usb` ve `gozlemci` [KopruYonetici] tarafindan sahiplenip paylasilir:
 * ayni USB cihazi ayni anda yalniz bir strateji acabilir ve arayuz
 * cihaz taramasi icin tek bir [UsbSeri] ornegi gormelidir.
 */
class ArduPilotStrateji(
    private val baglam: Context,
    private val usb: UsbSeri,
    private val gozlemci: MavGozlemci
) : KopruStrateji {

    override val tip = KopruTipi.ARDUPILOT

    private var _kanallar: AkisKanallari? = null
    val kanallar: AkisKanallari? get() = _kanallar

    private var _ajan: KopruAjan? = null
    override val ajan: KopruAjan? get() = _ajan

    private val baslamaTs = System.currentTimeMillis()

    @Volatile
    private var kuruldu = false

    override fun kur(baglam: Context) {
        if (kuruldu) return
        kuruldu = true
        val k = AkisKanallari(
            usb = usb,
            gonder = { kid, v -> _ajan?.akisGonder(kid, v) ?: false },
            gozlemci = gozlemci
        )
        _kanallar = k
        _ajan = KopruAjan(
            kimlikOku = { KopruKimlik.oku(baglam) },
            surum = BuildConfig.VERSION_NAME,
            platform = KopruOrtak.platform(),
            makineAdi = KopruOrtak.makineAdi(),
            islevler = islevler(k, usb),
            akisYaz = { kid, v -> k.yaz(kid, v) },
            yetenekler = ::yetenekler,
            dronSayisi = { k.temizleOlu(); k.etkinSayi() },
            nabizEk = {
                JSONObject()
                    .put("servisler", servisler(k, usb))
                    .put("kanallar", k.durum())
            }
        )
        Gunluk.yaz("KOPRU", "ArduPilot (MAVLink) stratejisi kuruldu")
    }

    override fun kuruldu(): Boolean = kuruldu

    override fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("KOPRU", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        _ajan?.baslat()
        return true
    }

    override fun durdur() {
        _ajan?.durdur()
        _kanallar?.tumunuKapat()
        gozlemci.sifirla()
    }

    override fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    override fun bagliMi(): Boolean = _ajan?.bagliMi() == true

    override fun etkinKanalSayi(): Int = _kanallar?.etkinSayi() ?: 0

    override fun kanalOzet(): String = _kanallar?.ozet() ?: ""

    override fun aracSatiri(baglam: Context): Pair<String, Int>? {
        val t = gozlemci.durum.value
        return if (t.aracVar) {
            baglam.getString(
                R.string.durum_arac_bagli, "sys ${t.sysid} · ${gozlemci.kipAdi()}"
            ) to R.color.iyi
        } else {
            baglam.getString(R.string.durum_arac_yok) to R.color.soluk
        }
    }

    override fun telemetriMetni(baglam: Context): String {
        val t = gozlemci.durum.value
        val yok = baglam.getString(R.string.tel_deger_yok)
        return buildString {
            val konum = t.konum
            if (konum == null) {
                appendLine(baglam.getString(R.string.tel_konum_yok))
            } else {
                appendLine(
                    "%s  %.6f, %.6f".format(
                        baglam.getString(R.string.tel_konum), konum.enlem, konum.boylam
                    )
                )
            }
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_irtifa),
                    t.altRel?.let { "%.1f m".format(it) } ?: yok
                )
            )
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_yon),
                    t.heading?.let { "%.0f".format(it) } ?: yok
                )
            )
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_batarya),
                    if (t.bataryaPct != null || t.bataryaV != null) {
                        "%s  %s".format(
                            t.bataryaPct?.let { "$it%" } ?: "-",
                            t.bataryaV?.let { "%.1f V".format(it) } ?: "-"
                        )
                    } else yok
                )
            )
            appendLine(
                "%s  %s".format(
                    baglam.getString(R.string.tel_arm),
                    baglam.getString(
                        if (t.armed) R.string.tel_arm_acik else R.string.tel_arm_kapali
                    )
                )
            )
            append(
                "%s  %s".format(
                    baglam.getString(R.string.tel_mod),
                    gozlemci.kipAdi().ifEmpty { yok }
                )
            )
        }
    }

    // ------------------------------------------------------------------
    // Merkezin gordugu bilgiler (1.1.x ile AYNI)
    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", "kopru")
        .put("platform", "android")
        .put("kopru_tipi", tip.id)
        .put("mavlink", true)
        .put("servis", true)
        .put("konsol", true)
        .put("telemetri", false)

    private fun servisler(k: AkisKanallari, u: UsbSeri): JSONArray {
        val portSayisi = runCatching { u.cihazlariListele().size }.getOrDefault(0)
        val dron = JSONObject()
            .put("ad", "dron")
            .put("baslik", "Dron Servisi (Android MAVLink)")
            .put("aciklama", "USB seri / UDP / TCP MAVLink akisi")
            .put("calisiyor", calisiyorMu())
            .put("pid", JSONObject.NULL)
            .put("baslama_ts", baslamaTs / 1000.0)
            .put("bitis_ts", JSONObject.NULL)
            .put("cikis_kodu", JSONObject.NULL)
            .put("son_hata", _ajan?.sonHata?.value ?: "")
            .put("konsol_satir", Gunluk.kayitlar.value.size)
            .put(
                "olcumler",
                JSONObject()
                    .put("seri_port", portSayisi)
                    .put("kanal", k.etkinSayi())
                    .put("etkin_kanal", k.etkinSayi())
            )
            .put("surum", BuildConfig.VERSION_NAME)
        return JSONArray().put(dron)
    }

    private fun islevler(k: AkisKanallari, u: UsbSeri): Map<String, (JSONObject) -> JSONObject> {
        val servisDurum: (JSONObject) -> JSONObject = { _ ->
            JSONObject().put("servisler", servisler(k, u)).put("kanallar", k.durum())
        }
        return mapOf(
            "sistem_bilgi" to { _ -> KopruOrtak.sistemBilgi(baslamaTs) },
            "servis_durum" to servisDurum,
            "durum" to servisDurum,
            "yetenekler" to { _ -> yetenekler() },
            "dron_sayisi" to { _ -> JSONObject().put("sonuc", k.etkinSayi()) },
            "konsol" to { v -> KopruOrtak.konsol(v) },
            "servis_baslat" to { v ->
                val ad = v.optString("servis")
                if (ad == "dron") JSONObject().put("tamam", true).put("hata", "")
                else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis: $ad")
            },
            "servis_durdur" to { v ->
                val ad = v.optString("servis")
                if (ad == "dron") {
                    k.tumunuKapat()
                    JSONObject().put("tamam", true).put("hata", "")
                } else {
                    JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis: $ad")
                }
            },
            "seri_portlar" to { _ ->
                val portlar = JSONArray()
                u.portEnvanteri().forEach { p -> portlar.put(JSONObject(p)) }
                JSONObject().put("portlar", portlar)
            },
            "akis_ac" to { v ->
                val (ozet, hata) = k.ac(
                    v.optInt("kanal_id", 0), v.optJSONObject("tanim") ?: JSONObject()
                )
                if (hata != null) JSONObject().put("tamam", false).put("hata", hata)
                else JSONObject().put("tamam", true).put("kanal", ozet)
            },
            "akis_kapat" to { v ->
                JSONObject().put("tamam", true).put("vardi", k.kapat(v.optInt("kanal_id", 0)))
            },
            "akis_yaz" to { v ->
                val veri = try {
                    Base64.decode(v.optString("veri"), Base64.DEFAULT)
                } catch (e: Exception) {
                    ByteArray(0)
                }
                if (veri.isEmpty()) JSONObject().put("yazilan", 0)
                else JSONObject().put("yazilan", k.yaz(v.optInt("kanal_id", 0), veri))
            },
            "akis_durum" to { _ -> JSONObject().put("kanallar", k.durum()) },
            "protokol_algila" to { _ ->
                JSONObject()
                    .put("tamam", true)
                    .put("protokol", "ardupilot")
                    .put("kanit", "Android MAVLink koprusu: ham MAVLink akisi")
            }
        )
    }
}
