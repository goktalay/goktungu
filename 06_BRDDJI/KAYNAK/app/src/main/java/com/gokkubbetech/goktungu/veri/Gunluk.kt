package com.gokkubbetech.goktungu.veri

import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Uygulama gunlugu.  Arayuzde gosterilir ve tanisal icin tutulur.
 *
 * Bellek sinirlidir: en son [AZAMI_SATIR] kayit tutulur.  Telemetri
 * saniyede onlarca ornek uretebildigi icin sinirsiz buyume kabul
 * edilemez.
 */
object Gunluk {

    const val AZAMI_SATIR = 500

    enum class Tur { BILGI, BASARI, UYARI, HATA }

    data class Kayit(
        val zaman: Long,
        val etiket: String,
        val ileti: String,
        val tur: Tur
    ) {
        fun zamanMetni(): String =
            BICIM.format(Date(zaman))
    }

    private val BICIM = SimpleDateFormat("HH:mm:ss", Locale.US)

    private val _kayitlar = MutableStateFlow<List<Kayit>>(emptyList())
    val kayitlar: StateFlow<List<Kayit>> = _kayitlar.asStateFlow()

    fun yaz(etiket: String, ileti: String, tur: Tur = Tur.BILGI) {
        val k = Kayit(System.currentTimeMillis(), etiket, ileti, tur)
        synchronized(this) {
            val yeni = _kayitlar.value + k
            _kayitlar.value =
                if (yeni.size > AZAMI_SATIR) yeni.takeLast(AZAMI_SATIR)
                else yeni
        }
        when (tur) {
            Tur.BILGI -> Log.i("GOKTUNGU/$etiket", ileti)
            Tur.BASARI -> Log.i("GOKTUNGU/$etiket", ileti)
            Tur.UYARI -> Log.w("GOKTUNGU/$etiket", ileti)
            Tur.HATA -> Log.e("GOKTUNGU/$etiket", ileti)
        }
    }

    fun basari(etiket: String, ileti: String) =
        yaz(etiket, ileti, Tur.BASARI)

    fun uyari(etiket: String, ileti: String) = yaz(etiket, ileti, Tur.UYARI)
    fun hata(etiket: String, ileti: String) = yaz(etiket, ileti, Tur.HATA)

    fun temizle() {
        synchronized(this) { _kayitlar.value = emptyList() }
    }
}
