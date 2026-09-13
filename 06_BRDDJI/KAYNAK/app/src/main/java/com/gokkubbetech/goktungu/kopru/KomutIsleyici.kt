package com.gokkubbetech.goktungu.kopru

import com.gokkubbetech.goktungu.dji.DjiKopru
import com.gokkubbetech.goktungu.dji.GorevYonetici
import com.gokkubbetech.goktungu.dji.KmzUretici
import com.gokkubbetech.goktungu.veri.GdpKoordinat
import com.gokkubbetech.goktungu.veri.GdpMesaj
import com.gokkubbetech.goktungu.veri.Gunluk
import org.json.JSONObject

/**
 * Sunucudan gelen GDP komutlarini yurutur ve `yanit` mesaji uretir.
 *
 * ## Koordinat guvencesi
 *
 * `goto` ve `gorev_yukle` komutlarindaki koordinatlar
 * [GdpKoordinat.dogrula] suzgecinden gecer.  Referans olarak aracin
 * ANLIK KONUMU verilir; bu, eksen takasini cografyadan bagimsiz
 * yakalayan en guclu olcuttur (bkz. `BULGU_dji_koordinat.md`).
 *
 * Reddedilen komut sessizce yutulmaz: sunucuya `hata` yaniti ve okunabilir
 * neden doner, boylece pilot haritada neden bir sey olmadigini gorur.
 */
class KomutIsleyici(
    private val dji: DjiKopru,
    private val gorev: GorevYonetici,
    private val gonder: (JSONObject) -> Unit
) {

    /** Varsayilan gorev irtifasi (m), sunucu belirtmezse. */
    private val varsayilanIrtifa = 30.0

    /** Varsayilan seyir hizi (m/s). */
    private val varsayilanHiz = 8.0

    fun isle(k: GdpMesaj.GelenKomut) {
        Gunluk.yaz("KOMUT", "Gelen: ${k.ad} (id=${k.id})")
        try {
            when (k.ad) {
                GdpMesaj.Komut.TAKEOFF -> dji.kalkis { b, m -> yanit(k, b, m) }
                GdpMesaj.Komut.LAND -> dji.inis { b, m -> yanit(k, b, m) }
                GdpMesaj.Komut.RTL -> dji.eveDon { b, m -> yanit(k, b, m) }

                GdpMesaj.Komut.GOTO -> goto(k)
                GdpMesaj.Komut.EV_AYARLA -> evAyarla(k)

                GdpMesaj.Komut.GOREV_YUKLE -> gorevYukle(k)
                GdpMesaj.Komut.GOREV_BASLAT -> gorev.baslat { b, m ->
                    yanit(k, b, m)
                }
                GdpMesaj.Komut.GOREV_DURDUR,
                GdpMesaj.Komut.GOREV_IPTAL -> gorev.durdur { b, m ->
                    yanit(k, b, m)
                }
                GdpMesaj.Komut.GOREV_DURAKLAT -> gorev.duraklat { b, m ->
                    yanit(k, b, m)
                }
                GdpMesaj.Komut.GOREV_DEVAM -> gorev.devam { b, m ->
                    yanit(k, b, m)
                }

                // ARM/DISARM: DJI araclarinda ayri bir kavram degildir;
                // motorlar kalkisla birlikte calisir.  Sessizce "tamam"
                // demek yaniltici olurdu.
                GdpMesaj.Komut.ARM, GdpMesaj.Komut.DISARM -> yanit(
                    k, false,
                    "DJI araclarinda ${k.ad} ayri bir islem degildir; " +
                        "motorlar kalkis/inis ile yonetilir"
                )

                else -> yanit(k, false, "desteklenmeyen komut: ${k.ad}")
            }
        } catch (e: Exception) {
            Gunluk.hata("KOMUT", "${k.ad} istisna: ${e.message}")
            yanit(k, false, "istisna: ${e.message}")
        }
    }

    // ------------------------------------------------------------------
    // goto — kusurun yasadigi yol
    // ------------------------------------------------------------------

    private fun goto(k: GdpMesaj.GelenKomut) {
        val ref = dji.telemetri.value.konum
        if (ref == null) {
            // Referans yoksa yakinlik denetimi yapilamaz.  Komutu
            // reddetmek dogru davranistir: GPS kilidi olmayan araca
            // konum komutu vermek zaten guvenli degildir.
            yanit(k, false,
                "arac konumu bilinmiyor (GPS kilidi yok); hedef " +
                    "dogrulanamadigi icin komut reddedildi")
            return
        }

        when (val s = k.hedefKoordinat(ref)) {
            is GdpKoordinat.Companion.Sonuc.Gecersiz -> {
                // Kusurun kullaniciya gorunur oldugu yer: sessiz sapma
                // yerine acik ret.
                Gunluk.hata("KOMUT", "goto reddedildi: ${s.neden}")
                yanit(k, false, s.neden)
            }

            is GdpKoordinat.Companion.Sonuc.Gecerli -> {
                val hedef = s.koordinat
                val irtifa = k.args.optDouble("alt", varsayilanIrtifa)
                    .let { if (it.isNaN() || it <= 0) varsayilanIrtifa else it }
                val hiz = k.args.optDouble("hiz", varsayilanHiz)
                    .let { if (it.isNaN() || it <= 0) varsayilanHiz else it }

                val km = ref.mesafeKm(hedef)
                Gunluk.yaz("KOMUT",
                    "goto hedef=${hedef.kisa()} irtifa=${irtifa}m " +
                        "uzaklik=%.2f km".format(km))
                if (hedef.belirsiz) {
                    Gunluk.uyari("KOMUT",
                        "Hedef kosegen bolgede (${hedef.kisa()}): olasi " +
                            "eksen takasi ayirt edilemez")
                }

                gorev.tekNoktayaGit(hedef, irtifa, hiz) { b, m ->
                    yanit(k, b, m)
                }
            }
        }
    }

    private fun evAyarla(k: GdpMesaj.GelenKomut) {
        // Alan yoksa "mevcut konumu ev yap" anlamindadir.
        if (!k.args.has("lat") && !k.args.has("lon")) {
            dji.evAyarlaMevcutKonum { b, m -> yanit(k, b, m) }
            return
        }
        val ref = dji.telemetri.value.konum
        when (val s = k.hedefKoordinat(ref)) {
            is GdpKoordinat.Companion.Sonuc.Gecersiz ->
                yanit(k, false, s.neden)
            is GdpKoordinat.Companion.Sonuc.Gecerli ->
                dji.evAyarla(s.koordinat) { b, m -> yanit(k, b, m) }
        }
    }

    // ------------------------------------------------------------------
    // Cok noktali gorev
    // ------------------------------------------------------------------

    private fun gorevYukle(k: GdpMesaj.GelenKomut) {
        val dizi = k.args.optJSONArray("noktalar")
        if (dizi == null || dizi.length() == 0) {
            yanit(k, false, "gorev noktasi yok")
            return
        }
        val ref = dji.telemetri.value.konum
        val noktalar = ArrayList<KmzUretici.Nokta>(dizi.length())

        for (i in 0 until dizi.length()) {
            val n = dizi.optJSONObject(i)
            if (n == null) {
                yanit(k, false, "nokta $i okunamadi")
                return
            }
            if (!n.has("lat") || !n.has("lon")) {
                yanit(k, false, "nokta $i icinde lat/lon alani yok")
                return
            }
            // Her nokta ayni suzgecten gecer.  Referans olarak aracin
            // konumu kullanilir; gorev menzili disi nokta reddedilir.
            val s = GdpKoordinat.dogrula(
                n.optDouble("lat", Double.NaN),
                n.optDouble("lon", Double.NaN),
                ref?.enlem, ref?.boylam
            )
            when (s) {
                is GdpKoordinat.Companion.Sonuc.Gecersiz -> {
                    Gunluk.hata("KOMUT",
                        "gorev noktasi $i reddedildi: ${s.neden}")
                    yanit(k, false, "nokta $i: ${s.neden}")
                    return
                }
                is GdpKoordinat.Companion.Sonuc.Gecerli -> {
                    val irtifa = n.optDouble("alt", varsayilanIrtifa)
                        .let {
                            if (it.isNaN() || it <= 0) varsayilanIrtifa else it
                        }
                    noktalar.add(KmzUretici.Nokta(s.koordinat, irtifa))
                }
            }
        }

        val hiz = k.args.optDouble("hiz", varsayilanHiz)
            .let { if (it.isNaN() || it <= 0) varsayilanHiz else it }

        gorev.gorevYukle(noktalar, hiz) { b, m -> yanit(k, b, m) }
    }

    private fun yanit(k: GdpMesaj.GelenKomut, basarili: Boolean, m: String) {
        gonder(GdpMesaj.yanit(k.id, basarili, m))
    }
}
