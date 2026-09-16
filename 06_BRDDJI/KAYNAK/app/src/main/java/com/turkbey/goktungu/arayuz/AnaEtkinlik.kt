package com.turkbey.goktungu.arayuz

import android.Manifest
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungu.BuildConfig
import com.turkbey.goktungu.R
import com.turkbey.goktungu.databinding.EtkinlikAnaBinding
import com.turkbey.goktungu.dji.DjiKopru
import com.turkbey.goktungu.kopru.GdpIstemci
import com.turkbey.goktungu.kopru.KopruHizmeti
import com.turkbey.goktungu.kopru.KopruYonetici
import com.turkbey.goktungu.veri.Ayarlar
import com.turkbey.goktungu.veri.Gunluk
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * GOKTUNGU DJI Koprusu — ana ekran.
 *
 * Gorevi yalniz sunum ve kullanici girisidir; is mantigi
 * [KopruYonetici] icindedir.  Koordinat donusumu bu katmanda
 * YAPILMAZ (bkz. GdpKoordinat sozlesmesi).
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var bag: EtkinlikAnaBinding

    /** Konum + bildirim izinleri; telemetri icin konum zorunludur. */
    private val izinSonucu = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        val konumVar = ContextCompat.checkSelfPermission(
            this, Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        if (!konumVar) {
            Gunluk.uyari("IZIN", getString(R.string.izin_reddedildi))
            Toast.makeText(
                this, R.string.izin_reddedildi, Toast.LENGTH_LONG
            ).show()
        }
    }

    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)
        bag = EtkinlikAnaBinding.inflate(layoutInflater)
        setContentView(bag.root)

        ayarlariYukle()
        izinleriIste()

        bag.dgBaglan.setOnClickListener { baglan() }
        bag.dgKes.setOnClickListener { kes() }
        bag.dgGunlukTemizle.setOnClickListener { Gunluk.temizle() }
        bag.dgHakkinda.setOnClickListener { hakkindaGoster() }

        KopruYonetici.kur(applicationContext)
        akislariDinle()

        // Kullanici daha once "acilista baglan" dediyse ve ayarlar
        // eksiksizse kendiliginden baglan.
        val a = Ayarlar.oku(this)
        if (a.otoBaglan && a.eksiksizMi()) baglan(sessiz = true)

        Gunluk.yaz("ARAYUZ", "Ana ekran acildi")
    }

    // ------------------------------------------------------------ ayarlar

    private fun ayarlariYukle() {
        val a = Ayarlar.oku(this)
        bag.girisAdres.setText(a.sunucu)
        bag.girisPort.setText(a.port.toString())
        bag.girisKullanici.setText(a.kullanici)
        // BULGU_07: GDP belirteci (bos olabilir; yerel
        // kurulumda gerekmez).
        bag.girisBelirtec.setText(a.belirtec)
        bag.kutuOto.isChecked = a.otoBaglan
    }

    private fun baglan(sessiz: Boolean = false) {
        val adres = bag.girisAdres.text.toString().trim()
        val portMetni = bag.girisPort.text.toString().trim()
        val kullanici = bag.girisKullanici.text.toString().trim()
        val belirtec = bag.girisBelirtec.text.toString().trim()

        if (adres.isEmpty()) return uyar(R.string.hata_adres_bos)
        val port = portMetni.toIntOrNull()
        if (port == null || port < 1 || port > 65535) {
            return uyar(R.string.hata_port_gecersiz)
        }
        if (kullanici.isEmpty()) return uyar(R.string.hata_kullanici_bos)

        val mevcut = Ayarlar.oku(this)

        Ayarlar.yaz(
            baglam = this,
            sunucu = adres,
            port = port,
            tls = mevcut.tls,
            kullanici = kullanici,
            otoBaglan = bag.kutuOto.isChecked
        )

        // BULGU_07: belirtec AYRI yazilir. `Ayarlar.yaz` imzasi
        // DEGISTIRILMEDI cunku o imza baska yerlerden de
        // cagriliyor. Bos girildiyse kayit SILINIR: bos
        // belirtecli kayit uzak baglantida reddedilir ve
        // kullanici nedenini anlamaz -> sessiz kusur.
        // `KopruYonetici.baglan` cagrisindan ONCE yazilir;
        // yoksa ilk baglanti ESKI belirteci kullanir.
        if (belirtec.isEmpty()) {
            Ayarlar.belirtecSil(this)
        } else {
            Ayarlar.belirtecYaz(this, belirtec)
        }

        KopruYonetici.baglan(applicationContext, Ayarlar.oku(this))

        val niyet = Intent(this, KopruHizmeti::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(niyet)
        } else {
            startService(niyet)
        }
        if (!sessiz) {
            Toast.makeText(
                this, R.string.durum_merkez_baglaniyor, Toast.LENGTH_SHORT
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
        val dji = KopruYonetici.dji ?: return

        // SDK kayit durumu
        lifecycleScope.launch {
            combine(dji.kayit, dji.kayitHata) { d, h -> d to h }
                .collect { (d, h) ->
                    bag.etiketSdk.text = when (d) {
                        DjiKopru.KayitDurum.BASLAMADI,
                        DjiKopru.KayitDurum.BASLIYOR ->
                            getString(R.string.durum_sdk_kayit_bekliyor)
                        DjiKopru.KayitDurum.KAYITLI ->
                            getString(R.string.durum_sdk_kayit_tamam)
                        DjiKopru.KayitDurum.HATA ->
                            getString(R.string.durum_sdk_kayit_hata, h)
                    }
                    bag.etiketSdk.setTextColor(
                        renk(
                            when (d) {
                                DjiKopru.KayitDurum.KAYITLI -> R.color.iyi
                                DjiKopru.KayitDurum.HATA -> R.color.kotu
                                else -> R.color.govde_renk
                            }
                        )
                    )
                }
        }

        // Arac baglantisi
        lifecycleScope.launch {
            dji.urunBagli.collect { bagli ->
                bag.etiketArac.text = if (bagli) {
                    getString(R.string.durum_arac_bagli, dji.urunModeli())
                } else {
                    getString(R.string.durum_arac_yok)
                }
                bag.etiketArac.setTextColor(
                    renk(if (bagli) R.color.iyi else R.color.soluk)
                )
            }
        }

        // Merkez baglantisi + gonderilen ornek sayisi
        lifecycleScope.launch {
            KopruYonetici.ornekSayisi.collect { sayi ->
                merkezDurumuYaz(sayi)
            }
        }

        // Telemetri paneli
        lifecycleScope.launch {
            dji.telemetri.collect { t ->
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
                        "%s  %.1f m".format(
                            getString(R.string.tel_irtifa), t.altRel
                        )
                    )
                    appendLine(
                        "%s  %.1f m/s".format(
                            getString(R.string.tel_hiz), t.yatayHiz
                        )
                    )
                    appendLine(
                        "%s  %.0f".format(
                            getString(R.string.tel_yon), t.heading
                        )
                    )
                    appendLine(
                        "%s  %d%%  %.1f V".format(
                            getString(R.string.tel_batarya),
                            t.bataryaPct, t.bataryaV
                        )
                    )
                    appendLine(
                        "%s  %d".format(getString(R.string.tel_uydu), t.uydu)
                    )
                    append(
                        "%s  %s".format(
                            getString(R.string.tel_mod),
                            t.mod.ifEmpty {
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

    private fun merkezDurumuYaz(ornek: Long) {
        val ist = KopruYonetici.istemci
        val durum = ist?.durum?.value ?: GdpIstemci.Durum.KOPUK
        val a = Ayarlar.oku(this)
        bag.etiketMerkez.text = when (durum) {
            GdpIstemci.Durum.KOPUK ->
                getString(R.string.durum_merkez_kopuk)
            GdpIstemci.Durum.BAGLANIYOR ->
                getString(R.string.durum_merkez_baglaniyor)
            GdpIstemci.Durum.BAGLI ->
                getString(
                    R.string.durum_merkez_bagli, "${a.sunucu}:${a.port}"
                ) + "  " + getString(R.string.tel_ornek) + " " + ornek
            GdpIstemci.Durum.HATA ->
                getString(
                    R.string.durum_merkez_hata, ist?.sonHata?.value ?: ""
                )
        }
        bag.etiketMerkez.setTextColor(
            renk(
                when (durum) {
                    GdpIstemci.Durum.BAGLI -> R.color.iyi
                    GdpIstemci.Durum.HATA -> R.color.kotu
                    GdpIstemci.Durum.BAGLANIYOR -> R.color.uyari
                    else -> R.color.soluk
                }
            )
        )
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
        // Merkez durumu akis disinda da degisebilir (yeniden baglanma).
        merkezDurumuYaz(KopruYonetici.ornekSayisi.value)
    }
}
