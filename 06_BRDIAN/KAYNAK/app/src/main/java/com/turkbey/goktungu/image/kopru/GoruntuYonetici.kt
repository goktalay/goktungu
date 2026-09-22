package com.turkbey.goktungu.image.kopru

import android.content.Context
import com.turkbey.goktungu.image.BuildConfig
import com.turkbey.goktungu.image.goruntu.KameraKopru
import com.turkbey.goktungu.image.goruntu.MjpegSunucu
import com.turkbey.goktungu.image.veri.Gunluk
import androidx.camera.core.Preview
import androidx.lifecycle.LifecycleOwner
import org.json.JSONArray
import org.json.JSONObject

/**
 * Goruntu koprusu cekirdegine tek erisim noktasi.
 *
 * BRDAND'in `KopruYonetici` koordinatorunun GORUNTU karsiligidir; ancak
 * BRDAND cok-kopru (ArduPilot/BetaFlight/DJI/…) yonetirken BRDIAN TEK
 * amaclidir: cihaz kamerasi -> yerel MJPEG + merkeze durum. Bu yuzden
 * strateji deseni yoktur; tek bir kamera + tek bir ajan tutulur.
 *
 * Sahiplenen parcalar:
 *   - [KameraKopru]  : CameraX yakalama + JPEG kodlama
 *   - [MjpegSunucu]  : yerel HTTP MJPEG fan-out (kareler yerelde kalir)
 *   - [GoruntuKanallari] : merkezin actigi mantiksal akislar + meta
 *   - [KopruAjan]    : merkeze (GRCON/GRCOFF) ters WebSocket
 */
object GoruntuYonetici {

    private lateinit var baglam: Context

    private var _kamera: KameraKopru? = null
    val kamera: KameraKopru? get() = _kamera

    private var _mjpeg: MjpegSunucu? = null
    val mjpeg: MjpegSunucu? get() = _mjpeg

    private var _kanallar: GoruntuKanallari? = null
    private var _ajan: KopruAjan? = null
    val ajan: KopruAjan? get() = _ajan

    private val baslamaTs = System.currentTimeMillis()

    @Volatile
    private var kuruldu = false

    /** Uygulama/etkinlik acilisinda bir kez cagrilir. */
    fun kur(b: Context) {
        if (kuruldu) return
        kuruldu = true
        baglam = b.applicationContext
        val kam = KameraKopru(baglam)
        val mj = MjpegSunucu()
        val kanal = GoruntuKanallari(kam, mj)
        _kamera = kam
        _mjpeg = mj
        _kanallar = kanal
        _ajan = KopruAjan(
            kimlikOku = { KopruKimlik.oku(baglam) },
            surum = BuildConfig.VERSION_NAME,
            platform = KopruOrtak.platform(),
            makineAdi = KopruOrtak.makineAdi(),
            islevler = islevler(kanal),
            // Merkezden kopruye ham byte AKMAZ (goruntu tek yonludur:
            // kareler yerelde, merkeze yalniz durum). No-op.
            akisYaz = { _, _ -> },
            yetenekler = ::yetenekler,
            dronSayisi = { kanal.etkinSayi() },
            nabizEk = {
                JSONObject()
                    .put("servisler", servisler(kanal))
                    .put("kanallar", kanal.durum())
            }
        )
        Gunluk.yaz("KOPRU", "Goruntu koprusu cekirdegi kuruldu")
    }

    /**
     * Kamerayi verilen yasam dongusune baglar (analiz + MJPEG besleme).
     * On plan hizmeti [com.turkbey.goktungu.image.kopru.KopruHizmeti]
     * cagirir; boylece arayuz kapali olsa da yakalama surer.
     */
    fun kameraBagla(sahip: LifecycleOwner) {
        val mj = _mjpeg ?: return
        if (!mj.calisiyor) mj.baslat()
        _kamera?.bagla(sahip, mj)
    }

    /** Arayuz onizleme yuzeyini takar/kaldirir. */
    fun onizlemeAyarla(saglayan: Preview.SurfaceProvider?) {
        _kamera?.onizlemeAyarla(saglayan)
    }

    fun kameraCoz() {
        _kamera?.coz()
    }

    fun baslat(): Boolean {
        if (!KopruKimlik.var_(baglam)) {
            Gunluk.uyari("KOPRU", "Kurulum kimligi yok; once API kodu girin")
            return false
        }
        _mjpeg?.let { if (!it.calisiyor) it.baslat() }
        _ajan?.baslat()
        return true
    }

    fun durdur() {
        _ajan?.durdur()
        _kanallar?.tumunuKapat()
    }

    fun calisiyorMu(): Boolean = _ajan?.calisiyorMu() == true

    fun bagliMi(): Boolean = _ajan?.bagliMi() == true

    fun etkinKanalSayi(): Int = _kanallar?.etkinSayi() ?: 0

    fun kanalOzet(): String = _kanallar?.ozet() ?: ""

    // ------------------------------------------------------------------
    // Merkezin gordugu bilgiler
    // ------------------------------------------------------------------
    private fun yetenekler(): JSONObject = JSONObject()
        .put("urun", KopruOrtak.URUN)          // "goruntu"
        .put("platform", "android")
        .put("goruntu", true)
        .put("kamera", true)
        .put("servis", true)
        .put("konsol", true)
        .put("telemetri", false)

    private fun servisler(k: GoruntuKanallari): JSONArray {
        val kam = _kamera
        val goruntu = JSONObject()
            .put("ad", "goruntu")
            .put("baslik", "Goruntu Servisi (Android CameraX)")
            .put("aciklama", "Cihaz kamerasi -> yerel MJPEG; merkeze durum")
            .put("calisiyor", calisiyorMu())
            .put("pid", JSONObject.NULL)
            .put("baslama_ts", baslamaTs / 1000.0)
            .put("bitis_ts", JSONObject.NULL)
            .put("cikis_kodu", JSONObject.NULL)
            .put("son_hata", kam?.sonHata ?: "")
            .put("konsol_satir", Gunluk.kayitlar.value.size)
            .put(
                "olcumler",
                JSONObject()
                    .put("kamera_bagli", kam?.bagli == true)
                    .put("kanal", k.etkinSayi())
                    .put("etkin_kanal", k.etkinSayi())
                    .put("uretilen_kare", kam?.uretilenKare?.get() ?: 0L)
                    .put("izleyici", _mjpeg?.izleyici?.get() ?: 0L)
            )
            .put("surum", BuildConfig.VERSION_NAME)
        return JSONArray().put(goruntu)
    }

    private fun islevler(k: GoruntuKanallari): Map<String, (JSONObject) -> JSONObject> {
        val servisDurum: (JSONObject) -> JSONObject = { _ ->
            JSONObject().put("servisler", servisler(k)).put("kanallar", k.durum())
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
                if (ad == "goruntu" || ad == "dron") {
                    _mjpeg?.let { if (!it.calisiyor) it.baslat() }
                    JSONObject().put("tamam", true).put("hata", "")
                } else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis: $ad")
            },
            "servis_durdur" to { v ->
                val ad = v.optString("servis")
                if (ad == "goruntu" || ad == "dron") {
                    k.tumunuKapat()
                    JSONObject().put("tamam", true).put("hata", "")
                } else JSONObject().put("tamam", false).put("hata", "Bilinmeyen servis: $ad")
            },
            // Merkez bu makinedeki kamera kaynaklarini sorar (video_vekil
            // cihaz_listesi karsiligi). Android'de tek mantiksal kaynak
            // (secili mercek) sunulur; ayrinti CameraX'te yonetilir.
            "kamera_kaynaklari" to { _ ->
                val liste = JSONArray().put(
                    JSONObject()
                        .put("indeks", 0)
                        .put("ad", "Cihaz kamerasi")
                        .put("protokol", "donanim")
                )
                JSONObject().put("kaynaklar", liste)
            },
            "akis_ac" to { v ->
                val (meta, hata) = k.ac(
                    v.optInt("kanal_id", 0), v.optJSONObject("tanim") ?: JSONObject()
                )
                if (hata != null) JSONObject().put("tamam", false).put("hata", hata)
                else JSONObject().put("tamam", true).put("kanal", meta)
            },
            "akis_kapat" to { v ->
                JSONObject().put("tamam", true).put("vardi", k.kapat(v.optInt("kanal_id", 0)))
            },
            "akis_durum" to { _ -> JSONObject().put("kanallar", k.durum()) },
            "protokol_algila" to { _ ->
                JSONObject()
                    .put("tamam", true)
                    .put("protokol", "goruntu")
                    .put("kanit", "Android goruntu koprusu: CameraX -> yerel MJPEG")
            }
        )
    }
}
