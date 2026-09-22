package com.turkbey.goktungu.bridge.veri

import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Uygulama gunlugu.
 *
 * Kayitlar hem `logcat`e hem de arayuzde gosterilen bir akisa yazilir.
 * Sahada `logcat` erisimi olmadigi icin ekranda gunluk gormek tanilama
 * icin zorunludur.
 *
 * Kayit sayisi [SINIR] ile kisitlidir: sinirsiz liste uzun ucuslarda
 * bellek tuketir ve arayuzu yavaslatir.
 */
object Gunluk {

    data class Kayit(
        val zaman: Long,
        val etiket: String,
        val ileti: String,
        val duzey: Duzey
    ) {
        fun zamanMetni(): String = BICIM.format(Date(zaman))
    }

    enum class Duzey { BILGI, UYARI, HATA }

    private const val SINIR = 300
    private const val ETIKET = "GOKTUNGUMAV"
    private val BICIM = SimpleDateFormat("HH:mm:ss", Locale.US)

    private val _kayitlar = MutableStateFlow<List<Kayit>>(emptyList())
    val kayitlar: StateFlow<List<Kayit>> = _kayitlar.asStateFlow()

    fun yaz(etiket: String, ileti: String) =
        ekle(etiket, ileti, Duzey.BILGI)

    /**
     * Basari kaydi. DJI cekirdegi (DjiKopru/GorevYonetici/KmzUretici)
     * ayri bir "basari" duzeyi bekliyor; MAVLink tarafi bu duzeyi ayirt
     * etmedigi icin BILGI olarak yazilir. Boylece tasinan DJI koduna
     * dokunmadan ayni cagri karsilanir.
     */
    fun basari(etiket: String, ileti: String) =
        ekle(etiket, ileti, Duzey.BILGI)

    fun uyari(etiket: String, ileti: String) =
        ekle(etiket, ileti, Duzey.UYARI)

    fun hata(etiket: String, ileti: String) =
        ekle(etiket, ileti, Duzey.HATA)

    private fun ekle(etiket: String, ileti: String, duzey: Duzey) {
        when (duzey) {
            Duzey.BILGI -> Log.i(ETIKET, "[$etiket] $ileti")
            Duzey.UYARI -> Log.w(ETIKET, "[$etiket] $ileti")
            Duzey.HATA -> Log.e(ETIKET, "[$etiket] $ileti")
        }
        val yeni = _kayitlar.value + Kayit(
            System.currentTimeMillis(), etiket, ileti, duzey
        )
        _kayitlar.value =
            if (yeni.size > SINIR) yeni.takeLast(SINIR) else yeni
    }

    fun temizle() {
        _kayitlar.value = emptyList()
    }
}
