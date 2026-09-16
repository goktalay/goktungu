package com.turkbey.goktungu.veri

/**
 * Duz metin (TLS'siz) baglantinin nereye izinli oldugunu belirler.
 *
 * ## Neden kodda
 *
 * Android'in `network-security-config` dosyasi CIDR araligi kabul
 * etmez, yalniz tek tek ad/IP.  Kullanicinin yerel merkez sunucusu
 * herhangi bir ozel ag adresi olabilecegi icin (192.168.8.186 gibi)
 * adresleri onceden listelemek olanaksizdir.
 *
 * Bu yuzden manifest genel izin verir, gercek kisitlama burada
 * uygulanir: duz metin YALNIZ ozel ag / dongu adreslerinde izinli.
 * Genel internet adresinde TLS zorunludur.
 */
object AgKisiti {

    /**
     * [adres] ozel bir ag adresi mi (RFC 1918, bagli-yerel, dongu)?
     *
     * Ad cozumlemesi YAPILMAZ; yalniz sayisal IPv4 ve bilinen yerel
     * adlar taninir.  Alan adi verilirse `false` doner, boylece
     * `goktungu.com` gibi genel adresler TLS'e zorlanir.
     */
    fun ozelAgMi(adres: String): Boolean {
        val a = adres.trim().lowercase()
        if (a.isEmpty()) return false
        if (a == "localhost" || a == "::1") return true

        val parcalar = a.split(".")
        if (parcalar.size != 4) return false
        val sekizli = parcalar.map { it.toIntOrNull() ?: return false }
        if (sekizli.any { it < 0 || it > 255 }) return false

        val (b1, b2) = sekizli[0] to sekizli[1]
        return when {
            b1 == 127 -> true                       // dongu
            b1 == 10 -> true                        // 10.0.0.0/8
            b1 == 172 && b2 in 16..31 -> true       // 172.16.0.0/12
            b1 == 192 && b2 == 168 -> true          // 192.168.0.0/16
            b1 == 169 && b2 == 254 -> true          // bagli-yerel
            else -> false
        }
    }

    /**
     * [adres] icin duz metin baglanti izinli mi?
     *
     * @param tlsKullaniliyor Baglanti TLS ile kuruluyorsa duz metin
     *   kisiti uygulanmaz.
     */
    fun duzMetinIzinliMi(adres: String, tlsKullaniliyor: Boolean): Boolean =
        tlsKullaniliyor || ozelAgMi(adres)

    /**
     * Reddetme gerekcesi; arayuzde gosterilir.
     */
    fun redNedeni(adres: String): String =
        "Genel internet adresine ($adres) TLS'siz baglanti reddedildi. " +
            "Kapali devre kurulumda yerel ag adresi kullanin " +
            "(10.x, 172.16-31.x, 192.168.x veya 127.0.0.1), " +
            "internet uzerinden baglaniyorsaniz TLS'i etkinlestirin."
}
