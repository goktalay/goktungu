package com.turkbey.goktungu.bridge.arayuz

import android.Manifest
import android.app.AlertDialog
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.GravityCompat
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.databinding.EtkinlikAnaBinding
import com.turkbey.goktungu.bridge.kopru.KimlikKodu
import com.turkbey.goktungu.bridge.kopru.KopruAjan
import com.turkbey.goktungu.bridge.kopru.KopruHizmeti
import com.turkbey.goktungu.bridge.kopru.KopruKimlik
import com.turkbey.goktungu.bridge.kopru.KopruTipi
import com.turkbey.goktungu.bridge.kopru.KopruYonetici
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Ayarlar
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * GOKTUNGU Koprusu — ana ekran (Faz 2: SOL MENULU cok-kopru arayuzu).
 *
 * Sol menuden (DrawerLayout + NavigationView) kopru tipi secilir:
 * ArduPilot / BetaFlight / DJI Mobile SDK / Elektro-Optik / Radar. Secilen
 * tipin durum ve telemetri kartlari gosterilir; kurulum (GRCON/GRCOFF +
 * API kodu) ve gunluk kartlari kopru tipinden BAGIMSIZ ortaktir.
 *
 * Is mantigi [KopruYonetici] koordinatorunde ve tipe ozel
 * [com.turkbey.goktungu.bridge.kopru.KopruStrateji] gerceklemelerindedir;
 * bu sinif yalniz sunum yapar. Durum/telemetri tek bir 1 sn'lik yoklama
 * dongusunden gelir; boylece tip degisince yeniden abone olmak gerekmez.
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var bag: EtkinlikAnaBinding
    private var cihazlar: List<UsbDevice> = emptyList()

    private val izinSonucu = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    /** USB izin yaniti (eszamansiz). */
    private val usbAlici = object : BroadcastReceiver() {
        override fun onReceive(baglam: Context?, niyet: Intent?) {
            if (niyet?.action != UsbSeri.EYLEM_IZIN) return
            val verildi = niyet.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
            Gunluk.yaz("USB", if (verildi) "USB izni verildi" else "USB izni reddedildi")
            cihazlariTara()
        }
    }

    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)
        bag = EtkinlikAnaBinding.inflate(layoutInflater)
        setContentView(bag.root)

        KopruYonetici.kur(applicationContext)
        izinleriIste()

        bag.dgKur.setOnClickListener { kurulumKaydet() }
        bag.dgBaslat.setOnClickListener { baslat(sessiz = false) }
        bag.dgKes.setOnClickListener { durdur() }
        bag.dgTara.setOnClickListener { cihazlariTara(bildir = true) }
        bag.dgUsbIzin.setOnClickListener { usbIzniIste() }
        bag.dgKimlikSil.setOnClickListener { kimlikSilSor() }
        bag.dgGunlukTemizle.setOnClickListener { Gunluk.temizle() }
        bag.dgHakkinda.setOnClickListener { hakkindaGoster() }
        bag.dgMenu.setOnClickListener { bag.drawer.openDrawer(GravityCompat.START) }
        bag.kutuOto.setOnCheckedChangeListener { _, secili ->
            Ayarlar.otoBaslatYaz(this, secili)
        }
        bag.radioGrcon.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }
        bag.radioGrcoff.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }

        // Sol menu: kopru tipi secimi (tek secilebilir grup).
        menuIsaretle(KopruYonetici.aktifTip.value)
        bag.navGoruntu.setNavigationItemSelectedListener { oge ->
            tipSec(menuTip(oge.itemId))
            bag.drawer.closeDrawer(GravityCompat.START)
            true
        }

        val suzgec = IntentFilter(UsbSeri.EYLEM_IZIN)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbAlici, suzgec, RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(usbAlici, suzgec)
        }

        bag.kutuOto.isChecked = Ayarlar.oku(this).otoBaslat
        kurulumNotuTazele()
        gorunumTazele()
        cihazlariTara()
        durumDongusu()

        // Kimlik varsa ve tercih acik ise kendiliginden baslar: saha
        // pilotu telefonu acar, secili kopru tipi merkeze baglanir.
        if (KopruKimlik.var_(this) && Ayarlar.oku(this).otoBaslat &&
            !KopruYonetici.calisiyorMu()
        ) {
            baslat(sessiz = true)
        }
        Gunluk.yaz("ARAYUZ", "Ana ekran acildi (aktif tip: ${KopruYonetici.aktifTip.value.etiket})")
    }

    override fun onDestroy() {
        runCatching { unregisterReceiver(usbAlici) }
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        cihazlariTara()
        gorunumTazele()
    }

    // ------------------------------------------------------------ kopru tipi

    private fun menuTip(itemId: Int): KopruTipi = when (itemId) {
        R.id.tip_betaflight -> KopruTipi.BETAFLIGHT
        R.id.tip_dji -> KopruTipi.DJI
        R.id.tip_eo -> KopruTipi.ELEKTRO_OPTIK
        R.id.tip_radar -> KopruTipi.RADAR
        else -> KopruTipi.ARDUPILOT
    }

    private fun tipMenuId(tip: KopruTipi): Int = when (tip) {
        KopruTipi.BETAFLIGHT -> R.id.tip_betaflight
        KopruTipi.DJI -> R.id.tip_dji
        KopruTipi.ELEKTRO_OPTIK -> R.id.tip_eo
        KopruTipi.RADAR -> R.id.tip_radar
        KopruTipi.ARDUPILOT -> R.id.tip_ardupilot
    }

    private fun menuIsaretle(tip: KopruTipi) {
        bag.navGoruntu.setCheckedItem(tipMenuId(tip))
    }

    /** Sol menuden kopru tipi secilince: onceki durdurulur, yenisi kurulur. */
    private fun tipSec(tip: KopruTipi) {
        if (KopruYonetici.aktifTip.value == tip) return
        // Etkin kopruyu ve on plan hizmetini durdur (tek ajan baglanir).
        durdur()
        KopruYonetici.secTip(tip)
        menuIsaretle(tip)
        cihazlariTara()
        gorunumTazele()
        Toast.makeText(
            this, getString(R.string.tip_secili, tip.etiket), Toast.LENGTH_SHORT
        ).show()
    }

    // ------------------------------------------------------------ kurulum

    private fun kurulumNotuTazele() {
        bag.etiketKurulumNot.text = getString(
            if (bag.radioGrcoff.isChecked) R.string.kurulum_not_grcoff
            else R.string.kurulum_not_grcon
        )
    }

    private fun kurulumKaydet() {
        val secim = if (bag.radioGrcoff.isChecked) "grcoff" else "grcon"
        val ham = bag.girisKod.text.toString()
        when (val s = KimlikKodu.coz(ham)) {
            is KimlikKodu.Sonuc.Gecersiz -> {
                uyarMetin(getString(R.string.hata_kod, s.neden))
            }

            is KimlikKodu.Sonuc.Gecerli -> {
                val kod = s.kod
                if (kod.tur.isNotBlank() && kod.tur != secim) {
                    uyarMetin(
                        getString(
                            R.string.hata_kod_secim,
                            if (kod.tur == "grcoff") "GRCOFF" else "GRCON",
                            if (secim == "grcoff") "GRCOFF" else "GRCON"
                        )
                    )
                    return
                }
                KopruYonetici.durdur()
                KopruKimlik.yaz(this, kod, secim)
                bag.girisKod.setText("")
                Gunluk.yaz(
                    "KURULUM",
                    "API kodu ile kurulum: ${kod.ad} (${secim.uppercase()}) -> ${kod.merkezAdres}"
                )
                Toast.makeText(this, R.string.kurulum_tamam, Toast.LENGTH_SHORT).show()
                gorunumTazele()
                baslat(sessiz = true)
            }
        }
    }

    private fun kimlikSilSor() {
        AlertDialog.Builder(this)
            .setTitle(R.string.kimlik_sil_baslik)
            .setMessage(R.string.kimlik_sil_govde)
            .setPositiveButton(R.string.kimlik_sil_onay) { _, _ ->
                durdur()
                KopruKimlik.sil(this)
                Gunluk.uyari("KURULUM", "Kurulum kimligi silindi")
                gorunumTazele()
            }
            .setNegativeButton(R.string.hakkinda_kapat, null)
            .show()
    }

    // ------------------------------------------------------------ calisma

    private fun baslat(sessiz: Boolean) {
        if (!KopruYonetici.baslat()) {
            if (!sessiz) uyar(R.string.hata_kimlik_yok)
            return
        }
        val niyet = Intent(this, KopruHizmeti::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(niyet)
        } else {
            startService(niyet)
        }
        if (!sessiz) Toast.makeText(this, R.string.kopru_baslatildi, Toast.LENGTH_SHORT).show()
        gorunumTazele()
    }

    private fun durdur() {
        KopruYonetici.durdur()
        stopService(Intent(this, KopruHizmeti::class.java))
        gorunumTazele()
    }

    private fun cihazlariTara(bildir: Boolean = false) {
        val usb = KopruYonetici.usb ?: return
        cihazlar = usb.cihazlariListele()
        val adlar = if (cihazlar.isEmpty()) {
            listOf(getString(R.string.cihaz_yok))
        } else {
            cihazlar.map { d ->
                usb.cihazEtiketi(d) +
                    (if (usb.izinVarMi(d)) "  ✓" else "  (" + getString(R.string.usb_izin_yok) + ")")
            }
        }
        bag.secimCihaz.adapter = ArrayAdapter(
            this, android.R.layout.simple_spinner_dropdown_item, adlar
        )
        val izinli = cihazlar.count { usb.izinVarMi(it) }
        bag.etiketUsb.text = if (cihazlar.isEmpty()) {
            getString(R.string.durum_usb_yok)
        } else {
            getString(R.string.durum_usb_var, cihazlar.size, izinli)
        }
        bag.etiketUsb.setTextColor(
            renk(
                when {
                    cihazlar.isEmpty() -> R.color.soluk
                    izinli == cihazlar.size -> R.color.iyi
                    else -> R.color.uyari
                }
            )
        )
        if (bildir) {
            Toast.makeText(
                this, getString(R.string.tarama_sonuc, cihazlar.size), Toast.LENGTH_SHORT
            ).show()
        }
    }

    /**
     * Secili USB cihaz icin izin ister. Izin ONCEDEN verilmelidir:
     * merkez `akis_ac` dediginde kullanici basinda olmayabilir.
     */
    private fun usbIzniIste() {
        val usb = KopruYonetici.usb ?: return
        if (cihazlar.isEmpty()) return uyar(R.string.hata_cihaz_yok)
        val secim = bag.secimCihaz.selectedItemPosition.coerceIn(0, cihazlar.size - 1)
        val d = cihazlar[secim]
        if (usb.izinVarMi(d)) {
            Toast.makeText(this, R.string.usb_izin_var, Toast.LENGTH_SHORT).show()
            return
        }
        usb.izinIste(d)
        Toast.makeText(this, R.string.usb_izin_isteniyor, Toast.LENGTH_SHORT).show()
    }

    private fun uyar(kaynak: Int) {
        Toast.makeText(this, kaynak, Toast.LENGTH_LONG).show()
    }

    private fun uyarMetin(ileti: String) {
        Toast.makeText(this, ileti, Toast.LENGTH_LONG).show()
    }

    // ------------------------------------------------------------ izinler

    private fun izinleriIste() {
        val istenecek = mutableListOf<String>()
        for (i in listOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )) {
            if (ContextCompat.checkSelfPermission(this, i) != PackageManager.PERMISSION_GRANTED) {
                istenecek += i
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) istenecek += Manifest.permission.POST_NOTIFICATIONS
        if (istenecek.isNotEmpty()) izinSonucu.launch(istenecek.toTypedArray())
    }

    // ------------------------------------------------------------ gorunum

    /** Aktif tip etiketi, kart gorunurlukleri, USB bolumu ve kimlik. */
    private fun gorunumTazele() {
        val tip = KopruYonetici.aktifTip.value
        bag.etiketTip.text = tip.etiket

        val k = KopruKimlik.oku(this)
        val kimlikVar = k != null && k.eksiksizMi()
        bag.kartKurulum.visibility = if (kimlikVar) View.GONE else View.VISIBLE
        bag.kartKimlik.visibility = if (kimlikVar) View.VISIBLE else View.GONE
        if (k != null && kimlikVar) {
            bag.etiketKimlik.text = getString(
                R.string.kimlik_ozet,
                k.ad.ifBlank { "—" }, k.turEtiketi(), k.merkezAdres
            )
        }

        // USB bolumu ve durum satiri yalniz seri kullanan tiplerde.
        val seri = tip.seriKullanir
        bag.bolumUsb.visibility = if (seri) View.VISIBLE else View.GONE
        bag.etiketUsb.visibility = if (seri) View.VISIBLE else View.GONE

        val calisiyor = KopruYonetici.calisiyorMu()
        bag.dgBaslat.isEnabled = kimlikVar && !calisiyor
        bag.dgKes.isEnabled = calisiyor
    }

    // ------------------------------------------------------------ durum dongusu

    /**
     * Tek yoklama dongusu: merkez baglantisi, kanal, arac ve telemetri
     * satirlarini AKTIF stratejiden 1 sn'de bir okur. Boylece kopru tipi
     * degisince arayuzun yeniden abone olmasi gerekmez. Gunluk ayrica
     * tepkimeli olarak izlenir.
     */
    private fun durumDongusu() {
        lifecycleScope.launch {
            while (true) {
                tazeleDurum()
                delay(1000)
            }
        }

        lifecycleScope.launch {
            Gunluk.kayitlar.collect { kayitlar ->
                bag.etiketGunluk.text = if (kayitlar.isEmpty()) {
                    getString(R.string.gunluk_bos)
                } else {
                    kayitlar.takeLast(60).reversed().joinToString("\n") { kt ->
                        "${kt.zamanMetni()} [${kt.etiket}] ${kt.ileti}"
                    }
                }
            }
        }
    }

    private fun tazeleDurum() {
        val strateji = KopruYonetici.aktif
        val ajan = KopruYonetici.ajan

        // Merkez baglantisi
        val d = ajan?.durum?.value ?: KopruAjan.Durum.KAPALI
        val bilgi = ajan?.bilgi?.value ?: KopruAjan.Bilgi()
        val (merkezMetin, merkezRenk) = when (d) {
            KopruAjan.Durum.BAGLI -> getString(
                R.string.durum_merkez_bagli,
                bilgi.ad.ifBlank { "#${bilgi.ornekId}" }, bilgi.adres
            ) to R.color.iyi
            KopruAjan.Durum.BAGLANIYOR -> getString(R.string.durum_merkez_baglaniyor) to R.color.uyari
            KopruAjan.Durum.HATA -> getString(
                R.string.durum_merkez_hata, ajan?.sonHata?.value ?: ""
            ) to R.color.kotu
            else -> if (KopruYonetici.calisiyorMu()) {
                getString(R.string.durum_merkez_yeniden) to R.color.soluk
            } else {
                getString(R.string.durum_merkez_kopuk) to R.color.soluk
            }
        }
        bag.etiketMerkez.text = merkezMetin
        bag.etiketMerkez.setTextColor(renk(merkezRenk))

        // Kanal / oturum
        val n = KopruYonetici.etkinKanalSayi()
        val ozet = strateji.kanalOzet()
        bag.etiketKanal.text = when {
            n > 0 -> getString(R.string.durum_kanal_var, n, ozet)
            ozet.isNotBlank() -> ozet
            else -> getString(R.string.durum_kanal_yok)
        }
        bag.etiketKanal.setTextColor(renk(if (n > 0) R.color.iyi else R.color.soluk))

        // Arac / durum satiri
        val arac = strateji.aracSatiri(this)
        if (arac != null) {
            bag.etiketArac.visibility = View.VISIBLE
            bag.etiketArac.text = arac.first
            bag.etiketArac.setTextColor(renk(arac.second))
        } else {
            bag.etiketArac.visibility = View.GONE
        }

        // Sayac
        bag.etiketSayac.text = getString(
            R.string.durum_sayac,
            bilgi.gidenAkisByte / 1024, bilgi.gelenAkisByte / 1024
        )

        // Telemetri
        bag.etiketTelemetri.text = strateji.telemetriMetni(this)

        // Baslat/durdur dugmeleri
        val kimlikVar = KopruKimlik.var_(this)
        val calisiyor = KopruYonetici.calisiyorMu()
        bag.dgBaslat.isEnabled = kimlikVar && !calisiyor
        bag.dgKes.isEnabled = calisiyor
    }

    private fun renk(kaynak: Int) = ContextCompat.getColor(this, kaynak)

    private fun hakkindaGoster() {
        val govde = buildString {
            appendLine(getString(R.string.uygulama_adi) + " " + getString(R.string.uygulama_alt_adi))
            appendLine(getString(R.string.hakkinda_surum, BuildConfig.VERSION_NAME))
            appendLine(getString(R.string.hakkinda_telif))
            appendLine()
            appendLine(getString(R.string.hakkinda_lisans))
            append(getString(R.string.hakkinda_lisans_metni))
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.hakkinda_baslik)
            .setMessage(govde)
            .setPositiveButton(R.string.hakkinda_kapat, null)
            .show()
    }
}
