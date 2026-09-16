package com.turkbey.goktungumav.mavlink

import android.content.Context
import android.hardware.usb.UsbDevice
import com.turkbey.goktungumav.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * MAVLink koprusu: USB seri <-> UDP arasinda **seffaf** iki yonlu boru.
 *
 * ## Mimari karar: neden seffaf boru, neden GDP degil
 *
 * DJI koprusu MSDK cagrilarini GDP/NDJSON'a cevirmek ZORUNDAYDI cunku
 * MSDK MAVLink konusmuyor.  MAVLink araci **zaten MAVLink konusuyor**.
 * Araya JSON cevirisi koymak:
 *   - her yeni MAVLink mesaji icin kod guncellemesi gerektirir,
 *   - koordinat donusumu ekler, yani enlem/boylam ters cevrilme
 *     riskini geri getirir,
 *   - gecikme ve bilgi kaybi uretir.
 *
 * Bu yuzden cerceveler **degistirilmeden** tasinir.  Sonuc: merkezdeki
 * dron panelinin butun yetenekleri (kalibrasyon, motor testi,
 * yakinlik algilayicisi, ilk ayar parametreleri) kopru tarafinda HIC
 * kod olmadan calisir.
 *
 * ## Akis
 *
 * ```
 * Yukari yon:  USB seri --oku--> MavCerceve --tam cerceve--> UDP --> merkez
 * Asagi yon:   merkez --UDP--> (cerceve) --yaz--> USB seri --> arac
 * Gozlem:      gecen cerceve --kopya--> MavGozlemci (SALT OKUMA)
 * ```
 *
 * ## Neden iki ayri is (coroutine)
 *
 * Okuma ve yazma birbirini engellememeli.  USB okumasi zaman asimina
 * kadar bloke olur; ayni is icinde UDP dinlemek komut gecikmesi
 * uretirdi.  Iki bagimsiz dongu her iki yonde de en kucuk gecikmeyi
 * saglar.
 */
class MavlinkKopru(private val baglam: Context) {

    enum class Durum { KAPALI, ARAC_BEKLENIYOR, CALISIYOR, HATA }

    val usb = UsbSeri(baglam)
    val udp = UdpTasima()
    val gozlemci = MavGozlemci()
    private val cerceveci = MavCerceve()

    private var kapsam: CoroutineScope? = null
    private var yukariIs: Job? = null
    private var asagiIs: Job? = null
    private var izlemeIs: Job? = null

    private val _durum = MutableStateFlow(Durum.KAPALI)
    val durum: StateFlow<Durum> = _durum.asStateFlow()

    private val _hataIletisi = MutableStateFlow("")
    val hataIletisi: StateFlow<String> = _hataIletisi.asStateFlow()

    /**
     * Kopruyu baslatir.
     *
     * @param cihaz Acilacak USB seri cihaz
     * @param hiz Seri hat hizi
     * @param sunucu Merkez adresi
     * @param port Merkez UDP portu
     * @return hata iletisi, basarili ise `null`
     */
    fun baslat(
        cihaz: UsbDevice, hiz: Int, sunucu: String, port: Int
    ): String? {
        durdur()

        val usbHata = usb.ac(cihaz, hiz)
        if (usbHata != null) {
            _durum.value = Durum.HATA
            _hataIletisi.value = usbHata
            return usbHata
        }

        val udpHata = udp.ac(sunucu, port)
        if (udpHata != null) {
            usb.kapat()
            _durum.value = Durum.HATA
            _hataIletisi.value = udpHata
            return udpHata
        }

        cerceveci.sifirla()
        gozlemci.sifirla()
        _hataIletisi.value = ""

        val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        kapsam = k
        yukariIs = k.launch { yukariDongu() }
        asagiIs = k.launch { asagiDongu() }
        izlemeIs = k.launch { izlemeDongusu() }
        _durum.value = Durum.ARAC_BEKLENIYOR
        Gunluk.yaz("KOPRU", "Baslatildi: ${usb.cihazAdi} @ $hiz " +
            "-> ${udp.hedefEtiketi()}")
        return null
    }

    /**
     * Yukari yon: aractan merkeze.
     *
     * Cerceve siniri MavCerceve tarafindan korunur; UDP'ye yalniz TAM
     * cerceveler yazilir.  Yarim cerceve gondermek merkezdeki
     * ayristiriciyi bozar.
     */
    private suspend fun yukariDongu() {
        val tampon = ByteArray(OKUMA_TAMPON)
        var hataSayaci = 0
        while (true) {
            try {
                val n = usb.oku(tampon)
                if (n < 0) {
                    hataSayaci++
                    // Ard arda okuma hatasi kablo cikmis demektir.
                    if (hataSayaci >= HATA_ESIGI) {
                        _durum.value = Durum.HATA
                        _hataIletisi.value = "USB baglantisi kesildi"
                        Gunluk.hata("KOPRU", "USB okuma hatasi surekli")
                        return
                    }
                    delay(100)
                    continue
                }
                if (n == 0) {
                    delay(2)
                    continue
                }
                hataSayaci = 0
                for (c in cerceveci.besle(tampon, n)) {
                    udp.gonder(c)
                    // SALT OKUMA gozlem: akisa dokunulmaz.
                    gozlemci.gozlemle(c)
                    if (_durum.value == Durum.ARAC_BEKLENIYOR) {
                        _durum.value = Durum.CALISIYOR
                    }
                }
            } catch (e: Exception) {
                Gunluk.hata("KOPRU", "Yukari yon: ${e.message}")
                delay(200)
            }
        }
    }

    /**
     * Asagi yon: merkezden araca.
     *
     * Merkezden gelen paket bir veya birden cok MAVLink cercevesi
     * icerebilir; icerige BAKILMAZ, oldugu gibi seri hatta yazilir.
     * Ayristirmak gereksiz risk olurdu: bilinmeyen bir mesaj turu
     * dusurulurse komut kaybolur.
     */
    private suspend fun asagiDongu() {
        val tampon = ByteArray(UdpTasima.ALMA_TAMPON)
        while (true) {
            try {
                val n = udp.al(tampon)
                if (n < 0) {
                    delay(200)
                    continue
                }
                if (n == 0) continue
                if (!usb.yaz(tampon, n)) {
                    Gunluk.hata("KOPRU", "Araca yazma basarisiz ($n bayt)")
                }
            } catch (e: Exception) {
                Gunluk.hata("KOPRU", "Asagi yon: ${e.message}")
                delay(200)
            }
        }
    }

    /** Arac kopmasini saptar ve durumu tazeler. */
    private suspend fun izlemeDongusu() {
        while (true) {
            delay(1000)
            gozlemci.zamanAsimiDenetle()
            if (_durum.value == Durum.CALISIYOR &&
                !gozlemci.durum.value.aracVar
            ) {
                _durum.value = Durum.ARAC_BEKLENIYOR
            }
        }
    }

    fun durdur() {
        yukariIs?.cancel()
        asagiIs?.cancel()
        izlemeIs?.cancel()
        yukariIs = null
        asagiIs = null
        izlemeIs = null
        kapsam?.cancel()
        kapsam = null
        udp.kapat()
        usb.kapat()
        cerceveci.sifirla()
        gozlemci.sifirla()
        _durum.value = Durum.KAPALI
    }

    /** Tanisal ozet; arayuzde gosterilir. */
    fun sayaclar(): String =
        "↑${udp.gonderilenCerceve} ↓${udp.alinanCerceve} " +
            "C:${cerceveci.toplamCerceve} X:${cerceveci.atilanBayt}"

    companion object {
        /**
         * USB toplu aktarim paketi 512 bayt (yuksek hiz) veya 64 bayt
         * (tam hiz).  4096 birden cok paketi tek okumada toplar ve
         * sistem cagrisi sayisini dusurur.
         */
        const val OKUMA_TAMPON = 4096

        /** Ard arda bu kadar okuma hatasi baglanti koptu sayilir. */
        const val HATA_ESIGI = 20
    }
}
