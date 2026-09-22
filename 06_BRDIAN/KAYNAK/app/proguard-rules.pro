# GOKTUNGU Goruntu Koprusu (BRDIAN) -- kucultme kurallari.
#
# Uygulama saf AndroidX + CameraX + OkHttp'tir; DJI/MSDK YOKTUR, bu
# yuzden BRDAND'daki onlarca DJI `-keep` kurali burada bulunmaz.

# Gorunum baglama (ViewBinding) siniflari yansima ile olusturulur.
-keep class com.turkbey.goktungu.image.databinding.** { *; }

# On plan hizmeti, etkinlik ve uygulama sinifi manifestten adiyla
# cagrilir; kucultme adlarini degistirirse calisma aninda
# ClassNotFoundException olusur.
-keep class com.turkbey.goktungu.image.kopru.KopruHizmeti { *; }
-keep class com.turkbey.goktungu.image.arayuz.AnaEtkinlik { *; }
-keep class com.turkbey.goktungu.image.GoktunguGoruntuUygulama { *; }

# Kotlin coroutines ic gerceklemesi
-dontwarn kotlinx.coroutines.**

# Kaynak dosya adi ve satir numarasi korunur: sahadan gelen cokme
# kayitlarini okunur kilar.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# OkHttp/Okio (kopru ajani WebSocket). Kutuphane kendi tuketici
# kurallarini tasir; yalniz uyarilar susturulur.
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
