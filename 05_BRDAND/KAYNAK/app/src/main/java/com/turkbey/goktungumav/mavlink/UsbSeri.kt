package com.turkbey.goktungumav.mavlink

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import com.turkbey.goktungumav.veri.Gunluk

/**
 * USB seri baglantisi (uçuş kontrolcusu / telemetri modemi).
 *
 * ## Neden dis kutuphane yok
 *
 * `usb-serial-for-android` yaygin bir cozumdur, ancak bu kopru yalniz
 * **bir** islevi kullanacakti: sabit hizda bayt okumak/yazmak.  Dis
 * bagimlilik yerine Android USB Host API dogrudan kullanildi; boylece
 * paket kucuk kaldi ve surucu davranisi bu dosyada acikca gorulur
 * (hata ayiklamada kritik).
 *
 * ## Desteklenen surucu aileleri
 *
 * | Aile | Nasil taninir | Yapilandirma |
 * |---|---|---|
 * | CDC-ACM | Arayuz sinifi 0x02/0x0A | `SET_LINE_CODING` denetim aktarimi |
 * | FTDI | Satici 0x0403 | Satici ozel `SET_BAUDRATE` |
 * | CP210x | Satici 0x10C4 | `IFC_ENABLE` + `SET_BAUDRATE` |
 * | CH34x | Satici 0x1A86 | Satici ozel baslatma dizisi |
 *
 * Pixhawk, Cube ve ArduPilot uyumlu kartlarin buyuk cogunlugu
 * **CDC-ACM** siniftadir (STM32 USB yigini).  FTDI/CP210x/CH34x
 * destegi harici telemetri modemleri (SiK radyo, 3DR) icindir.
 *
 * ## Neden hiz (baud) onemsiz gorunse de ayarlanir
 *
 * CDC-ACM USB uzerinden dogrudan baglandiginda hiz kuramsal olarak
 * anlamsizdir (USB kendi hizinda calisir).  Ancak ArduPilot kartlari
 * `SET_LINE_CODING` gelmezse bazi durumlarda akisi baslatmaz.
 * Ayrica araya SiK radyo girerse hiz GERCEKTEN onemlidir (57600).
 */
class UsbSeri(private val baglam: Context) {

    private var yonetici: UsbManager? = null
    private var cihaz: UsbDevice? = null
    private var baglanti: UsbDeviceConnection? = null
    private var arayuz: UsbInterface? = null
    private var okuUc: UsbEndpoint? = null
    private var yazUc: UsbEndpoint? = null

    @Volatile
    var acik = false
        private set

    var cihazAdi: String = ""
        private set

    /** Uygulanan hiz; arayuzde gosterilir. */
    var hiz: Int = VARSAYILAN_HIZ
        private set

    /**
     * Bagli MAVLink uyumlu gorunen ilk cihazi bulur.
     *
     * Tum USB seri cihazlar dondurulur; secim kullaniciya birakilir
     * cunku telefona ayni anda birden fazla seri cihaz bagli olabilir
     * (ornegin hem ucus kontrolcusu hem de bir modem).
     */
    fun cihazlariListele(): List<UsbDevice> {
        val y = yonetici ?: (baglam.getSystemService(Context.USB_SERVICE)
            as UsbManager).also { yonetici = it }
        return y.deviceList.values.filter { d -> seriMi(d) }
    }

    /** [cihaz] icin kullanici izni istenir. */
    fun izinIste(hedef: UsbDevice) {
        val y = yonetici ?: return
        val niyet = PendingIntent.getBroadcast(
            baglam, 0, Intent(EYLEM_IZIN).setPackage(baglam.packageName),
            PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        y.requestPermission(hedef, niyet)
    }

    fun izinVarMi(hedef: UsbDevice): Boolean =
        yonetici?.hasPermission(hedef) == true

    /**
     * Cihazi acar ve seri hatti yapilandirir.
     *
     * @return hata iletisi, basarili ise `null`
     */
    fun ac(hedef: UsbDevice, istenenHiz: Int): String? {
        kapat()
        val y = yonetici ?: return "USB yoneticisi yok"
        if (!y.hasPermission(hedef)) return "USB izni verilmedi"

        val b = y.openDevice(hedef) ?: return "USB cihazi acilamadi"
        // Veri arayuzunu ve uclari bul.  CDC-ACM'de iki arayuz vardir:
        // denetim (sinif 0x02) ve veri (sinif 0x0A).  Toplu (bulk)
        // uclar VERI arayuzundedir.
        var secilenArayuz: UsbInterface? = null
        var girisUc: UsbEndpoint? = null
        var cikisUc: UsbEndpoint? = null

        for (i in 0 until hedef.interfaceCount) {
            val a = hedef.getInterface(i)
            var gr: UsbEndpoint? = null
            var ck: UsbEndpoint? = null
            for (j in 0 until a.endpointCount) {
                val u = a.getEndpoint(j)
                if (u.type != UsbConstants.USB_ENDPOINT_XFER_BULK) continue
                if (u.direction == UsbConstants.USB_DIR_IN) gr = u
                else ck = u
            }
            if (gr != null && ck != null) {
                secilenArayuz = a
                girisUc = gr
                cikisUc = ck
                break
            }
        }
        if (secilenArayuz == null || girisUc == null || cikisUc == null) {
            b.close()
            return "Toplu aktarim ucu bulunamadi"
        }
        if (!b.claimInterface(secilenArayuz, true)) {
            b.close()
            return "USB arayuzu alinamadi"
        }

        baglanti = b
        cihaz = hedef
        arayuz = secilenArayuz
        okuUc = girisUc
        yazUc = cikisUc
        hiz = istenenHiz
        cihazAdi = cihazEtiketi(hedef)

        val hata = hattiYapilandir(hedef, b, secilenArayuz, istenenHiz)
        if (hata != null) {
            // Yapilandirma basarisiz olsa bile okuma denenir: bazi
            // kartlar denetim aktarimini reddeder ama akis yine
            // calisir.  Bu yuzden hata KAYDA gecer, baglanti kapanmaz.
            Gunluk.yaz("USB", "Hat yapilandirmasi uyarisi: $hata")
        }
        acik = true
        Gunluk.yaz("USB", "Acildi: $cihazAdi @ $istenenHiz")
        return null
    }

    /**
     * Seri hattini surucu ailesine gore yapilandirir.
     */
    private fun hattiYapilandir(
        d: UsbDevice, b: UsbDeviceConnection, a: UsbInterface, baud: Int
    ): String? = runCatching {
        when {
            d.vendorId == SATICI_FTDI -> {
                // FTDI: SIO_RESET, sonra bolen ile hiz.
                b.controlTransfer(0x40, 0x00, 0x0000, 0, null, 0, ZAMAN)
                val bolen = ftdiBolen(baud)
                b.controlTransfer(
                    0x40, 0x03, bolen and 0xFFFF, bolen shr 16,
                    null, 0, ZAMAN
                )
                // 8N1
                b.controlTransfer(0x40, 0x04, 0x0008, 0, null, 0, ZAMAN)
            }
            d.vendorId == SATICI_CP210X -> {
                // IFC_ENABLE = 1
                b.controlTransfer(0x41, 0x00, 0x0001, 0, null, 0, ZAMAN)
                val veri = baudBaytlari(baud)
                // SET_BAUDRATE (0x1E) 4 baytlik little-endian deger
                b.controlTransfer(0x41, 0x1E, 0, 0, veri, 4, ZAMAN)
                // SET_LINE_CTL: 8 veri biti, parite yok, 1 dur biti
                b.controlTransfer(0x41, 0x03, 0x0800, 0, null, 0, ZAMAN)
            }
            d.vendorId == SATICI_CH34X -> {
                // CH34x baslatma dizisi (satici belgelenmemis, yaygin
                // gerceklemelerde dogrulanmis siralama).
                b.controlTransfer(0x40, 0xA1, 0, 0, null, 0, ZAMAN)
                val (c1, c2) = ch34xBolen(baud)
                b.controlTransfer(0x40, 0x9A, 0x1312, c1, null, 0, ZAMAN)
                b.controlTransfer(0x40, 0x9A, 0x0F2C, c2, null, 0, ZAMAN)
                // 8N1
                b.controlTransfer(0x40, 0x9A, 0x2518, 0x00C3, null, 0, ZAMAN)
            }
            else -> {
                // CDC-ACM: SET_CONTROL_LINE_STATE (DTR+RTS acik),
                // sonra SET_LINE_CODING.
                //
                // DTR onemli: STM32 tabanli kartlarin cogu DTR
                // yukselene kadar veri gondermez.
                b.controlTransfer(
                    0x21, 0x22, 0x03, a.id, null, 0, ZAMAN
                )
                val kodlama = ByteArray(7)
                val v = baudBaytlari(baud)
                kodlama[0] = v[0]; kodlama[1] = v[1]
                kodlama[2] = v[2]; kodlama[3] = v[3]
                kodlama[4] = 0    // 1 dur biti
                kodlama[5] = 0    // parite yok
                kodlama[6] = 8    // 8 veri biti
                b.controlTransfer(
                    0x21, 0x20, 0, a.id, kodlama, 7, ZAMAN
                )
            }
        }
        null
    }.getOrElse { it.message ?: "bilinmeyen hata" }

    /**
     * Cihazdan bayt okur.
     *
     * @return okunan bayt sayisi; zaman asiminda 0, hatada negatif
     */
    fun oku(hedef: ByteArray): Int {
        val b = baglanti ?: return -1
        val u = okuUc ?: return -1
        return try {
            // Zaman asimi kisa: okuma engellenirse kapatma gecikir.
            val n = b.bulkTransfer(u, hedef, hedef.size, OKUMA_ZAMAN)
            if (n < 0) 0 else n
        } catch (e: Exception) {
            Gunluk.hata("USB", "Okuma: ${e.message}")
            -1
        }
    }

    /** Cihaza bayt yazar.  Kismi yazma yeniden denenir. */
    fun yaz(veri: ByteArray, n: Int): Boolean {
        val b = baglanti ?: return false
        val u = yazUc ?: return false
        var yazildi = 0
        return try {
            while (yazildi < n) {
                val parca = if (yazildi == 0 && n == veri.size) veri
                else veri.copyOfRange(yazildi, n)
                val k = b.bulkTransfer(u, parca, parca.size, YAZMA_ZAMAN)
                if (k <= 0) return false
                yazildi += k
            }
            true
        } catch (e: Exception) {
            Gunluk.hata("USB", "Yazma: ${e.message}")
            false
        }
    }

    fun kapat() {
        acik = false
        runCatching {
            val a = arayuz
            val b = baglanti
            if (a != null && b != null) b.releaseInterface(a)
            b?.close()
        }
        baglanti = null
        arayuz = null
        okuUc = null
        yazUc = null
        cihaz = null
        cihazAdi = ""
    }

    private fun seriMi(d: UsbDevice): Boolean {
        if (d.vendorId in SATICILAR) return true
        for (i in 0 until d.interfaceCount) {
            val s = d.getInterface(i).interfaceClass
            if (s == UsbConstants.USB_CLASS_COMM ||
                s == UsbConstants.USB_CLASS_CDC_DATA
            ) return true
        }
        return false
    }

    private fun cihazEtiketi(d: UsbDevice): String {
        val ad = runCatching { d.productName }.getOrNull()
        if (!ad.isNullOrBlank()) return ad
        return String.format("%04X:%04X", d.vendorId, d.productId)
    }

    private fun baudBaytlari(baud: Int) = byteArrayOf(
        (baud and 0xFF).toByte(),
        ((baud shr 8) and 0xFF).toByte(),
        ((baud shr 16) and 0xFF).toByte(),
        ((baud shr 24) and 0xFF).toByte()
    )

    /** FTDI 3 MHz temel saat bolenini hesaplar. */
    private fun ftdiBolen(baud: Int): Int {
        if (baud <= 0) return 0x4138          // 9600
        val temel = 3000000
        val tam = temel / baud
        val artik = temel % baud
        // FTDI'nin kesirli bolen kodlamasi: ust bitler kesir.
        val kesir = when ((artik * 8 + baud / 2) / baud) {
            0 -> 0; 1 -> 3; 2 -> 2; 3 -> 4
            4 -> 1; 5 -> 5; 6 -> 6; else -> 7
        }
        return tam or (kesir shl 14)
    }

    /** CH34x on bolen ve bolen ciftini hesaplar. */
    private fun ch34xBolen(baud: Int): Pair<Int, Int> {
        val temel = 12000000
        // Yaygin gerceklemelerde kullanilan on bolen basamaklari.
        val basamaklar = intArrayOf(1, 2, 8, 64, 1024)
        for ((i, on) in basamaklar.withIndex()) {
            val b = temel / (on * baud)
            if (b in 2..255) {
                val c1 = 0x00 or i
                return Pair(c1, (256 - b) and 0xFF)
            }
        }
        return Pair(0x02, (256 - 12000000 / (8 * 57600)) and 0xFF)
    }

    companion object {
        const val EYLEM_IZIN = "com.turkbey.goktungumav.USB_IZIN"

        /**
         * ArduPilot USB dogrudan baglantida 115200 kullanir; SiK
         * telemetri radyolari 57600.  115200 varsayilan secildi cunku
         * dogrudan USB en sik kurulum.
         */
        const val VARSAYILAN_HIZ = 115200

        val HIZLAR = intArrayOf(
            9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
        )

        const val SATICI_FTDI = 0x0403
        const val SATICI_CP210X = 0x10C4
        const val SATICI_CH34X = 0x1A86
        val SATICILAR = setOf(SATICI_FTDI, SATICI_CP210X, SATICI_CH34X)

        private const val ZAMAN = 2000

        /**
         * Okuma zaman asimi kisa tutuldu: uzun engelleme kopruyu
         * kapatirken gecikme uretir.  Bos donus zararsizdir.
         */
        private const val OKUMA_ZAMAN = 200
        private const val YAZMA_ZAMAN = 1000
    }
}
