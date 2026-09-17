# GOKTUNGU MAVLink Koprusu -- kucultme kurallari
#
# DJI MSDK kalktigi icin o kutuphaneye ait onlarca `-keep` kurali da
# kalkti.  Kalan kurallar yalniz kendi kodumuz ve Android cercevesi
# icin gerekli olanlardir.

# Gorunum baglama (ViewBinding) siniflari yansima ile olusturulur.
-keep class com.turkbey.goktungumav.databinding.** { *; }

# On plan hizmeti, etkinlik ve uygulama sinifi manifestten adiyla
# cagrilir; kucultme adlarini degistirirse calisma aninda
# ClassNotFoundException olusur.
-keep class com.turkbey.goktungumav.kopru.KopruHizmeti { *; }
-keep class com.turkbey.goktungumav.arayuz.AnaEtkinlik { *; }
-keep class com.turkbey.goktungumav.GoktunguMavUygulama { *; }

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
