package com.gokkubbetech.goktungumav.mavlink

import com.gokkubbetech.goktungumav.veri.Gunluk
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress

/**
 * MAVLink cercevelerini merkeze tasiyan UDP katmani.
 *
 * ## Neden UDP, neden TCP degil
 *
 * Sunucu tarafi (`baglantilar.py`) `udp` turunu
 * `udpin:0.0.0.0:<port>` olarak dinler; yani merkez **dinleyen**,
 * kopru **gonderen** taraftir.  Bu, GOKTUNGU mimarisinin temel
 * karariyla ortusur: saha cihazlarinin sabit IP'si yoktur, merkeze
 * KENDILERI baglanir.
 *
 * UDP secimi ayrica telemetri icin dogru olandir: gecikmeli bir
 * konum paketi degersizdir, yeniden iletimi beklemek zarardir.
 * Komut tarafinda MAVLink kendi onay dizgesini (COMMAND_ACK) kullanir,
 * yani ust katman zaten guvenilirligi sagliyor.
 *
 * ## Geri yol nasil calisir
 *
 * Ayni soket hem gonderir hem dinler.  Merkez, kopruden gelen ilk
 * paketin kaynak adresini ogrenir ve komutlari **oraya** gonderir
 * (`pymavlink`in `udpin` davranisi).  Bu yuzden ayri bir dinleme
 * portu acmak gerekmez ve NAT arkasindan calisir: giden paket NAT
 * eslemesini acar, donen paket ayni esleme uzerinden gelir.
 *
 * Bu, kapali devre kurulumda da mobil sebeke uzerinde de calisir.
 */
class UdpTasima {

    private var soket: DatagramSocket? = null
    private var hedefAdres: InetAddress? = null
    private var hedefPort = 0

    @Volatile
    var acik = false
        private set

    var gonderilenCerceve = 0L
        private set
    var alinanCerceve = 0L
        private set
    var gonderilenBayt = 0L
        private set

    /**
     * Soketi acar ve hedefi cozer.
     *
     * @return hata iletisi, basarili ise `null`
     */
    fun ac(sunucu: String, port: Int): String? {
        kapat()
        return try {
            hedefAdres = InetAddress.getByName(sunucu)
            hedefPort = port
            val s = DatagramSocket()
            // Zaman asimi olmadan `receive` sonsuza kadar engeller ve
            // kapatma isini bitiremez.
            s.soTimeout = ALMA_ZAMAN_MS
            // Gonderim tamponu: telemetri patlamalarinda paket
            // dusmesini azaltir.
            runCatching { s.sendBufferSize = 64 * 1024 }
            runCatching { s.receiveBufferSize = 64 * 1024 }
            soket = s
            acik = true
            Gunluk.yaz("UDP", "Hedef: $sunucu:$port")
            null
        } catch (e: Exception) {
            acik = false
            "UDP acilamadi: ${e.message}"
        }
    }

    /**
     * Bir MAVLink cercevesini merkeze gonderir.
     *
     * Cerceve **oldugu gibi** gonderilir: baslik, govde ve CRC'ye
     * dokunulmaz.  Bu, koprunun seffafligini saglayan sozlesmedir.
     */
    fun gonder(cerceve: ByteArray): Boolean {
        val s = soket ?: return false
        val a = hedefAdres ?: return false
        return try {
            s.send(DatagramPacket(cerceve, cerceve.size, a, hedefPort))
            gonderilenCerceve++
            gonderilenBayt += cerceve.size
            true
        } catch (e: Exception) {
            Gunluk.hata("UDP", "Gonderim: ${e.message}")
            false
        }
    }

    /**
     * Merkezden gelen paketi okur.
     *
     * @return gelen bayt sayisi; zaman asiminda 0, hatada negatif
     */
    fun al(hedef: ByteArray): Int {
        val s = soket ?: return -1
        return try {
            val p = DatagramPacket(hedef, hedef.size)
            s.receive(p)
            alinanCerceve++
            p.length
        } catch (e: java.net.SocketTimeoutException) {
            0
        } catch (e: Exception) {
            if (acik) Gunluk.hata("UDP", "Alma: ${e.message}")
            -1
        }
    }

    fun hedefEtiketi(): String {
        val a = hedefAdres ?: return ""
        return "${a.hostAddress}:$hedefPort"
    }

    fun kapat() {
        acik = false
        runCatching { soket?.close() }
        soket = null
        hedefAdres = null
        hedefPort = 0
    }

    companion object {
        /**
         * `mavutil` varsayilan MAVLink UDP portu.  GOKTUNGU'de
         * baglanti kaydinin `port` alani bu degeri tasir.
         */
        const val VARSAYILAN_PORT = 14550

        /** Kapatmanin gecikmemesi icin kisa alma zaman asimi. */
        private const val ALMA_ZAMAN_MS = 300

        /**
         * En buyuk MAVLink cercevesi 280 bayt civari; 512 rahat sinir.
         * Merkez birden cok cerceveyi tek pakette birlestirebilir,
         * bu yuzden alma tamponu daha buyuk tutulur.
         */
        const val ALMA_TAMPON = 2048
    }
}
