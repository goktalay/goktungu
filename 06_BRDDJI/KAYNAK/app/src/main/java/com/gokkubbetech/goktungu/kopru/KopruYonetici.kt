package com.gokkubbetech.goktungu.kopru

import android.content.Context
import com.gokkubbetech.goktungu.dji.DjiKopru
import com.gokkubbetech.goktungu.dji.GorevYonetici
import com.gokkubbetech.goktungu.veri.Ayarlar
import com.gokkubbetech.goktungu.veri.GdpMesaj
import com.gokkubbetech.goktungu.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Kopru cekirdegi: DJI MSDK ile GDP sunucusunu birlestirir.
 *
 * Tek ornek (singleton) olarak tutulur cunku MSDK de tek ornektir;
 * ikinci bir kayit denemesi hataya yol acar.
 *
 * ## Akis
 *
 * ```
 * DJI arac --(MSDK anahtar dinleme)--> DjiKopru.telemetri
 *          --(periyodik ornekleme)--> GdpIstemci --(NDJSON/TCP)--> merkez
 * merkez --(komut)--> KomutIsleyici --> DjiKopru / GorevYonetici
 * ```
 */
object KopruYonetici {

    /** Telemetri gonderim araligi (ms).  Merkez 5 Hz bekliyor. */
    const val TELEMETRI_ARALIK_MS = 200L

    private var kapsam: CoroutineScope? = null
    private var telemetriIsi: Job? = null

    private var _dji: DjiKopru? = null
    val dji: DjiKopru? get() = _dji

    private var _istemci: GdpIstemci? = null
    val istemci: GdpIstemci? get() = _istemci

    private var gorev: GorevYonetici? = null
    private var isleyici: KomutIsleyici? = null

    private val _calisiyor = MutableStateFlow(false)
    val calisiyor: StateFlow<Boolean> = _calisiyor.asStateFlow()

    /** Sunucuya gonderilen telemetri ornegi sayisi (tanisal). */
    private val _ornekSayisi = MutableStateFlow(0L)
    val ornekSayisi: StateFlow<Long> = _ornekSayisi.asStateFlow()

    @Volatile
    private var kuruldu = false

    /**
     * MSDK'yi baslatir.  Uygulama acilisinda bir kez cagrilir.
     */
    fun kur(baglam: Context) {
        if (kuruldu) return
        kuruldu = true
        val d = DjiKopru(baglam.applicationContext)
        _dji = d
        gorev = GorevYonetici(
            baglam.applicationContext,
            durumBildir = { durum, nokta ->
                _istemci?.gonder(GdpMesaj.gorevDurum(durum, nokta))
            },
            yuklemeBildir = { y, t, durum, mesaj ->
                _istemci?.gonder(GdpMesaj.gorevYukleme(y, t, durum, mesaj))
            }
        )
        d.baslat()
    }

    /**
     * Merkeze baglanir ve telemetri akisini baslatir.
     */
    fun baglan(baglam: Context, ayarlar: Ayarlar.Deger) {
        val d = _dji ?: run {
            Gunluk.hata("KOPRU", "MSDK kurulmadan baglanti denendi")
            return
        }
        kes()

        val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        kapsam = k

        val g = gorev
        if (g != null) g.baslatModulu()

        val ist = GdpIstemci(k)
        _istemci = ist

        val isl = KomutIsleyici(d, g!!) { m -> ist.gonder(m) }
        isleyici = isl

        ist.komutIsleyici = { komut -> isl.isle(komut) }
        ist.merhabaUretici = {
            GdpMesaj.merhaba(
                sn = d.seriNo() ?: ayarlar.cihazKimlik,
                model = d.urunModeli(),
                fw = d.yazilimSurumu(),
                videoUrl = null,
                // BULGU_07: belirtec el sikismada gonderilir.
                belirtec = ayarlar.belirtec
            )
        }

        ist.baslat(ayarlar.sunucu, ayarlar.port, ayarlar.tls)
        telemetriIsi = k.launch { telemetriDongusu() }
        _calisiyor.value = true
        Gunluk.yaz("KOPRU", "Kopru baslatildi -> " +
            "${ayarlar.sunucu}:${ayarlar.port}")
    }

    fun kes() {
        telemetriIsi?.cancel()
        telemetriIsi = null
        _istemci?.durdur()
        _istemci = null
        isleyici = null
        kapsam = null
        _calisiyor.value = false
    }

    /**
     * Telemetri gonderim dongusu.
     *
     * ## Neden ornekleme, itme degil
     *
     * MSDK anahtarlari bagimsiz olarak ve cok sik tetiklenir; her
     * degisimde mesaj gondermek agi gereksiz doldurur.  Bunun yerine
     * en son durum sabit araliklarla orneklenir.
     *
     * ## Konum yoksa gonderilmez
     *
     * `konum == null` ise (GPS kilidi yok veya (0,0)) telemetri
     * GONDERILMEZ.  Sifir gondermek araci Gine Korfezi'nde gosterirdi.
     */
    private suspend fun telemetriDongusu() {
        val d = _dji ?: return
        while (true) {
            try {
                val ist = _istemci
                if (ist == null) return
                ist.urunBagli = d.urunBagli.value

                if (ist.durum.value == GdpIstemci.Durum.BAGLI) {
                    val t = d.telemetri.value
                    val konum = t.konum
                    if (konum != null) {
                        ist.gonder(
                            GdpMesaj.telemetri(
                                konum = konum,
                                altMsl = t.altMsl,
                                altRel = t.altRel,
                                heading = t.heading,
                                hiz = t.yatayHiz,
                                vz = t.dikeyHiz,
                                roll = t.roll,
                                pitch = t.pitch,
                                bataryaPct = t.bataryaPct,
                                bataryaV = t.bataryaV,
                                gpsFix = t.gpsSeviye,
                                uydu = t.uydu,
                                mod = t.mod,
                                armed = t.motorAcik,
                                ucusta = t.ucusta,
                                ev = t.ev
                            )
                        )
                        _ornekSayisi.value = _ornekSayisi.value + 1
                    }
                }
            } catch (e: Exception) {
                Gunluk.hata("KOPRU", "Telemetri dongusu: ${e.message}")
            }
            delay(TELEMETRI_ARALIK_MS)
        }
    }
}
