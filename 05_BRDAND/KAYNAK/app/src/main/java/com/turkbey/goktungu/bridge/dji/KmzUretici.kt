package com.turkbey.goktungu.bridge.dji

import com.turkbey.goktungu.bridge.veri.GdpKoordinat
import com.turkbey.goktungu.bridge.veri.Gunluk
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * WPMZ (DJI dalga hatti) KMZ gorev dosyasi ureticisi.
 *
 * ## Neden gerekli
 *
 * MSDK v5'te "su noktaya git" diye tek atislik bir komut YOKTUR.
 * `WaypointMissionManager` yalnizca KMZ dosyasi kabul eder:
 * `pushKMZFileToAircraft(yol, ...)` ardindan `startMission(ad, ...)`.
 *
 * Bu yuzden GDP `goto` komutu **tek noktali bir KMZ** uretilerek
 * gerceklestirilir.  Ayni uretici cok noktali `gorev_yukle` komutunu da
 * karsilar.
 *
 * ## KMZ yapisi (WPMZ 1.0.6)
 *
 * ```
 * wpmz/template.kml   -> gorev sablonu (dalga hatti tanimi)
 * wpmz/waylines.wpml  -> yurutulecek dalga hatti
 * ```
 *
 * ## KRITIK: koordinat sirasi
 *
 * WPML `<coordinates>` ogesi **KML sozlesmesini** izler:
 * `boylam,enlem` — yani GDP'nin tersi.  Bu, enlem/boylam takas
 * kusurunun bir baska tuzagidir.
 *
 * Sira burada TEK yerde, [nokta] islevinde yazilir ve olcumle
 * dogrulanir.  Cagiranlar [GdpKoordinat] gecirir; ham cift gecemez.
 */
object KmzUretici {

    /** WPMZ surumu; DJI ornek projeleri 1.0.6 kullanir. */
    const val WPMZ_SURUM = "1.0.6"

    /**
     * Ucus bitiminde davranis.
     * `goHome`: eve don, `noAction`: son noktada bekle,
     * `autoLand`: bulundugu yerde in.
     */
    enum class BitisEylemi(val wpml: String) {
        EVE_DON("goHome"),
        BEKLE("noAction"),
        IN("autoLand")
    }

    /**
     * Bir gorev noktasi.
     *
     * @param konum Dogrulanmis koordinat.  Ham `Double` cifti
     *   KABUL EDILMEZ; boylece cagri yerinde eksen hatasi olanaksizdir.
     * @param irtifa Kalkis noktasina gore irtifa (m).
     */
    data class Nokta(
        val konum: GdpKoordinat,
        val irtifa: Double
    )

    /**
     * KMZ dosyasi uretir.
     *
     * @param dizin Dosyanin yazilacagi dizin (uygulama ozel deposu).
     * @param ad Dosya adi (uzantisiz).  `startMission` bu adi ister.
     * @param noktalar En az bir nokta.
     * @param hiz Seyir hizi (m/s).
     * @return Uretilen dosya, veya girdi gecersizse `null`.
     */
    fun uret(
        dizin: File,
        ad: String,
        noktalar: List<Nokta>,
        hiz: Double,
        bitis: BitisEylemi = BitisEylemi.BEKLE
    ): File? {
        if (noktalar.isEmpty()) {
            Gunluk.hata("KMZ", "Gorev noktasi yok; KMZ uretilemez")
            return null
        }
        // Belirsiz (kosegen bolge) koordinatlar gunluklenir: takas
        // tespit edilemedigi icin pilot bilmeli.
        noktalar.filter { it.konum.belirsiz }.forEach {
            Gunluk.uyari("KMZ", "Kosegen bolge noktasi " +
                "(${it.konum.kisa()}): olasi eksen takasi ayirt " +
                "edilemez, konumu haritada dogrulayin")
        }

        val guvenliHiz = hiz.coerceIn(1.0, 15.0)
        val sablon = sablonKml(noktalar, guvenliHiz, bitis)
        val hatlar = waylinesWpml(noktalar, guvenliHiz, bitis)

        val dosya = File(dizin, "$ad.kmz")
        return try {
            ZipOutputStream(FileOutputStream(dosya)).use { z ->
                z.putNextEntry(ZipEntry("wpmz/template.kml"))
                z.write(sablon.toByteArray(Charsets.UTF_8))
                z.closeEntry()
                z.putNextEntry(ZipEntry("wpmz/waylines.wpml"))
                z.write(hatlar.toByteArray(Charsets.UTF_8))
                z.closeEntry()
            }
            Gunluk.yaz("KMZ", "Gorev uretildi: ${dosya.name} " +
                "(${noktalar.size} nokta, ${guvenliHiz} m/s)")
            dosya
        } catch (e: Exception) {
            Gunluk.hata("KMZ", "KMZ yazilamadi: ${e.message}")
            null
        }
    }

    /**
     * KML/WPML koordinat ogesi.
     *
     * KRITIK: KML sirasi **boylam,enlem** — GDP'nin tersi.  Bu, eksen
     * sirasinin yazildigi TEK yerdir.
     */
    private fun nokta(k: GdpKoordinat): String =
        "${k.boylam},${k.enlem}"

    private fun sablonKml(
        noktalar: List<Nokta>,
        hiz: Double,
        bitis: BitisEylemi
    ): String {
        val ogeler = noktalar.mapIndexed { i, n ->
            """
        <Placemark>
          <Point>
            <coordinates>${nokta(n.konum)}</coordinates>
          </Point>
          <wpml:index>$i</wpml:index>
          <wpml:executeHeight>${n.irtifa}</wpml:executeHeight>
          <wpml:waypointSpeed>$hiz</wpml:waypointSpeed>
          <wpml:waypointHeadingParam>
            <wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode>
          </wpml:waypointHeadingParam>
          <wpml:waypointTurnParam>
            <wpml:waypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:waypointTurnMode>
            <wpml:waypointTurnDampingDist>0</wpml:waypointTurnDampingDist>
          </wpml:waypointTurnParam>
        </Placemark>"""
        }.joinToString("")

        return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/$WPMZ_SURUM">
  <Document>
    <wpml:author>GOKTUNGU</wpml:author>
    <wpml:createTime>${System.currentTimeMillis()}</wpml:createTime>
    <wpml:updateTime>${System.currentTimeMillis()}</wpml:updateTime>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>${bitis.wpml}</wpml:finishAction>
      <wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>20</wpml:takeOffSecurityHeight>
      <wpml:globalTransitionalSpeed>$hiz</wpml:globalTransitionalSpeed>
      <wpml:droneInfo>
        <wpml:droneEnumValue>68</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>0</wpml:droneSubEnumValue>
      </wpml:droneInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>waypoint</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>relativeToStartPoint</wpml:heightMode>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>$hiz</wpml:autoFlightSpeed>
      <wpml:globalHeight>${noktalar.first().irtifa}</wpml:globalHeight>$ogeler
    </Folder>
  </Document>
</kml>
"""
    }

    private fun waylinesWpml(
        noktalar: List<Nokta>,
        hiz: Double,
        bitis: BitisEylemi
    ): String {
        val ogeler = noktalar.mapIndexed { i, n ->
            """
        <Placemark>
          <Point>
            <coordinates>${nokta(n.konum)}</coordinates>
          </Point>
          <wpml:index>$i</wpml:index>
          <wpml:executeHeight>${n.irtifa}</wpml:executeHeight>
          <wpml:waypointSpeed>$hiz</wpml:waypointSpeed>
          <wpml:waypointHeadingParam>
            <wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode>
            <wpml:waypointHeadingPathMode>followBadArc</wpml:waypointHeadingPathMode>
          </wpml:waypointHeadingParam>
          <wpml:waypointTurnParam>
            <wpml:waypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:waypointTurnMode>
            <wpml:waypointTurnDampingDist>0</wpml:waypointTurnDampingDist>
          </wpml:waypointTurnParam>
          <wpml:useStraightLine>1</wpml:useStraightLine>
        </Placemark>"""
        }.joinToString("")

        return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/$WPMZ_SURUM">
  <Document>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>${bitis.wpml}</wpml:finishAction>
      <wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>20</wpml:takeOffSecurityHeight>
      <wpml:globalTransitionalSpeed>$hiz</wpml:globalTransitionalSpeed>
      <wpml:droneInfo>
        <wpml:droneEnumValue>68</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>0</wpml:droneSubEnumValue>
      </wpml:droneInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateId>0</wpml:templateId>
      <wpml:executeHeightMode>relativeToStartPoint</wpml:executeHeightMode>
      <wpml:waylineId>0</wpml:waylineId>
      <wpml:autoFlightSpeed>$hiz</wpml:autoFlightSpeed>$ogeler
    </Folder>
  </Document>
</kml>
"""
    }
}
