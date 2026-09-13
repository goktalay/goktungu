"""Windows SERVIS kipini taklit edip kurulum yonergesini olcer.

NEDEN TAKLIT: kullanicinin yasadigi durum Windows'ta LocalSystem
hesabiyla kosan bir servistir. Bu sandik Linux oldugu icin gercek
kosullar dogal olarak olusmaz; `arac_bul`'un platform ve servis-kipi
dallarini dogrudan zorlayarak kullanicinin GORECEGI metni uretiriz.

Bu bir "sinav" degil OLCUMDUR: cikti insan tarafindan okunup
yonergenin gercekten uygulanabilir olup olmadigina karar verilir.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kopru import arac_bul  # noqa: E402


def windows_taklit():
    """Windows + servis kipi + ffmpeg yok senaryosunu zorlar."""
    arac_bul._windows_mu = lambda: True
    arac_bul._servis_kipi_mi = lambda: True
    arac_bul._onbellek["ffmpeg"] = None
    # sys.executable'i Windows servis Python'u gibi gosterelim
    gercek = sys.executable
    sys.executable = (r"C:\Program Files\Goktungu\Kopru\python\python.exe")
    return gercek


def main():
    print("=" * 66)
    print("OLCUM: Windows servis kipinde kullanicinin gordugu metin")
    print("=" * 66)
    gercek = windows_taklit()
    try:
        print()
        print(">>> ffmpeg BULUNAMADI durumunda konsola yazilan:")
        print()
        print("[UYARI] ffmpeg BULUNAMADI - RTSP/MJPEG/HTTP akislari "
              "calismayacak.")
        print("[UYARI] --- KURULUM YARDIMI (FFMPEG) ---")
        for s in arac_bul.kurulum_yonergesi("ffmpeg"):
            print("[UYARI] " + s)
        print("[UYARI] --- YARDIM SONU ---")

        print()
        print(">>> OpenCV yok durumunda konsola yazilan:")
        print()
        print("[UYARI] OpenCV yok - ag kameralari calisir, USB kamera ve "
              "AI kutu cizimi devre disi")
        print("[UYARI] --- KURULUM YARDIMI (OPENCV) ---")
        for s in arac_bul.kurulum_yonergesi("opencv"):
            print("[UYARI] " + s)
        print("[UYARI] --- YARDIM SONU ---")

        print()
        print(">>> Akis acilamadiginda istemciye giden TEK SATIR:")
        print()
        print("  " + arac_bul.eksik_arac_ozeti("ffmpeg"))

        print()
        print(">>> Servis yeniden baslatma komutu:")
        print("  " + arac_bul.servis_yeniden_baslat_komutu())
    finally:
        sys.executable = gercek

    print()
    print("=" * 66)
    print("DENETIM LISTESI (insan degerlendirmesi)")
    print("=" * 66)
    denetim = [
        "Yonerge servisin GERCEK Python yolunu yaziyor mu?",
        "winget komutu makine kapsamli mi (--scope machine)?",
        "PATH ayarlamaya gerek olmadigi belirtiliyor mu?",
        "Servisi yeniden baslatma adimi var mi?",
        "Linux komutlari Windows metninde GORUNMUYOR mu?",
    ]
    for d in denetim:
        print("  [ ] " + d)


if __name__ == "__main__":
    main()
