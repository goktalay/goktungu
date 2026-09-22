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
