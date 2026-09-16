package com.turkbey.goktungumav.mavlink

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Gecen MAVLink cercevelerinden **yalniz gosterim** icin bilgi okur.
 *
 * ## SALT OKUMA sozlesmesi
 *
 * Bu sinif akisa DOKUNMAZ.  Cerceve gecerken bir kopyasi buraya
 * verilir; burada cikan hicbir sonuc boruya geri yazilmaz.  Amac
 * yalnizca telefon ekraninda "arac bagli, GPS kilidi var, batarya
 * %78" gibi bir durum gostermektir.
 *
 * Bu ayrim onemli: eger gozlemci akisi degistirebilseydi kopru artik
 * seffaf olmaz ve yeni MAVLink mesajlari icin kod guncellemesi
 * gerekirdi.
 *
 * ## Neden yalniz uc mesaj
 *
 * `HEARTBEAT` (0), `SYS_STATUS` (1), `GLOBAL_POSITION_INT` (33) her
 * ArduPilot/PX4 kurulumunda bulunur ve govde duzenleri **kararlidir**
 * (MAVLink alan sirasi surumler arasi degismez; yeni alanlar yalniz
 * SONA eklenir).  Bu yuzden sabit uzaklik okumasi guvenlidir.
 *
 * ## Koordinat sozlesmesi (KRITIK)
 *
 * `GLOBAL_POSITION_INT.lat` ve `.lon` **int32, derece x 1e7**.
 * Donusum bu dosyada **tek noktada** yapilir ([MavKonum.olustur]) ve
 * sonuc adlandirilmis alanlarla (`enlem`, `boylam`) tasinir.  Sirali
 * cift KULLANILMAZ.
 *
 * Gerekce: DJI koprusunde enlem/boylam ters calisma kusuru,
 * koordinatlarin siraya bagli tasinmasindan dogmustu.  Adlandirilmis
 * alan, sira hatasini yapisal olarak olanaksiz kilar.
 */
class MavGozlemci {

    data class MavKonum(val enlem: Double, val boylam: Double) {
        companion object {
            /**
             * MAVLink olcegindeki (`1e7`) tam sayilardan konum uretir.
             *
             * **Tek donusum noktasi.**  Baska hicbir yerde `1e7`
             * bolmesi yapilmaz.
             */
            fun olustur(latE7: Int, lonE7: Int): MavKonum? {
                val enlem = latE7 / 1.0e7
                val boylam = lonE7 / 1.0e7
                // (0,0) gecerli bir konum degil: GPS kilidi yokken
                // ArduPilot sifir gonderir.  Sifiri gostermek araci
                // Gine Korfezi'nde isaretlerdi.
                if (enlem == 0.0 && boylam == 0.0) return null
                if (enlem < -90.0 || enlem > 90.0) return null
                if (boylam < -180.0 || boylam > 180.0) return null
                return MavKonum(enlem, boylam)
            }
        }
    }

    data class Durum(
        val aracVar: Boolean = false,
        val sysid: Int = 0,
        val compid: Int = 0,
        val armed: Boolean = false,
        val ucusKipi: Long = -1,
        val aracTuru: Int = -1,
        val otopilot: Int = -1,
        val konum: MavKonum? = null,
        val altRel: Double? = null,
        val heading: Double? = null,
        val bataryaPct: Int? = null,
        val bataryaV: Double? = null,
        val cerceveSayisi: Long = 0
    )

    private val _durum = MutableStateFlow(Durum())
    val durum: StateFlow<Durum> = _durum.asStateFlow()

    /** Son cerceve zamani; arac kopmasini saptamak icin. */
    @Volatile
    private var sonCerceveMs = 0L

    /**
     * Bir MAVLink cercevesini gozlemler.  Cerceve **degistirilmez**.
     */
    fun gozlemle(cerceve: ByteArray) {
        sonCerceveMs = System.currentTimeMillis()
        val d = _durum.value
        var y = d.copy(
            aracVar = true,
            cerceveSayisi = d.cerceveSayisi + 1
        )

        val v2 = cerceve.isNotEmpty() && cerceve[0] == MavCerceve.STX_V2
        // Govde baslangici ve mesaj kimligi surume gore farkli yerde.
        val govdeBas: Int
        val msgId: Int
        val sysid: Int
        val compid: Int
        if (v2) {
            if (cerceve.size < MavCerceve.V2_EK) return
            sysid = cerceve[5].toInt() and 0xFF
            compid = cerceve[6].toInt() and 0xFF
            msgId = (cerceve[7].toInt() and 0xFF) or
                ((cerceve[8].toInt() and 0xFF) shl 8) or
                ((cerceve[9].toInt() and 0xFF) shl 16)
            govdeBas = 10
        } else {
            if (cerceve.size < MavCerceve.V1_EK) return
            sysid = cerceve[3].toInt() and 0xFF
            compid = cerceve[4].toInt() and 0xFF
            msgId = cerceve[5].toInt() and 0xFF
            govdeBas = 6
        }

        val govdeUzunluk = cerceve[1].toInt() and 0xFF
        // Yalniz otopilot bileseninin (1) mesajlari durum uretir;
        // yer istasyonu ve kamera bilesenlerinin HEARTBEAT'i araci
        // temsil etmez.
        if (compid != KOMP_OTOPILOT && msgId == ID_HEARTBEAT) return

        when (msgId) {
            ID_HEARTBEAT -> {
                // HEARTBEAT: custom_mode(u32) type(u8) autopilot(u8)
                //            base_mode(u8) system_status(u8) version(u8)
                if (govdeUzunluk < 9) return
                val kip = u32(cerceve, govdeBas)
                val tur = cerceve[govdeBas + 4].toInt() and 0xFF
                val otop = cerceve[govdeBas + 5].toInt() and 0xFF
                val temelKip = cerceve[govdeBas + 6].toInt() and 0xFF
                y = y.copy(
                    sysid = sysid,
                    compid = compid,
                    ucusKipi = kip,
                    aracTuru = tur,
                    otopilot = otop,
                    // MAV_MODE_FLAG_SAFETY_ARMED = 0x80
                    armed = (temelKip and 0x80) != 0
                )
            }
            ID_SYS_STATUS -> {
                // SYS_STATUS govdesi: onboard_control_sensors_*(3xu32)
                // load(u16) voltage_battery(u16) current_battery(i16)
                // ... battery_remaining(i8) 30. baytta
                if (govdeUzunluk < 31) return
                val mv = u16(cerceve, govdeBas + 14)
                val kalan = cerceve[govdeBas + 30].toInt()   // isaretli
                y = y.copy(
                    bataryaV = if (mv > 0) mv / 1000.0 else null,
                    bataryaPct = if (kalan in 0..100) kalan else null
                )
            }
            ID_GLOBAL_POSITION_INT -> {
                // time_boot_ms(u32) lat(i32) lon(i32) alt(i32)
                // relative_alt(i32) vx vy vz(i16 x3) hdg(u16)
                if (govdeUzunluk < 28) return
                val latE7 = i32(cerceve, govdeBas + 4)
                val lonE7 = i32(cerceve, govdeBas + 8)
                val relMm = i32(cerceve, govdeBas + 16)
                val hdg = u16(cerceve, govdeBas + 26)
                y = y.copy(
                    konum = MavKonum.olustur(latE7, lonE7) ?: y.konum,
                    altRel = relMm / 1000.0,
                    // hdg 65535 = bilinmiyor
                    heading = if (hdg != 65535) hdg / 100.0 else y.heading
                )
            }
        }
        _durum.value = y
    }

    /**
     * Arac kopmasini saptar.  Cerceve akisi [ZAMAN_ASIMI_MS] boyunca
     * durursa arac yok sayilir.
     */
    fun zamanAsimiDenetle() {
        val d = _durum.value
        if (!d.aracVar) return
        if (System.currentTimeMillis() - sonCerceveMs > ZAMAN_ASIMI_MS) {
            _durum.value = Durum(cerceveSayisi = d.cerceveSayisi)
        }
    }

    fun sifirla() {
        _durum.value = Durum()
        sonCerceveMs = 0L
    }

    /** ArduPilot ucus kipi adi (kopter).  Yalniz gosterim icin. */
    fun kipAdi(): String {
        val d = _durum.value
        if (!d.aracVar || d.ucusKipi < 0) return ""
        return KOPTER_KIPLERI[d.ucusKipi.toInt()] ?: "KIP ${d.ucusKipi}"
    }

    private fun u16(b: ByteArray, i: Int): Int =
        (b[i].toInt() and 0xFF) or ((b[i + 1].toInt() and 0xFF) shl 8)

    private fun u32(b: ByteArray, i: Int): Long =
        (b[i].toLong() and 0xFF) or
            ((b[i + 1].toLong() and 0xFF) shl 8) or
            ((b[i + 2].toLong() and 0xFF) shl 16) or
            ((b[i + 3].toLong() and 0xFF) shl 24)

    private fun i32(b: ByteArray, i: Int): Int =
        (b[i].toInt() and 0xFF) or
            ((b[i + 1].toInt() and 0xFF) shl 8) or
            ((b[i + 2].toInt() and 0xFF) shl 16) or
            ((b[i + 3].toInt() and 0xFF) shl 24)

    companion object {
        const val ID_HEARTBEAT = 0
        const val ID_SYS_STATUS = 1
        const val ID_GLOBAL_POSITION_INT = 33

        /** `MAV_COMP_ID_AUTOPILOT1` */
        const val KOMP_OTOPILOT = 1

        /** Bu sureden uzun sessizlik arac koptu demektir. */
        const val ZAMAN_ASIMI_MS = 4000L

        /** ArduCopter ucus kipleri (gosterim icin). */
        val KOPTER_KIPLERI = mapOf(
            0 to "STABILIZE", 1 to "ACRO", 2 to "ALT_HOLD", 3 to "AUTO",
            4 to "GUIDED", 5 to "LOITER", 6 to "RTL", 7 to "CIRCLE",
            9 to "LAND", 11 to "DRIFT", 13 to "SPORT", 14 to "FLIP",
            15 to "AUTOTUNE", 16 to "POSHOLD", 17 to "BRAKE",
            18 to "THROW", 19 to "AVOID_ADSB", 20 to "GUIDED_NOGPS",
            21 to "SMART_RTL", 22 to "FLOWHOLD", 23 to "FOLLOW",
            24 to "ZIGZAG", 25 to "SYSTEMID", 26 to "AUTOROTATE",
            27 to "AUTO_RTL"
        )
    }
}
