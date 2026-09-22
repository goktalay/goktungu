package com.turkbey.goktungu.bridge.veri

import dji.sdk.keyvalue.value.common.LocationCoordinate2D
import kotlin.math.abs
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Bir WGS-84 koordinat cifti ve GDP <-> DJI MSDK arasindaki TEK
 * donusum noktasi.
 *
 * ## Neden bu sinif var
 *
 * 16 Agustos 2026'da bildirilen kusur: haritada CTRL+tik ile verilen
 * `goto` komutu araci gitmesi gereken yere degil baska bir yone
 * goturuyordu.  Telemetri dogru gorunuyordu.
 *
 * Kok neden, katmanlarin farkli eksen sirasi kullanmasi:
 *
 * | Katman | Sira |
 * |---|---|
 * | GDP protokolu (bizim) | `lat`, `lon` — adlandirilmis alanlar |
 * | DJI MSDK | `LocationCoordinate2D(latitude, longitude)` |
 * | Cesium (merkez arayuz) | `fromDegrees(longitude, latitude)` — TERS |
 * | GeoJSON | `[longitude, latitude]` — TERS |
 *
 * Sunucu tarafi (Python) bastan sona denetlendi ve TEMIZ; takas cihaz
 * tarafinda olusuyordu.  Bu sinif takasi yapisal olarak olanaksiz kilar.
 *
 * ## Sozlesme (BOZULMAMALI)
 *
 * 1. Bu dosya DISINDA `LocationCoordinate2D(...)` yapicisi **cagrilmaz**.
 *    Olcum bunu kaynak taramasiyla denetler.
 * 2. Koordinatlar daima **adlandirilmis alanlarla** tasinir; sirali
 *    dizi/cift KULLANILMAZ.
 * 3. Ham `Double` cifti alan islevler yerine bu tur gecirilir; boylece
 *    cagri yerinde sira hatasi yapilamaz.
 */
data class GdpKoordinat(
    val enlem: Double,
    val boylam: Double,
    /** Kosegen bolgede uretildi; olasi eksen takasi ayirt edilemedi. */
    val belirsiz: Boolean = false
) {

    /**
     * DJI MSDK turune cevirir.
     *
     * Bu, uygulamada `LocationCoordinate2D` yapicisinin cagrildigi
     * TEK yerdir.  Sira burada bir kez dogru yazilir ve bir daha
     * tekrarlanmaz.
     */
    fun djiyeCevir(): LocationCoordinate2D =
        LocationCoordinate2D(enlem, boylam)

    /** Gunlukleme icin kisa gosterim. */
    fun kisa(): String = "%.6f,%.6f".format(enlem, boylam)

    /** Bu noktadan [o] noktasina buyuk daire mesafesi (km). */
    fun mesafeKm(o: GdpKoordinat): Double =
        mesafeKm(enlem, boylam, o.enlem, o.boylam)

    companion object {

        /** Evrensel WGS-84 sinirlari. */
        const val ENLEM_SINIR = 90.0
        const val BOYLAM_SINIR = 180.0

        /**
         * Hedef referans konumdan bu kadar uzaktaysa supheli sayilir.
         * DJI araclarinin azami menzili ~15 km oldugu icin 60 km cok
         * comert bir sinirdir; mesru hedefi reddetmez.
         */
        const val AZAMI_HEDEF_KM = 60.0

        /**
         * Kosegen bolge esigi.  |enlem| ile |boylam| farki bundan
         * kucukse eksen takasi tespit EDILEMEZ.  Ornek: Malatya
         * (38.355, 38.309) takas edilince yalniz ~7 km sapar.
         */
        const val KOSEGEN_ESIK = 0.5

        /** (0,0) Gine Korfezi'dir; "veri yok" gercek konum sanilamaz. */
        const val SIFIR_TOLERANS = 1e-7

        /** Dogrulama sonucu. */
        sealed class Sonuc {
            data class Gecerli(val koordinat: GdpKoordinat) : Sonuc()
            data class Gecersiz(val neden: String) : Sonuc()
        }

        fun mesafeKm(
            enlem1: Double, boylam1: Double,
            enlem2: Double, boylam2: Double
        ): Double {
            val r = 6371.0
            val f1 = Math.toRadians(enlem1)
            val f2 = Math.toRadians(enlem2)
            val df = f2 - f1
            val dl = Math.toRadians(boylam2 - boylam1)
            val a = sin(df / 2) * sin(df / 2) +
                cos(f1) * cos(f2) * sin(dl / 2) * sin(dl / 2)
            return 2 * r * asin(min(1.0, sqrt(a)))
        }

        fun sifirMi(enlem: Double, boylam: Double): Boolean =
            abs(enlem) < SIFIR_TOLERANS && abs(boylam) < SIFIR_TOLERANS

        fun kosegendeMi(enlem: Double, boylam: Double): Boolean =
            abs(abs(enlem) - abs(boylam)) < KOSEGEN_ESIK

        /**
         * Dogrular ve gecerliyse koordinat uretir.
         *
         * @param refEnlem Referans konum (aracin anlik konumu veya ev
         *   noktasi).  Verilirse YAKINLIK denetimi devreye girer; bu en
         *   guclu olcuttur ve cografyadan bagimsizdir.
         */
        fun dogrula(
            enlem: Double?,
            boylam: Double?,
            refEnlem: Double? = null,
            refBoylam: Double? = null
        ): Sonuc {
            if (enlem == null || boylam == null) {
                return Sonuc.Gecersiz(
                    "koordinat eksik (enlem veya boylam yok)"
                )
            }
            if (enlem.isNaN() || boylam.isNaN() ||
                enlem.isInfinite() || boylam.isInfinite()
            ) {
                return Sonuc.Gecersiz("koordinat sayi degil (NaN/sonsuz)")
            }

            // --- 1. katman: kesin denetimler ---
            if (abs(enlem) > ENLEM_SINIR) {
                return Sonuc.Gecersiz(
                    "enlem araligin disinda: $enlem " +
                        "(sinir +-${ENLEM_SINIR.toInt()}). Boylam degeri " +
                        "enlem alanina yazilmis olabilir."
                )
            }
            if (abs(boylam) > BOYLAM_SINIR) {
                return Sonuc.Gecersiz(
                    "boylam araligin disinda: $boylam " +
                        "(sinir +-${BOYLAM_SINIR.toInt()})"
                )
            }
            if (sifirMi(enlem, boylam)) {
                return Sonuc.Gecersiz(
                    "koordinat (0,0) — 'veri yok' degeri gercek konum " +
                        "sanilamaz"
                )
            }

            // --- 2. katman: yakinlik (en guclu olcut) ---
            if (refEnlem != null && refBoylam != null &&
                !refEnlem.isNaN() && !refBoylam.isNaN() &&
                !sifirMi(refEnlem, refBoylam)
            ) {
                val dDogru = mesafeKm(refEnlem, refBoylam, enlem, boylam)
                if (dDogru > AZAMI_HEDEF_KM) {
                    val dTakas = mesafeKm(refEnlem, refBoylam, boylam, enlem)
                    return if (dTakas < dDogru) {
                        Sonuc.Gecersiz(
                            "EKSEN TAKASI: hedef referanstan " +
                                "${dDogru.toInt()} km uzakta; eksenler " +
                                "takas edilince ${dTakas.toInt()} km'ye " +
                                "dusuyor. Cagiran taraf enlem/boylam " +
                                "sirasini ters vermis olmali."
                        )
                    } else {
                        Sonuc.Gecersiz(
                            "hedef cok uzak: referanstan " +
                                "${dDogru.toInt()} km " +
                                "(sinir ${AZAMI_HEDEF_KM.toInt()} km)"
                        )
                    }
                }
            }

            return Sonuc.Gecerli(
                GdpKoordinat(enlem, boylam, kosegendeMi(enlem, boylam))
            )
        }

        /**
         * Dogrulayip koordinat uretir; gecersizse `null`.
         *
         * Reddetme nedenini gormek gerekiyorsa [dogrula] kullanilmali.
         */
        fun olustur(
            enlem: Double?,
            boylam: Double?,
            refEnlem: Double? = null,
            refBoylam: Double? = null
        ): GdpKoordinat? =
            when (val s = dogrula(enlem, boylam, refEnlem, refBoylam)) {
                is Sonuc.Gecerli -> s.koordinat
                is Sonuc.Gecersiz -> null
            }

        /**
         * DJI MSDK turunden okur.
         *
         * MSDK arac konumu yokken (0,0) dondurur; bu deger gercek konum
         * sanilmamali, bu yuzden `null` olarak islenir.
         */
        fun djidenOku(k: LocationCoordinate2D?): GdpKoordinat? {
            if (k == null) return null
            val e = k.latitude
            val b = k.longitude
            if (e.isNaN() || b.isNaN()) return null
            if (sifirMi(e, b)) return null
            if (abs(e) > ENLEM_SINIR || abs(b) > BOYLAM_SINIR) return null
            return GdpKoordinat(e, b, kosegendeMi(e, b))
        }
    }
}
