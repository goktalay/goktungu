# GRCOFFANDR ProGuard/R8 kuralları
#
# Yayın derlemesinde R8 kapalıdır (minifyEnabled false), ancak ileride
# açılırsa Chaquopy yansıması ve WebView JS köprüsü korunmalıdır.

# Chaquopy (gömülü Python) — yansıma ile çağrılan sınıflar korunur.
-keep class com.chaquo.python.** { *; }
-keep class com.turkbey.goktungu.** { *; }

# WebView JavaScript arayüzü (JS ↔ Kotlin köprüsü) korunur.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Uyarıları bastır (Chaquopy paketleri).
-dontwarn com.chaquo.python.**

# --- DJI MSDK v5 (Faz 4) ---
# MSDK yansıma ve yerel çağrılar kullanır; küçültme kırar. R8 şu an
# kapalı olsa da ileride açılırsa diye korunur (güvenli).
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
-keep class io.reactivex.** { *; }
-dontwarn io.reactivex.**
-keep class * extends androidx.room.RoomDatabase
-dontwarn androidx.room.**
-dontwarn okio.**
-dontwarn okhttp3.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# GDP protokol veri sınıfları — alan adları JSON'a birebir yansır.
-keep class com.turkbey.goktungu.veri.** { *; }
