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
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungu.bridge.BuildConfig
import com.turkbey.goktungu.bridge.R
import com.turkbey.goktungu.bridge.databinding.EtkinlikAnaBinding
import com.turkbey.goktungu.bridge.kopru.KimlikKodu
import com.turkbey.goktungu.bridge.kopru.KopruAjan
import com.turkbey.goktungu.bridge.kopru.KopruHizmeti
import com.turkbey.goktungu.bridge.kopru.KopruKimlik
import com.turkbey.goktungu.bridge.kopru.KopruYonetici
import com.turkbey.goktungu.bridge.mavlink.UsbSeri
import com.turkbey.goktungu.bridge.veri.Ayarlar
import com.turkbey.goktungu.bridge.veri.Gunluk
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * GOKTUNGU MAVLink Koprusu — ana ekran (1.1.0).
 *
 * Iki hal vardir:
 *  1. KURULUM: kimlik yok. "GRCON — Merkez Sunucu mu, GRCOFF — Yerel
 *     Kurulum mu?" secimi + API kodu. Kod merkezin Destek > Kopruler
 *     panelinden kopyalanir ve adresi de tasidigi icin IP/port
 *     girilmez.
 *  2. CALISMA: kimlik var. Ajan merkeze bagli; USB cihazlar
 *     bildirilir, kanallar merkezden acilir. Ekran yalniz durum,
 *     USB izni, baslat/durdur ve gunluk gosterir.
 *
 * Is mantigi [KopruYonetici] icindedir; bu sinif yalniz sunum yapar.
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
        bag.kutuOto.setOnCheckedChangeListener { _, secili ->
            Ayarlar.otoBaslatYaz(this, secili)
        }
        bag.radioGrcon.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }
        bag.radioGrcoff.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }

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
        akislariDinle()

        // Kimlik varsa ve tercih acik ise kendiliginden baslar: saha
        // pilotu telefonu acar, kopru merkeze baglanir.
        if (KopruKimlik.var_(this) && Ayarlar.oku(this).otoBaslat &&
            !KopruYonetici.calisiyorMu()
        ) {
            baslat(sessiz = true)
        }
        Gunluk.yaz("ARAYUZ", "Ana ekran acildi")
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

    /** Kurulum/calisma kartlarinin gorunurlugu ve kimlik etiketi. */
    private fun gorunumTazele() {
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
        val calisiyor = KopruYonetici.calisiyorMu()
        bag.dgBaslat.isEnabled = kimlikVar && !calisiyor
        bag.dgKes.isEnabled = calisiyor
    }

    private fun akislariDinle() {
        val ajan = KopruYonetici.ajan ?: return

        lifecycleScope.launch {
            ajan.durum.collect { d ->
                val b = ajan.bilgi.value
                bag.etiketMerkez.text = when (d) {
                    KopruAjan.Durum.BAGLI -> getString(
                        R.string.durum_merkez_bagli, b.ad.ifBlank { "#" + b.ornekId }, b.adres
                    )
                    KopruAjan.Durum.BAGLANIYOR -> getString(R.string.durum_merkez_baglaniyor)
                    KopruAjan.Durum.HATA -> getString(
                        R.string.durum_merkez_hata, ajan.sonHata.value
                    )
                    else -> if (KopruYonetici.calisiyorMu()) {
                        getString(R.string.durum_merkez_yeniden)
                    } else {
                        getString(R.string.durum_merkez_kopuk)
                    }
                }
                bag.etiketMerkez.setTextColor(
                    renk(
                        when (d) {
                            KopruAjan.Durum.BAGLI -> R.color.iyi
                            KopruAjan.Durum.HATA -> R.color.kotu
                            KopruAjan.Durum.BAGLANIYOR -> R.color.uyari
                            else -> R.color.soluk
                        }
                    )
                )
                gorunumTazele()
            }
        }

        // Kanal ve sayac satiri: kanallar merkezden acilir; yoklamayla
        // gosterilir (basit ve yeterli).
        lifecycleScope.launch {
            while (true) {
                val k = KopruYonetici.kanallar
                val n = k?.etkinSayi() ?: 0
                bag.etiketKanal.text = if (n == 0) {
                    getString(R.string.durum_kanal_yok)
                } else {
                    getString(R.string.durum_kanal_var, n, k?.ozet() ?: "")
                }
                bag.etiketKanal.setTextColor(renk(if (n > 0) R.color.iyi else R.color.soluk))
                val b = ajan.bilgi.value
                bag.etiketSayac.text = getString(
                    R.string.durum_sayac, b.gidenAkisByte / 1024, b.gelenAkisByte / 1024
                )
                delay(1000)
            }
        }

        lifecycleScope.launch {
            KopruYonetici.gozlemci.durum.collect { t ->
                bag.etiketArac.text = if (t.aracVar) {
                    getString(
                        R.string.durum_arac_bagli,
                        "sys ${t.sysid} · ${KopruYonetici.gozlemci.kipAdi()}"
                    )
                } else {
                    getString(R.string.durum_arac_yok)
                }
                bag.etiketArac.setTextColor(renk(if (t.aracVar) R.color.iyi else R.color.soluk))
                val konum = t.konum
                bag.etiketTelemetri.text = buildString {
                    if (konum == null) {
                        appendLine(getString(R.string.tel_konum_yok))
                    } else {
                        appendLine(
                            "%s  %.6f, %.6f".format(
                                getString(R.string.tel_konum), konum.enlem, konum.boylam
                            )
                        )
                    }
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_irtifa),
                            t.altRel?.let { "%.1f m".format(it) } ?: getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_yon),
                            t.heading?.let { "%.0f".format(it) } ?: getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_batarya),
                            if (t.bataryaPct != null || t.bataryaV != null) {
                                "%s  %s".format(
                                    t.bataryaPct?.let { "$it%%" } ?: "-",
                                    t.bataryaV?.let { "%.1f V".format(it) } ?: "-"
                                )
                            } else getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_arm),
                            getString(if (t.armed) R.string.tel_arm_acik else R.string.tel_arm_kapali)
                        )
                    )
                    append(
                        "%s  %s".format(
                            getString(R.string.tel_mod),
                            KopruYonetici.gozlemci.kipAdi().ifEmpty { getString(R.string.tel_deger_yok) }
                        )
                    )
                }
            }
        }

        lifecycleScope.launch {
            Gunluk.kayitlar.collect { kayitlar ->
                bag.etiketGunluk.text = if (kayitlar.isEmpty()) {
                    getString(R.string.gunluk_bos)
                } else {
                    kayitlar.takeLast(60).reversed().joinToString("\n") { k ->
                        "${k.zamanMetni()} [${k.etiket}] ${k.ileti}"
                    }
                }
            }
        }
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
