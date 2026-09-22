package com.turkbey.goktungu.bridge.betaflight

import android.hardware.usb.UsbDevice
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import java.util.ArrayDeque

/**
 * Bir USB seri (VCP) portunda SALT-OKUNUR MSP sorgu dongusu yurutur.
 *
 * `betaflight_msp.py::BetaflightMspOturumu` sinifinin Kotlin
 * karsiligidir. Yalniz [Msp.mspV1Sorgu] cagrisi yazabilir; izin listesi
 * ([Msp.IZINLI_SORGU_KOMUTLARI]) hem kodlayicida hem burada IKINCI kez
 * zorlanir. Motor/ARM/RC/ayar/reboot/CLI URETILMEZ.
 *
 * Once tanilama sorgulari (API/FC/kart/isim) bir tur sorulur; sonra 1
 * Hz'de canli sorgular (durum/tutum/irtifa/gerilim/batarya) tekrarlanir.
 * Cozulen degerler [durum] akisina yazilir; arayuz ve merkez servis
 * durumu bunu okur.
 */
class MspOturumu(
    private val usb: UsbSeri,
    private val cihaz: UsbDevice,
    private val baud: Int = VARSAYILAN_BAUD
) {

    data class Durum(
        val faz: String = "kapali",        // baglaniyor / bagli / hata / kapali
        val hata: String = "",
        val fcTuru: String = "",
        val fcSurumu: String = "",
        val api: String = "",
        val kart: String = "",
        val ad: String = "",
        val rollDeg: Double? = null,
        val pitchDeg: Double? = null,
        val headingDeg: Int? = null,
        val irtifaCm: Int? = null,
        val dikeyHizCmS: Int? = null,
        val gerilimV: Double? = null,
        val hucreSayisi: Int? = null,
        val sensorMaskesi: Int? = null,
        val yanitSayisi: Long = 0,
        val hataliChecksum: Int = 0,
        val sonVeriTs: Long = 0
    )

    private val _durum = MutableStateFlow(Durum())
    val durum: StateFlow<Durum> = _durum.asStateFlow()

    /** Merkeze `servisler` olcumlerinde bildirilecek ham tani sozlugu. */
    private val bilgi = JSONObject()

    @Volatile
    private var calisiyor = false
    private var iplik: Thread? = null

    fun bagliMi(): Boolean = calisiyor && _durum.value.faz == "bagli"

    fun calisiyorMu(): Boolean = calisiyor

    fun baslat(): Boolean {
        if (calisiyor) return true
        if (!usb.izinVarMi(cihaz)) {
            usb.izinIste(cihaz)
            _durum.value = _durum.value.copy(
                faz = "hata",
                hata = "USB izni verilmedi (${usb.cihazEtiketi(cihaz)}); izni onaylayin"
            )
            return false
        }
        calisiyor = true
        _durum.value = _durum.value.copy(faz = "baglaniyor", hata = "")
        iplik = Thread({ calis() }, "bf-msp").apply { isDaemon = true; start() }
        return true
    }

    fun durdur() {
        calisiyor = false
        iplik?.let { runCatching { it.join(800) } }
        iplik = null
        runCatching { usb.kapat() }
        _durum.value = _durum.value.copy(faz = "kapali")
    }

    fun bilgiKopyasi(): JSONObject = JSONObject(bilgi.toString())

    private fun calis() {
        val hata = usb.ac(cihaz, baud)
        if (hata != null) {
            _durum.value = _durum.value.copy(faz = "hata", hata = "MSP portu acilamadi: $hata")
            calisiyor = false
            return
        }
        Gunluk.yaz("BETAFLIGHT", "Salt-okunur MSP baslatildi: ${usb.cihazEtiketi(cihaz)}")
        _durum.value = _durum.value.copy(faz = "bagli", hata = "")
        val cozucu = MspV1Cozucu()
        val sorgular = ArrayDeque<Int>(Msp.TANILAMA_SORGULARI)
        var sonrakiCanli = System.currentTimeMillis()
        val gecici = ByteArray(512)
        try {
            while (calisiyor) {
                val simdi = System.currentTimeMillis()
                if (sorgular.isEmpty() && simdi >= sonrakiCanli) {
                    sorgular.addAll(Msp.CANLI_SORGULAR)
                    sonrakiCanli = simdi + 1000  // 1 Hz sorgu turu
                }
                if (sorgular.isNotEmpty()) {
                    val komut = sorgular.pollFirst()
                    // Izin listesi burada IKINCI kez zorlanir.
                    if (komut in Msp.IZINLI_SORGU_KOMUTLARI) {
                        val cerceve = Msp.mspV1Sorgu(komut)
                        usb.yaz(cerceve, cerceve.size)
                    }
                }
                val n = usb.oku(gecici)
                if (n < 0) {
                    _durum.value = _durum.value.copy(faz = "hata", hata = "MSP okuma hatasi")
                    break
                }
                if (n > 0) {
                    val parca = if (n == gecici.size) gecici else gecici.copyOfRange(0, n)
                    for ((komut, yuk, hataYaniti) in cozucu.besle(parca)) {
                        if (komut !in Msp.IZINLI_SORGU_KOMUTLARI) continue
                        if (hataYaniti) continue
                        isle(komut, yuk, cozucu)
                    }
                } else if (sorgular.isEmpty()) {
                    // Bosta: hizli donuyu onlemek icin kisa uyku.
                    Thread.sleep(20)
                }
            }
        } catch (e: Exception) {
            _durum.value = _durum.value.copy(
                faz = "hata", hata = "MSP okuma/sorgu hatasi: ${e.message}"
            )
        } finally {
            runCatching { usb.kapat() }
            calisiyor = false
        }
    }

    private fun isle(komut: Int, yuk: ByteArray, cozucu: MspV1Cozucu) {
        val parca = Msp.mspVeriCoz(komut, yuk)
        bilgi.put(komut.toString(), parca)
        var d = _durum.value.copy(
            yanitSayisi = _durum.value.yanitSayisi + 1,
            hataliChecksum = cozucu.hataliChecksum,
            sonVeriTs = System.currentTimeMillis(),
            faz = "bagli"
        )
        when (komut) {
            Msp.MSP_API_VERSION -> d = d.copy(api = parca.optString("api", d.api))
            Msp.MSP_FC_VARIANT -> d = d.copy(fcTuru = parca.optString("fc_turu", d.fcTuru))
            Msp.MSP_FC_VERSION -> d = d.copy(fcSurumu = parca.optString("fc_surumu", d.fcSurumu))
            Msp.MSP_BOARD_INFO -> d = d.copy(kart = parca.optString("kart", d.kart))
            Msp.MSP_NAME -> d = d.copy(ad = parca.optString("ad_metin", d.ad))
            Msp.MSP_STATUS ->
                d = d.copy(sensorMaskesi = parca.optInt("sensor_maskesi", d.sensorMaskesi ?: 0))
            Msp.MSP_ATTITUDE -> {
                val t = parca.optJSONObject("tutum")
                if (t != null) d = d.copy(
                    rollDeg = t.optDouble("roll_deg"),
                    pitchDeg = t.optDouble("pitch_deg"),
                    headingDeg = if (t.isNull("heading_deg")) d.headingDeg else t.optInt("heading_deg")
                )
            }
            Msp.MSP_ALTITUDE -> d = d.copy(
                irtifaCm = if (parca.isNull("irtifa_cm")) d.irtifaCm else parca.optInt("irtifa_cm"),
                dikeyHizCmS = if (parca.has("dikey_hiz_cm_s")) parca.optInt("dikey_hiz_cm_s") else d.dikeyHizCmS
            )
            Msp.MSP_ANALOG ->
                if (parca.has("gerilim_v")) d = d.copy(gerilimV = parca.optDouble("gerilim_v"))
            Msp.MSP_BATTERY_STATE ->
                if (parca.has("hucre_sayisi")) d = d.copy(hucreSayisi = parca.optInt("hucre_sayisi"))
        }
        _durum.value = d
    }

    companion object {
        // BetaFlight VCP genelde baud'a bakmaz; 115200 yaygin varsayilan.
        const val VARSAYILAN_BAUD = 115200
    }
}
