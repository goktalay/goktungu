package com.turkbey.goktungu.bridge.kopru

/**
 * KOPRU TIPLERI (Faz 2: cok-kopru soyutlamasi).
 *
 * BRDAND artik tek bir MAVLink koprusu degil; kullanici sol menuden
 * bes farkli kopru tipi arasindan secer. Her tip kendi [KopruStrateji]
 * gerceklemesine sahiptir ve merkeze KENDI yeteneklerini bildirir.
 *
 * | tip           | yol                       | durum   |
 * |---------------|---------------------------|---------|
 * | ARDUPILOT     | USB seri MAVLink          | tam     |
 * | BETAFLIGHT    | USB seri MSP (salt-okunur)| tam     |
 * | DJI           | DJI Mobile SDK v5         | tam     |
 * | ELEKTRO_OPTIK | EO telemetri              | iskele  |
 * | RADAR         | Radar telemetri           | iskele  |
 *
 * `yetenek` alani merkezin `merhaba`/`nabiz` paketinde gordugu ana
 * yetenek anahtaridir (mavlink/msp/dji/eo/radar); merkez otomatik
 * yonlendirmeyi buna gore yapar.
 *
 * `hazir` false ise backend henuz tam entegre degildir: tip
 * SECILEBILIR ama arayuz "baglanti bekleniyor / pasif" gosterir
 * (ileride doldurulacak iskele). `seriKullanir` USB seri kartinin bu
 * tip icin anlamli olup olmadigini soyler.
 */
enum class KopruTipi(
    val id: String,
    val etiket: String,
    val yetenek: String,
    val seriKullanir: Boolean,
    val hazir: Boolean
) {
    ARDUPILOT("ardupilot", "ArduPilot · MAVLink", "mavlink", true, true),
    BETAFLIGHT("betaflight", "BetaFlight · MSP", "msp", true, true),
    DJI("dji", "DJI Mobile SDK", "dji", false, true),
    ELEKTRO_OPTIK("eo", "Elektro-Optik telemetri", "eo", false, false),
    RADAR("radar", "Radar", "radar", false, false);

    companion object {
        fun idden(id: String?): KopruTipi =
            entries.firstOrNull { it.id == id } ?: ARDUPILOT
    }
}
