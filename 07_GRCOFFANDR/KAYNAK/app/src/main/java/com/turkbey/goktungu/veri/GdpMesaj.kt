package com.turkbey.goktungu.veri

import org.json.JSONArray
import org.json.JSONObject

/**
 * GOKTUNGU DJI Kopru Protokolu (GDP) mesaj bicimleri.
 *
 * Sozlesme kaynagi: sunucu tarafi `goktungu/dji_kopru.py` bas yorumu.
 * Tasima: TCP, satir-ayrilmis JSON (NDJSON).  Her satir bir nesne.
 *
 * ## KRITIK: koordinat alanlari
 *
 * Koordinatlar DAIMA adlandirilmis alanlarla tasinir (`lat`, `lon`).
 * Sirali dizi/cift KULLANILMAZ.  Sebep: enlem/boylam ters calisma
 * kusurunun kok nedeni, koordinatlarin siraya bagli tasinmasidir.
 * Adlandirilmis alan, sira hatasini yapisal olarak olanaksiz kilar.
 *
 * `LocationCoordinate2D` gibi DJI turlerine cevrim YALNIZ
 * [GdpKoordinat] icinde yapilir.
 */
object GdpMesaj {

    // Mesaj turleri: istemci -> sunucu
    const val TIP_MERHABA = "merhaba"
    const val TIP_TELEMETRI = "telemetri"
    const val TIP_YANIT = "yanit"
    const val TIP_KALP = "kalp"
    const val TIP_PARAM_LISTE = "param_liste"
    const val TIP_GOREV_DURUM = "gorev_durum"
    const val TIP_GOREV_YUKLEME = "gorev_yukleme"
    const val TIP_MESAJ = "mesaj"
    const val TIP_HAZIRLIK = "hazirlik"

    // Mesaj turu: sunucu -> istemci
    const val TIP_KOMUT = "komut"

    /** Sunucunun gonderebilecegi komut adlari (dji_kopru.py sozlesmesi). */
    object Komut {
        const val ARM = "arm"
        const val DISARM = "disarm"
        const val TAKEOFF = "takeoff"
        const val LAND = "land"
        const val RTL = "rtl"
        const val GOTO = "goto"
        const val HIZ = "hiz"
        const val DUR = "dur"
        const val GIMBAL = "gimbal"
        const val FOTO = "foto"
        const val VIDEO_BASLAT = "video_baslat"
        const val VIDEO_DURDUR = "video_durdur"
        const val GOREV_YUKLE = "gorev_yukle"
        const val GOREV_BASLAT = "gorev_baslat"
        const val GOREV_DURDUR = "gorev_durdur"
        const val GOREV_DURAKLAT = "gorev_duraklat"
        const val GOREV_DEVAM = "gorev_devam"
        const val GOREV_IPTAL = "gorev_iptal"
        const val PARAM_OKU = "param_oku"
        const val PARAM_YAZ = "param_yaz"
        const val LOG_LISTESI = "log_listesi"
        const val LOG_INDIR = "log_indir"
        const val LOG_IPTAL = "log_iptal"
        const val HAZIRLIK_OKU = "hazirlik_oku"
        const val EV_AYARLA = "ev_ayarla"
    }

    const val SONUC_TAMAM = "tamam"
    const val SONUC_HATA = "hata"

    /** Istemcinin bildirdigi yetenekler. */
    val YETENEKLER = listOf(
        "ucus", "telemetri", "param", "gorev", "hazirlik", "gimbal", "foto"
    )

    /**
     * El sikisma mesaji.
     *
     * @param sn Aracin seri numarasi.  Sunucu bunu kalici sysid
     *   eslemesi icin kullanir; ayni arac tekrar baglaninca ayni sanal
     *   sysid'yi alir ve gecmisi korunur.
     */
    fun merhaba(
        sn: String,
        model: String,
        fw: String,
        videoUrl: String?,
        belirtec: String = ""
    ): JSONObject = JSONObject().apply {
        put("tip", TIP_MERHABA)
        put("sdk", "msdk")
        put("sn", sn)
        put("model", model)
        put("fw", fw)
        if (!videoUrl.isNullOrBlank()) put("video_url", videoUrl)
        // BULGU_07: sunucu (`dji_kopru.py` `merhaba` islemi)
        // belirteci `hmac.compare_digest` ile dogrular; UZAK
        // baglantida belirtec yoksa baglanti REDDEDILIR. Yerel
        // (127.0.0.1) kurulumda belirtec istenmez; alan yalniz
        // DOLUYSA eklenir, boylece yerel protokol degismez.
        if (belirtec.isNotBlank()) put("belirtec", belirtec)
        put("yetenekler", JSONArray(YETENEKLER))
    }

    /**
     * Telemetri mesaji.
     *
     * Koordinatlar [GdpKoordinat] uzerinden gelir; ham `Double`
     * ciftleri buraya DOGRUDAN gecirilmez.
     */
    fun telemetri(
        konum: GdpKoordinat,
        altMsl: Double,
        altRel: Double,
        heading: Double,
        hiz: Double,
        vz: Double,
        roll: Double,
        pitch: Double,
        bataryaPct: Int,
        bataryaV: Double,
        gpsFix: Int,
        uydu: Int,
        mod: String,
        armed: Boolean,
        ucusta: Boolean,
        ev: GdpKoordinat?
    ): JSONObject = JSONObject().apply {
        put("tip", TIP_TELEMETRI)
        put("lat", konum.enlem)
        put("lon", konum.boylam)
        put("alt_msl", altMsl)
        put("alt_rel", altRel)
        put("heading", heading)
        put("hiz", hiz)
        put("vz", vz)
        put("roll", roll)
        put("pitch", pitch)
        put("batarya_pct", bataryaPct)
        put("batarya_v", bataryaV)
        put("gps_fix", gpsFix)
        put("uydu", uydu)
        put("mod", mod)
        put("armed", armed)
        put("ucusta", ucusta)
        if (ev != null) {
            put("ev_lat", ev.enlem)
            put("ev_lon", ev.boylam)
        }
    }

    fun yanit(komutId: Int, basarili: Boolean, mesaj: String): JSONObject =
        JSONObject().apply {
            put("tip", TIP_YANIT)
            put("komut_id", komutId)
            put("sonuc", if (basarili) SONUC_TAMAM else SONUC_HATA)
            put("mesaj", mesaj)
        }

    /**
     * Canlilik mesaji.  Arac RC'ye bagli olmasa da istemci soketini
     * canli tutar.
     *
     * @param urunBagli `false` ise sunucu dronu modelden duser ama
     *   istemci baglantisini korur.
     */
    fun kalp(urunBagli: Boolean): JSONObject = JSONObject().apply {
        put("tip", TIP_KALP)
        put("urun", urunBagli)
    }

    fun mesaj(metin: String, seviye: Int): JSONObject = JSONObject().apply {
        put("tip", TIP_MESAJ)
        put("metin", metin)
        put("seviye", seviye.coerceIn(0, 7))
    }

    fun hazirlik(
        ucusaHazir: Boolean,
        engel: String,
        sensorler: Map<String, String>,
        rcBagli: Boolean,
        rcSinyal: Int
    ): JSONObject = JSONObject().apply {
        put("tip", TIP_HAZIRLIK)
        put("ucusa_hazir", ucusaHazir)
        put("engel", engel)
        put("sensorler", JSONObject(sensorler))
        put("rc_bagli", rcBagli)
        put("rc_sinyal", rcSinyal)
    }

    fun gorevDurum(durum: String, nokta: Int): JSONObject =
        JSONObject().apply {
            put("tip", TIP_GOREV_DURUM)
            put("durum", durum)
            put("nokta", nokta)
        }

    fun gorevYukleme(
        yuklenen: Int, toplam: Int, durum: String, mesaj: String = ""
    ): JSONObject = JSONObject().apply {
        put("tip", TIP_GOREV_YUKLEME)
        put("yuklenen", yuklenen)
        put("toplam", toplam)
        put("durum", durum)
        if (mesaj.isNotBlank()) put("mesaj", mesaj)
    }

    fun paramListe(parametreler: Map<String, Any>): JSONObject =
        JSONObject().apply {
            put("tip", TIP_PARAM_LISTE)
            put("parametreler", JSONObject(parametreler))
        }

    /**
     * Sunucudan gelen komutu ayristirir.
     *
     * @return `null` ise mesaj komut degil veya bicimi gecersiz.
     */
    fun komutAyristir(m: JSONObject): GelenKomut? {
        if (m.optString("tip") != TIP_KOMUT) return null
        val ad = m.optString("ad").takeIf { it.isNotBlank() } ?: return null
        return GelenKomut(
            id = m.optInt("id", 0),
            ad = ad,
            args = m.optJSONObject("args") ?: JSONObject()
        )
    }

    data class GelenKomut(
        val id: Int,
        val ad: String,
        val args: JSONObject
    ) {
        /**
         * `args` icindeki hedef koordinati [GdpKoordinat] olarak cozer.
         *
         * KRITIK: alanlar ADLA okunur (`lat`, `lon`).  Sirali okuma
         * yapilmaz.  Alan eksikse veya sayi degilse `null` doner ve
         * cagiran komutu reddeder — sessiz sifir/varsayilan KULLANILMAZ,
         * cunku (0,0) gecerli bir koordinattir ve araci Gine Korfezi'ne
         * gonderirdi.
         */
        fun hedefKoordinat(
            ref: GdpKoordinat? = null
        ): GdpKoordinat.Companion.Sonuc {
            if (!args.has("lat") || !args.has("lon")) {
                return GdpKoordinat.Companion.Sonuc.Gecersiz(
                    "komut '$ad' icinde lat/lon alani yok"
                )
            }
            val e = args.optDouble("lat", Double.NaN)
            val b = args.optDouble("lon", Double.NaN)
            return GdpKoordinat.dogrula(e, b, ref?.enlem, ref?.boylam)
        }
    }
}
