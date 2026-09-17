package com.turkbey.goktungu.arayuz

import android.Manifest
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.turkbey.goktungu.BuildConfig
import com.turkbey.goktungu.R
import com.turkbey.goktungu.databinding.EtkinlikAnaBinding
import com.turkbey.goktungu.dji.DjiKopru
import com.turkbey.goktungu.kopru.KimlikKodu
import com.turkbey.goktungu.kopru.KopruAjan
import com.turkbey.goktungu.kopru.KopruHizmeti
import com.turkbey.goktungu.kopru.KopruKimlik
import com.turkbey.goktungu.kopru.KopruYonetici
import com.turkbey.goktungu.veri.Ayarlar
import com.turkbey.goktungu.veri.Gunluk
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * GOKTUNGU DJI Koprusu — ana ekran (1.1.0).
 *
 * Iki hal: KURULUM (kimlik yok: GRCON/GRCOFF secimi + API kodu) ve
 * CALISMA (ajan merkeze bagli; DJI kanali merkezden acilir). Is
 * mantigi [KopruYonetici] icindedir; koordinat donusumu bu katmanda
 * YAPILMAZ (bkz. GdpKoordinat sozlesmesi).
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var bag: EtkinlikAnaBinding

    private val izinSonucu = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        val konumVar = ContextCompat.checkSelfPermission(
            this, Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        if (!konumVar) {
            Gunluk.uyari("IZIN", getString(R.string.izin_reddedildi))
            Toast.makeText(this, R.string.izin_reddedildi, Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)
        bag = EtkinlikAnaBinding.inflate(layoutInflater)
        setContentView(bag.root)

        izinleriIste()
        KopruYonetici.kur(applicationContext)

        bag.dgKur.setOnClickListener { kurulumKaydet() }
        bag.dgBaslat.setOnClickListener { baslat(sessiz = false) }
        bag.dgKes.setOnClickListener { durdur() }
        bag.dgKimlikSil.setOnClickListener { kimlikSilSor() }
        bag.dgGunlukTemizle.setOnClickListener { Gunluk.temizle() }
        bag.dgHakkinda.setOnClickListener { hakkindaGoster() }
        bag.kutuOto.setOnCheckedChangeListener { _, secili ->
            Ayarlar.otoBaslatYaz(this, secili)
        }
        bag.radioGrcon.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }
        bag.radioGrcoff.setOnCheckedChangeListener { _, _ -> kurulumNotuTazele() }

        bag.kutuOto.isChecked = Ayarlar.oku(this).otoBaslat
        kurulumNotuTazele()
        gorunumTazele()
        akislariDinle()

        if (KopruKimlik.var_(this) && Ayarlar.oku(this).otoBaslat &&
            !KopruYonetici.calisiyorMu()
        ) {
            baslat(sessiz = true)
        }
        Gunluk.yaz("ARAYUZ", "Ana ekran acildi")
    }

    override fun onResume() {
        super.onResume()
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
        when (val s = KimlikKodu.coz(bag.girisKod.text.toString())) {
            is KimlikKodu.Sonuc.Gecersiz -> uyarMetin(getString(R.string.hata_kod, s.neden))
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

    private fun gorunumTazele() {
        val k = KopruKimlik.oku(this)
        val kimlikVar = k != null && k.eksiksizMi()
        bag.kartKurulum.visibility = if (kimlikVar) View.GONE else View.VISIBLE
        bag.kartKimlik.visibility = if (kimlikVar) View.VISIBLE else View.GONE
        if (k != null && kimlikVar) {
            bag.etiketKimlik.text = getString(
                R.string.kimlik_ozet, k.ad.ifBlank { "—" }, k.turEtiketi(), k.merkezAdres
            )
        }
        val calisiyor = KopruYonetici.calisiyorMu()
        bag.dgBaslat.isEnabled = kimlikVar && !calisiyor
        bag.dgKes.isEnabled = calisiyor
    }

    private fun akislariDinle() {
        val dji = KopruYonetici.dji ?: return
        val ajan = KopruYonetici.ajan ?: return

        // SDK kayit durumu
        lifecycleScope.launch {
            combine(dji.kayit, dji.kayitHata) { d, h -> d to h }.collect { (d, h) ->
                bag.etiketSdk.text = when (d) {
                    DjiKopru.KayitDurum.BASLAMADI,
                    DjiKopru.KayitDurum.BASLIYOR -> getString(R.string.durum_sdk_kayit_bekliyor)
                    DjiKopru.KayitDurum.KAYITLI -> getString(R.string.durum_sdk_kayit_tamam)
                    DjiKopru.KayitDurum.HATA -> getString(R.string.durum_sdk_kayit_hata, h)
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
                bag.etiketArac.setTextColor(renk(if (bagli) R.color.iyi else R.color.soluk))
            }
        }

        // Merkez baglantisi
        lifecycleScope.launch {
            ajan.durum.collect { d ->
                val b = ajan.bilgi.value
                bag.etiketMerkez.text = when (d) {
                    KopruAjan.Durum.BAGLI -> getString(
                        R.string.durum_merkez_bagli, b.ad.ifBlank { "#" + b.ornekId }, b.adres
                    )
                    KopruAjan.Durum.BAGLANIYOR -> getString(R.string.durum_merkez_baglaniyor)
                    KopruAjan.Durum.HATA -> getString(R.string.durum_merkez_hata, ajan.sonHata.value)
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

        // Kanal + ornek sayaci (yoklama)
        lifecycleScope.launch {
            while (true) {
                val n = KopruYonetici.kanallar?.etkinSayi() ?: 0
                bag.etiketKanal.text = if (n == 0) {
                    getString(R.string.durum_kanal_yok)
                } else {
                    getString(R.string.durum_kanal_var, n, KopruYonetici.ornekSayisi.value)
                }
                bag.etiketKanal.setTextColor(renk(if (n > 0) R.color.iyi else R.color.soluk))
                delay(1000)
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
                                getString(R.string.tel_konum), konum.enlem, konum.boylam
                            )
                        )
                    }
                    appendLine("%s  %.1f m".format(getString(R.string.tel_irtifa), t.altRel))
                    appendLine("%s  %.1f m/s".format(getString(R.string.tel_hiz), t.yatayHiz))
                    appendLine("%s  %.0f".format(getString(R.string.tel_yon), t.heading))
                    appendLine(
                        "%s  %d%%  %.1f V".format(
                            getString(R.string.tel_batarya), t.bataryaPct, t.bataryaV
                        )
                    )
                    appendLine("%s  %d".format(getString(R.string.tel_uydu), t.uydu))
                    append(
                        "%s  %s".format(
                            getString(R.string.tel_mod),
                            t.mod.ifEmpty { getString(R.string.tel_deger_yok) }
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
