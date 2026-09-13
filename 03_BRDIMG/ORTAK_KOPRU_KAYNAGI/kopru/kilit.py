# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — tek ornek kilidi.

## NEDEN GEREKLI

Kopru merkeze `kurulum_uid` ile baglanir. Merkez tasarim geregi ayni
kurulum kimliginin IKINCI baglantisini kabul edip eskisini dusurur —
aksi halde makine yeniden baslatildiginda olu oturum yerinde kalir ve
kullanici bir daha baglanamaz.

Ancak ayni makinede IKI kopru sureci ayni anda calisirsa bu davranis
sonsuz bir dusurme dongusune girer: A baglanir, B baglanir ve A'yi
dusurur, A yeniden baglanir ve B'yi dusurur... Baglanti saniyeler
icinde surekli kopar ve telemetri hicbir zaman duzgun akmaz.

Bu gelistirme sirasinda GERCEKTEN yasandi: iki sureci ayni
`kimlik.json` ile calistirdim, baglanti 7 saniyede bir koptu ve
nedenini bulmak uzun surdu. Sahada kullanicinin bunu teshis etmesi
beklenemez. Bu yuzden ikinci ornek BASLAMAZ ve nedenini SOYLER.

## NEDEN PORT DEGIL DOSYA KILIDI

Panel portu zaten dolu olurdu ve ikinci ornek hata verirdi — ama bu
yeterli DEGIL: ikinci ornek `--port 8791` ile baska bir portta
acilabilir, panel calisir, kullanici hicbir uyari gormez, yalniz
merkez baglantisi bozulur. Kilit PORTA degil KIMLIGE baglanmali,
cunku catisan kaynak merkez oturumudur.

Windows'ta `msvcrt.locking`, POSIX'te `fcntl.flock` kullanilir. Ikisi
de surec oldugunde kilidi ISLETIM SISTEMI birakir; bu yuzden cokme
sonrasi bayat kilit dosyasi kalmaz (PID dosyasi yaklasiminin en sik
arizasi budur).
"""
import os

_TUTAMAK = None          # acik dosya nesnesi: surec boyunca yasar
_YOL = ""


class KilitMesgul(Exception):
    """Baska bir kopru ornegi zaten calisiyor."""

    def __init__(self, mesaj, sahip_pid=None):
        super().__init__(mesaj)
        self.sahip_pid = sahip_pid


def _kilit_yolu():
    from . import ayar as ayar_mod
    return os.path.join(ayar_mod.veri_dizini(), "kopru.kilit")


def _oku_pid(yol):
    """Kilidi tutan surecin PID'ini okur (yalniz mesaj icin)."""
    try:
        with open(yol, "r", encoding="utf-8") as f:
            return int((f.read() or "").strip() or 0) or None
    except Exception:
        return None


def al():
    """Tek ornek kilidini alir.

    Basarili olursa kilit tutamagi modul duzeyinde SAKLANIR: dosya
    nesnesi cop toplayiciya giderse kilit de birakilir.

    Alinamazsa `KilitMesgul` YUKSELTIR.
    """
    global _TUTAMAK, _YOL
    if _TUTAMAK is not None:
        return True                      # ayni surecte ikinci cagri
    yol = _kilit_yolu()
    # "a+" kullanilir: dosya varsa SILINMEZ. "w" ile acmak, kilidi
    # almadan once icerigi bosaltir; kilit mesgulse sahibin PID'ini
    # kaybederiz ve kullaniciya hangi sureci kapatacagini soyleyemeyiz.
    f = open(yol, "a+", encoding="utf-8")
    try:
        _kilitle(f)
    except OSError as e:
        sahip = _oku_pid(yol)
        try:
            f.close()
        except Exception:
            pass
        ek = (" (surec %d)" % sahip) if sahip else ""
        raise KilitMesgul(
            "Bu bilgisayarda baska bir GOKTUNGU Kopru ornegi zaten "
            "calisiyor%s. Iki ornek ayni merkez kimligini kullanirsa "
            "merkez baglantisi surekli kopar. Once digerini kapatin. "
            "[%s]" % (ek, e), sahip_pid=sahip)
    # Kilit alindi: PID yazilir. Amaci ISLEVSEL degil, TANILAMA —
    # kullaniciya hangi sureci kapatacagini soylemek icin.
    try:
        f.seek(0)
        f.truncate(0)
        f.write(str(os.getpid()))
        f.flush()
        os.fsync(f.fileno())
    except Exception:
        pass                             # PID yazamamak kilidi bozmaz
    _TUTAMAK, _YOL = f, yol
    return True


def birak():
    """Kilidi birakir. Normal kapanista cagrilir.

    Cagrilmasa bile isletim sistemi surec bittiginde kilidi birakir;
    bu islev yalniz ayni surecte yeniden baslatma senaryosu icindir.
    """
    global _TUTAMAK, _YOL
    f, _TUTAMAK = _TUTAMAK, None
    if f is None:
        return
    try:
        _kilidi_coz(f)
    except Exception:
        pass
    try:
        f.close()
    except Exception:
        pass
    # Dosya SILINMEZ: silme ile kapanma arasindaki yaris, baska bir
    # ornegin yeni olusturdugu dosyayi silmemize yol acabilir.
    _YOL = ""


def sahip_pid():
    """Kilidi tutan surecin PID'i (kilit bizde degilse de calisir)."""
    return _oku_pid(_kilit_yolu())


# ---------------------------------------------------------------------
# PLATFORMA OZGU KILITLEME
# ---------------------------------------------------------------------
if os.name == "nt":                      # Windows
    import msvcrt

    def _kilitle(f):
        # LK_NBLCK: bloke etmeden dene. Bloke eden kip, ikinci ornegi
        # sessizce askida bekletirdi.
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _kilidi_coz(f):
        try:
            f.seek(0)
        except Exception:
            pass
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:                                    # Linux / macOS
    import fcntl

    def _kilitle(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _kilidi_coz(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
