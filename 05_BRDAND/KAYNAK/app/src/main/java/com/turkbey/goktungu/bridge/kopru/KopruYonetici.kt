package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import android.os.Build
import android.util.Base64
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.mavlink.MavGozlemci
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Gunluk
import org.json.JSONArray
import org.json.JSONObject

/**
 * Kopru cekirdegine tek erisim noktasi (1.1.0: GERCEK KOPRU AJANI).
 *
 * ## Mimari degisiklik (kullanici karari, 2026-09-17)
 *
 * 1.0.x seffaf UDP boruydu: telefon MAVLink cercevelerini girilen IP'nin
 * 14550 portuna atiyordu. Bu, merkezin (GRCON) "kopru disinda dogrudan
 * baglanti olamaz" kuraliyla bagdasmiyordu ve NAT arkasindan calismiyordu.
 *
 * 1.1.0 ile telefon masaustu kopruyle AYNI ajan protokolunu konusur:
 * merkeze API koduyla eslesir, ters WebSocket acar, `seri_portlar` ile
 * USB cihazlarini bildirir ve merkezin Baglanti Yoneticisi `akis_ac`
 * dediginde kanali acip ham byte'i role uzerinden tasir. Merkezdeki
 * "Destek > Kopruler" panelinde telefon bir kopru olarak, "Dron"
 * servisi cevrimici gorunur.
 *
 * ## Neden tek ornek
 *
 * USB cihazi ayni anda yalniz bir kez acilabilir ve on plan hizmeti ile
 * arayuz AYNI ajani gormelidir.
 */
object KopruYonetici {

    private lateinit var baglam: Context

    private var _usb: UsbSeri? = null
    val usb: UsbSeri? get() = _usb

    val gozlemci = MavGozlemci()

    private var _kanallar: AkisKanallari? = null
    val kanallar: AkisKanallari? get() = _kanallar

    private var _ajan: KopruAjan? = null
    val ajan: KopruAjan? get() = _ajan

    private val baslamaTs = System.currentTimeMillis()

    @Volatile
    private var kuruldu = false

    /** Uygulama acilisinda bir kez cagrilir. */
    fun kur(b: Context) {
        if (kuruldu) return
        kuruldu = true
        baglam = b.applicationContext
        val u = UsbSeri(baglam)
        _usb = u
        val k = AkisKanallari(
            usb = u,
            gonder = { kid, v -> _ajan?.akisGonder(kid, v) ?: false },
            gozlemci = gozlemci
        )
        _kanallar = k
        _ajan = KopruAjan(
            kimlikOku = { KopruKimlik.oku(baglam) },
            surum = BuildConfig.VERSION_NAME,
            platform = "android-" + Build.VERSION.RELEASE,
            makineAdi = (Build.MANUFACTURER + " " + Build.MODEL).trim(),
            islevler = islevler(k, u),
            akisYaz = { kid, v -> k.yaz(kid, v) },
            yetenekler = ::yetenekler,
            dronSayisi = { k.temizleOlu(); k.etkinSayi() },
            nabizEk = {
                JSONObject()
                    .put("servisler", servisler(k, u))
                    .put("kanallar", k.durum())
            }
        )
        Gunluk.yaz("KOPRU", "Kopru cekirdegi kuruldu (ajan 1.1.0)")
    }

    /** Ajani baslatir; kimlik yoksa `false` doner. */
    fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("KOPRU", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        _ajan?.baslat()
        return true
    }

    fun durdur() {
        _ajan?.durdur()
        _kanallar?.tumunuKapat()
        gozlemci.sifirla()
    }

    fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    fun bagliMi(): Boolean = _ajan?.bagliMi() == true

    // ------------------------------------------------------------------
    // Merkezin gordugu bilgiler
    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", "kopru")
        .put("platform", "android")
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

    private fun sistemBilgi(): JSONObject = JSONObject()
        .put("surum", BuildConfig.VERSION_NAME)
        .put("platform", "android-" + Build.VERSION.RELEASE)
        .put("makine_adi", (Build.MANUFACTURER + " " + Build.MODEL).trim())
        .put("urun", "kopru")
        .put("calisma_sn", (System.currentTimeMillis() - baslamaTs) / 1000)
        .put("panel_port", JSONObject.NULL)

    /**
     * Merkezin sorabilecegi eylemler (`kopru/uygulama.py::_ajan_islevleri`
     * ile ayni adlar ve yanit bicimleri).
     */
    private fun islevler(k: AkisKanallari, u: UsbSeri): Map<String, (JSONObject) -> JSONObject> {
        val servisDurum: (JSONObject) -> JSONObject = { _ ->
            JSONObject().put("servisler", servisler(k, u)).put("kanallar", k.durum())
        }
        return mapOf(
            "sistem_bilgi" to { _ -> sistemBilgi() },
            "servis_durum" to servisDurum,
            "durum" to servisDurum,
            "yetenekler" to { _ -> yetenekler() },
            "dron_sayisi" to { _ -> JSONObject().put("sonuc", k.etkinSayi()) },
            "konsol" to { v ->
                val ad = v.optString("servis")
                if (ad != "dron") {
                    JSONObject().put("hata", "Bilinmeyen servis: $ad")
                } else {
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
                    JSONObject().put("servis", "dron").put("satirlar", satirlar)
                }
            },
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
                // Telefon yalniz ham MAVLink tasir; MSP (Betaflight)
                // desteklenmez. Acik yanit: merkez otomatik algilamada
                // ArduPilot yolunu secer.
                JSONObject()
                    .put("tamam", true)
                    .put("protokol", "ardupilot")
                    .put("kanit", "Android MAVLink koprusu: ham MAVLink akisi")
            }
        )
    }
}
