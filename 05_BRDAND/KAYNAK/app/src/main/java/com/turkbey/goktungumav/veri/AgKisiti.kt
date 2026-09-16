package com.turkbey.goktungumav.veri

/**
 * Telemetri gonderiminin nereye izinli oldugunu belirler.
 *
 * ## Neden kisitlama gerekli
 *
 * MAVLink UDP telemetrisi **sifrelenmemistir**.  Genel internet
 * uzerinden gondermek aracin konumunu, irtifasini ve ucus rotasini
 * yol boyundaki herkese aciga cikarir.  Savunma kullaniminda bu kabul
 * edilemez.
 *
 * Bu yuzden gonderim yalniz **ozel ag** adreslerine izinlidir.
 * Uzak baglanti gerekiyorsa kullanici VPN veya SSH tuneli kurar; o
 * durumda hedef adres yine ozel ag icinde gorunur ve kisit dogal
 * olarak saglanir.
 *
 * ## Neden kodda, manifestte degil
 *
 * Android'in `network-security-config` dosyasi CIDR araligi kabul
 * etmez, yalniz tek tek ad/IP.  Kullanicinin yerel merkez sunucusu
 * herhangi bir ozel ag adresi olabilecegi icin (192.168.8.186 gibi)
 * adresleri onceden listelemek olanaksizdir.  Bu yuzden gercek
 * kisitlama burada uygulanir.
 */
object AgKisiti {

    /**
     * [adres] ozel bir ag adresi mi (RFC 1918, bagli-yerel, dongu)?
     *
     * Ad cozumlemesi YAPILMAZ; yalniz sayisal IPv4 ve bilinen yerel
     * adlar taninir.  Alan adi verilirse `false` doner, boylece
     * `goktungu.com` gibi genel adresler reddedilir.
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
     * Reddetme gerekcesi; arayuzde gosterilir.
     */
    fun redNedeni(adres: String): String =
        "Genel internet adresine ($adres) sifrelenmemis MAVLink " +
            "telemetrisi gonderilmez: arac konumu ve ucus rotasi aciga " +
            "cikar. Yerel ag adresi kullanin (10.x, 172.16-31.x, " +
            "192.168.x veya 127.0.0.1). Uzaktan baglanmaniz gerekiyorsa " +
            "VPN kurun; VPN arkasindaki merkez adresi yerel ag icinde " +
            "gorunur."
}
