package com.turkbey.goktungu.kopru

import android.content.Context
import com.turkbey.goktungu.dji.DjiKopru
import com.turkbey.goktungu.dji.GorevYonetici
import com.turkbey.goktungu.veri.Ayarlar
import com.turkbey.goktungu.veri.GdpMesaj
import com.turkbey.goktungu.veri.Gunluk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket

/**
 * YEREL DJI KOPRUSU (GRCOFFANDR Faz 4).
 *
 * ## Mimari (BRDAND/BRDDJI'den FARKLI)
 *
 * BRDAND/06_BRDDJI'de DJI GDP akisi MERKEZE ters-WebSocket ([KopruAjan])
 * uzerinden gidiyordu. GRCOFFANDR TEK APK'dir: gomulu Python arka uc
 * (`goktungu/dji_kopru.py`) cihaz uzerinde bir NDJSON TCP SUNUCUSU
 * (127.0.0.1:8790) acar. Bu sinif o sunucuya YEREL ISTEMCI olarak
 * baglanir; merkez/ters-WS katmani YOKTUR.
 *
 * ```
 * DJI arac --(MSDK anahtar dinleme)--> DjiKopru.telemetri
 *          --(200 ms ornekleme)--> GdpKanal --(NDJSON satir)-->
 *          TCP 127.0.0.1:8790 (dji_kopru.py) --> gomulu Python -->
 *          WebSocket --> WebView arayuzu
 *
 * dji_kopru.py --(komut satiri)--> GdpKanal --> KomutIsleyici --> DjiKopru
 * ```
 *
 * [GdpKanal] tasima-bagimsizdir; burada [gonder] geri cagrisi ham
 * NDJSON baytlarini dogrudan yerel sokete yazar ve soketten okunan
 * baytlar [GdpKanal.yaz] ile geri beslenir. Boylece 06_BRDDJI'nin
 * cerceveleme/kalp/komut-yanit mantigi AYNEN yeniden kullanilir.
 *
 * Sunucu henuz ayakta degilse (kullanici arayuzden DJI baglantisini
 * baslatmadiysa) baglanti ustel geri cekilmeyle yeniden denenir.
 */
object YerelDjiKopru {

    /** Gomulu dji_kopru.py yerel sunucusu. */
    const val DJI_HOST = "127.0.0.1"

    /** dji_kopru.py varsayilan dinleme portu (baglantilar.py: "dji" -> 8790). */
    const val DJI_PORT = 8790

    /** Tek yerel kanal kimligi. */
    const val KANAL_ID = 1

    /** Telemetri ornekleme araligi (ms) — arayuz 5 Hz bekliyor. */
    const val TELEMETRI_ARALIK_MS = 200L

    private const val BAGLANTI_ZAMAN_ASIMI_MS = 4_000
    private const val YENIDEN_TABAN_MS = 2_000L
    private const val YENIDEN_ENUST_MS = 15_000L

    private lateinit var baglam: Context

    private var _dji: DjiKopru? = null
    val dji: DjiKopru? get() = _dji

    private var gorev: GorevYonetici? = null
    private var isleyici: KomutIsleyici? = null

    private var _kanallar: GdpKanal? = null
    val kanallar: GdpKanal? get() = _kanallar

    private var kapsam: CoroutineScope? = null
    private var baglantiIsi: Job? = null
    private var telemetriIsi: Job? = null

    @Volatile
    private var soket: Socket? = null

    /** Sokete yazma seri hale getirilir: telemetri dongusu ve komut
     *  yanitlari (okuma iş parçacığı) ayni akisa yazar. */
    private val yazKilit = Any()

    @Volatile
    private var kuruldu = false

    @Volatile
    private var calisiyor = false

    /** Bagli olup olmadigi (arayuz/bildirim icin). */
    fun bagliMi(): Boolean = soket?.isConnected == true &&
        (_kanallar?.etkinSayi() ?: 0) > 0

    /**
     * MSDK'yi ve GDP katmanini kurar. Uygulama/servis acilisinda bir kez.
     */
    fun kur(b: Context) {
        if (kuruldu) return
        kuruldu = true
        baglam = b.applicationContext
        val d = DjiKopru(baglam)
        _dji = d
        val kn = GdpKanal(
            // NDJSON satiri dogrudan yerel sokete yazilir.
            gonder = { _, v -> soketeYaz(v) },
            merhabaUretici = {
                GdpMesaj.merhaba(
                    sn = d.seriNo() ?: Ayarlar.oku(baglam).cihazKimlik,
                    model = d.urunModeli(),
                    fw = d.yazilimSurumu(),
                    videoUrl = null
                    // belirtec YOK: yerel (127.0.0.1) baglanti sunucuda
                    // belirtec istemez (dji_kopru.py `_belirtec_dogrula`).
                )
            },
            komutIsle = { komut, _ -> isleyici?.isle(komut) },
            urunBagli = { d.urunBagli.value }
        )
        _kanallar = kn
        gorev = GorevYonetici(
            baglam,
            durumBildir = { durum, nokta ->
                kn.yayinla(GdpMesaj.gorevDurum(durum, nokta))
            },
            yuklemeBildir = { y, t, durum, mesaj ->
                kn.yayinla(GdpMesaj.gorevYukleme(y, t, durum, mesaj))
            }
        )
        isleyici = KomutIsleyici(d, gorev!!) { m -> kn.yayinla(m) }
        d.baslat()
        Gunluk.yaz("KOPRU", "Yerel DJI koprusu kuruldu " +
            "(hedef $DJI_HOST:$DJI_PORT)")
    }

    /** Baglanti + telemetri donguleri baslatilir. */
    fun baslat() {
        if (!kuruldu) return
        if (calisiyor) return
        calisiyor = true
        gorev?.baslatModulu()
        val k = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        kapsam = k
        baglantiIsi = k.launch { baglantiDongusu() }
        telemetriIsi = k.launch { telemetriDongusu() }
        Gunluk.yaz("KOPRU", "Yerel DJI koprusu baslatildi")
    }

    fun durdur() {
        calisiyor = false
        telemetriIsi?.cancel()
        telemetriIsi = null
        baglantiIsi?.cancel()
        baglantiIsi = null
        _kanallar?.tumunuKapat()
        runCatching { soket?.close() }
        soket = null
        kapsam?.cancel()
        kapsam = null
        Gunluk.yaz("KOPRU", "Yerel DJI koprusu durduruldu")
    }

    // ------------------------------------------------------------------
    // Yerel soket tasima
    // ------------------------------------------------------------------
    private fun soketeYaz(v: ByteArray): Boolean {
        val s = soket ?: return false
        return try {
            synchronized(yazKilit) {
                val cikti = s.getOutputStream()
                cikti.write(v)
                cikti.flush()
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    private suspend fun baglantiDongusu() {
        val kn = _kanallar ?: return
        var bekleme = YENIDEN_TABAN_MS
        while (calisiyor) {
            var s: Socket? = null
            try {
                s = Socket()
                s.tcpNoDelay = true
                s.connect(
                    InetSocketAddress(DJI_HOST, DJI_PORT),
                    BAGLANTI_ZAMAN_ASIMI_MS
                )
                soket = s
                bekleme = YENIDEN_TABAN_MS

                // Kanali ac: `merhaba` ILK satir olarak gonderilir, kalp
                // dongusu baslar. `gonder` bu noktada `soket`e yazar.
                kn.kapat(KANAL_ID)
                val (_, hata) = kn.ac(
                    KANAL_ID,
                    JSONObject().put("tur", "dji").put("isim", "Yerel DJI")
                )
                if (hata != null) throw IOException("kanal acilamadi: $hata")
                Gunluk.basari("KOPRU",
                    "Yerel DJI sunucusuna baglanildi ($DJI_HOST:$DJI_PORT)")

                // Okuma dongusu: sunucudan gelen komut satirlari.
                val giris = s.getInputStream()
                val tampon = ByteArray(65536)
                while (calisiyor) {
                    val n = giris.read(tampon)
                    if (n < 0) break
                    if (n > 0) kn.yaz(KANAL_ID, tampon.copyOf(n))
                }
            } catch (e: Exception) {
                if (calisiyor) {
                    Gunluk.uyari("KOPRU",
                        "Yerel DJI baglantisi yok: ${e.message} " +
                            "(${bekleme / 1000} sn sonra yeniden)")
                }
            } finally {
                kn.kapat(KANAL_ID)
                runCatching { s?.close() }
                if (soket === s) soket = null
            }
            if (!calisiyor) break
            delay(bekleme)
            bekleme = (bekleme * 2).coerceAtMost(YENIDEN_ENUST_MS)
        }
    }

    /**
     * Telemetri ornekleme dongusu. Konum yoksa GONDERILMEZ: (0,0)
     * gondermek araci Gine Korfezi'nde gosterirdi.
     */
    private suspend fun telemetriDongusu() {
        val d = _dji ?: return
        val kn = _kanallar ?: return
        while (calisiyor) {
            try {
                if (kn.etkinSayi() > 0) {
                    val t = d.telemetri.value
                    val konum = t.konum
                    if (konum != null) {
                        kn.yayinla(
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
                    }
                }
            } catch (e: Exception) {
                Gunluk.hata("KOPRU", "Telemetri dongusu: ${e.message}")
            }
            delay(TELEMETRI_ARALIK_MS)
        }
    }
}
