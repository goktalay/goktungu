package com.turkbey.goktungu.usb

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import android.util.Log
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * USB seri (uçuş kontrolcüsü / SiK telemetri) ile gömülü GRCOFF arka ucu
 * arasında MAVLink köprüsü.
 *
 * ## Neden TCP köprüsü
 *
 * Android'de pymavlink bir USB aygıtını doğrudan açamaz (`/dev/tty*`
 * erişimi yok). USB Host erişimi Android/Kotlin katmanındadır. Bu sınıf
 * USB seri baytlarını `127.0.0.1:5760` üzerinde bir TCP sunucusuna
 * köprüler; Python tarafındaki GRCOFF arka ucu buraya
 * `tcp:127.0.0.1:5760` ile MAVLink istemcisi olarak bağlanır. Kotlin
 * yalnız ham bayt aktarır; MAVLink çerçeve ayrıştırmayı pymavlink yapar.
 *
 * ## Akış
 *
 *   USB aygıtı takılır -> izin istenir -> açılır
 *   pymavlink 5760'a bağlanır -> iki yönlü aktarım başlar
 *   USB(oku) -> TCP(yaz)   ve   TCP(oku) -> USB(yaz)
 *
 * Aygıt çıkarılır veya istemci koparsa köprü kendini toparlar ve bekler.
 */
class UsbMavKoprusu(private val baglam: Context) {

    private val usb = UsbSeri(baglam)
    private var sunucu: ServerSocket? = null

    @Volatile private var istemci: Socket? = null
    @Volatile private var calisiyor = false
    @Volatile private var hiz = UsbSeri.VARSAYILAN_HIZ

    private val alici = object : BroadcastReceiver() {
        override fun onReceive(c: Context, niyet: Intent) {
            when (niyet.action) {
                UsbSeri.EYLEM_IZIN -> {
                    val aygit = aygitAl(niyet)
                    val verildi = niyet.getBooleanExtra(
                        UsbManager.EXTRA_PERMISSION_GRANTED, false)
                    if (verildi && aygit != null) usbAc(aygit)
                    else Log.w(ETIKET, "USB izni reddedildi")
                }
                UsbManager.ACTION_USB_DEVICE_ATTACHED -> aygitAra()
                UsbManager.ACTION_USB_DEVICE_DETACHED -> usb.kapat()
            }
        }
    }

    /** Köprüyü başlatır: alıcıları kaydeder, TCP sunucusunu açar, USB tarar. */
    fun baslat(istenenHiz: Int = UsbSeri.VARSAYILAN_HIZ) {
        if (calisiyor) return
        calisiyor = true
        hiz = istenenHiz

        val suzgec = IntentFilter().apply {
            addAction(UsbSeri.EYLEM_IZIN)
            addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED)
            addAction(UsbManager.ACTION_USB_DEVICE_DETACHED)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            baglam.registerReceiver(alici, suzgec, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            baglam.registerReceiver(alici, suzgec)
        }

        tcpSunucusunuBaslat()
        aygitAra()
    }

    fun durdur() {
        calisiyor = false
        runCatching { baglam.unregisterReceiver(alici) }
        runCatching { istemci?.close() }
        runCatching { sunucu?.close() }
        usb.kapat()
        istemci = null
        sunucu = null
    }

    /** Bağlı MAVLink uyumlu ilk aygıtı bulur; izin varsa açar, yoksa ister. */
    private fun aygitAra() {
        val aygitlar = usb.cihazlariListele()
        val aygit = aygitlar.firstOrNull() ?: return
        if (usb.izinVarMi(aygit)) usbAc(aygit) else usb.izinIste(aygit)
    }

    private fun usbAc(aygit: UsbDevice) {
        val hata = usb.ac(aygit, hiz)
        if (hata != null) {
            Log.e(ETIKET, "USB açılamadı: $hata")
            return
        }
        Log.i(ETIKET, "USB açık: ${usb.cihazAdi}; USB->TCP aktarımı başlıyor")
        usbdenTcpyeAktar()
    }

    private fun tcpSunucusunuBaslat() = thread(name = "usb-mav-tcp", isDaemon = true) {
        try {
            val s = ServerSocket()
            s.reuseAddress = true
            s.bind(InetSocketAddress("127.0.0.1", TCP_PORT))
            sunucu = s
            Log.i(ETIKET, "TCP sunucusu 127.0.0.1:$TCP_PORT dinliyor (pymavlink bağlanır)")
            while (calisiyor) {
                val c = try { s.accept() } catch (e: Exception) {
                    if (calisiyor) Log.e(ETIKET, "accept: ${e.message}"); break
                }
                c.tcpNoDelay = true
                // Yeni istemci öncekini değiştirir (tek tüketici).
                runCatching { istemci?.close() }
                istemci = c
                Log.i(ETIKET, "pymavlink bağlandı; TCP->USB aktarımı başlıyor")
                tcpdenUsbeAktar(c)
            }
        } catch (e: Exception) {
            Log.e(ETIKET, "TCP sunucusu: ${e.message}")
        }
    }

    /** USB -> TCP: uçuş kontrolcüsünden gelen telemetriyi istemciye iletir. */
    private fun usbdenTcpyeAktar() = thread(name = "usb->tcp", isDaemon = true) {
        val tampon = ByteArray(4096)
        while (calisiyor && usb.acik) {
            val n = usb.oku(tampon)
            if (n < 0) { usb.kapat(); break }
            if (n == 0) continue
            val c = istemci ?: continue
            try {
                c.getOutputStream().apply { write(tampon, 0, n); flush() }
            } catch (e: Exception) {
                Log.w(ETIKET, "TCP yazma koptu: ${e.message}")
                runCatching { c.close() }
                if (istemci === c) istemci = null
            }
        }
    }

    /** TCP -> USB: GRCOFF'tan gelen komutları uçuş kontrolcüsüne iletir. */
    private fun tcpdenUsbeAktar(c: Socket) = thread(name = "tcp->usb", isDaemon = true) {
        val tampon = ByteArray(4096)
        try {
            val giris = c.getInputStream()
            while (calisiyor && !c.isClosed) {
                val n = giris.read(tampon)
                if (n < 0) break
                if (n > 0 && usb.acik) usb.yaz(tampon, n)
            }
        } catch (e: Exception) {
            Log.w(ETIKET, "TCP okuma koptu: ${e.message}")
        } finally {
            runCatching { c.close() }
            if (istemci === c) istemci = null
        }
    }

    private fun aygitAl(niyet: Intent): UsbDevice? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
            niyet.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
        else @Suppress("DEPRECATION") niyet.getParcelableExtra(UsbManager.EXTRA_DEVICE)

    companion object {
        private const val ETIKET = "GRCOFF-USB"

        /** pymavlink `tcp:127.0.0.1:5760` ile bağlanır (yaygın SITL/MAVLink portu). */
        const val TCP_PORT = 5760
    }
}
