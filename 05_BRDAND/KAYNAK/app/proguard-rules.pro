# GOKTUNGU MAVLink Koprusu -- kucultme kurallari
#
# DJI MSDK kalktigi icin o kutuphaneye ait onlarca `-keep` kurali da
# kalkti.  Kalan kurallar yalniz kendi kodumuz ve Android cercevesi
# icin gerekli olanlardir.

# Gorunum baglama (ViewBinding) siniflari yansima ile olusturulur.
-keep class com.turkbey.goktungu.bridge.databinding.** { *; }

# On plan hizmeti, etkinlik ve uygulama sinifi manifestten adiyla
# cagrilir; kucultme adlarini degistirirse calisma aninda
# ClassNotFoundException olusur.
-keep class com.turkbey.goktungu.bridge.kopru.KopruHizmeti { *; }
-keep class com.turkbey.goktungu.bridge.arayuz.AnaEtkinlik { *; }
-keep class com.turkbey.goktungu.bridge.GoktunguMavUygulama { *; }

# Kotlin coroutines ic gerceklemesi
-dontwarn kotlinx.coroutines.**

# Kaynak dosya adi ve satir numarasi korunur: sahadan gelen cokme
# kayitlarini okunur kilar.  Gercek dosya adi gizlenir, esleme
# mapping.txt uzerinden yapilir.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# 1.1.0: OkHttp/Okio (kopru ajani WebSocket). Kutuphane kendi tuketici
# kurallarini tasir; yalniz uyarilar susturulur.
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# ------------------------------------------------------------------
# 1.1.3: DJI MSDK v5 gommeli DJI kopru tipi
# ------------------------------------------------------------------
# MSDK yansima ve yerel cagrilar kullanir; kucultme kirabilir.
-keep class dji.** { *; }
-keep class com.dji.** { *; }
-keep class sdk.** { *; }
-dontwarn dji.**
-dontwarn com.dji.**

-keep class com.secneo.** { *; }
-dontwarn com.secneo.**
-keep class net.sqlcipher.** { *; }
-dontwarn net.sqlcipher.**
-keep class org.aspectj.** { *; }
-dontwarn org.aspectj.**
-dontwarn com.squareup.wire.**

-dontwarn io.reactivex.**
-keep class io.reactivex.** { *; }

-keep class * extends androidx.room.RoomDatabase
-dontwarn androidx.room.**

# GDP protokol veri siniflari -- alan adlari JSON'a birebir yansir.
-keep class com.turkbey.goktungu.bridge.veri.GdpMesaj { *; }
-keep class com.turkbey.goktungu.bridge.veri.GdpMesaj$** { *; }
-keep class com.turkbey.goktungu.bridge.veri.GdpKoordinat { *; }
-keep class com.turkbey.goktungu.bridge.veri.GdpKoordinat$** { *; }

# DJI cekirdegi Faz 1'de arayuzden henuz cagrilmiyor (UI baglamasi
# Faz 2). R8'in bu siniflari OLU sayip atmasini onlemek icin
# korunuyorlar; boylece DJI cekirdegi APK'da kalir ve Faz 2'de
# dogrudan cagrilabilir.
-keep class com.turkbey.goktungu.bridge.dji.** { *; }
-keep class com.turkbey.goktungu.bridge.kopru.DjiKopruCekirdegi { *; }
-keep class com.turkbey.goktungu.bridge.kopru.GdpKanal { *; }
-keep class com.turkbey.goktungu.bridge.kopru.GdpKanal$** { *; }
-keep class com.turkbey.goktungu.bridge.kopru.KomutIsleyici { *; }
