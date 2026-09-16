package com.turkbey.goktungumav.arayuz

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
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungumav.BuildConfig
import com.turkbey.goktungumav.R
import com.turkbey.goktungumav.databinding.EtkinlikAnaBinding
import com.turkbey.goktungumav.kopru.KopruHizmeti
import com.turkbey.goktungumav.kopru.KopruYonetici
import com.turkbey.goktungumav.mavlink.MavlinkKopru
import com.turkbey.goktungumav.mavlink.UdpTasima
import com.turkbey.goktungumav.mavlink.UsbSeri
import com.turkbey.goktungumav.veri.AgKisiti
import com.turkbey.goktungumav.veri.Ayarlar
import com.turkbey.goktungumav.veri.Gunluk
import kotlinx.coroutines.launch

/**
 * GOKTUNGU MAVLink Koprusu — ana ekran.
 *
 * Gorevi yalniz sunum ve kullanici girisidir; is mantigi
 * [KopruYonetici] ve [MavlinkKopru] icindedir.  Koordinat donusumu bu
 * katmanda YAPILMAZ (bkz. `MavGozlemci.MavKonum` sozlesmesi).
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var bag: EtkinlikAnaBinding

    private var cihazlar: List<UsbDevice> = emptyList()

    /** USB izni verildikten sonra baglanti yeniden denenir. */
    private var izinBekleyenBaglanti = false

    private val izinSonucu = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    /**
     * USB izin yanitini alan yayin alicisi.
     *
     * Android USB izni eszamansizdir: `requestPermission` cagrisi
     * hemen doner, kullanici karari yayin olarak gelir.  Bu yuzden
     * baglanti akisi ikiye bolunmustur.
     */
    private val usbAlici = object : BroadcastReceiver() {
        override fun onReceive(baglam: Context?, niyet: Intent?) {
            if (niyet?.action != UsbSeri.EYLEM_IZIN) return
            val verildi = niyet.getBooleanExtra(
                UsbManager.EXTRA_PERMISSION_GRANTED, false
            )
            if (verildi && izinBekleyenBaglanti) {
                izinBekleyenBaglanti = false
                baglan()
            } else if (!verildi) {
                izinBekleyenBaglanti = false
                uyar(R.string.hata_usb_izin)
            }
        }
    }

    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)
        bag = EtkinlikAnaBinding.inflate(layoutInflater)
        setContentView(bag.root)

        KopruYonetici.kur(applicationContext)

        hizlariDoldur()
        ayarlariYukle()
        izinleriIste()
        cihazlariTara()

        bag.dgTara.setOnClickListener { cihazlariTara(bildir = true) }
        bag.dgBaglan.setOnClickListener { baglan() }
        bag.dgKes.setOnClickListener { kes() }
        bag.dgGunlukTemizle.setOnClickListener { Gunluk.temizle() }
        bag.dgHakkinda.setOnClickListener { hakkindaGoster() }

        // Android 14+ kayitli aliciyi acikca disa donuk/ic olarak
        // isaretlemeyi zorunlu kilar; bu yayin yalniz kendi
        // uygulamamizdan gelir.
        val suzgec = IntentFilter(UsbSeri.EYLEM_IZIN)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbAlici, suzgec, RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(usbAlici, suzgec)
        }

        akislariDinle()

        val a = Ayarlar.oku(this)
        if (a.otoBaglan && a.eksiksizMi() && cihazlar.isNotEmpty()) {
            baglan(sessiz = true)
        }

        Gunluk.yaz("ARAYUZ", "Ana ekran acildi")
    }

    override fun onDestroy() {
        runCatching { unregisterReceiver(usbAlici) }
        super.onDestroy()
    }

    // ------------------------------------------------------------ ayarlar

    private fun hizlariDoldur() {
        val uyarlayici = ArrayAdapter(
            this, android.R.layout.simple_spinner_dropdown_item,
            UsbSeri.HIZLAR.map { it.toString() }
        )
        bag.secimHiz.adapter = uyarlayici
        val v = UsbSeri.HIZLAR.indexOf(UsbSeri.VARSAYILAN_HIZ)
        if (v >= 0) bag.secimHiz.setSelection(v)
    }

    private fun ayarlariYukle() {
        val a = Ayarlar.oku(this)
        bag.girisAdres.setText(a.sunucu)
        bag.girisPort.setText(
            if (a.port > 0) a.port.toString()
            else UdpTasima.VARSAYILAN_PORT.toString()
        )
        bag.kutuOto.isChecked = a.otoBaglan
        val h = UsbSeri.HIZLAR.indexOf(a.hiz)
        if (h >= 0) bag.secimHiz.setSelection(h)
    }

    /**
     * Bagli USB seri cihazlari listeler.
     *
     * Secim kullaniciya birakilir: telefona ayni anda ucus
     * kontrolcusu ve telemetri modemi bagli olabilir.
     */
    private fun cihazlariTara(bildir: Boolean = false) {
        val kopru = KopruYonetici.kopru ?: return
        cihazlar = kopru.usb.cihazlariListele()
        val adlar = if (cihazlar.isEmpty()) {
            listOf(getString(R.string.cihaz_yok))
        } else {
            cihazlar.map { d ->
                val ad = runCatching { d.productName }.getOrNull()
                if (ad.isNullOrBlank()) {
                    String.format("%04X:%04X", d.vendorId, d.productId)
                } else {
                    "$ad  (${String.format("%04X:%04X", d.vendorId, d.productId)})"
                }
            }
        }
        bag.secimCihaz.adapter = ArrayAdapter(
            this, android.R.layout.simple_spinner_dropdown_item, adlar
        )
        if (bildir) {
            Toast.makeText(
                this,
                getString(R.string.tarama_sonuc, cihazlar.size),
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun baglan(sessiz: Boolean = false) {
        val kopru = KopruYonetici.kopru ?: return
        val adres = bag.girisAdres.text.toString().trim()
        val portMetni = bag.girisPort.text.toString().trim()

        if (adres.isEmpty()) return uyar(R.string.hata_adres_bos)
        val port = portMetni.toIntOrNull()
        if (port == null || port < 1 || port > 65535) {
            return uyar(R.string.hata_port_gecersiz)
        }
        if (cihazlar.isEmpty()) return uyar(R.string.hata_cihaz_yok)

        // Duz metin kisiti: UDP telemetrisi TLS tasimaz, bu yuzden
        // yalniz ozel ag adresleri kabul edilir.  Genel internet
        // adresine sifrelenmemis telemetri gondermek konum ve ucus
        // verisini aciga cikarir.
        if (!AgKisiti.ozelAgMi(adres)) {
            AlertDialog.Builder(this)
                .setTitle(R.string.hata_baslik)
                .setMessage(AgKisiti.redNedeni(adres))
                .setPositiveButton(R.string.hakkinda_kapat, null)
                .show()
            return
        }

        val secim = bag.secimCihaz.selectedItemPosition
            .coerceIn(0, cihazlar.size - 1)
        val cihaz = cihazlar[secim]
        val hiz = UsbSeri.HIZLAR.getOrElse(
            bag.secimHiz.selectedItemPosition
        ) { UsbSeri.VARSAYILAN_HIZ }

        // USB izni eszamansiz: izin yoksa istenir ve yayin
        // beklenir; baglanti izin gelince yeniden denenir.
        if (!kopru.usb.izinVarMi(cihaz)) {
            izinBekleyenBaglanti = true
            kopru.usb.izinIste(cihaz)
            if (!sessiz) {
                Toast.makeText(
                    this, R.string.usb_izin_isteniyor, Toast.LENGTH_SHORT
                ).show()
            }
            return
        }

        Ayarlar.yaz(
            baglam = this,
            sunucu = adres,
            port = port,
            hiz = hiz,
            otoBaglan = bag.kutuOto.isChecked
        )

        val hata = KopruYonetici.baglan(cihaz, hiz, adres, port)
        if (hata != null) {
            uyarMetin(hata)
            return
        }

        val niyet = Intent(this, KopruHizmeti::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(niyet)
        } else {
            startService(niyet)
        }
        if (!sessiz) {
            Toast.makeText(
                this, R.string.kopru_baslatildi, Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun kes() {
        KopruYonetici.kes()
        stopService(Intent(this, KopruHizmeti::class.java))
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
            if (ContextCompat.checkSelfPermission(this, i)
                != PackageManager.PERMISSION_GRANTED
            ) istenecek += i
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED
        ) istenecek += Manifest.permission.POST_NOTIFICATIONS

        if (istenecek.isNotEmpty()) izinSonucu.launch(istenecek.toTypedArray())
    }

    // ------------------------------------------------------------ akislar

    private fun akislariDinle() {
        val kopru = KopruYonetici.kopru ?: return

        // Kopru durumu
        lifecycleScope.launch {
            kopru.durum.collect { d ->
                bag.etiketUsb.text = when (d) {
                    MavlinkKopru.Durum.KAPALI ->
                        getString(R.string.durum_usb_yok)
                    MavlinkKopru.Durum.HATA ->
                        getString(
                            R.string.durum_usb_hata,
                            kopru.hataIletisi.value
                        )
                    else -> getString(
                        R.string.durum_usb_acik,
                        kopru.usb.cihazAdi, kopru.usb.hiz
                    )
                }
                bag.etiketUsb.setTextColor(
                    renk(
                        when (d) {
                            MavlinkKopru.Durum.CALISIYOR -> R.color.iyi
                            MavlinkKopru.Durum.HATA -> R.color.kotu
                            MavlinkKopru.Durum.ARAC_BEKLENIYOR ->
                                R.color.uyari
                            else -> R.color.soluk
                        }
                    )
                )

                bag.etiketMerkez.text = if (kopru.udp.acik) {
                    getString(
                        R.string.durum_merkez_bagli, kopru.udp.hedefEtiketi()
                    )
                } else {
                    getString(R.string.durum_merkez_kopuk)
                }
                bag.etiketMerkez.setTextColor(
                    renk(if (kopru.udp.acik) R.color.iyi else R.color.soluk)
                )
            }
        }

        // Arac durumu ve telemetri (SALT OKUMA gozlemden)
        lifecycleScope.launch {
            kopru.gozlemci.durum.collect { t ->
                bag.etiketArac.text = if (t.aracVar) {
                    getString(
                        R.string.durum_arac_bagli,
                        "sys ${t.sysid} · ${kopru.gozlemci.kipAdi()}"
                    )
                } else {
                    getString(R.string.durum_arac_yok)
                }
                bag.etiketArac.setTextColor(
                    renk(if (t.aracVar) R.color.iyi else R.color.soluk)
                )

                bag.etiketSayac.text = kopru.sayaclar()

                val konum = t.konum
                bag.etiketTelemetri.text = buildString {
                    if (konum == null) {
                        appendLine(getString(R.string.tel_konum_yok))
                    } else {
                        appendLine(
                            "%s  %.6f, %.6f".format(
                                getString(R.string.tel_konum),
                                konum.enlem, konum.boylam
                            )
                        )
                    }
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_irtifa),
                            t.altRel?.let { "%.1f m".format(it) }
                                ?: getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_yon),
                            t.heading?.let { "%.0f".format(it) }
                                ?: getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_batarya),
                            if (t.bataryaPct != null || t.bataryaV != null) {
                                "%s  %s".format(
                                    t.bataryaPct?.let { "$it%%" } ?: "-",
                                    t.bataryaV?.let { "%.1f V".format(it) }
                                        ?: "-"
                                )
                            } else getString(R.string.tel_deger_yok)
                        )
                    )
                    appendLine(
                        "%s  %s".format(
                            getString(R.string.tel_arm),
                            getString(
                                if (t.armed) R.string.tel_arm_acik
                                else R.string.tel_arm_kapali
                            )
                        )
                    )
                    append(
                        "%s  %s".format(
                            getString(R.string.tel_mod),
                            kopru.gozlemci.kipAdi().ifEmpty {
                                getString(R.string.tel_deger_yok)
                            }
                        )
                    )
                }
            }
        }

        // Gunluk
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
            appendLine(
                getString(R.string.uygulama_adi) + " " +
                    getString(R.string.uygulama_alt_adi)
            )
            appendLine(
                getString(R.string.hakkinda_surum, BuildConfig.VERSION_NAME)
            )
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

    override fun onResume() {
        super.onResume()
        // Kablo uygulama arka plandayken takilmis olabilir.
        cihazlariTara()
    }
}
