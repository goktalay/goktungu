package com.turkbey.goktungu.bridge.betaflight

import org.json.JSONArray
import org.json.JSONObject

/**
 * GOKTUNGU — BetaFlight MSP v1 SALT-OKUNUR tanilama surucusu (Kotlin).
 *
 * Masaustu/GRCOFFANDR `goktungu/betaflight_msp.py` modulunun Kotlin
 * portudur. MAVLink'e veri donusturmez ve ucus kumandasi saglamaz.
 * Yalniz [IZINLI_SORGU_KOMUTLARI] listesindeki BOS-YUK sorgular
 * gonderilebilir; MSP_SET_*, MSP_REBOOT, MSP_SET_RAW_RC, motor, ARM,
 * kalibrasyon ve CLI bu modulde TANIMLI DEGILDIR ve uretilemez.
 *
 * MSP v1 referansi:
 * https://betaflight.com/docs/development/MSP-Protocol-Reference-Dev
 */
object Msp {

    // Salt-okunur sorgular. Sayisal kimlikler MSP v1 komut baytidir;
    // izin listesi hem kodlayicida hem oturumda ZORUNLU denetlenir.
    const val MSP_API_VERSION = 1
    const val MSP_FC_VARIANT = 2
    const val MSP_FC_VERSION = 3
    const val MSP_BOARD_INFO = 4
    const val MSP_BUILD_INFO = 5
    const val MSP_NAME = 10
    const val MSP_STATUS = 101
    const val MSP_RAW_IMU = 102
    const val MSP_RC = 105
    const val MSP_ATTITUDE = 108
    const val MSP_ALTITUDE = 109
    const val MSP_ANALOG = 110
    const val MSP_BATTERY_STATE = 130
    const val MSP_UID = 160

    val IZINLI_SORGU_KOMUTLARI: Set<Int> = setOf(
        MSP_API_VERSION, MSP_FC_VARIANT, MSP_FC_VERSION, MSP_BOARD_INFO,
        MSP_BUILD_INFO, MSP_NAME, MSP_UID, MSP_STATUS, MSP_RAW_IMU, MSP_RC,
        MSP_ATTITUDE, MSP_ALTITUDE, MSP_ANALOG, MSP_BATTERY_STATE
    )

    /** Baglantida bir kez sorulan kimlik/tanilama sorgulari. */
    val TANILAMA_SORGULARI: List<Int> = listOf(
        MSP_API_VERSION, MSP_FC_VARIANT, MSP_FC_VERSION, MSP_BOARD_INFO,
        MSP_BUILD_INFO, MSP_NAME, MSP_UID
    )

    /** 1 Hz tekrarlanan canli telemetri sorgulari. */
    val CANLI_SORGULAR: List<Int> = listOf(
        MSP_STATUS, MSP_RAW_IMU, MSP_ATTITUDE, MSP_ALTITUDE, MSP_ANALOG,
        MSP_BATTERY_STATE
    )

    val KOMUT_ADLARI: Map<Int, String> = mapOf(
        MSP_API_VERSION to "API_VERSION", MSP_FC_VARIANT to "FC_VARIANT",
        MSP_FC_VERSION to "FC_VERSION", MSP_BOARD_INFO to "BOARD_INFO",
        MSP_BUILD_INFO to "BUILD_INFO", MSP_NAME to "NAME", MSP_UID to "UID",
        MSP_STATUS to "STATUS", MSP_RAW_IMU to "RAW_IMU", MSP_RC to "RC",
        MSP_ATTITUDE to "ATTITUDE", MSP_ALTITUDE to "ALTITUDE",
        MSP_ANALOG to "ANALOG", MSP_BATTERY_STATE to "BATTERY_STATE"
    )

    fun komutAdi(komut: Int): String = KOMUT_ADLARI[komut] ?: komut.toString()

    /**
     * Yalniz BOS-YUK MSP v1 sorgu cercevesi uretir.
     *
     * Bu kodlayici kasitli olarak veri yuku ALMAZ; boylece MSP yazma
     * komutlari ya da ayar/motor/RC icerigi bu modulden uretilemez.
     *
     * @throws SecurityException komut izin listesinde degilse.
     */
    fun mspV1Sorgu(komut: Int): ByteArray {
        if (komut !in IZINLI_SORGU_KOMUTLARI) {
            throw SecurityException("Bu MSP komutu salt-okunur izin listesinde degil: $komut")
        }
        // $M< + payload_size(0) + command + xor(size, command)
        val cs = (0 xor komut) and 0xFF
        return byteArrayOf(
            '$'.code.toByte(), 'M'.code.toByte(), '<'.code.toByte(),
            0, komut.toByte(), cs.toByte()
        )
    }

    private fun metin(veri: ByteArray): String {
        val son = veri.indexOf(0.toByte()).let { if (it < 0) veri.size else it }
        return String(veri, 0, son, Charsets.US_ASCII).trim()
    }

    private fun u16(v: ByteArray, o: Int): Int? =
        if (v.size < o + 2) null
        else (v[o].toInt() and 0xFF) or ((v[o + 1].toInt() and 0xFF) shl 8)

    private fun i16(v: ByteArray, o: Int): Int? {
        val u = u16(v, o) ?: return null
        return if (u >= 0x8000) u - 0x10000 else u
    }

    private fun i32(v: ByteArray, o: Int): Int? {
        if (v.size < o + 4) return null
        return (v[o].toInt() and 0xFF) or ((v[o + 1].toInt() and 0xFF) shl 8) or
            ((v[o + 2].toInt() and 0xFF) shl 16) or ((v[o + 3].toInt() and 0xFF) shl 24)
    }

    private fun u32(v: ByteArray, o: Int): Long? {
        if (v.size < o + 4) return null
        return (v[o].toLong() and 0xFF) or ((v[o + 1].toLong() and 0xFF) shl 8) or
            ((v[o + 2].toLong() and 0xFF) shl 16) or ((v[o + 3].toLong() and 0xFF) shl 24)
    }

    /**
     * Izinli MSP yanitini kucuk, seri hale getirilebilir tani sozlugune
     * cevirir. Bilinmeyen/uzatilmis alanlar yok sayilir; bir ucus komutu
     * ya da MAVLink telemetrisi URETMEZ.
     */
    fun mspVeriCoz(komut: Int, yuk: ByteArray): JSONObject {
        val ad = komutAdi(komut)
        val s = JSONObject()
        if (komut !in IZINLI_SORGU_KOMUTLARI) {
            return s.put("ad", ad).put("bilinmiyor", true)
        }
        s.put("ad", ad)
        when {
            komut == MSP_API_VERSION && yuk.size >= 3 -> {
                s.put("protokol", yuk[0].toInt() and 0xFF)
                s.put("api", "${yuk[1].toInt() and 0xFF}.${yuk[2].toInt() and 0xFF}")
            }
            komut == MSP_FC_VARIANT ->
                s.put("fc_turu", metin(yuk.copyOfRange(0, minOf(4, yuk.size))))
            komut == MSP_FC_VERSION && yuk.size >= 3 ->
                s.put(
                    "fc_surumu",
                    "${yuk[0].toInt() and 0xFF}.${yuk[1].toInt() and 0xFF}." +
                        "${yuk[2].toInt() and 0xFF}"
                )
            komut == MSP_BOARD_INFO -> {
                s.put("kart", metin(yuk.copyOfRange(0, minOf(4, yuk.size))))
                if (yuk.size >= 6) s.put("kart_surumu", u16(yuk, 4))
                if (yuk.size > 6) s.put("hedef", metin(yuk.copyOfRange(6, yuk.size)))
            }
            komut == MSP_BUILD_INFO -> s.put("yapi", metin(yuk))
            komut == MSP_NAME -> s.put("ad_metin", metin(yuk))
            komut == MSP_UID && yuk.size >= 12 -> {
                val p = intArrayOf(0, 4, 8).joinToString("-") {
                    "%08x".format(u32(yuk, it) ?: 0L)
                }
                s.put("uid", p)
            }
            komut == MSP_STATUS -> {
                s.put("dovus_dongusu_us", u16(yuk, 0))
                s.put("i2c_hata", u16(yuk, 2))
                s.put("sensor_maskesi", u16(yuk, 4))
                s.put("ucus_modu_maskesi", u32(yuk, 6))
                s.put("profil", if (yuk.size > 10) yuk[10].toInt() and 0xFF else JSONObject.NULL)
            }
            komut == MSP_RAW_IMU && yuk.size >= 18 -> {
                s.put(
                    "imu",
                    JSONObject()
                        .put("ivme", JSONArray(listOf(i16(yuk, 0), i16(yuk, 2), i16(yuk, 4))))
                        .put("gyro", JSONArray(listOf(i16(yuk, 6), i16(yuk, 8), i16(yuk, 10))))
                        .put(
                            "manyeto",
                            JSONArray(listOf(i16(yuk, 12), i16(yuk, 14), i16(yuk, 16)))
                        )
                )
            }
            komut == MSP_RC && yuk.size >= 2 -> {
                val kanallar = JSONArray()
                var i = 0
                while (i < yuk.size - 1) {
                    kanallar.put(u16(yuk, i)); i += 2
                }
                s.put("kanallar", kanallar)
            }
            komut == MSP_ATTITUDE && yuk.size >= 6 -> {
                s.put(
                    "tutum",
                    JSONObject()
                        .put("roll_deg", (i16(yuk, 0) ?: 0) / 10.0)
                        .put("pitch_deg", (i16(yuk, 2) ?: 0) / 10.0)
                        .put("heading_deg", i16(yuk, 4))
                )
            }
            komut == MSP_ALTITUDE && yuk.size >= 4 -> {
                s.put("irtifa_cm", i32(yuk, 0))
                if (yuk.size >= 6) s.put("dikey_hiz_cm_s", i16(yuk, 4))
            }
            komut == MSP_ANALOG -> {
                if (yuk.isNotEmpty()) s.put("gerilim_v", (yuk[0].toInt() and 0xFF) / 10.0)
                if (yuk.size >= 3) s.put("tuketim_mah", u16(yuk, 1))
                if (yuk.size >= 5) s.put("rssi", u16(yuk, 3))
            }
            komut == MSP_BATTERY_STATE -> {
                if (yuk.isNotEmpty()) s.put("hucre_sayisi", yuk[0].toInt() and 0xFF)
                if (yuk.size >= 3) s.put("kapasite_mah", u16(yuk, 1))
                if (yuk.size >= 4) s.put("durum", yuk[3].toInt() and 0xFF)
            }
            else -> s.put("ham_hex", yuk.copyOfRange(0, minOf(64, yuk.size)).joinToString("") {
                "%02x".format(it)
            })
        }
        return s
    }
}

/**
 * Parcali seri okumada MSP v1 yanitlarini checksum ile cozer.
 *
 * Yalniz `$M>` (basari) ve `$M!` (hata) yanitlari kabul edilir. Girdi
 * yonu `$M<` gorulurse atilir: yerel seri hattindan komut enjekte
 * edilmesini isleme katmanina TASIMAMAK icin bu yon yanit sayilmaz.
 */
class MspV1Cozucu {

    private val tampon = ArrayList<Byte>(512)

    var hataliChecksum = 0
        private set
    var gecersizCerceve = 0
        private set

    /** `Triple(komut, yuk, hataYaniti)` listesi doner. */
    fun besle(veri: ByteArray?): List<Triple<Int, ByteArray, Boolean>> {
        if (veri != null && veri.isNotEmpty()) {
            for (b in veri) tampon.add(b)
        }
        val sonuc = ArrayList<Triple<Int, ByteArray, Boolean>>()
        while (true) {
            val bas = basBul()
            if (bas < 0) {
                // Baslik yoksa yalniz son iki bayti tut (olasi "$M").
                if (tampon.size > 2) {
                    val sonIki = tampon.subList(tampon.size - 2, tampon.size).toList()
                    tampon.clear(); tampon.addAll(sonIki)
                }
                break
            }
            if (bas > 0) repeat(bas) { tampon.removeAt(0) }
            if (tampon.size < 5) break
            val yon = tampon[2].toInt() and 0xFF
            val boy = tampon[3].toInt() and 0xFF
            val komut = tampon[4].toInt() and 0xFF
            if ((yon != '>'.code && yon != '!'.code) || boy > AZAMI_YUK) {
                gecersizCerceve++
                tampon.removeAt(0)
                continue
            }
            val toplam = 6 + boy
            if (tampon.size < toplam) break
            val paket = ByteArray(toplam) { tampon[it] }
            repeat(toplam) { tampon.removeAt(0) }
            var hesap = 0
            for (i in 3 until toplam - 1) hesap = hesap xor (paket[i].toInt() and 0xFF)
            if (hesap != (paket[toplam - 1].toInt() and 0xFF)) {
                hataliChecksum++
                continue
            }
            val yuk = paket.copyOfRange(5, toplam - 1)
            sonuc.add(Triple(komut, yuk, yon == '!'.code))
        }
        return sonuc
    }

    /** Tamponda "$M" baslangicini bulur (yoksa -1). */
    private fun basBul(): Int {
        var i = 0
        while (i < tampon.size - 1) {
            if (tampon[i].toInt() == '$'.code && tampon[i + 1].toInt() == 'M'.code) return i
            i++
        }
        return -1
    }

    companion object {
        const val AZAMI_YUK = 256
    }
}
