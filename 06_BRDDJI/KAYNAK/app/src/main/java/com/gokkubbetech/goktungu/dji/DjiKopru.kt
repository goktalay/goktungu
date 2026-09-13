package com.gokkubbetech.goktungu.dji

import android.content.Context
import com.gokkubbetech.goktungu.veri.GdpKoordinat
import com.gokkubbetech.goktungu.veri.Gunluk
import dji.sdk.keyvalue.key.BatteryKey
import dji.sdk.keyvalue.key.DJIKey
import dji.sdk.keyvalue.key.FlightControllerKey
import dji.sdk.keyvalue.key.KeyTools
import dji.sdk.keyvalue.key.ProductKey
import dji.sdk.keyvalue.value.common.Attitude
import dji.sdk.keyvalue.value.common.EmptyMsg
import dji.sdk.keyvalue.value.common.LocationCoordinate2D
import dji.sdk.keyvalue.value.common.Velocity3D
import dji.sdk.keyvalue.value.flightcontroller.GPSSignalLevel
import dji.v5.common.callback.CommonCallbacks
import dji.v5.common.error.IDJIError
import dji.v5.common.register.DJISDKInitEvent
import dji.v5.manager.KeyManager
import dji.v5.manager.SDKManager
import dji.v5.manager.interfaces.SDKManagerCallback
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.hypot

/**
 * DJI MSDK v5 sarmalayicisi.
 *
 * API imzalari `BULGU_msdk_api.md` icinde belgelenmistir; belgeye degil
 * paketin kendisine (javap) dayanir.
 *
 * ## Sorumluluk siniri
 *
 * Bu sinif MSDK ile konusur ve degerleri **GDP'den bagimsiz** turlerde
 * sunar.  Koordinatlar daima [GdpKoordinat] olarak disa verilir; ham
 * `LocationCoordinate2D` sizdirilmaz.  Boylece eksen sirasi hatasi
 * cagri yerlerine yayilamaz.
 */
class DjiKopru(private val baglam: Context) {

    enum class KayitDurum { BASLAMADI, BASLIYOR, KAYITLI, HATA }

    private val _kayit = MutableStateFlow(KayitDurum.BASLAMADI)
    val kayit: StateFlow<KayitDurum> = _kayit.asStateFlow()

    private val _kayitHata = MutableStateFlow("")
    val kayitHata: StateFlow<String> = _kayitHata.asStateFlow()

    /** Arac (urun) RC uzerinden bagli mi. */
    private val _urunBagli = MutableStateFlow(false)
    val urunBagli: StateFlow<Boolean> = _urunBagli.asStateFlow()

    private val _telemetri = MutableStateFlow(DjiTelemetri())
    val telemetri: StateFlow<DjiTelemetri> = _telemetri.asStateFlow()

    /** Dinleyici tutamaci; `cancelListen` bununla toplu iptal eder. */
    private val tutamak = Any()

    private val km: KeyManager get() = KeyManager.getInstance()

    // ------------------------------------------------------------------
    // Kayit
    // ------------------------------------------------------------------

    /**
     * MSDK'yi baslatir ve uygulamayi kaydeder.
     *
     * API anahtari `AndroidManifest.xml` icindeki
     * `com.dji.sdk.API_KEY` meta-verisinden okunur; kodda gomulu
     * DEGILDIR.  Anahtar paket adina baglidir (`com.gokkubbetech.goktungu`).
     */
    fun baslat() {
        if (_kayit.value == KayitDurum.BASLIYOR ||
            _kayit.value == KayitDurum.KAYITLI
        ) return
        _kayit.value = KayitDurum.BASLIYOR
        Gunluk.yaz("DJI", "MSDK baslatiliyor...")
        SDKManager.getInstance().init(baglam, object : SDKManagerCallback {
            override fun onRegisterSuccess() {
                _kayit.value = KayitDurum.KAYITLI
                _kayitHata.value = ""
                val s = SDKManager.getInstance().sdkVersion
                Gunluk.basari("DJI", "MSDK kaydi basarili (surum $s)")
            }

            override fun onRegisterFailure(hata: IDJIError?) {
                _kayit.value = KayitDurum.HATA
                val a = hata?.description() ?: hata?.toString() ?: "bilinmiyor"
                _kayitHata.value = a
                // En sik neden: API anahtari yok/yanlis veya paket adi
                // anahtarla uyusmuyor.  Bunu acikca soyle.
                Gunluk.hata("DJI", "MSDK kaydi BASARISIZ: $a — " +
                    "API anahtarinin com.gokkubbetech.goktungu paket adina " +
                    "kayitli oldugunu ve cihazin internete " +
                    "erisebildigini dogrulayin")
            }

            override fun onProductConnect(urun: Int) {
                _urunBagli.value = true
                Gunluk.basari("DJI", "Arac baglandi (urun=$urun)")
                dinlemeyeBasla()
            }

            override fun onProductDisconnect(urun: Int) {
                _urunBagli.value = false
                Gunluk.uyari("DJI", "Arac ayrildi (urun=$urun)")
            }

            override fun onProductChanged(urun: Int) {
                Gunluk.yaz("DJI", "Arac degisti (urun=$urun)")
            }

            override fun onInitProcess(
                olay: DJISDKInitEvent?, ilerleme: Int
            ) {
                if (olay?.name == "INITIALIZE_COMPLETE") {
                    Gunluk.yaz("DJI", "MSDK baslatma tamam, kayit yapiliyor")
                    SDKManager.getInstance().registerApp()
                }
            }

            override fun onDatabaseDownloadProgress(
                mevcut: Long, toplam: Long
            ) {
                if (toplam > 0 && mevcut == toplam) {
                    Gunluk.yaz("DJI", "Ucusa yasak bolge veritabani hazir")
                }
            }
        })
    }

    fun durdur() {
        try {
            km.cancelListen(tutamak)
        } catch (e: Exception) {
            Gunluk.uyari("DJI", "Dinleyiciler iptal edilemedi: ${e.message}")
        }
        try {
            SDKManager.getInstance().destroy()
        } catch (e: Exception) {
            Gunluk.uyari("DJI", "MSDK kapatilamadi: ${e.message}")
        }
        _kayit.value = KayitDurum.BASLAMADI
        _urunBagli.value = false
    }

    // ------------------------------------------------------------------
    // Telemetri
    // ------------------------------------------------------------------

    private fun <T> anahtar(bilgi: dji.sdk.keyvalue.key.DJIKeyInfo<T>):
        DJIKey<T> = KeyTools.createKey(bilgi)

    /**
     * Telemetri anahtarlarini dinlemeye baslar.
     *
     * `listen` cagrilari MSDK'nin itme (push) mekanizmasini kullanir;
     * yoklama (polling) yapilmaz.  Bu, batarya ve gecikme acisindan
     * dogru olan yontemdir.
     */
    private fun dinlemeyeBasla() {
        Gunluk.yaz("DJI", "Telemetri anahtarlari dinleniyor")

        dinle(FlightControllerKey.KeyAircraftLocation) { k ->
            // KRITIK: donusum yalniz GdpKoordinat icinde yapilir.
            val koord = GdpKoordinat.djidenOku(k)
            _telemetri.value = _telemetri.value.copy(konum = koord)
        }
        dinle(FlightControllerKey.KeyAltitude) { d ->
            _telemetri.value = _telemetri.value.copy(altRel = d ?: 0.0)
        }
        dinle(FlightControllerKey.KeyAircraftAttitude) { a: Attitude? ->
            _telemetri.value = _telemetri.value.copy(
                roll = a?.roll ?: 0.0,
                pitch = a?.pitch ?: 0.0,
                yaw = a?.yaw ?: 0.0
            )
        }
        dinle(FlightControllerKey.KeyAircraftVelocity) { v: Velocity3D? ->
            // Velocity3D: x=kuzey, y=dogu, z=asagi (NED, m/s).
            // Alanlar java.lang.Double dondurur; null olabilir.
            val x = v?.x ?: 0.0
            val y = v?.y ?: 0.0
            val z = v?.z ?: 0.0
            _telemetri.value = _telemetri.value.copy(
                yatayHiz = hypot(x, y),
                // GDP 'vz' isareti: yukari pozitif.  NED'de z asagi
                // pozitif oldugu icin isaret cevrilir.
                dikeyHiz = -z
            )
        }
        dinle(FlightControllerKey.KeyCompassHeading) { d ->
            _telemetri.value = _telemetri.value.copy(heading = d ?: 0.0)
        }
        dinle(FlightControllerKey.KeyGPSSatelliteCount) { i ->
            _telemetri.value = _telemetri.value.copy(uydu = i ?: 0)
        }
        dinle(FlightControllerKey.KeyGPSSignalLevel) { s: GPSSignalLevel? ->
            _telemetri.value = _telemetri.value.copy(
                gpsSeviye = s?.value() ?: 0
            )
        }
        dinle(FlightControllerKey.KeyIsFlying) { b ->
            _telemetri.value = _telemetri.value.copy(ucusta = b == true)
        }
        dinle(FlightControllerKey.KeyAreMotorsOn) { b ->
            _telemetri.value = _telemetri.value.copy(motorAcik = b == true)
        }
        dinle(FlightControllerKey.KeyFlightModeString) { s ->
            _telemetri.value = _telemetri.value.copy(mod = s ?: "")
        }
        dinle(FlightControllerKey.KeyHomeLocation) { k ->
            _telemetri.value = _telemetri.value.copy(
                ev = GdpKoordinat.djidenOku(k)
            )
        }
        dinle(BatteryKey.KeyChargeRemainingInPercent) { i ->
            _telemetri.value = _telemetri.value.copy(bataryaPct = i ?: 0)
        }
        dinle(BatteryKey.KeyVoltage) { i ->
            // KeyVoltage mV birimindedir
            _telemetri.value = _telemetri.value.copy(
                bataryaV = (i ?: 0) / 1000.0
            )
        }
    }

    private fun <T> dinle(
        bilgi: dji.sdk.keyvalue.key.DJIKeyInfo<T>,
        geri: (T?) -> Unit
    ) {
        val k = anahtar(bilgi)
        if (!km.isKeySupported(k)) {
            // Her arac her anahtari desteklemez; bu bir kusur degildir.
            Gunluk.uyari("DJI", "Anahtar desteklenmiyor, atlandi: " +
                bilgi.identifier)
            return
        }
        try {
            km.listen(k, tutamak,
                object : CommonCallbacks.KeyListener<T> {
                    override fun onValueChange(eski: T?, yeni: T?) {
                        try {
                            geri(yeni)
                        } catch (e: Exception) {
                            Gunluk.hata("DJI", "Telemetri isleme hatasi " +
                                "(${bilgi.identifier}): ${e.message}")
                        }
                    }
                })
        } catch (e: Exception) {
            Gunluk.hata("DJI", "Dinlenemedi (${bilgi.identifier}): " +
                "${e.message}")
        }
    }

    /** Seri numarasi; `merhaba` mesajinda kalici sysid icin kullanilir. */
    fun seriNo(): String? = try {
        km.getValue(anahtar(FlightControllerKey.KeySerialNumber))
    } catch (e: Exception) {
        null
    }

    fun urunModeli(): String = try {
        km.getValue(anahtar(ProductKey.KeyProductType))?.name ?: "DJI"
    } catch (e: Exception) {
        "DJI"
    }

    fun yazilimSurumu(): String = try {
        km.getValue(anahtar(FlightControllerKey.KeyFirmwareVersion)) ?: ""
    } catch (e: Exception) {
        ""
    }

    // ------------------------------------------------------------------
    // Ucus komutlari
    // ------------------------------------------------------------------

    /**
     * Eylem anahtari yurutur (takeoff/land/rtl gibi).
     *
     * @param geri `(basarili, mesaj)` — GDP `yanit` mesajina dogrudan
     *   donusturulur.
     */
    private fun eylem(
        bilgi: dji.sdk.keyvalue.key.DJIActionKeyInfo<EmptyMsg, EmptyMsg>,
        ad: String,
        geri: (Boolean, String) -> Unit
    ) {
        if (!_urunBagli.value) {
            geri(false, "arac bagli degil")
            return
        }
        try {
            km.performAction(
                KeyTools.createKey(bilgi), EmptyMsg(),
                object : CommonCallbacks.CompletionCallbackWithParam<EmptyMsg> {
                    override fun onSuccess(t: EmptyMsg?) {
                        Gunluk.basari("DJI", "$ad tamam")
                        geri(true, "$ad tamam")
                    }

                    override fun onFailure(hata: IDJIError) {
                        val a = hata.description() ?: hata.toString()
                        Gunluk.hata("DJI", "$ad basarisiz: $a")
                        geri(false, a)
                    }
                })
        } catch (e: Exception) {
            geri(false, e.message ?: "istisna")
        }
    }

    fun kalkis(geri: (Boolean, String) -> Unit) =
        eylem(FlightControllerKey.KeyStartTakeoff, "kalkis", geri)

    fun inis(geri: (Boolean, String) -> Unit) =
        eylem(FlightControllerKey.KeyStartAutoLanding, "inis", geri)

    fun eveDon(geri: (Boolean, String) -> Unit) =
        eylem(FlightControllerKey.KeyStartGoHome, "eve donus", geri)

    /**
     * Ev noktasini aracin anlik konumuna ayarlar.
     */
    fun evAyarlaMevcutKonum(geri: (Boolean, String) -> Unit) =
        eylem(
            FlightControllerKey
                .KeyHomeLocationUsingCurrentAircraftLocation,
            "ev noktasi (mevcut konum)", geri
        )

    /**
     * Ev noktasini belirtilen koordinata ayarlar.
     *
     * Koordinat [GdpKoordinat] turunde alinir; ham cift ALINMAZ, boylece
     * cagri yerinde eksen sirasi hatasi yapilamaz.
     */
    fun evAyarla(hedef: GdpKoordinat, geri: (Boolean, String) -> Unit) {
        if (!_urunBagli.value) {
            geri(false, "arac bagli degil")
            return
        }
        try {
            km.setValue(
                anahtar(FlightControllerKey.KeyHomeLocation),
                hedef.djiyeCevir(),
                object : CommonCallbacks.CompletionCallback {
                    override fun onSuccess() {
                        Gunluk.basari("DJI",
                            "Ev noktasi ayarlandi: ${hedef.kisa()}")
                        geri(true, "ev noktasi ayarlandi")
                    }

                    override fun onFailure(hata: IDJIError) {
                        val a = hata.description() ?: hata.toString()
                        geri(false, a)
                    }
                })
        } catch (e: Exception) {
            geri(false, e.message ?: "istisna")
        }
    }
}

/**
 * Anlik telemetri goruntusu.
 *
 * Konum [GdpKoordinat] turundedir; `null` ise arac konum bildirmiyor
 * (GPS kilidi yok veya (0,0) donuyor).  `null` durumu GDP telemetrisine
 * sifir olarak YAZILMAZ — aksi halde arac Gine Korfezi'nde gorunurdu.
 */
data class DjiTelemetri(
    val konum: GdpKoordinat? = null,
    val ev: GdpKoordinat? = null,
    val altRel: Double = 0.0,
    val altMsl: Double = 0.0,
    val roll: Double = 0.0,
    val pitch: Double = 0.0,
    val yaw: Double = 0.0,
    val heading: Double = 0.0,
    val yatayHiz: Double = 0.0,
    val dikeyHiz: Double = 0.0,
    val bataryaPct: Int = 0,
    val bataryaV: Double = 0.0,
    val uydu: Int = 0,
    val gpsSeviye: Int = 0,
    val ucusta: Boolean = false,
    val motorAcik: Boolean = false,
    val mod: String = ""
)
