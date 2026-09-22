package com.turkbey.goktungu

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.webkit.GeolocationPermissions
import android.webkit.WebChromeClient
import android.webkit.WebChromeClient.CustomViewCallback
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import java.io.File

/**
 * GRCOFFANDR ana ekranı.
 *
 * Mimari: gömülü Python arka ucu (Chaquopy) [ArkaUcServisi] içinde
 * 127.0.0.1 üzerinde bir HTTP + WebSocket sunucusu açar; bu WebView o
 * sunucuya bağlanarak mevcut GRCOFF web arayüzünü (Cesium harita,
 * uçuş göstergesi, paneller) gösterir. Böylece arayüz kodu masaüstü
 * GRCOFF ile birebir paylaşılır.
 */
class AnaEtkinlik : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var kok: FrameLayout
    private var tamEkranGorunum: View? = null
    private var tamEkranGeri: CustomViewCallback? = null

    companion object {
        private const val IZIN_KODU = 101
    }

    /** Arayüzün tam ekran düğmesi (HTML Fullscreen) çağrılınca. */
    private fun tamEkranGoster(view: View, geri: CustomViewCallback) {
        if (tamEkranGorunum != null) { geri.onCustomViewHidden(); return }
        tamEkranGorunum = view
        tamEkranGeri = geri
        kok.addView(view, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT))
        web.visibility = View.GONE
        sistemCubuklari(gizle = true)
        ViewCompat.requestApplyInsets(kok)   // padding sıfırlansın
    }

    private fun tamEkranGizle() {
        val v = tamEkranGorunum ?: return
        kok.removeView(v)
        tamEkranGorunum = null
        tamEkranGeri?.onCustomViewHidden()
        tamEkranGeri = null
        web.visibility = View.VISIBLE
        sistemCubuklari(gizle = false)
        ViewCompat.requestApplyInsets(kok)   // padding üstbara göre geri gelsin
    }

    /** Sistem çubuklarını (durum + gezinme) gizler/gösterir. */
    private fun sistemCubuklari(gizle: Boolean) {
        val kontrol = WindowCompat.getInsetsController(window, window.decorView)
        if (gizle) {
            kontrol.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            kontrol.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            kontrol.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(durum: Bundle?) {
        super.onCreate(durum)

        // Açılışta gerekli izinleri iste (konum, bildirim). USB izni
        // aygıt takıldığında sistem tarafından ayrıca sorulur.
        izinleriIste()

        // Arka uç (Python) servisini başlat — arayüz yüklenmeden önce
        // sunucunun ayakta olması için ön planda çalışır.
        val niyet = Intent(this, ArkaUcServisi::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(niyet)
        } else {
            startService(niyet)
        }

        web = WebView(this)
        kok = FrameLayout(this)
        kok.addView(web)
        setContentView(kok)

        // Android 15+ (targetSdk 36) varsayılan olarak edge-to-edge çizer:
        // içerik sistem çubuklarının ALTINA/ARKASINA gelir ve GRCOFF'un üst
        // menüsü Android durum çubuğunun arkasında kalır. Sistem çubuğu
        // insetlerini padding olarak uygula; tam ekranda padding sıfırlanır.
        ViewCompat.setOnApplyWindowInsetsListener(kok) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            if (tamEkranGorunum != null) {
                v.setPadding(0, 0, 0, 0)
            } else {
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            }
            insets
        }

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            // Cesium/WebGL için donanım hızlandırma + yerel dosya erişimi
            allowFileAccess = true
            allowContentAccess = true
            mediaPlaybackRequiresUserGesture = false
            // Çevrimdışı harita döşemeleri için önbellek
            cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            userAgentString = userAgentString + " GRCOFFANDR/" +
                BuildConfig.VERSION_NAME
        }

        // Uyarılar sistemi (uyari_merkezi.js) → Android bildirimleri köprüsü.
        // Arayüz `window.AndroidBildirim.bildir(baslik, metin)` çağırır.
        web.addJavascriptInterface(BildirimKopru(this), "AndroidBildirim")

        // Arka uç (uygulama_kur) birkaç saniyede ayağa kalkar; sunucu
        // hazır olana kadar bağlantı reddedilir. Hata gelince kısa aralıkla
        // yeniden dener (WebView boş sayfada takılı kalmasın).
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(
                view: WebView, istek: WebResourceRequest, hata: WebResourceError
            ) {
                if (istek.isForMainFrame) {
                    Handler(Looper.getMainLooper()).postDelayed({
                        view.loadUrl("http://127.0.0.1:${ArkaUcServisi.PORT}/")
                    }, 800)
                }
            }
        }
        // WebView geolokasyon + TAM EKRAN köprüsü.
        // Uygulama normal pencerede (üst bar görünür) açılır; arayüzdeki
        // tam ekran düğmesi HTML Fullscreen API'sini çağırınca WebView
        // onShowCustomView tetiklenir ve sistem çubukları gizlenir.
        web.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(
                origin: String, callback: GeolocationPermissions.Callback
            ) {
                callback.invoke(origin, true, false)
            }

            override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                tamEkranGoster(view, callback)
            }

            override fun onHideCustomView() {
                tamEkranGizle()
            }
        }

        // Arka uç sunucusu ayağa kalkınca AnaKopru üzerinden yüklenir;
        // hazır olana kadar açılış ekranı gösterilir.
        web.loadUrl("http://127.0.0.1:${ArkaUcServisi.PORT}/")

        // TANI FALLBACK: Python arka ucu GIL'i tutan bir çağrıda asılırsa
        // hem açılış sunucusu hem watchdog donar (WebView "Başlatılıyor"da
        // kalır). Bu durumda 'hazir.flag' oluşmaz. 80 sn sonra bayrak yoksa
        // günlük + C-seviyesi yığın dökümünü doğrudan WebView'de göster
        // (Kotlin GIL'e bağlı değildir).
        Handler(Looper.getMainLooper()).postDelayed({ taniGerekliyseGoster() }, 80_000)
    }

    /** Arka uç 80 sn'de hazır olmadıysa günlük + yığın dökümünü gösterir. */
    private fun taniGerekliyseGoster() {
        val gunluk = File(filesDir, "gunluk")
        if (File(gunluk, "hazir.flag").exists()) return  // arka uç ayakta
        val yigin = File(gunluk, "yigin_dokumu.log").takeIf { it.exists() }?.readText()
            ?: "(yığın dökümü yok)"
        val log = File(gunluk, "android_arka_uc.log").takeIf { it.exists() }?.readText()
            ?: "(günlük yok)"
        val kacir = { s: String ->
            s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        }
        val html = """
            <!doctype html><html lang=tr><head><meta charset=utf-8>
            <meta name=viewport content='width=device-width,initial-scale=1'>
            <style>body{margin:0;background:#12161c;color:#e7eef6;
            font-family:system-ui,sans-serif;padding:16px}h1{color:#ff6b6b;
            font-size:20px}pre{white-space:pre-wrap;word-break:break-word;
            background:#0b0e12;border:1px solid #2a323c;border-radius:8px;
            padding:12px;font-size:12px}h2{font-size:14px;color:#9fb2c8}</style>
            </head><body><h1>GÖKTUNGU arka ucu başlamadı (asıldı)</h1>
            <p>Aşağıdaki bilgiyi geliştiriciye iletin.</p>
            <h2>Yığın dökümü (asılan yer)</h2><pre>${kacir(yigin)}</pre>
            <h2>Günlük</h2><pre>${kacir(log)}</pre></body></html>
        """.trimIndent()
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    /**
     * Açılışta gereken runtime (tehlikeli) izinleri toplu ister:
     * konum (telemetri/harita) ve bildirim (ön plan servisi). USB Host
     * erişimi ayrı bir izin modelidir; aygıt takıldığında sistem sorar.
     * Özel veri deposu (filesDir) izin gerektirmez.
     */
    private fun izinleriIste() {
        val gerekli = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gerekli.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val eksik = gerekli.filter {
            ContextCompat.checkSelfPermission(this, it) !=
                PackageManager.PERMISSION_GRANTED
        }
        if (eksik.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, eksik.toTypedArray(), IZIN_KODU)
        }
    }

    override fun onBackPressed() {
        when {
            tamEkranGorunum != null -> tamEkranGizle()  // önce tam ekrandan çık
            web.canGoBack() -> web.goBack()
            else -> super.onBackPressed()
        }
    }

    override fun onDestroy() {
        // Servisi durdur (uygulama kapanıyor).
        stopService(Intent(this, ArkaUcServisi::class.java))
        web.destroy()
        super.onDestroy()
    }
}
