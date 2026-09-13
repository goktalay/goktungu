# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.50 - Joystick eksen isleme (pilot bazli).

## NEDEN BU MODUL VAR

v2.4.49'a kadar joystick eksenleri UC AYRI YERDE, birbirinden bagimsiz
ve SABIT KODLU olarak isleniyordu:

  1. `js/dronlar.js`  -> tarayici Gamepad API (GP_OLU = 0.12 sabit)
  2. `manuel_kontrol.py` -> pygame joystick (OLU_BOLGE = 0.12 sabit)
  3. `istasyon2.py`   -> ESP32 cantasi (kendi merkez kalibrasyonu var)

Bu dagilim iki kusur uretti:

### Kusur 1 - YAW KAYMASI (kullanicinin bildirdigi belirti)

"durduk yere joystick ortadayken bile dron kendi etrafinda donuyor"

Kok neden: sabit olu bolge, cubugun merkezde TAM 0.0 verdigini varsayar.
Gercek analog cubuklar merkezde 0.0 vermez; potansiyometre toleransi ve
mekanik yaslanma nedeniyle tipik olarak 0.02-0.15 arasi bir kayma
(drift) kalir. Kayma olu bolgeyi asarsa:

  yaw = 0.13  ->  0.13 * YAW_HIZ (1.2 rad/s) = 0.156 rad/s
              ->  dron surekli kendi etrafinda doner

Yaw ekseninde bu ozellikle gorunurdur, cunku yatay eksenlerdeki kucuk
kayma dronu yavasca kaydirirken (pilot bunu ruzgar sanabilir), yaw
kaymasi apacik bir donme uretir.

Ayrica `manuel_kontrol._dongu()` icindeki fren mantigi
`abs(x) > 0.02` esigini kullanir; kayma bu esigi astigi icin
"hareket var" sayilir ve komut akisi HIC kesilmez. Yani dron sonsuza
kadar doner.

### Kusur 2 - SICRAMA (olculdu, giderildi)

Tarayici ve pygame yollarinda olu bolge yalnizca KIRPIYORDU:

    return 0.0 if abs(v) < 0.12 else v

Bu, 0.12 sinirinda hizin 0'dan aniden 0.12'ye sicramasina yol acar.
`istasyon2.py` bunu zaten dogru yapiyordu (oransal yeniden olcekleme);
o dogru davranis burada TUM kaynaklara tasindi.

## TASARIM

Tek dogruluk kaynagi bu modul. Uc kaynak da ayni islevi cagirir:

    isle(ham_eksenler, tercih) -> {"vx","vy","vz","yaw"}

Pilot tercihi `ayarlar` tablosunda `joystick_pilot` anahtari altinda,
E-POSTA ANAHTARLI olarak saklanir. Program genelinde tek ayar
tutulmasi yanlis olur: ayni yer istasyonunu birden fazla pilot kullanir
ve biri "Mode 1", digeri "Mode 2" yerlesimine alisiktir. Kullanicinin
istegi de tam olarak budur: "bazi pilotlar farkli kullanabiliyor".

## SINIRLAR

- Ters cevirme yalnizca ISARET degistirir; eksen SIRASINI degistirmez.
  Eksen sirasi (hangi cubuk hangi kanal) donanima baglidir ve
  `EKSEN_SIRA` ile ayrica ayarlanabilir.
- Olu bolge her eksen icin AYRI ayarlanabilir. Tek bir genel deger
  yetmez: yaw ekseni genellikle en cok kayan eksendir ve ona daha
  geniss olu bolge vermek digerlerinin hassasiyetini dusurmemelidir.
"""

# Eksen adlari - tum kaynaklarda ayni siralama kullanilir
EKSENLER = ("vx", "vy", "vz", "yaw")

# Varsayilan olu bolge (normalize -1..1 araliginda).
# Yaw icin daha GENIS: olculen kayma en cok bu eksende gorulur ve
# yaw kaymasinin sonucu (surekli donme) en rahatsiz edici olandir.
VARSAYILAN_OLU = {"vx": 0.08, "vy": 0.08, "vz": 0.08, "yaw": 0.12}

# Olu bolge ust siniri: 0.9 uzerinde eksen kullanilamaz hale gelir.
OLU_TAVAN = 0.9

# Egri katsayisi (expo). 1.0 = dogrusal. 1.0'dan buyuk degerler
# merkez cevresini yumusatir (hassas ucus icin), 1.0 kalirsa
# davranis v2.4.49 ile ayni kalir.
VARSAYILAN_EGRI = 1.0
EGRI_TAVAN = 3.0

# Hiz olcekleri icin carpan (pilot "cok hizli/cok yavas" diyebilir).
VARSAYILAN_OLCEK = {"vx": 1.0, "vy": 1.0, "vz": 1.0, "yaw": 1.0}
OLCEK_TAVAN = 1.0
OLCEK_TABAN = 0.1


def varsayilan_tercih():
    """Bos/yeni pilot icin varsayilan tercih sozlugu.

    `ters` degerleri v2.4.49 davranisiyla AYNIDIR (hepsi False);
    boylece yama uygulandiginda mevcut pilotlarin ucus hissi
    degismez. Yalniz olu bolge ve oransal olcekleme duzelir.
    """
    return {
        "ters": {e: False for e in EKSENLER},
        "olu": dict(VARSAYILAN_OLU),
        "egri": VARSAYILAN_EGRI,
        "olcek": dict(VARSAYILAN_OLCEK),
        "merkez": {},          # kaynak bazli merkez kalibrasyonu (ham)
    }


def _sayi(deger, varsayilan, taban, tavan):
    try:
        v = float(deger)
    except (TypeError, ValueError):
        return varsayilan
    if v != v:            # NaN
        return varsayilan
    return max(taban, min(tavan, v))


def tercih_duzelt(ham):
    """Disaridan gelen (arayuz/veritabani) tercihi guvenli hale getirir.

    Arayuzden gelen veri DOGRULANMADAN kullanilamaz: bozuk bir olu
    bolge degeri (ornegin 1.5) ekseni tamamen olduruur ve pilot bunu
    "joystick bozuldu" olarak yasar. Bu yuzden her alan kirpilir.
    """
    t = varsayilan_tercih()
    if not isinstance(ham, dict):
        return t
    ters = ham.get("ters")
    if isinstance(ters, dict):
        for e in EKSENLER:
            t["ters"][e] = bool(ters.get(e, False))
    olu = ham.get("olu")
    if isinstance(olu, dict):
        for e in EKSENLER:
            t["olu"][e] = _sayi(olu.get(e), VARSAYILAN_OLU[e],
                                0.0, OLU_TAVAN)
    t["egri"] = _sayi(ham.get("egri"), VARSAYILAN_EGRI, 1.0, EGRI_TAVAN)
    olcek = ham.get("olcek")
    if isinstance(olcek, dict):
        for e in EKSENLER:
            t["olcek"][e] = _sayi(olcek.get(e), VARSAYILAN_OLCEK[e],
                                  OLCEK_TABAN, OLCEK_TAVAN)
    merkez = ham.get("merkez")
    if isinstance(merkez, dict):
        # Merkez ham birimdedir (kaynaga gore -1..1 veya 0..4095).
        # Burada tip disiplinini korumak yeterlidir; aralik denetimi
        # kaynak tarafinda yapilir.
        temiz = {}
        for k, v in merkez.items():
            try:
                temiz[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        t["merkez"] = temiz
    return t


def olu_uygula(deger, olu, egri=1.0):
    """Olu bolgeyi ORANSAL olarak uygular (sicrama yapmaz).

    v2.4.49'daki yanlis davranis:
        0.12 sinirinda hiz 0'dan aniden 0.12'ye sicrar.
    Dogru davranis:
        olu bolge disindaki aralik 0..1'e yeniden olceklenir.

    `egri` 1.0'dan buyukse merkez cevresi yumusatilir (expo).
    """
    try:
        v = float(deger)
    except (TypeError, ValueError):
        return 0.0
    if v != v:
        return 0.0
    v = max(-1.0, min(1.0, v))
    o = max(0.0, min(OLU_TAVAN, float(olu)))
    a = abs(v)
    if a <= o:
        return 0.0
    # Oransal yeniden olcekleme: (a - o) / (1 - o)
    kalan = 1.0 - o
    if kalan <= 1e-9:
        return 0.0
    n = (a - o) / kalan
    if egri and egri > 1.0:
        n = n ** float(egri)
    n = max(0.0, min(1.0, n))
    return n if v > 0 else -n


def merkez_duzelt(ham, merkez, tam_aralik):
    """Ham degeri kalibre edilmis merkeze gore -1..1'e cevirir.

    `tam_aralik` kaynagin ham birimini bildirir:
      - None  : deger zaten -1..1 (tarayici Gamepad API, pygame)
      - 4095  : 12 bit ADC (ESP32 cantasi)

    Merkez kalibrasyonu YAW KAYMASININ asil cozumudur: olu bolge
    kaymayi maskeler, kalibrasyon ise kaynagindan giderir. Ikisi
    birlikte kullanilir cunku kalibrasyon sonrasi da sicaklik/yaslanma
    kaynakli kucuk kayma kalabilir.
    """
    try:
        h = float(ham)
    except (TypeError, ValueError):
        return 0.0
    if h != h:
        return 0.0
    if tam_aralik:
        try:
            m = float(merkez)
        except (TypeError, ValueError):
            m = tam_aralik / 2.0
        fark = h - m
        if fark >= 0:
            bolen = max(1.0, tam_aralik - m)
        else:
            bolen = max(1.0, m)
        return max(-1.0, min(1.0, fark / bolen))
    # -1..1 kaynak
    try:
        m = float(merkez)
    except (TypeError, ValueError):
        m = 0.0
    m = max(-1.0, min(1.0, m))
    fark = h - m
    if fark >= 0:
        bolen = max(1e-6, 1.0 - m)
    else:
        bolen = max(1e-6, 1.0 + m)
    return max(-1.0, min(1.0, fark / bolen))


def isle(ham, tercih=None, kaynak="", tam_aralik=None):
    """Ham eksen sozlugunu pilot tercihine gore islenmis degere cevirir.

    ham     : {"vx":..,"vy":..,"vz":..,"yaw":..} ham degerler
    tercih  : `tercih_duzelt` cikti bicimi (None -> varsayilan)
    kaynak  : merkez kalibrasyonu anahtar oneki ("gamepad","pygame","ist2")
    tam_aralik : ham birim ust siniri (None = -1..1)

    Sira: merkez duzeltmesi -> olu bolge + egri -> ters -> olcek
    Bu sira ZORUNLUDUR. Ters cevirme olu bolgeden SONRA gelmeli,
    aksi halde asimetrik merkez kalibrasyonunda olu bolge yanlis
    tarafa uygulanir.
    """
    t = tercih if isinstance(tercih, dict) and "ters" in tercih \
        else tercih_duzelt(tercih)
    merkezler = t.get("merkez") or {}
    sonuc = {}
    for e in EKSENLER:
        anahtar = ("%s_%s" % (kaynak, e)) if kaynak else e
        varsayilan_m = (tam_aralik / 2.0) if tam_aralik else 0.0
        m = merkezler.get(anahtar, merkezler.get(e, varsayilan_m))
        v = merkez_duzelt(ham.get(e, varsayilan_m), m, tam_aralik)
        v = olu_uygula(v, t["olu"].get(e, VARSAYILAN_OLU[e]),
                       t.get("egri", VARSAYILAN_EGRI))
        if t["ters"].get(e):
            v = -v
        v *= t["olcek"].get(e, 1.0)
        sonuc[e] = max(-1.0, min(1.0, v))
    return sonuc


def notr_mu(eksen, esik=1e-6):
    """Tum eksenler notr mu (fren/akis kesme karari icin).

    `manuel_kontrol` fren mantigi `abs(x) > 0.02` sabitini kullaniyordu;
    olu bolge ISLENDIKTEN sonra notr deger TAM 0.0 oldugu icin artik
    sabit esige gerek yok. Bu, kayan bir cubugun komut akisini sonsuza
    kadar acik tutmasini onler.
    """
    try:
        return all(abs(float(eksen.get(e, 0.0))) <= esik for e in EKSENLER)
    except (TypeError, ValueError):
        return True
