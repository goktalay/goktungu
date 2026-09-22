package com.turkbey.goktungu.image.arayuz

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
import com.turkbey.goktungu.image.BuildConfig
import com.turkbey.goktungu.image.R
import com.turkbey.goktungu.image.databinding.EtkinlikAnaBinding
import com.turkbey.goktungu.image.kopru.GoruntuYonetici
import com.turkbey.goktungu.image.kopru.KimlikKodu
import com.turkbey.goktungu.image.kopru.KopruAjan
import com.turkbey.goktungu.image.kopru.KopruHizmeti
import com.turkbey.goktungu.image.kopru.KopruKimlik
import com.turkbey.goktungu.image.veri.Ayarlar
import com.turkbey.goktungu.image.veri.Gunluk
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * GOKTUNGU Goruntu Koprusu — ana ekran (tek ekran).
 *
 * BRDAND'in cok-kopru sol menusu YOKTUR; BRDIAN tek amaclidir. Akis:
 * kamera onizleme + durum + kurulum (GRCON/GRCOFF + API kodu) + kimlik
 * + gunluk. Is mantigi [GoruntuYonetici] koordinatorundedir; bu sinif
 * yalniz sunum yapar.
 *
 * Kamera, on plan hizmetine ([KopruHizmeti]) baglidir (arka planda da
 * yakalar); bu etkinlik yalniz onizleme yuzeyini gorunur oldukca
 * takar/kaldirir.
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var bag: EtkinlikAnaBinding

    private val izinSonucu = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { sonuclar ->
        val kamera = sonuclar[Manifest.permission.CAMERA] == true ||
            kameraIzniVar()
        if (!kamera) {
            Toast.makeText(this, R.string.izin_kamera_gerek, Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)
        bag = EtkinlikAnaBinding.inflate(layoutInflater)
        setContentView(bag.root)

        GoruntuYonetici.kur(applicationContext)
        izinleriIste()

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
        bag.grupMercek.setOnCheckedChangeListener { _, secili ->
            val mercek = if (secili == R.id.radioOn) Ayarlar.MERCEK_ON else Ayarlar.MERCEK_ARKA
            Ayarlar.mercekYaz(this, mercek)
            // Mercek degisince kamera yeniden baglanmali; kopru
            // calisiyorsa hizmeti yeniden baslat.
            if (GoruntuYonetici.calisiyorMu()) {
                durdur()
                baslat(sessiz = true)
            }
        }

        // Kayitli tercihler
        val ayar = Ayarlar.oku(this)
        bag.kutuOto.isChecked = ayar.otoBaslat
        if (ayar.mercek == Ayarlar.MERCEK_ON) bag.radioOn.isChecked = true
        else bag.radioArka.isChecked = true

        kurulumNotuTazele()
        gorunumTazele()
        durumDongusu()

        // Kimlik varsa ve tercih acik ise kendiliginden baslar.
        if (KopruKimlik.var_(this) && ayar.otoBaslat && !GoruntuYonetici.calisiyorMu()) {
            baslat(sessiz = true)
        }
        Gunluk.yaz("ARAYUZ", "Ana ekran acildi")
    }

    override fun onResume() {
        super.onResume()
        // Onizleme yuzeyini kameraya tak (kamera hizmete baglidir).
        GoruntuYonetici.onizlemeAyarla(bag.onizleme.surfaceProvider)
        gorunumTazele()
    }

    override fun onPause() {
        // Yuzeyi birak; kamera hizmette bagli kalir (arka planda yakalar).
        GoruntuYonetici.onizlemeAyarla(null)
        super.onPause()
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
                GoruntuYonetici.durdur()
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
        if (!KopruKimlik.var_(this)) {
            if (!sessiz) uyar(R.string.hata_kimlik_yok)
            return
        }
        if (!kameraIzniVar()) {
            if (!sessiz) uyar(R.string.izin_kamera_gerek)
            izinleriIste()
            return
        }
        // Hizmet (kamera + MJPEG + bildirim) once baslar; ajan sonra.
        val niyet = Intent(this, KopruHizmeti::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(niyet)
        } else {
            startService(niyet)
        }
        GoruntuYonetici.baslat()
        if (!sessiz) Toast.makeText(this, R.string.kopru_baslatildi, Toast.LENGTH_SHORT).show()
        // Onizleme yuzeyini yeniden tak (hizmet kamerayi bagladiktan sonra).
        bag.onizleme.post { GoruntuYonetici.onizlemeAyarla(bag.onizleme.surfaceProvider) }
        gorunumTazele()
    }

    private fun durdur() {
        GoruntuYonetici.durdur()
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

    private fun kameraIzniVar(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED

    private fun izinleriIste() {
        val istenecek = mutableListOf<String>()
        if (!kameraIzniVar()) istenecek += Manifest.permission.CAMERA
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
                R.string.kimlik_ozet,
                k.ad.ifBlank { "—" }, k.turEtiketi(), k.merkezAdres
            )
        }
        val calisiyor = GoruntuYonetici.calisiyorMu()
        bag.dgBaslat.isEnabled = kimlikVar && !calisiyor
        bag.dgKes.isEnabled = calisiyor
    }

    // ------------------------------------------------------------ durum dongusu

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
        val ajan = GoruntuYonetici.ajan

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
            else -> if (GoruntuYonetici.calisiyorMu()) {
                getString(R.string.durum_merkez_yeniden) to R.color.soluk
            } else {
                getString(R.string.durum_merkez_kopuk) to R.color.soluk
            }
        }
        bag.etiketMerkez.text = merkezMetin
        bag.etiketMerkez.setTextColor(renk(merkezRenk))

        // Kamera durumu
        val kam = GoruntuYonetici.kamera
        val (kamMetin, kamRenk) = when {
            kam?.sonHata?.isNotBlank() == true && kam.bagli.not() ->
                getString(R.string.durum_kamera_hata, kam.sonHata) to R.color.kotu
            kam?.bagli == true ->
                getString(
                    R.string.durum_kamera_var,
                    kam.cozunurluk.ifBlank { "…" }, kam.uretilenKare.get()
                ) to R.color.iyi
            else -> getString(R.string.durum_kamera_yok) to R.color.soluk
        }
        bag.etiketKamera.text = kamMetin
        bag.etiketKamera.setTextColor(renk(kamRenk))

        // Kanal / oturum
        val n = GoruntuYonetici.etkinKanalSayi()
        val ozet = GoruntuYonetici.kanalOzet()
        bag.etiketKanal.text = when {
            n > 0 -> getString(R.string.durum_kanal_var, n, ozet)
            else -> getString(R.string.durum_kanal_yok)
        }
        bag.etiketKanal.setTextColor(renk(if (n > 0) R.color.iyi else R.color.soluk))

        // Sayac: kare + izleyici
        val kareSayi = kam?.uretilenKare?.get() ?: 0L
        val izleyici = GoruntuYonetici.mjpeg?.izleyici?.get() ?: 0L
        bag.etiketSayac.text = getString(R.string.durum_sayac, kareSayi, izleyici)

        // Baslat/durdur dugmeleri
        val kimlikVar = KopruKimlik.var_(this)
        val calisiyor = GoruntuYonetici.calisiyorMu()
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
