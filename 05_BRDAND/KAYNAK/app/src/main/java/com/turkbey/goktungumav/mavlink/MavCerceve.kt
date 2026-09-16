package com.turkbey.goktungumav.mavlink

/**
 * MAVLink v1/v2 cerceve ayristiricisi.
 *
 * ## Neden kendi ayristirici
 *
 * Kopru **seffaf borudur**: cerceveleri degistirmeden tasir.  Tam bir
 * MAVLink kutuphanesi (mesaj tanimlari, XML uretimi, CRC_EXTRA
 * tablolari) gereksiz agirlik olurdu.  Gereken tek sey cerceve
 * SINIRLARINI dogru bulmak; govde icerigi yorumlanmaz.
 *
 * ## Neden cerceve siniri onemli
 *
 * USB seri okumasi rastgele buyuklukte parca dondurur.  Bir okuma iki
 * cercevenin ortasinda bitebilir.  Parcalari oldugu gibi UDP paketine
 * koymak MAVLink'i BOZAR: alici taraf yarim cerceve gorur, CRC
 * basarisiz olur ve telemetri duser.  Bu yuzden bayt akisi once
 * cerceveye ayrilir, sonra TAM cerceveler UDP'ye yazilir.
 *
 * ## Cerceve bicimi
 *
 * v1 (`0xFE`): `STX LEN SEQ SYS COMP MSGID PAYLOAD[LEN] CRC[2]`
 *   -> toplam 8 + LEN
 *
 * v2 (`0xFD`): `STX LEN INCOMPAT COMPAT SEQ SYS COMP MSGID[3]
 *              PAYLOAD[LEN] CRC[2] [SIGNATURE[13]]`
 *   -> toplam 12 + LEN (+13 imzali ise)
 *
 * v2'de `INCOMPAT_FLAGS` bit 0 (`0x01`) imza varligini bildirir.
 * OLCULDU (MAVLink v2 belirtimi): imzali cerceve 13 bayt daha uzundur;
 * bu bit gozden kacirilirsa cerceve sinirlari kayar ve akis bozulur.
 *
 * ## CRC dogrulamasi YAPILMAZ (bilincli karar)
 *
 * CRC dogrulamasi `CRC_EXTRA` tablosu ister; o tablo mesaj tanimlarina
 * baglidir ve her MAVLink surumunde degisir.  Tabloyu gomdugumuz an
 * kopru "bildigim mesajlar" ile sinirlanir ve yeni mesaj turleri
 * DUSER.  Seffaf boru bunu yapmamali.  Bozuk cerceve zaten ucus
 * denetleyicisi ve yer istasyonu tarafindan reddedilir; koprunun
 * yeniden dogrulamasi katma deger uretmez, kisitlama uretir.
 */
class MavCerceve {

    /** Ayristirma tamponu.  Yarim cerceveler burada bekler. */
    private val tampon = ByteArray(TAMPON_BOYU)
    private var uzunluk = 0

    /** Tanisal sayaclar. */
    var toplamCerceve = 0L
        private set
    var atilanBayt = 0L
        private set

    /**
     * [veri] icindeki ilk [n] bayti tampona ekler ve tamamlanan
     * cerceveleri dondurur.
     *
     * Donen liste ogeleri **tam** MAVLink cerceveleridir; her biri
     * dogrudan bir UDP paketi olarak gonderilebilir.
     */
    fun besle(veri: ByteArray, n: Int): List<ByteArray> {
        if (n <= 0) return emptyList()

        // Tampon tasmasi: gercek bir MAVLink akisinda olmaz, ancak
        // seri hattaki gurultu senkron baytina hic rastlamazsa tampon
        // dolabilir.  Tamponu bosaltmak, kopruyu kilitlemekten
        // yegdir; kaybedilen bayt sayisi kayda gecer.
        if (uzunluk + n > TAMPON_BOYU) {
            atilanBayt += uzunluk.toLong()
            uzunluk = 0
        }
        val kopyala = minOf(n, TAMPON_BOYU - uzunluk)
        System.arraycopy(veri, 0, tampon, uzunluk, kopyala)
        uzunluk += kopyala

        val cikti = ArrayList<ByteArray>(4)
        var oku = 0

        while (true) {
            // Senkron baytini bul.  Onundeki her sey gurultudur.
            var bas = -1
            var i = oku
            while (i < uzunluk) {
                val b = tampon[i]
                if (b == STX_V1 || b == STX_V2) {
                    bas = i
                    break
                }
                i++
            }
            if (bas < 0) {
                // Hic senkron bayti yok: tamponun tamami gurultu.
                atilanBayt += (uzunluk - oku).toLong()
                oku = uzunluk
                break
            }
            if (bas > oku) {
                atilanBayt += (bas - oku).toLong()
                oku = bas
            }

            val kalan = uzunluk - bas
            // Uzunluk baytini okumak icin en az 2 bayt gerekir.
            if (kalan < 2) break

            val govdeUzunluk = tampon[bas + 1].toInt() and 0xFF
            val cerceveBoyu = when (tampon[bas]) {
                STX_V1 -> V1_EK + govdeUzunluk
                else -> {
                    // v2: imza bayrağini okumak icin 3. bayt gerekli.
                    if (kalan < 3) break
                    val uyumsuzBayrak = tampon[bas + 2].toInt() and 0xFF
                    val imzali = (uyumsuzBayrak and IMZA_BAYRAGI) != 0
                    V2_EK + govdeUzunluk + if (imzali) IMZA_BOYU else 0
                }
            }

            if (kalan < cerceveBoyu) break   // cerceve henuz tamamlanmadi

            cikti.add(tampon.copyOfRange(bas, bas + cerceveBoyu))
            toplamCerceve++
            oku = bas + cerceveBoyu
        }

        // Islenmemis kuyrugu tamponun basina kaydir.
        if (oku > 0) {
            val kuyruk = uzunluk - oku
            if (kuyruk > 0) System.arraycopy(tampon, oku, tampon, 0, kuyruk)
            uzunluk = kuyruk
        }
        return cikti
    }

    fun sifirla() {
        uzunluk = 0
    }

    companion object {
        const val STX_V1: Byte = 0xFE.toByte()
        const val STX_V2: Byte = 0xFD.toByte()

        /** v1 cerceve sabit yuku: STX LEN SEQ SYS COMP MSGID CRC[2] */
        const val V1_EK = 8

        /**
         * v2 cerceve sabit yuku:
         * STX LEN INCOMPAT COMPAT SEQ SYS COMP MSGID[3] CRC[2]
         */
        const val V2_EK = 12

        /** `INCOMPAT_FLAGS` bit 0: cerceve imzali. */
        const val IMZA_BAYRAGI = 0x01

        /** MAVLink v2 imza alani uzunlugu. */
        const val IMZA_BOYU = 13

        /**
         * En buyuk MAVLink cercevesi 280 bayt civari (v2, imzali,
         * 255 bayt govde).  Tampon bunun birkac katı olmali ki tek
         * okumada gelen coklu cerceve bir kerede islenebilsin.
         */
        const val TAMPON_BOYU = 4096
    }
}
