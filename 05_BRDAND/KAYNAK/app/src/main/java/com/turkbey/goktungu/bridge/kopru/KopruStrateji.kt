package com.turkbey.goktungu.bridge.kopru

import android.content.Context

/**
 * KOPRU STRATEJISI — bir kopru tipinin davranis sozlesmesi (strateji
 * deseni).
 *
 * [KopruYonetici] ayni anda TEK bir stratejiyi etkin tutar (bir cihaz,
 * bir kurulum kimligi, merkeze bir baglanti). Her strateji kendi
 * yasam dongusunu, merkeze bildirecegi yetenekleri, servisleri ve
 * ajanini yonetir. Boylece MAVLink (ArduPilot) yolu, DJI MSDK yolu ve
 * MSP (BetaFlight) yolu ayni [KopruAjan] protokolunu paylasir ama
 * birbirinden yalitilir; birinin degismesi digerini bozmaz.
 *
 * Arayuz ([com.turkbey.goktungu.bridge.arayuz.AnaEtkinlik]) tipe ozel
 * kart icerigini bu sozlesme uzerinden okur (yoklamayla, 1 sn'de bir);
 * boylece tip degisince arayuzun yeniden abone olmasi gerekmez.
 */
interface KopruStrateji {

    val tip: KopruTipi

    /** Cekirdegi kurar (idempotent). DJI'de MSDK ANCAK burada baslar. */
    fun kur(baglam: Context)

    fun kuruldu(): Boolean

    /** Ajani baslatir; kurulum kimligi yoksa `false`. */
    fun baslat(): Boolean

    fun durdur()

    fun calisiyorMu(): Boolean

    fun bagliMi(): Boolean

    /** Merkeze baglanan ajan (kurulmamissa `null`). */
    val ajan: KopruAjan?

    /** USB seri kartinin bu tip icin anlamli olup olmadigi. */
    val seriKullanir: Boolean get() = tip.seriKullanir

    /** Backend tam entegre mi (iskele ise false → arayuz 'pasif'). */
    val hazir: Boolean get() = tip.hazir

    /** Etkin (calisan) yerel kanal / oturum sayisi. */
    fun etkinKanalSayi(): Int

    /** Kanal / oturum ozeti (arayuz durum satiri). */
    fun kanalOzet(): String

    /**
     * Arac/durum satiri: `(metin, renkKaynak)` ya da bu tip icin
     * anlamsizsa `null`.
     */
    fun aracSatiri(baglam: Context): Pair<String, Int>?

    /** Telemetri kart govdesi (cok satirli metin). */
    fun telemetriMetni(baglam: Context): String
}
