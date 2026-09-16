# DJI MSDK v5 -- yansima ve yerel cagrilar kullanir; kucultme kirabilir.
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
-dontwarn okio.**
-dontwarn com.squareup.wire.**

-dontwarn io.reactivex.**
-keep class io.reactivex.** { *; }

-keep class * extends androidx.room.RoomDatabase
-dontwarn androidx.room.**

# GDP protokol veri siniflari -- alan adlari JSON'a birebir yansir.
-keep class com.turkbey.goktungu.veri.** { *; }
