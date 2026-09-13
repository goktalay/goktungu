"""GOKTUNGU GCS — SUNUCU KAYNAK OLCUMU (v2.4.34)

Kullanici istegi:
    "calisan browser'in cpu, ram ve network'unu gorsel gosteren bir widget
     koy, canli olsun ki sisteme ne kadar yuklendigimizi gorelim"

Tarayici tarafi kendi FPS/bellek olcumunu yapar (bkz. js/widget_kaynaklar.js).
Bu modul ISLETIM SISTEMI tarafindaki gercek olcumu saglar: GCS surecinin
CPU/RAM tuketimi ve makinenin geneli. Boylece "arayuz mi yoksa sunucu mu
yukluyor" sorusu ayirt edilebilir.

TASARIM KARARLARI
-----------------
1) psutil OPSIYONELDIR. Yoksa modul `hazir=False` dondurur ve widget
   yalniz tarayici olcumlerini gosterir; GCS baslatilmasi ENGELLENMEZ.
   Dron ucuran bir sistemde izleme araci yuzunden acilisin durmasi kabul
   edilemez.

2) psutil yoksa Linux'ta /proc uzerinden YEDEK olcum yapilir. Kullanicinin
   kurulumu Windows olabilir; orada yedek yol yoktur, `hazir=False` doner.

3) CPU yuzdesi ARALIK farkindan hesaplanir (`cpu_times` deltalari).
   `psutil.cpu_percent(interval=…)` blokleyicidir ve asyncio dongusunu
   durdurur — telemetri akisini kesecegi icin KULLANILMAZ.

4) Ilk cagri referans damgasi kurar ve CPU icin None dondurur; iki olcum
   arasi fark olmadan yuzde hesabi anlamsizdir (0 gostermek yanlis olur).

5) Olcum COK HAFIF olmali: widget 1 Hz orneklerken bile fark edilmemeli.
   Bu nedenle disk/ag sayaclari yalniz istendiginde toplanir ve surec
   nesnesi yeniden yaratilmaz (modul duzeyinde onbelleklenir).
"""

from __future__ import annotations

import os
import time

try:
    import psutil  # type: ignore
    _PSUTIL = True
except Exception:            # ModuleNotFoundError ve import hatalari
    psutil = None            # type: ignore
    _PSUTIL = False

# Modul duzeyi durum: surec nesnesi ve son olcum damgalari
_surec = None
_son = {
    "t": 0.0,
    "surec_cpu": 0.0,     # surecin toplam CPU saniyesi
    "sistem_cpu": None,   # (kullanilan, toplam) jiffy ciftleri
    "ag": None,           # (gonderilen, alinan) bayt
}


def _surec_al():
    global _surec
    if not _PSUTIL:
        return None
    if _surec is None:
        try:
            _surec = psutil.Process(os.getpid())
        except Exception:
            return None
    return _surec


# ----------------------------------------------------------------------
# /proc YEDEK YOLU (psutil yoksa, Linux)
# ----------------------------------------------------------------------
def _proc_sistem_cpu():
    """/proc/stat'tan (kullanilan_jiffy, toplam_jiffy) dondurur."""
    try:
        with open("/proc/stat", "r") as f:
            satir = f.readline()
        parcalar = [float(x) for x in satir.split()[1:8]]
        toplam = sum(parcalar)
        # idle = 4. alan, iowait = 5. alan
        bosta = parcalar[3] + (parcalar[4] if len(parcalar) > 4 else 0.0)
        return (toplam - bosta, toplam)
    except Exception:
        return None


def _proc_bellek():
    """/proc/meminfo'dan (kullanilan_bayt, toplam_bayt) dondurur."""
    try:
        deger = {}
        with open("/proc/meminfo", "r") as f:
            for satir in f:
                ad, _, kalan = satir.partition(":")
                deger[ad.strip()] = float(kalan.split()[0]) * 1024.0
        toplam = deger.get("MemTotal", 0.0)
        # MemAvailable cekirdegin gercek "kullanilabilir" tahminidir;
        # MemFree onbellegi disladigi icin yaniltici olur.
        uygun = deger.get("MemAvailable", deger.get("MemFree", 0.0))
        return (toplam - uygun, toplam)
    except Exception:
        return None


def _proc_surec_cpu_saniye():
    """/proc/self/stat'tan surecin toplam CPU saniyesi."""
    try:
        with open("/proc/self/stat", "r") as f:
            alanlar = f.read().split()
        # 14: utime, 15: stime (1 tabanli alan numaralari)
        jiffy = float(alanlar[13]) + float(alanlar[14])
        hz = os.sysconf("SC_CLK_TCK") or 100
        return jiffy / float(hz)
    except Exception:
        return None


def _proc_surec_rss():
    try:
        with open("/proc/self/statm", "r") as f:
            alanlar = f.read().split()
        return float(alanlar[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return None


def _proc_ag():
    """/proc/net/dev toplam (gonderilen, alinan) bayt; lo haric."""
    try:
        gon = alin = 0.0
        with open("/proc/net/dev", "r") as f:
            for satir in f.readlines()[2:]:
                ad, _, kalan = satir.partition(":")
                if ad.strip() == "lo":
                    continue
                a = kalan.split()
                alin += float(a[0])
                gon += float(a[8])
        return (gon, alin)
    except Exception:
        return None


def kullanilabilir() -> bool:
    """Olcum yapilabiliyor mu (psutil veya /proc)."""
    if _PSUTIL:
        return True
    return _proc_sistem_cpu() is not None


def olc() -> dict:
    """Anlik kaynak ozeti dondurur.

    Doner:
        {
          "hazir": bool,          # olcum yapilabildi mi
          "kaynak": "psutil"|"proc"|"",
          "surec_cpu": float|None,   # GCS surecinin CPU yuzdesi (cekirdek
                                     # basina normalize edilmis, 0-100)
          "surec_ram": float|None,   # MB
          "sistem_cpu": float|None,  # tum makine, 0-100
          "sistem_ram": float|None,  # yuzde
          "ram_kullanilan": float|None,  # MB
          "ram_toplam": float|None,      # MB
          "ag_gonderilen": float|None,   # KB/s
          "ag_alinan": float|None,       # KB/s
          "cekirdek": int,
          "ilk": bool,               # ilk olcum (CPU degerleri None)
        }
    """
    simdi = time.time()
    gecen = simdi - _son["t"] if _son["t"] else 0.0
    ilk = _son["t"] == 0.0

    sonuc = {
        "hazir": False, "kaynak": "",
        "surec_cpu": None, "surec_ram": None,
        "sistem_cpu": None, "sistem_ram": None,
        "ram_kullanilan": None, "ram_toplam": None,
        "ag_gonderilen": None, "ag_alinan": None,
        "cekirdek": 0, "ilk": ilk,
    }

    # Cok sik cagri: iki olcum arasi en az 0.2 s olmali, yoksa CPU
    # yuzdesi olcum gurultusunden ibaret olur.
    if not ilk and gecen < 0.2:
        gecen = 0.2

    if _PSUTIL:
        sonuc["kaynak"] = "psutil"
        try:
            p = _surec_al()
            cek = psutil.cpu_count(logical=True) or 1
            sonuc["cekirdek"] = int(cek)

            # --- Surec CPU (delta) ---
            if p is not None:
                ct = p.cpu_times()
                toplam_cpu = float(ct.user + ct.system)
                if not ilk and gecen > 0:
                    fark = toplam_cpu - _son["surec_cpu"]
                    # Cekirdek sayisina bol: cok cekirdekli makinede
                    # %100'un uzerine cikan deger kullaniciyi yanlis
                    # yonlendirir.
                    sonuc["surec_cpu"] = max(
                        0.0, min(100.0, (fark / gecen) * 100.0 / cek))
                _son["surec_cpu"] = toplam_cpu
                try:
                    sonuc["surec_ram"] = p.memory_info().rss / (1024.0 * 1024.0)
                except Exception:
                    pass

            # --- Sistem CPU (delta; blokleyici cagri YOK) ---
            t = psutil.cpu_times()
            kullanilan = float(sum(t) - t.idle
                               - getattr(t, "iowait", 0.0))
            toplam = float(sum(t))
            if not ilk and _son["sistem_cpu"]:
                dk = kullanilan - _son["sistem_cpu"][0]
                dt = toplam - _son["sistem_cpu"][1]
                if dt > 0:
                    sonuc["sistem_cpu"] = max(0.0, min(100.0, dk / dt * 100.0))
            _son["sistem_cpu"] = (kullanilan, toplam)

            # --- Bellek ---
            vm = psutil.virtual_memory()
            sonuc["sistem_ram"] = float(vm.percent)
            sonuc["ram_toplam"] = vm.total / (1024.0 * 1024.0)
            sonuc["ram_kullanilan"] = (vm.total - vm.available) / (1024.0 * 1024.0)

            # --- Ag (delta) ---
            try:
                ag = psutil.net_io_counters()
                cift = (float(ag.bytes_sent), float(ag.bytes_recv))
                if not ilk and _son["ag"] and gecen > 0:
                    sonuc["ag_gonderilen"] = max(
                        0.0, (cift[0] - _son["ag"][0]) / gecen / 1024.0)
                    sonuc["ag_alinan"] = max(
                        0.0, (cift[1] - _son["ag"][1]) / gecen / 1024.0)
                _son["ag"] = cift
            except Exception:
                pass

            sonuc["hazir"] = True
        except Exception:
            sonuc["hazir"] = False
    else:
        # --- /proc yedek yolu ---
        s = _proc_sistem_cpu()
        if s is not None:
            sonuc["kaynak"] = "proc"
            try:
                sonuc["cekirdek"] = int(os.cpu_count() or 1)
            except Exception:
                sonuc["cekirdek"] = 1
            if not ilk and _son["sistem_cpu"]:
                dk = s[0] - _son["sistem_cpu"][0]
                dt = s[1] - _son["sistem_cpu"][1]
                if dt > 0:
                    sonuc["sistem_cpu"] = max(0.0, min(100.0, dk / dt * 100.0))
            _son["sistem_cpu"] = s

            sc = _proc_surec_cpu_saniye()
            if sc is not None:
                if not ilk and gecen > 0:
                    fark = sc - _son["surec_cpu"]
                    cek = sonuc["cekirdek"] or 1
                    sonuc["surec_cpu"] = max(
                        0.0, min(100.0, (fark / gecen) * 100.0 / cek))
                _son["surec_cpu"] = sc

            rss = _proc_surec_rss()
            if rss is not None:
                sonuc["surec_ram"] = rss / (1024.0 * 1024.0)

            bel = _proc_bellek()
            if bel and bel[1] > 0:
                sonuc["ram_kullanilan"] = bel[0] / (1024.0 * 1024.0)
                sonuc["ram_toplam"] = bel[1] / (1024.0 * 1024.0)
                sonuc["sistem_ram"] = bel[0] / bel[1] * 100.0

            ag = _proc_ag()
            if ag:
                if not ilk and _son["ag"] and gecen > 0:
                    sonuc["ag_gonderilen"] = max(
                        0.0, (ag[0] - _son["ag"][0]) / gecen / 1024.0)
                    sonuc["ag_alinan"] = max(
                        0.0, (ag[1] - _son["ag"][1]) / gecen / 1024.0)
                _son["ag"] = ag

            sonuc["hazir"] = True

    _son["t"] = simdi
    return sonuc
