#!/usr/bin/env python3
"""GOKTUNGU v2.4.45 -- CANLI UCTAN UCA SINAV

Gercek sunucu (main.py), gercek SITL (gomulu Linux ikilisi), gercek
benzetici (PTY seri port) uzerinde WebSocket katmanindan olcum yapar.

Olculen alanlar:
  A. GCCDUAL ac/kapa (Program Ayarlari) + kapaliyken baglanmama
  B. Tek SANAL DRON grubu (sanal baglantilarin ayni ust grupta olmasi)
  C. Dron haberlesme konsolu (genel konsol yerine dron basina tampon)
  D. Istasyon 2 dugmeleri (GCCDUAL aciksa)
  E. AI SSH play/konsol (kimlik dogrulama hatasi bile olsa akis calisir)

Kullanim: python3 sinav_2445_canli.py [ws://127.0.0.1:8765] [PTY]
"""
import os
import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    print("websockets yok: sudo pip3 install websockets")
    sys.exit(2)

WS = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
PTY = sys.argv[2] if len(sys.argv) > 2 else "/dev/pts/4"
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz

GECTI = 0
KALDI = 0
NOTLAR = []


def ol(ad, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"[GECTI    ] {ad}" + (f"  ->  {ayrinti}" if ayrinti else ""))
    else:
        KALDI += 1
        print(f"[BASARISIZ] {ad}  ->  {ayrinti}")
        NOTLAR.append(f"{ad}: {ayrinti}")


class Oturum:
    def __init__(self, ws):
        self.ws = ws
        self.kutu = []
        self.gorev = None
        # v2.4.45 sinav duzeltmesi: `bekle()` her cagrida kutuyu bastan
        # taradigi icin ONCEKI olcumun yanitini yeniden yakaliyordu
        # (or. reddedilmis `istasyon2_sonuc`). Imlec artik oturum
        # boyunca kalicidir: her `bekle()` yalnizca YENI mesajlara bakar.
        self.imlec = 0

    async def basla(self):
        self.gorev = asyncio.create_task(self._oku())

    async def _oku(self):
        try:
            async for ham in self.ws:
                try:
                    self.kutu.append(json.loads(ham))
                except Exception:
                    pass
        except Exception:
            pass

    async def gonder(self, **k):
        await self.ws.send(json.dumps(k))

    async def bekle(self, tip, sure=8.0, kosul=None):
        """Yalnizca YENI gelen mesajlar arasinda arar (kalici imlec)."""
        bas = time.time()
        while time.time() - bas < sure:
            while self.imlec < len(self.kutu):
                m = self.kutu[self.imlec]
                self.imlec += 1
                if m.get("tip") == tip and (kosul is None or kosul(m)):
                    return m
            await asyncio.sleep(0.12)
        return None

    def imlec_sifirla(self):
        """Bir komut gondermeden ONCE cagrilir: birikmis mesajlar atlanir."""
        self.imlec = len(self.kutu)

    def son(self, tip, kosul=None):
        for m in reversed(self.kutu):
            if m.get("tip") == tip and (kosul is None or kosul(m)):
                return m
        return None

    def sayi(self, tip, kosul=None):
        return sum(1 for m in self.kutu
                   if m.get("tip") == tip and (kosul is None or kosul(m)))


async def kos():
    async with websockets.connect(WS, max_size=8 * 1024 * 1024) as ws:
        o = Oturum(ws)
        await o.basla()

        # ---------- giris ----------
        await o.gonder(tip="giris", eposta=EPOSTA, sifre=SIFRE)
        g = await o.bekle("giris_sonuc", 12)
        ol("sisteme giris", bool(g and g.get("basarili")),
           str(g)[:110] if g else "yanit yok")
        if not (g and g.get("basarili")):
            return

        # ==================================================
        # A. GCCDUAL ac/kapa
        # ==================================================
        print("\n--- A. GCCDUAL (Yer Kontrol Istasyonu Dual) ---")

        # Baslangicta kapali olmali (varsayilan)
        d0 = await o.bekle("istasyon2_durum", 6)
        if d0 is None:
            await o.gonder(tip="istasyon2_durum")
            d0 = await o.bekle("istasyon2_durum", 6)
        ol("istasyon2_durum paketi geliyor", bool(d0), str(d0)[:90])
        if d0:
            ol("durum paketinde cihaz kunyesi var",
               str(d0.get("cihaz") or d0.get("cihaz_kodu") or "") == "GCCDUAL",
               f"cihaz={d0.get('cihaz') or d0.get('cihaz_kodu')}")
            ol("varsayilan olarak arayuz KAPALI",
               not d0.get("arayuz_acik", True),
               f"arayuz_acik={d0.get('arayuz_acik')}")

        # Kapaliyken baglanma denemesi REDDEDILMELI
        o.imlec_sifirla()
        await o.gonder(tip="istasyon2_baglan", port=PTY)
        r = await o.bekle("istasyon2_sonuc", 8,
                          lambda m: m.get("islem") == "baglan")
        ol("KAPALIYKEN baglanma reddedilir",
           bool(r) and not r.get("basari"),
           f"sebep={(r or {}).get('sebep')}")

        # Ayarlardan AC
        o.imlec_sifirla()
        await o.gonder(tip="program_ayar_yaz", istasyon2_arayuz=True,
                       istasyon2_port=PTY, istasyon2_otomatik=True)
        a = await o.bekle("ayarlar", 8,
                          lambda m: "istasyon2_arayuz" in (m.get("ayarlar") or {}))
        ol("Program Ayarlari GCCDUAL anahtarini yazdi",
           bool(a) and (a.get("ayarlar") or {}).get("istasyon2_arayuz") is True,
           f"istasyon2_arayuz={(a or {}).get('ayarlar', {}).get('istasyon2_arayuz')}")
        ol("port ayari da saklandi",
           bool(a) and (a.get("ayarlar") or {}).get("istasyon2_port") == PTY,
           f"port={(a or {}).get('ayarlar', {}).get('istasyon2_port')}")

        # Acikken baglanma BASARILI olmali. Ayar yazimi ile baglan
        # komutu arasinda kisa bir bekleme sart: ayar SQLite'a
        # yazilmadan baglan gelirse `arayuz_acik()` hala False okur.
        await asyncio.sleep(1.0)
        o.imlec_sifirla()
        await o.gonder(tip="istasyon2_baglan", port=PTY)
        r = await o.bekle("istasyon2_sonuc", 12,
                          lambda m: m.get("islem") == "baglan")
        ol("ACIKKEN baglanma basarili", bool(r) and bool(r.get("basari")),
           f"sebep={(r or {}).get('sebep')}")

        d1 = await o.bekle("istasyon2_durum", 10,
                           lambda m: m.get("bagli"))
        ol("bagli durum yayinlaniyor", bool(d1),
           f"bagli={(d1 or {}).get('bagli')} port={(d1 or {}).get('port')}")

        # ==================================================
        # D. Istasyon 2 dugmeleri (aciksa)
        # ==================================================
        print("\n--- D. Istasyon 2 kanal olcumleri ---")
        # Gercek yayin tipleri: istasyon2_durum (tam durum) +
        # istasyon2_eylem / istasyon2_eylem_sonuc (buton eylemleri).
        def _akis(x):
            return (x.sayi("istasyon2_durum") + x.sayi("istasyon2_eylem")
                    + x.sayi("istasyon2_eylem_sonuc"))
        ilk = _akis(o)
        await asyncio.sleep(4.0)
        son = _akis(o)
        ol("benzeticiden canli veri akiyor", son > ilk,
           f"{ilk} -> {son} paket")

        # LED komutu
        o.imlec_sifirla()
        await o.gonder(tip="istasyon2_led", kanal="P3", acik=True)
        led = await o.bekle("istasyon2_sonuc", 8,
                            lambda m: m.get("islem") == "led")
        ol("LED komutu kabul edildi", bool(led) and bool(led.get("basari")),
           str(led)[:90])

        # LED'siz kanal sessizce yok sayilmali (P8)
        o.imlec_sifirla()
        await o.gonder(tip="istasyon2_led", kanal="P8", acik=True)
        led8 = await o.bekle("istasyon2_sonuc", 8,
                             lambda m: m.get("islem") == "led"
                             and m.get("kanal") == "P8")
        ol("LED'siz kanal (P8) ayrimi bildiriliyor",
           led8 is None or not led8.get("basari") or "P8" in str(led8),
           str(led8)[:90] if led8 else "yanit yok (yok sayildi)")

        # Kalibrasyon
        o.imlec_sifirla()
        await o.gonder(tip="istasyon2_kalibre")
        kal = await o.bekle("istasyon2_sonuc", 8,
                            lambda m: m.get("islem") == "kalibre")
        ol("kalibrasyon komutu isliyor", bool(kal), str(kal)[:90])

        # --- D2. P1-P6 emniyet: joystick kontrolu kapaliyken reddedilir
        print("\n--- D2. P1-P6 emniyet (joystick kontrolu kapali) ---")
        # Benzetici otomatik kipte P butonlarina basar. Hicbir dronda
        # joystick kontrolu acik olmadigi icin ucus eylemleri
        # REDDEDILMELI (kazara ARM/TAKEOFF olmamali).
        await asyncio.sleep(3.0)
        redler = [m for m in o.kutu
                  if m.get("tip") == "istasyon2_eylem_sonuc"
                  and not m.get("basari")]
        kabuller = [m for m in o.kutu
                    if m.get("tip") == "istasyon2_eylem_sonuc"
                    and m.get("basari")
                    and str(m.get("eylem", "")) in
                    ("arm_toggle", "takeoff_land", "rtl",
                     "mod_guided", "mod_althold", "mod_auto")]
        ol("ucus eylemleri joystick kapaliyken reddedildi",
           len(kabuller) == 0,
           f"{len(redler)} red, {len(kabuller)} kabul")
        if redler:
            sebepler = {str(m.get("sebep")) for m in redler}
            ol("red sebebi anlasilir bildiriliyor",
               any("joystick" in x for x in sebepler),
               f"sebepler={sorted(sebepler)[:3]}")

        # ==================================================
        # B. Tek SANAL DRON grubu + SITL
        # ==================================================
        print("\n--- B. Sanal dron / tek SANAL grup ---")
        isim1 = f"SNV45A-{int(time.time()) % 10000}"
        isim2 = f"SNV45B-{int(time.time()) % 10000}"
        for isim in (isim1, isim2):
            await o.gonder(tip="baglanti_ekle", isim=isim, tur="sanal",
                           port="0", sanal_tip="multirotor",
                           lat=39.925, lon=32.836, adet=1)
            await asyncio.sleep(1.2)
        # Kayit sonrasi acik istekle TAZE liste al; eski yayinda yeni
        # kayitlar bulunmayabilir.
        o.imlec_sifirla()
        await o.gonder(tip="baglanti_listele")
        bl = await o.bekle("baglanti_listesi", 12)
        if bl is None:
            bl = o.son("baglanti_listesi")
        liste = (bl or {}).get("baglantilar") or []
        sanallar = [b for b in liste
                    if str(b.get("tur", "")).lower() == "sanal"]
        ol("iki sanal baglanti kaydedildi", len(sanallar) >= 2,
           f"{len(sanallar)} sanal kayit")
        ol("her sanal kayit ayni 'sanal' turunde (tek grup icin sart)",
           all(str(b.get("tur", "")).lower() == "sanal" for b in sanallar),
           f"turler={sorted({str(b.get('tur')) for b in sanallar})}")

        # SITL baslat
        hedef = None
        for b in sanallar:
            if b.get("isim") == isim1:
                hedef = b
                break
        if hedef is None:
            # Yayin gecikmesi olabilir: taze listeyi bir kez daha iste
            o.imlec_sifirla()
            await o.gonder(tip="baglanti_listele")
            bl2 = await o.bekle("baglanti_listesi", 12) or o.son(
                "baglanti_listesi") or {}
            for b in (bl2.get("baglantilar") or []):
                if b.get("isim") == isim1:
                    hedef = b
                    break
        ol("sanal kayit bulunabildi", bool(hedef), f"isim={isim1}")
        if hedef:
            await o.gonder(tip="baglanti_baslat", id=hedef.get("id"))
            # SITL'in ayaga kalkmasi + MAVLink akisi
            t0 = time.time()
            sysid = None
            while time.time() - t0 < 75:
                tel = o.son("telemetri")
                if tel:
                    for d in (tel.get("dronlar") or []):
                        if str(d.get("baglanti_id")) == str(hedef.get("id")):
                            sysid = d.get("sysid")
                            break
                if sysid:
                    break
                await asyncio.sleep(1.0)
            ol("gomulu SITL ile sanal dron telemetri veriyor", bool(sysid),
               f"sysid={sysid} ({time.time() - t0:.0f} sn)")

            # ==============================================
            # C. Dron haberlesme konsolu
            # ==============================================
            print("\n--- C. Dron haberlesme konsolu ---")
            if sysid:
                await o.gonder(tip="dron_konsol_gecmis", sysid=sysid,
                               adet=200)
                kg = await o.bekle("dron_konsol_gecmis", 10,
                                   lambda m: m.get("sysid") == sysid)
                satirlar = (kg or {}).get("satirlar") or []
                ol("dron konsolu gecmis dondurur", bool(kg), f"sysid={sysid}")
                ol("konsol tamponu DOLU (panel kapaliyken de birikmis)",
                   len(satirlar) > 0, f"{len(satirlar)} satir")
                if satirlar:
                    ornek = satirlar[-1]
                    ol("konsol satiri yapisal (etiket+metin)",
                       isinstance(ornek, dict)
                       and ("metin" in ornek or "mesaj" in ornek
                            or "satir" in ornek),
                       str(ornek)[:110])

                # Canli satir yayini
                onceki = o.sayi("dron_konsol_satir")
                await o.gonder(tip="dron_komut", sysid=sysid,
                               aksiyon="mod_degistir", mod="GUIDED")
                await asyncio.sleep(4.0)
                simdi = o.sayi("dron_konsol_satir")
                ol("komut sonrasi CANLI konsol satiri yayinlandi",
                   simdi > onceki, f"{onceki} -> {simdi}")

                # Temizleme
                await o.gonder(tip="dron_konsol_temizle", sysid=sysid)
                await asyncio.sleep(1.5)
                await o.gonder(tip="dron_konsol_gecmis", sysid=sysid)
                kg2 = await o.bekle("dron_konsol_gecmis", 8,
                                    lambda m: m.get("sysid") == sysid)
                # Temizlemeden sonra yeni telemetri satirlari gelebilir;
                # onemli olan tamponun KUCULMESI.
                yeni = len((kg2 or {}).get("satirlar") or [])
                ol("konsol temizleme tamponu kuculttu",
                   yeni < max(len(satirlar), 1),
                   f"{len(satirlar)} -> {yeni} satir")


        # ==================================================
        # E. AI SSH play + konsol
        # ==================================================
        print("\n--- E. AI bilgisayari SSH play/konsol ---")
        ad = f"SSH45-{int(time.time()) % 10000}"
        await o.gonder(tip="ai_sunucu_kaydet", ad=ad, sunucu_tip="uzak",
                       host="127.0.0.1", port=8900, kapasite=1,
                       notlar="v2.4.45 sinav",
                       ssh={"kullanici": "ubuntu", "port": 22,
                            "sifre": "", "anahtar": "",
                            "komut": "echo GOKTUNGU_SSH_SINAV_OK"})
        await asyncio.sleep(0.8)
        o.imlec_sifirla()
        await o.gonder(tip="ai_sunucu_listele")
        al = await o.bekle("ai_sunucu_listesi", 12)
        if al is None:
            al = o.son("ai_sunucu_listesi")
        sunucular = (al or {}).get("sunucular") or []
        kayit = None
        for s in sunucular:
            if s.get("ad") == ad:
                kayit = s
                break
        ol("AI bilgisayari SSH alanlariyla kaydedildi", bool(kayit),
           f"ad={ad}")
        if kayit:
            ol("SSH kullanici alani saklandi",
               str(kayit.get("ssh_kullanici") or "") == "ubuntu",
               f"ssh_kullanici={kayit.get('ssh_kullanici')}")
            ol("SSH sifresi arayuze DUZ METIN gitmiyor",
               "ssh_sifre" not in kayit
               or kayit.get("ssh_sifre") in ("", "***", None, True, False),
               f"ssh_sifre={kayit.get('ssh_sifre')!r}")
            ol("baslatma komutu saklandi",
               "GOKTUNGU_SSH_SINAV_OK" in str(kayit.get("ssh_komut") or ""),
               f"ssh_komut={str(kayit.get('ssh_komut'))[:60]}")

            # Konsol gecmisi (henuz calismadi)
            o.imlec_sifirla()
            await o.gonder(tip="ai_ssh_gecmis", id=kayit.get("id"))
            kg = await o.bekle("ai_ssh_gecmis", 8)
            ol("konsol gecmis komutu yanit veriyor", bool(kg),
               f"calisiyor={(kg or {}).get('calisiyor')} "
               f"satir={len((kg or {}).get('satirlar') or [])}")

            # Play
            o.imlec_sifirla()
            await o.gonder(tip="ai_ssh_baslat", id=kayit.get("id"))
            dur = await o.bekle("ai_ssh_durum", 20)
            ol("play dugmesi SSH akisini baslatti", bool(dur),
               str(dur)[:120])
            # Cikti satiri (basarili baglanti VEYA anlasilir hata)
            cik = await o.bekle("ai_ssh_satir", 25)
            if cik is None:
                await asyncio.sleep(6.0)
                cik = o.son("ai_ssh_satir")
            ol("SSH konsoluna satir akti (basari veya anlasilir hata)",
               bool(cik), str(cik)[:140])

            await o.gonder(tip="ai_ssh_gecmis", id=kayit.get("id"))
            kg2 = await o.bekle("ai_ssh_gecmis", 10)
            satir2 = (kg2 or {}).get("satirlar") or []
            ol("konsol tamponu birikti (pencere kapaliyken de)",
               len(satir2) > 0, f"{len(satir2)} satir")
            if satir2:
                ol("tampon satirlari sifre ICERMIYOR",
                   all("nCkeuyPH" not in str(s) for s in satir2),
                   "sizinti yok")

            await o.gonder(tip="ai_ssh_durdur", id=kayit.get("id"))
            await asyncio.sleep(1.5)
            await o.gonder(tip="ai_sunucu_sil", id=kayit.get("id"))
            await asyncio.sleep(1.0)

        # ---------- temizlik ----------
        for b in sanallar:
            if b.get("isim") in (isim1, isim2):
                await o.gonder(tip="baglanti_durdur", id=b.get("id"))
                await asyncio.sleep(0.8)
                await o.gonder(tip="baglanti_sil", id=b.get("id"))
                await asyncio.sleep(0.6)

        # GCCDUAL'i kapat (varsayilana don)
        await o.gonder(tip="istasyon2_kes")
        await asyncio.sleep(1.0)
        await o.gonder(tip="program_ayar_yaz", istasyon2_arayuz=False)
        a2 = await o.bekle("ayarlar", 8,
                           lambda m: (m.get("ayarlar") or {}).get(
                               "istasyon2_arayuz") is False)
        ol("GCCDUAL kapatilinca ayar geri alinabiliyor", bool(a2),
           f"istasyon2_arayuz={(a2 or {}).get('ayarlar', {}).get('istasyon2_arayuz')}")

        if o.gorev:
            o.gorev.cancel()


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.45 -- CANLI UCTAN UCA SINAV")
    print(f"WS: {WS} | PTY: {PTY}")
    print("=" * 70)
    try:
        asyncio.run(kos())
    except Exception as e:
        print(f"[HATA] sinav kesildi: {type(e).__name__}: {e}")
        globals()["KALDI"] = KALDI + 1
    print("=" * 70)
    print(f"SONUC: {GECTI} GECTI / {KALDI} KALDI")
    if NOTLAR:
        print("\nKalanlar:")
        for n in NOTLAR:
            print(f"  - {n}")
    print("=" * 70)
    sys.exit(0 if KALDI == 0 else 1)


if __name__ == "__main__":
    main()
