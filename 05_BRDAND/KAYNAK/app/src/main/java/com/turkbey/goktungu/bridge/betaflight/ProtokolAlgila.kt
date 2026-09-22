package com.turkbey.goktungu.bridge.betaflight

import android.hardware.usb.UsbDevice
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import org.json.JSONObject

/**
 * GOKTUNGU — Seri otomatik MAVLink veya MSP algilayici (Kotlin port).
 *
 * `goktungu/protokol_algilama.py` modulunun Kotlin portudur. Bir seri
 * portu kisa sureligine acar; once HICBIR veri iletmeden gecerli CRC'li
 * MAVLink HEARTBEAT dinler. Bu kanit yoksa YALNIZ BetaFlight'in
 * salt-okunur `MSP_API_VERSION` sorgusunu gonderir. ARM, motor, RC,
 * yapilandirma, reboot, CLI veya baska bir MSP/MAVLink komutu URETMEZ.
 */
object ProtokolAlgila {

    private const val MAVLINK_HEARTBEAT = 0
    private const val MAVLINK_HEARTBEAT_CRC_EXTRA = 50

    private fun x25Bayt(crc: Int, bayt: Int): Int {
        var tmp = (bayt xor (crc and 0xFF)) and 0xFF
        tmp = (tmp xor ((tmp shl 4) and 0xFF)) and 0xFF
        return ((crc shr 8) xor (tmp shl 8) xor (tmp shl 3) xor (tmp shr 4)) and 0xFFFF
    }

    private fun x25(veri: ByteArray, bas: Int, son: Int, extra: Int): Int {
        var crc = 0xFFFF
        for (i in bas until son) crc = x25Bayt(crc, veri[i].toInt() and 0xFF)
        return x25Bayt(crc, extra)
    }

    /**
     * Tampondaki gecerli MAVLink v1/v2 HEARTBEAT cercevesini bulur.
     * Yalniz mesaj kimligi 0 ve dogrulanmis CRC kabul edilir; rastgele
     * seri gurultusu yanlis ArduPilot sonucu uretemez.
     */
    fun mavlinkHeartbeatVarMi(tampon: ByteArray): Boolean {
        var i = 0
        val n = tampon.size
        while (i < n) {
            val stx = tampon[i].toInt() and 0xFF
            if (stx != 0xFE && stx != 0xFD) {
                i++; continue
            }
            if (stx == 0xFE) {
                if (n - i < 8) break
                val yukBoy = tampon[i + 1].toInt() and 0xFF
                val toplam = 8 + yukBoy
                if (n - i < toplam) break
                val mesajId = tampon[i + 5].toInt() and 0xFF
                val crcOfset = i + 6 + yukBoy
                val crcAlinan = (tampon[crcOfset].toInt() and 0xFF) or
                    ((tampon[crcOfset + 1].toInt() and 0xFF) shl 8)
                if (mesajId == MAVLINK_HEARTBEAT &&
                    x25(tampon, i + 1, i + 6 + yukBoy, MAVLINK_HEARTBEAT_CRC_EXTRA) == crcAlinan
                ) return true
                i += toplam
                continue
            }
            // MAVLink v2: STX, 9 bayt baslik, yuk, CRC ve imzaliysa 13 bayt imza.
            if (n - i < 12) break
            val yukBoy = tampon[i + 1].toInt() and 0xFF
            val uyumsuz = tampon[i + 2].toInt() and 0xFF
            val temel = 12 + yukBoy
            val toplam = temel + (if (uyumsuz and 0x01 != 0) 13 else 0)
            if (n - i < toplam) break
            val mesajId = (tampon[i + 7].toInt() and 0xFF) or
                ((tampon[i + 8].toInt() and 0xFF) shl 8) or
                ((tampon[i + 9].toInt() and 0xFF) shl 16)
            val crcOfset = i + 10 + yukBoy
            val crcAlinan = (tampon[crcOfset].toInt() and 0xFF) or
                ((tampon[crcOfset + 1].toInt() and 0xFF) shl 8)
            if (mesajId == MAVLINK_HEARTBEAT &&
                x25(tampon, i + 1, i + 10 + yukBoy, MAVLINK_HEARTBEAT_CRC_EXTRA) == crcAlinan
            ) return true
            i += toplam
        }
        return false
    }

    /**
     * Seri baglantinin ucus yazilimini guvenli bicimde belirler. Donus
     * `protokol` alani yalniz `ardupilot`, `betaflight` veya
     * `bilinmiyor` tasir. Port, sonuc ne olursa olsun kapatilir.
     */
    fun seriProtokolAlgila(
        usb: UsbSeri,
        cihaz: UsbDevice,
        baud: Int,
        mavlinkSureMs: Long = 2500,
        mspSureMs: Long = 1200
    ): JSONObject {
        val hata = usb.ac(cihaz, baud)
        if (hata != null) {
            return JSONObject().put("tamam", false).put("protokol", "bilinmiyor")
                .put("hata", "Seri port acilamadi: $hata")
        }
        try {
            val tampon = ArrayList<Byte>(4096)
            val gecici = ByteArray(512)
            var son = System.currentTimeMillis() + maxOf(200, mavlinkSureMs)
            while (System.currentTimeMillis() < son) {
                val k = usb.oku(gecici)
                if (k > 0) {
                    for (j in 0 until k) tampon.add(gecici[j])
                    if (mavlinkHeartbeatVarMi(tampon.toByteArray())) {
                        return JSONObject().put("tamam", true).put("protokol", "ardupilot")
                            .put("kanit", "mavlink_heartbeat").put("baud", baud)
                    }
                }
            }
            // MAVLink kaniti yoksa yalniz MSP API_VERSION sorgusu.
            val sorgu = Msp.mspV1Sorgu(Msp.MSP_API_VERSION)
            if (!usb.yaz(sorgu, sorgu.size)) {
                return JSONObject().put("tamam", false).put("protokol", "bilinmiyor")
                    .put("hata", "MSP API_VERSION sorgusu gonderilemedi")
            }
            val cozucu = MspV1Cozucu()
            son = System.currentTimeMillis() + maxOf(200, mspSureMs)
            while (System.currentTimeMillis() < son) {
                val k = usb.oku(gecici)
                if (k > 0) {
                    val parca = if (k == gecici.size) gecici else gecici.copyOfRange(0, k)
                    for ((komut, yuk, hataYaniti) in cozucu.besle(parca)) {
                        if (komut == Msp.MSP_API_VERSION && !hataYaniti && yuk.size >= 3) {
                            return JSONObject().put("tamam", true).put("protokol", "betaflight")
                                .put("kanit", "msp_api_version").put("baud", baud)
                                .put(
                                    "msp_api",
                                    "${yuk[1].toInt() and 0xFF}.${yuk[2].toInt() and 0xFF}"
                                )
                        }
                    }
                }
            }
            return JSONObject().put("tamam", false).put("protokol", "bilinmiyor")
                .put(
                    "hata",
                    "MAVLink HEARTBEAT veya BetaFlight MSP API_VERSION yaniti alinmadi. " +
                        "Seri hat, baud hizi ve FC uzerindeki MSP ayarini kontrol edin."
                )
        } finally {
            usb.kapat()
        }
    }
}
