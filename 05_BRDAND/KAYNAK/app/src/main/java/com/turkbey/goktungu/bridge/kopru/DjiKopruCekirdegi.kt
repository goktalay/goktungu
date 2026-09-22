package com.turkbey.goktungu.bridge.kopru

import android.content.Context
import android.os.Build
import android.util.Base64
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.dji.DjiKopru
import com.turkbey.goktungu.bridge.dji.GorevYonetici
import com.turkbey.goktungu.bridge.veri.Ayarlar
import com.turkbey.goktungu.bridge.veri.GdpMesaj
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/**
 * DJI KOPRU CEKIRDEGI (Faz 1: gommeli DJI kopru tipi).
 *
 * ## Neden ayri bir nesne
 *
 * BRDAND'in kendi [KopruYonetici] nesnesi MAVLink yolunu yonetir ve
 * REGRESYONSUZ kalmali; bu yuzden DJI cekirdegi ayri, kendine yeten bir
 * nesne olarak eklendi. BRDDJI'nin `KopruYonetici` deseninin birebir
 * karsiligidir; yalniz ad cakismasini onlemek icin yeniden adlandirildi.
 *
 * Bu nesne, tasinan DJI kodunun (DjiKopru / GorevYonetici / KmzUretici /
 * GdpKanal / KomutIsleyici) OLU kalmamasini saglar: hepsi burada
 * kurulur ve BRDAND'in mevcut [KopruAjan] protokolune (GTK1 ters-WS /
 * `akis` kanali) baglanir. Merkez tarafinda ikinci bir protokol
 * gerekmez.
 *
 * ## Akis
 *
 * ```
 * DJI arac --(MSDK anahtar dinleme)--> DjiKopru.telemetri
 *          --(periyodik ornekleme)--> GdpKanal --{"tur":"akis"}--> merkez role
 * merkez --{"tur":"akis"}(komut satiri)--> GdpKanal --> KomutIsleyici --> DjiKopru
 * ```
 *
 * ## Faz 1 kapsami
 *
 * Sol-menu / cok-kopru UI baglamasi Faz 2'dedir. Bu nesne DERLENEBILIR
 * ve CAGRILABILIR haldedir; arayuzden `kur()`/`baslat()` ile
 * tetiklenmeye hazirdir. Kur cagrilmadigi surece MSDK BASLATILMAZ, yani
 * mevcut MAVLink davranisi hicbir sekilde etkilenmez.
 */
object DjiKopruCekirdegi {

    /** Telemetri gonderim araligi (ms). Merkez 5 Hz bekliyor. */
    const val TELEMETRI_ARALIK_MS = 200L

    private lateinit var baglam: Context

    private var _dji: DjiKopru? = null
    val dji: DjiKopru? get() = _dji

    private var gorev: GorevYonetici? = null
    private var isleyici: KomutIsleyici? = null

    private var _kanallar: GdpKanal? = null
    val kanallar: GdpKanal? get() = _kanallar

    private var _ajan: KopruAjan? = null
    val ajan: KopruAjan? get() = _ajan

    private var kapsam: CoroutineScope? = null
    private var telemetriIsi: Job? = null

    private val _ornekSayisi = MutableStateFlow(0L)
    val ornekSayisi: StateFlow<Long> = _ornekSayisi.asStateFlow()

    private val baslamaTs = System.currentTimeMillis()

    @Volatile
    private var kuruldu = false

    /**
     * MSDK'yi ve DJI kopru ajanini kurar. Faz 2'de arayuz DJI kopru
     * tipini secince bir kez cagrilir. Cagrilmadan MSDK BASLAMAZ.
     */
    fun kur(b: Context) {
        if (kuruldu) return
        kuruldu = true
        baglam = b.applicationContext
        val d = DjiKopru(baglam)
        _dji = d
        val kn = GdpKanal(
            gonder = { kid, v -> _ajan?.akisGonder(kid, v) ?: false },
            merhabaUretici = {
                GdpMesaj.merhaba(
                    sn = d.seriNo() ?: Ayarlar.oku(baglam).cihazKimlik,
                    model = d.urunModeli(),
                    fw = d.yazilimSurumu(),
                    videoUrl = null
                )
            },
            komutIsle = { komut, _ -> isleyici?.isle(komut) },
            urunBagli = { d.urunBagli.value }
        )
        _kanallar = kn
        gorev = GorevYonetici(
            baglam,
            durumBildir = { durum, nokta -> kn.yayinla(GdpMesaj.gorevDurum(durum, nokta)) },
            yuklemeBildir = { y, t, durum, mesaj ->
                kn.yayinla(GdpMesaj.gorevYukleme(y, t, durum, mesaj))
            }
        )
        // Komut yanitlari acik GDP oturumlarina yayinlanir (normalde tek).
        isleyici = KomutIsleyici(d, gorev!!) { m -> kn.yayinla(m) }
        _ajan = KopruAjan(
            kimlikOku = { KopruKimlik.oku(baglam) },
            surum = BuildConfig.VERSION_NAME,
            platform = "android-" + Build.VERSION.RELEASE,
            makineAdi = (Build.MANUFACTURER + " " + Build.MODEL).trim(),
            islevler = islevler(kn, d),
            akisYaz = { kid, v -> kn.yaz(kid, v) },
            yetenekler = ::yetenekler,
            dronSayisi = { if (d.urunBagli.value && kn.etkinSayi() > 0) 1 else 0 },
            nabizEk = {
                JSONObject().put("servisler", servisler(kn, d)).put("kanallar", kn.durum())
            }
        )
        d.baslat()
        Gunluk.yaz("DJI-KOPRU", "DJI kopru cekirdegi kuruldu (ajan 1.1.0)")
    }

    /** Ajani ve telemetri dongusunu baslatir; kimlik yoksa `false`. */
    fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("DJI-KOPRU", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        gorev?.baslatModulu()
        _ajan?.baslat()
        if (telemetriIsi == null) {
            val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
            kapsam = k
            telemetriIsi = k.launch { telemetriDongusu() }
        }
        return true
    }

    fun durdur() {
        telemetriIsi?.cancel()
        telemetriIsi = null
        kapsam?.cancel()
        kapsam = null
        _kanallar?.tumunuKapat()
        _ajan?.durdur()
    }

    fun kuruldu(): Boolean = kuruldu

    fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    /**
     * Telemetri ornekleme dongusu. Konum yoksa GONDERILMEZ: sifir
     * gondermek araci Gine Korfezi'nde gosterirdi.
     */
    private suspend fun telemetriDongusu() {
        val d = _dji ?: return
        while (true) {
            try {
                val kn = _kanallar
                if (kn != null && kn.etkinSayi() > 0) {
                    val t = d.telemetri.value
                    val konum = t.konum
                    if (konum != null) {
                        val n = kn.yayinla(
                            GdpMesaj.telemetri(
                                konum = konum,
                                altMsl = t.altMsl,
                                altRel = t.altRel,
                                heading = t.heading,
                                hiz = t.yatayHiz,
                                vz = t.dikeyHiz,
                                roll = t.roll,
                                pitch = t.pitch,
                                bataryaPct = t.bataryaPct,
                                bataryaV = t.bataryaV,
                                gpsFix = t.gpsSeviye,
                                uydu = t.uydu,
                                mod = t.mod,
                                armed = t.motorAcik,
                                ucusta = t.ucusta,
                                ev = t.ev
                            )
                        )
                        if (n > 0) _ornekSayisi.value = _ornekSayisi.value + 1
                    }
                }
            } catch (e: Exception) {
                Gunluk.hata("DJI-KOPRU", "Telemetri dongusu: ${e.message}")
            }
            delay(TELEMETRI_ARALIK_MS)
        }
    }

    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", "kopru")
        .put("platform", "android")
        .put("dji", true)
        .put("servis", true)
        .put("konsol", true)
        .put("telemetri", false)

    private fun servisler(kn: GdpKanal, d: DjiKopru): JSONArray {
        val dron = JSONObject()
            .put("ad", "dron")
            .put("baslik", "Dron Servisi (DJI MSDK)")
            .put("aciklama", "DJI araci: GDP telemetri ve komut")
            .put("calisiyor", calisiyorMu())
            .put("pid", JSONObject.NULL)
            .put("baslama_ts", baslamaTs / 1000.0)
            .put("bitis_ts", JSONObject.NULL)
            .put("cikis_kodu", JSONObject.NULL)
            .put("son_hata", d.kayitHata.value)
            .put("konsol_satir", Gunluk.kayitlar.value.size)
            .put(
                "olcumler",
                JSONObject()
                    .put("sdk_kayitli", d.kayit.value == DjiKopru.KayitDurum.KAYITLI)
                    .put("arac_bagli", d.urunBagli.value)
                    .put("model", d.urunModeli())
                    .put("kanal", kn.etkinSayi())
                    .put("etkin_kanal", kn.etkinSayi())
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

    private fun islevler(kn: GdpKanal, d: DjiKopru): Map<String, (JSONObject) -> JSONObject> {
        val servisDurum: (JSONObject) -> JSONObject = { _ ->
            JSONObject().put("servisler", servisler(kn, d)).put("kanallar", kn.durum())
        }
        return mapOf(
            "sistem_bilgi" to { _ -> sistemBilgi() },
            "servis_durum" to servisDurum,
            "durum" to servisDurum,
            "yetenekler" to { _ -> yetenekler() },
            "dron_sayisi" to { _ ->
                JSONObject().put("sonuc", if (d.urunBagli.value && kn.etkinSayi() > 0) 1 else 0)
            },
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
                if (v.optString("servis") == "dron") JSONObject().put("tamam", true).put("hata", "")
                else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis")
            },
            "servis_durdur" to { v ->
                if (v.optString("servis") == "dron") {
                    kn.tumunuKapat()
                    JSONObject().put("tamam", true).put("hata", "")
                } else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis")
            },
            "seri_portlar" to { _ ->
                // DJI koprusunde seri port yoktur; bos liste (hata degil).
                JSONObject().put("portlar", JSONArray())
            },
            "akis_ac" to { v ->
                val (ozet, hata) = kn.ac(
                    v.optInt("kanal_id", 0), v.optJSONObject("tanim") ?: JSONObject()
                )
                if (hata != null) JSONObject().put("tamam", false).put("hata", hata)
                else JSONObject().put("tamam", true).put("kanal", ozet)
            },
            "akis_kapat" to { v ->
                JSONObject().put("tamam", true).put("vardi", kn.kapat(v.optInt("kanal_id", 0)))
            },
            "akis_yaz" to { v ->
                val veri = try {
                    Base64.decode(v.optString("veri"), Base64.DEFAULT)
                } catch (e: Exception) {
                    ByteArray(0)
                }
                if (veri.isEmpty()) JSONObject().put("yazilan", 0)
                else JSONObject().put("yazilan", kn.yaz(v.optInt("kanal_id", 0), veri))
            },
            "akis_durum" to { _ -> JSONObject().put("kanallar", kn.durum()) },
            "protokol_algila" to { _ ->
                JSONObject()
                    .put("tamam", false)
                    .put("hata", "DJI koprusu MAVLink/MSP tasimaz; Baglanti Yoneticisi'nde DJI turu kayit kullanin.")
            }
        )
    }
}
