#!/usr/bin/env python3.11
"""Android MAVLink Koprusu 1.1.1 (gercek kopru ajani) katalog yayini."""
import sys
sys.path.insert(0, "/opt/goktungu/merkez/python")
import mk_depo
APK = "/root/goktungu_github/05_BRDAND/KAYNAK/dagitim/GOKTUNGU-MAVLink-Koprusu-1.1.1.apk"
NOT = ("MAVLink Koprusu 1.1.1: yeni Turkbey kurt ikonu (baslatici, yuvarlak ve uyarlanabilir ikon). "
       "Islev degisikligi yok; 1.1.0 kopru ajani (API kodu ile kurulum, seri/UDP/TCP akis kanallari) aynen.")
s = mk_depo.paket_ekle("kopru", "1.1.1", APK, platform="android", kanal="kararli", paket_tur="tam", notlar=NOT)
print("[OK]", s.get("dosya_ad"), s.get("dosya_boyut"), "imza=", "VAR" if s.get("imza") else "YOK")
print("son:", mk_depo.son_surum("kopru", platform="android", paket_tur="tam"))
