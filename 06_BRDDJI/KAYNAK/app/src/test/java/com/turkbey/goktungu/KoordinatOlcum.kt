package com.turkbey.goktungu

import com.turkbey.goktungu.veri.GdpKoordinat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Koordinat dogrulama olcumu.
 *
 * Bu olcum, 16 Agustos 2026'da bildirilen enlem/boylam ters calisma
 * kusurunun geri donmesini engeller.  Sunucu tarafi karsiligi
 * `~/olc_koordinat.py` (88/0) ile ayni senaryolari sinar.
 */
class KoordinatOlcum {

    // Referans: Ankara Sincan (Turkbey Teknoloji A.S. adresi)
    private val ankaraEnlem = 39.9700
    private val ankaraBoylam = 32.8200

    private fun gecerli(s: GdpKoordinat.Companion.Sonuc) =
        s as? GdpKoordinat.Companion.Sonuc.Gecerli

    private fun gecersiz(s: GdpKoordinat.Companion.Sonuc) =
        s as? GdpKoordinat.Companion.Sonuc.Gecersiz

    // ------------------------------------------------------------------
    // 1. katman: kesin denetimler
    // ------------------------------------------------------------------

    @Test
    fun `enlem 90 ustu reddedilir`() {
        val s = GdpKoordinat.dogrula(100.0, 32.0)
        assertNotNull("enlem 100 gecersiz olmali", gecersiz(s))
    }

    @Test
    fun `boylam 180 ustu reddedilir`() {
        assertNotNull(gecersiz(GdpKoordinat.dogrula(39.0, 200.0)))
    }

    @Test
    fun `sifir sifir reddedilir`() {
        // (0,0) Gine Korfezi; MSDK konum yokken bunu dondurur.
        assertNotNull(gecersiz(GdpKoordinat.dogrula(0.0, 0.0)))
    }

    @Test
    fun `eksik alan reddedilir`() {
        assertNotNull(gecersiz(GdpKoordinat.dogrula(null, 32.0)))
        assertNotNull(gecersiz(GdpKoordinat.dogrula(39.0, null)))
    }

    @Test
    fun `NaN reddedilir`() {
        assertNotNull(gecersiz(GdpKoordinat.dogrula(Double.NaN, 32.0)))
        assertNotNull(
            gecersiz(GdpKoordinat.dogrula(39.0, Double.POSITIVE_INFINITY))
        )
    }

    // ------------------------------------------------------------------
    // 2. katman: yakinlik olcutu — kusurun asil sinavi
    // ------------------------------------------------------------------

    @Test
    fun `ankara takasi yakalanir`() {
        // Ankara (39.97, 32.82) takas edilince (32.82, 39.97) olur:
        // Irak/Suudi sinirinda, ~900 km uzakta.
        val s = GdpKoordinat.dogrula(
            32.8200, 39.9700, ankaraEnlem, ankaraBoylam
        )
        val g = gecersiz(s)
        assertNotNull("Ankara takasi reddedilmeli", g)
        assertTrue(
            "neden EKSEN TAKASI demeli, dedigi: ${g!!.neden}",
            g.neden.contains("EKSEN TAKASI")
        )
    }

    @Test
    fun `dogru ankara hedefi kabul edilir`() {
        // 5 km kuzeydeki mesru hedef
        val s = GdpKoordinat.dogrula(
            40.0150, 32.8200, ankaraEnlem, ankaraBoylam
        )
        assertNotNull("mesru hedef kabul edilmeli", gecerli(s))
    }

    /**
     * Kutu sezgisinin kacirdigi yedi il.  Diyarbakir gibi noktalarda
     * enlem ve boylam araliklari ortustugu icin cografi kutu takasi
     * yakalayamaz; yakinlik olcutu yakalar.
     */
    @Test
    fun `dogu illerinde takas yakalanir`() {
        val iller = listOf(
            Triple("Diyarbakir", 37.9144, 40.2306),
            Triple("Erzurum", 39.9000, 41.2700),
            Triple("Elazig", 38.6810, 39.2264),
            Triple("Mus", 38.7432, 41.5064),
            Triple("Bitlis", 38.4006, 42.1095),
            Triple("Sivas", 39.7477, 37.0179)
        )
        for ((ad, e, b) in iller) {
            val s = GdpKoordinat.dogrula(b, e, e, b)
            val g = gecersiz(s)
            assertNotNull("$ad takasi reddedilmeli", g)
            assertTrue(
                "$ad nedeni EKSEN TAKASI demeli: ${g!!.neden}",
                g.neden.contains("EKSEN TAKASI")
            )
        }
    }

    /**
     * Malatya (38.355, 38.309): enlem ~ boylam.  Takas edilince yalniz
     * ~7 km sapar; HICBIR yontem bunu ayirt edemez.  Dogru davranis
     * kabul etmek ama BELIRSIZ isaretlemektir — sahte guven vermemek.
     */
    @Test
    fun `kosegen bolge belirsiz isaretlenir`() {
        val s = GdpKoordinat.dogrula(38.3552, 38.3095, 38.3552, 38.3095)
        val g = gecerli(s)
        assertNotNull("kosegen nokta kabul edilmeli", g)
        assertTrue(
            "kosegen nokta belirsiz isaretlenmeli",
            g!!.koordinat.belirsiz
        )
    }

    @Test
    fun `ankara kosegende degil`() {
        val g = gecerli(
            GdpKoordinat.dogrula(39.97, 32.82, ankaraEnlem, ankaraBoylam)
        )
        assertNotNull(g)
        assertFalse(
            "Ankara kosegen bolgede olmamali (39.97 vs 32.82)",
            g!!.koordinat.belirsiz
        )
    }

    // ------------------------------------------------------------------
    // Yurt disi mesru konumlar — YANLIS REDDETME olmamali
    // ------------------------------------------------------------------

    @Test
    fun `yurt disi mesru hedefler kabul edilir`() {
        // Kullanicinin is gelistirme cografyasi: Suudi Arabistan,
        // Katar, Pakistan.  Tabuk daha once cografi kutu sezgisi
        // yuzunden YANLIS reddediliyordu; bu olcum onu korur.
        val yerler = listOf(
            Triple("Riyad", 24.7136, 46.6753),
            Triple("Tabuk", 28.3835, 36.5662),
            Triple("Doha", 25.2854, 51.5310),
            Triple("Islamabad", 33.6844, 73.0479)
        )
        for ((ad, e, b) in yerler) {
            // Arac ayni sehirde; hedef 3 km kuzeyde.
            val s = GdpKoordinat.dogrula(e + 0.027, b, e, b)
            assertNotNull(
                "$ad yakinindaki mesru hedef kabul edilmeli",
                gecerli(s)
            )
        }
    }

    @Test
    fun `referanssiz cok uzak hedef kabul edilir`() {
        // Referans yoksa yakinlik denetimi yapilamaz; kutu sezgisi
        // KULLANILMAZ cunku yurt disi mesru konumlari reddeder.
        val s = GdpKoordinat.dogrula(24.7136, 46.6753)
        assertNotNull("referanssiz mesru koordinat kabul edilmeli",
            gecerli(s))
    }

    @Test
    fun `menzil disi hedef reddedilir`() {
        // Takas olmasa da 900 km uzaktaki hedef DJI menzilinde degil.
        val s = GdpKoordinat.dogrula(
            48.0000, 32.8200, ankaraEnlem, ankaraBoylam
        )
        val g = gecersiz(s)
        assertNotNull("menzil disi hedef reddedilmeli", g)
        assertTrue(
            "neden 'cok uzak' demeli: ${g!!.neden}",
            g.neden.contains("cok uzak")
        )
    }

    // ------------------------------------------------------------------
    // Mesafe hesabi
    // ------------------------------------------------------------------

    @Test
    fun `mesafe hesabi dogru`() {
        // Ankara -> Istanbul yaklasik 350 km
        val d = GdpKoordinat.mesafeKm(39.97, 32.82, 41.01, 28.98)
        assertTrue("Ankara-Istanbul 300-400 km olmali, bulunan: $d",
            d in 300.0..400.0)
    }

    @Test
    fun `ayni nokta sifir mesafe`() {
        val d = GdpKoordinat.mesafeKm(39.97, 32.82, 39.97, 32.82)
        assertEquals(0.0, d, 1e-9)
    }

    // ------------------------------------------------------------------
    // Kontrol deneyi: olcum gercekten kusur yakaliyor mu
    // ------------------------------------------------------------------

    @Test
    fun `kontrol deneyi takas edilmis cift dogru cifte esit degil`() {
        // Bu olcum, sinavin kendisinin anlamli oldugunu kanitlar:
        // takas edilmis cift ile dogru cift ayni sonucu vermemeli.
        val dogru = GdpKoordinat.dogrula(
            40.0150, 32.8200, ankaraEnlem, ankaraBoylam
        )
        val ters = GdpKoordinat.dogrula(
            32.8200, 40.0150, ankaraEnlem, ankaraBoylam
        )
        assertNotNull("dogru cift gecerli olmali", gecerli(dogru))
        assertNotNull("ters cift gecersiz olmali", gecersiz(ters))
    }

    @Test
    fun `olustur gecersizde null doner`() {
        assertNull(GdpKoordinat.olustur(0.0, 0.0))
        assertNull(GdpKoordinat.olustur(100.0, 32.0))
        assertNotNull(GdpKoordinat.olustur(39.97, 32.82))
    }

    @Test
    fun `sifirMi ve kosegendeMi tutarli`() {
        assertTrue(GdpKoordinat.sifirMi(0.0, 0.0))
        assertFalse(GdpKoordinat.sifirMi(39.97, 32.82))
        assertTrue(GdpKoordinat.kosegendeMi(38.35, 38.31))
        assertFalse(GdpKoordinat.kosegendeMi(39.97, 32.82))
    }
}
