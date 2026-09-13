#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.49: arayuzden servis DURDUR/BASLAT/YENIDEN BASLAT eylemlerini
GERCEK systemd servisi uzerinde sinar.

Neden ayri betik: bu sinav servisi gercekten durdurur. Durdurma aninda
WS baglantisi kopar (sunucu kendisini durduruyor), bu yuzden sinav
kopmayi HATA saymaz, aksine BEKLER. Sonra systemctl ile durumu olcup
yeniden baslatir. dene_servis_ws.py bu yuzden yalnizca okuma yapar.

Kullanim:
  python3 dene_servis_eylem.py [ws_adres] [eposta] [sifre]
"""
import asyncio
import json
import ssl
import subprocess
import sys
import time

WS = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
EPOSTA = sys.argv[2] if len(sys.argv) > 2 else "mkaderoglu@gokkubbetech.com"
SIFRE = sys.argv[3] if len(sys.argv) > 3 else "gokkubbe2026"

gecti = 0
kaldi = 0


def olc(ad, kosul, ayrinti=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  GECTI  {ad}")
    else:
        kaldi += 1
        print(f"  KALDI  {ad}  {ayrinti}")


def sysd(*args):
    """systemctl cagirir, (cikis_kodu, cikti) doner."""
    p = subprocess.run(["systemctl"] + list(args), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def aktif_mi():
    return sysd("is-active", "goktungu")[1] == "active"


def bekle_pid_degisimi(onceki, sn=60):
    """MainPID gercekten degisene kadar bekler.

    KRITIK: `systemctl restart` ONCE eski sureci durdurur. Sinav PID'i
    hemen okursa eski PID'i gorur (henuz oldurulmemistir) ve yanlislikla
    "degismedi" der. Bu yuzden degisim BEKLENIR.
    """
    son = onceki
    for _ in range(sn * 2):
        son = sysd("show", "-p", "MainPID", "--value", "goktungu")[1]
        if son not in ("", "0", onceki) and aktif_mi():
            return True, son
        time.sleep(0.5)
    return False, son


def bekle_durum(hedef, sn=40):
    """Servis hedef duruma gelene kadar bekler."""
    son = ""
    for _ in range(sn * 2):
        son = sysd("is-active", "goktungu")[1]
        if son == hedef:
            return True, son
        time.sleep(0.5)
    return False, son


async def ws_komut(komut, ek=None, yanit_bekle=True, zaman=15):
    """Giris yapip tek komut gonderir. (yanit|None, kopma_oldu) doner."""
    import websockets

    ctx = None
    if WS.startswith("wss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    async with websockets.connect(WS, ssl=ctx, max_size=None) as ws:
        # KRITIK: gercek sozlesme alani "tip" ("komut" DEGIL)
        await ws.send(json.dumps({"tip": "giris", "eposta": EPOSTA, "sifre": SIFRE}))
        giris_tamam = False
        bitis = time.time() + 20
        while time.time() < bitis:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("tip") == "giris_sonuc" and m.get("basarili"):
                giris_tamam = True
                break
        if not giris_tamam:
            return None, False, False

        istek = {"tip": komut}
        if ek:
            istek.update(ek)
        await ws.send(json.dumps(istek))

        if not yanit_bekle:
            return None, False, True

        bitis = time.time() + zaman
        while time.time() < bitis:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            except asyncio.TimeoutError:
                continue
            except Exception:
                # baglanti koptu: servis kendisini durdurdu -> BEKLENEN
                return None, True, True
            if m.get("tip", "").startswith("servis"):
                return m, False, True
        return None, False, True


async def main():
    print("=== v2.4.49 SERVIS EYLEM SINAVI (gercek systemd) ===")

    # 0) onkosul
    olc("servis kurulu ve aktif", aktif_mi(), sysd("is-active", "goktungu")[1])
    if not aktif_mi():
        print("  [dur] servis aktif degil; sinav anlamsiz")
        return

    # 1) YENIDEN BASLAT — en guvenli eylem: servis geri gelir
    print("\n--- 1) yeniden baslat ---")
    onceki_pid = sysd("show", "-p", "MainPID", "--value", "goktungu")[1]
    yanit, kopma, tamam = await ws_komut("servis_eylem", {"ad": "yeniden"},
                                         yanit_bekle=True, zaman=20)
    olc("komut gonderildi", tamam)
    # KRITIK: sunucu eylemi UYGULAMADAN once yanit gonderir (kendini
    # durdurma sorunu). Bu yuzden yanit 'beklemede' isaretli gelmeli.
    olc("yanit alindi (kopma oncesi)", yanit is not None,
        f"kopma={kopma}")
    if yanit:
        olc("yanit basarili", bool(yanit.get("basarili")), str(yanit)[:120])
        olc("beklemede isareti var (once yanit, sonra eylem)",
            bool(yanit.get("beklemede")), str(yanit)[:120])
    # yeniden baslatmada kopma normaldir
    ok, son = bekle_durum("active", 60)
    olc("servis yeniden active oldu", ok, f"durum={son}")
    pid_ok, yeni_pid = bekle_pid_degisimi(onceki_pid, 60)
    olc("surec kimligi degisti (gercekten yeniden basladi)", pid_ok,
        f"once={onceki_pid} sonra={yeni_pid}")

    # sunucunun tam ayaga kalkmasini bekle
    time.sleep(20)

    # 2) DURDUR — servis kendisini durdurur, WS kopmasi BEKLENIR
    print("\n--- 2) durdur (WS kopmasi beklenir) ---")
    yanit, kopma, tamam = await ws_komut("servis_eylem", {"ad": "durdur"},
                                         yanit_bekle=True, zaman=15)
    olc("durdur komutu gonderildi", tamam)
    olc("durdur yaniti alindi (kopmadan once)", yanit is not None,
        f"kopma={kopma}")
    if yanit:
        olc("durdur yaniti basarili", bool(yanit.get("basarili")),
            str(yanit)[:120])
    ok, son = bekle_durum("inactive", 60)
    olc("servis gercekten durdu", ok, f"durum={son}")

    # 3) systemctl ile yeniden baslat (arayuz yok artik)
    print("\n--- 3) systemctl start ile geri getir ---")
    subprocess.run(["sudo", "systemctl", "start", "goktungu"], capture_output=True)
    ok, son = bekle_durum("active", 60)
    olc("servis geri basladi", ok, f"durum={son}")

    print(f"\nSONUC: {gecti} gecti / {kaldi} kaldi")


if __name__ == "__main__":
    asyncio.run(main())
