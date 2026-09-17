# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — ters WebSocket röle katmanı.

Sorun
-----
Müşterilerin kurduğu köprü/GCS sunucularının **sabit IP'si yoktur** ve
NAT arkasındadır. Merkez onlara bağlanamaz. Ancak bağlantı yöneticisinde
kullanıcı, o an **açık olan sunucuları görmeli ve seçmelidir**.

Çözüm
-----
İletişim tek yönlü kurulur: **köprü → merkez**. Köprü açıldığında
merkeze bir WebSocket bağlantısı açar ve açık tutar. Merkez bu soket
üzerinden köprüye istek gönderebilir; yani yön tersine çevrilmiş olur
(reverse tunnel). Böylece:

  * köprünün açık portu, sabit IP'si veya port yönlendirmesi gerekmez,
  * merkez hangi sunucuların çevrimiçi olduğunu **gerçek bağlantı**
    üzerinden bilir (veritabanı işareti değil, canlı soket),
  * kullanıcı arayüzü açık sunucuları listeleyip seçebilir.

Protokol
--------
Köprü bağlanır → `{"tur":"merhaba", ...}` gönderir → merkez doğrular →
`{"tur":"merhaba_tamam"}`. Sonrasında:

  köprü → merkez : `nabiz`, `durum`, `yanit`, `ucus`, `video`
  merkez → köprü : `istek` (id ile), `kapat`

`istek`/`yanit` çifti, merkezin köprüden veri istemesini sağlar
(örn. dron listesi, uçuş kaydı, video parçası). Her istek bir
`istek_id` taşır ve `asyncio.Future` ile eşleşir.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import mk_db as db
from mk_ayar import ayar_oku

# --------------------------------------------------------------------------
# Bellekteki canlı köprü kayıtları
# --------------------------------------------------------------------------


class KopruOturumu:
    """Merkeze bağlı tek bir köprü sunucusu."""

    __slots__ = (
        "soket", "ornek_id", "kurulum_uid", "firma_id", "ad", "surum",
        "platform", "makine_adi", "ip", "baglanma_ts", "son_nabiz",
        "yetenekler", "dron_sayisi", "oturum_id", "bekleyen", "kanal",
    )

    def __init__(self, soket: Any, ip: str | None) -> None:
        self.soket = soket
        self.ip = ip
        self.ornek_id: int | None = None
        self.kurulum_uid: str = ""
        self.firma_id: int | None = None
        self.ad: str = ""
        self.surum: str = ""
        self.platform: str = ""
        self.makine_adi: str = ""
        self.baglanma_ts: float = time.time()
        self.son_nabiz: float = time.time()
        self.yetenekler: dict[str, Any] = {}
        self.dron_sayisi: int = 0
        self.oturum_id: int | None = None
        self.kanal: str = secrets.token_hex(8)
        # istek_id -> Future
        self.bekleyen: dict[str, asyncio.Future] = {}

    def ozet(self) -> dict[str, Any]:
        return {
            "ornek_id": self.ornek_id,
            "kurulum_uid": self.kurulum_uid,
            "firma_id": self.firma_id,
            "ad": self.ad,
            "surum": self.surum,
            "platform": self.platform,
            "makine_adi": self.makine_adi,
            "kanal": self.kanal,
            "cevrimici": True,
            "dron_sayisi": self.dron_sayisi,
            "yetenekler": self.yetenekler,
            "baglanma_ts": dt.datetime.fromtimestamp(
                self.baglanma_ts, dt.timezone.utc
            ).isoformat(),
            "son_nabiz_sn": round(time.time() - self.son_nabiz, 1),
        }


# IS47_TEK_OTURUM_v1: ayni kurulum_uid ile IKINCI baglanti geldiginde eski
# oturum CANLI ise yenisi reddedilir. Bu sure icinde nabiz
# alinmis bir oturum "canli" sayilir. 0 yapilirsa yama
# etkisizlesir ve eski (dusurme) davranisi geri gelir.
TEK_OTURUM_KORUMA_SN = 45


class IkinciOturumHatasi(Exception):
    """Ayni kurulum icin canli bir oturum zaten var.

    Cagiran bu hatayi yakalayip koprue nazik bir ret yaniti
    gondermeli ve soketi kapatmalidir. Koprunun ustel geri
    cekilmesi devreye girer; ILK baglanti kesintisiz kalir.
    """


class RoleYoneticisi:
    """Canlı köprü bağlantılarının kayıt defteri."""

    def __init__(self) -> None:
        self._kanallar: dict[str, KopruOturumu] = {}
        self._uid: dict[str, KopruOturumu] = {}
        self._kilit = asyncio.Lock()

    # ---- kayıt ----------------------------------------------------------
    async def ekle(self, o: KopruOturumu) -> None:
        async with self._kilit:
            # Aynı kurulum ikinci kez bağlanırsa eskisi düşürülür
            eski = self._uid.get(o.kurulum_uid)
            if eski is not None and eski is not o:
                # IS47_TEK_OTURUM_v1: eski oturum CANLI ise yenisini REDDET.
                # Eskiden kosulsuz dusurulurdu; ayni kopru iki
                # yoldan (443 tuneli + dogrudan 9443) baglandigi
                # icin taraflar birbirini surekli dusuruyor ve
                # `cevrimici` bayragi saniyelik salinim yapiyordu.
                if TEK_OTURUM_KORUMA_SN > 0 and (
                        time.time() - eski.son_nabiz
                ) < TEK_OTURUM_KORUMA_SN:
                    raise IkinciOturumHatasi(o.kurulum_uid)
                with contextlib.suppress(Exception):
                    await eski.soket.close()
                self._kanallar.pop(eski.kanal, None)
            self._uid[o.kurulum_uid] = o
            self._kanallar[o.kanal] = o

    async def cikar(self, o: KopruOturumu) -> None:
        async with self._kilit:
            if self._uid.get(o.kurulum_uid) is o:
                self._uid.pop(o.kurulum_uid, None)
            self._kanallar.pop(o.kanal, None)
        for f in list(o.bekleyen.values()):
            if not f.done():
                f.set_exception(ConnectionError("Köprü bağlantısı kapandı"))
        o.bekleyen.clear()

    # ---- sorgulama ------------------------------------------------------
    def kanal_ile(self, kanal: str) -> KopruOturumu | None:
        return self._kanallar.get(kanal)

    def uid_ile(self, kurulum_uid: str) -> KopruOturumu | None:
        return self._uid.get(kurulum_uid)

    def ornek_ile(self, ornek_id: int) -> KopruOturumu | None:
        for o in self._uid.values():
            if o.ornek_id == ornek_id:
                return o
        return None

    def firma_sunuculari(self, firma_id: int) -> list[dict[str, Any]]:
        """Bağlantı yöneticisi için: firmanın **açık** sunucuları."""
        return [o.ozet() for o in self._uid.values() if o.firma_id == firma_id]

    def tumu(self) -> list[dict[str, Any]]:
        return [o.ozet() for o in self._uid.values()]

    def sayi(self) -> int:
        return len(self._uid)


ROLE = RoleYoneticisi()


# --------------------------------------------------------------------------
# Kurulum kimliği ve sır doğrulama
# --------------------------------------------------------------------------
def gizli_ozetle(gizli: str) -> str:
    return hashlib.sha256(("GOKTUNGU-MERKEZ-2026" + gizli).encode("utf-8")).hexdigest()


def gizli_dogrula(gizli: str, saklanan_ozet: str) -> bool:
    return hmac.compare_digest(gizli_ozetle(gizli), saklanan_ozet or "")


def kurulum_uid_uret() -> str:
    return secrets.token_hex(16)


# --------------------------------------------------------------------------
# v2.4.232 (2026-09-17): KÖPRÜ API KODU
# --------------------------------------------------------------------------
# Köprü kurulumunda tek bir kod girilir; kod kurulum kimliğini (uid),
# sırrı, merkezin WS adresini ve kayıt adını taşır. Biçim
# `GTK1.` + base64url(JSON) — GRCOFF `kopru_kabul.api_kodu_uret` ile aynı.
# Kod sırrı AÇIK taşıdığı için yalnız köprü ilk kez başarıyla bağlanana
# kadar saklanır (`baglanti_acildi` siler); kaybolursa `gizli_yenile`.
API_KOD_ONEK = "GTK1."


def api_kodu_uret(kurulum_uid: str, gizli: str, merkez_adres: str,
                  merkez_http: str = "", ad: str = "",
                  ornek_id: int | None = None, tur: str = "grcon") -> str:
    import base64
    govde: dict[str, Any] = {"u": str(kurulum_uid or ""),
                             "g": str(gizli or ""),
                             "m": str(merkez_adres or ""),
                             "t": str(tur or "grcon")}
    if merkez_http:
        govde["h"] = str(merkez_http)
    if ad:
        govde["a"] = str(ad)
    if ornek_id:
        govde["o"] = int(ornek_id)
    ham = json.dumps(govde, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return API_KOD_ONEK + base64.urlsafe_b64encode(ham).decode(
        "ascii").rstrip("=")


def _kopru_adresleri() -> tuple[str, str]:
    a = ayar_oku()
    ws = str(a.get("kopru_adres") or "wss://goktungu.com/kopru")
    # HTTP tabanı köprü tarafından WS adresinden türetilir (bulutta
    # port düşürülür); ayarda açık bir değer varsa o yollanır.
    return ws, str(a.get("kopru_http") or "")


def gizli_yenile(ornek_id: int) -> tuple[dict | None, str | None]:
    """Sırrı ve API kodunu yeniler; eski sırla bağlanan köprü düşer."""
    o = db.tek("SELECT ornek_id, kurulum_uid, ad FROM sunucu_ornekleri "
               "WHERE ornek_id = %s AND durum <> 'iptal'", (int(ornek_id),))
    if not o:
        return None, "Sunucu bulunamadı"
    gizli = secrets.token_urlsafe(32)
    ws, http = _kopru_adresleri()
    kod = api_kodu_uret(o["kurulum_uid"], gizli, ws, http, o["ad"],
                        int(o["ornek_id"]))
    db.calistir(
        "UPDATE sunucu_ornekleri SET gizli_ozet = %s, api_kodu = %s, "
        "guncel_ts = now() WHERE ornek_id = %s",
        (gizli_ozetle(gizli), kod, int(ornek_id)))
    return {"ornek_id": int(o["ornek_id"]), "ad": o["ad"],
            "api_kodu": kod}, None


def ornek_kaydet(firma_id: int, ad: str, aciklama: str | None = None,
                 platform: str | None = None,
                 makine_adi: str | None = None) -> tuple[dict | None, str | None]:
    """Yeni köprü sunucusu kaydı üretir; `gizli` yalnız bir kez döner."""
    f = db.tek(
        "SELECT maks_sunucu, "
        "(SELECT count(*) FROM sunucu_ornekleri s WHERE s.firma_id = f.firma_id "
        " AND s.durum <> 'iptal') AS mevcut "
        "FROM firmalar f WHERE firma_id = %s",
        (firma_id,),
    )
    if not f:
        return None, "Firma bulunamadı"
    if int(f["mevcut"]) >= int(f["maks_sunucu"]):
        return None, f"Firma sunucu sınırına ulaştı ({f['maks_sunucu']})"

    uid = kurulum_uid_uret()
    gizli = secrets.token_urlsafe(32)
    oid = db.deger(
        "INSERT INTO sunucu_ornekleri (kurulum_uid, firma_id, ad, aciklama, "
        "platform, makine_adi, gizli_ozet) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING ornek_id",
        (uid, firma_id, ad, aciklama, platform, makine_adi, gizli_ozetle(gizli)),
    )
    ws, http = _kopru_adresleri()
    # v2.4.232: API kodu ilk bağlantıya kadar saklanır (bkz. api_kodu_uret).
    kod = api_kodu_uret(uid, gizli, ws, http, ad, int(oid))
    with contextlib.suppress(Exception):
        db.calistir("UPDATE sunucu_ornekleri SET api_kodu = %s "
                    "WHERE ornek_id = %s", (kod, int(oid)))
    return {
        "ornek_id": int(oid),
        "kurulum_uid": uid,
        "gizli": gizli,          # bir daha gösterilmez
        "ad": ad,
        "merkez_adres": ws,
        "api_kodu": kod,
    }, None


# --------------------------------------------------------------------------
# Bağlantı yaşam döngüsü (veritabanı tarafı)
# --------------------------------------------------------------------------
def baglanti_acildi(o: KopruOturumu) -> None:
    db.calistir(
        "UPDATE sunucu_ornekleri SET cevrimici = TRUE, son_gorulme_ts = now(), "
        "son_ip = %s, role_kanal = %s, surum = COALESCE(%s, surum), "
        "platform = COALESCE(%s, platform), makine_adi = COALESCE(%s, makine_adi), "
        # v2.4.232: köprü bağlandı -> sırrı açık taşıyan API kodu silinir.
        "api_kodu = '', "
        "guncel_ts = now() WHERE ornek_id = %s",
        (o.ip, o.kanal, o.surum or None, o.platform or None,
         o.makine_adi or None, o.ornek_id),
    )
    o.oturum_id = db.deger(
        "INSERT INTO sunucu_oturumlari (ornek_id, ip) VALUES (%s, %s) "
        "RETURNING oturum_id",
        (o.ornek_id, o.ip),
    )


def baglanti_kapandi(o: KopruOturumu, neden: str = "") -> None:
    """Kapanan oturumu işaretler.

    KRİTİK: `role_kanal = %s` koşulu ZORUNLUDUR. Köprü yeniden
    bağlandığında `ROLE.ekle()` eski soketi kapatır; yeni oturum
    `baglanti_acildi()` ile `cevrimici = TRUE` yazar. Eski oturumun
    `finally` bloğu ise ANCAK soket kapanışı işlendikten sonra çalışır
    — yani YENİ kayıttan SONRA. Koşul olmadan eski oturum taze
    `cevrimici` işaretini ezer ve kurulum canlı olduğu halde panelde
    KAPALI görünür (v2.4.53'te ölçüldü: oturum 37 açıkken
    `cevrimici = False`, `role_kanal = NULL`).

    `kanal` her oturumda benzersiz üretildiği için bu koşul "yalnız
    kendi oturumumu kapat" anlamına gelir.
    """
    db.calistir(
        "UPDATE sunucu_ornekleri SET cevrimici = FALSE, son_gorulme_ts = now(), "
        "role_kanal = NULL, guncel_ts = now() "
        "WHERE ornek_id = %s AND role_kanal = %s",
        (o.ornek_id, o.kanal),
    )
    if o.oturum_id:
        db.calistir(
            "UPDATE sunucu_oturumlari SET bitis_ts = now(), kapanma_nedeni = %s "
            "WHERE oturum_id = %s",
            (neden[:200], o.oturum_id),
        )


def nabiz_isle(o: KopruOturumu, m: dict) -> None:
    o.son_nabiz = time.time()
    o.dron_sayisi = int(m.get("dron_sayisi") or 0)
    if isinstance(m.get("yetenekler"), dict):
        o.yetenekler = m["yetenekler"]
    db.calistir(
        "UPDATE sunucu_ornekleri SET son_gorulme_ts = now(), dron_sayisi = %s, "
        "yetenekler = %s::jsonb, guncel_ts = now() WHERE ornek_id = %s",
        (o.dron_sayisi, json.dumps(o.yetenekler, ensure_ascii=False), o.ornek_id),
    )


def bayat_temizle(zaman_asimi_sn: int | None = None) -> int:
    """Süreç yeniden başlatıldıysa veritabanında 'çevrimiçi' kalmış
    kayıtlar olur; bunlar temizlenir."""
    if zaman_asimi_sn is None:
        zaman_asimi_sn = int(ayar_oku().get("kopru_zaman_asimi_sn", 90))
    canli = [o["ornek_id"] for o in ROLE.tumu() if o.get("ornek_id")]
    if canli:
        return db.calistir(
            "UPDATE sunucu_ornekleri SET cevrimici = FALSE, role_kanal = NULL "
            "WHERE cevrimici AND NOT (ornek_id = ANY(%s))",
            (canli,),
        )
    return db.calistir(
        "UPDATE sunucu_ornekleri SET cevrimici = FALSE, role_kanal = NULL "
        "WHERE cevrimici"
    )


# --------------------------------------------------------------------------
# Merkez → köprü istek/yanıt
# --------------------------------------------------------------------------
async def kopruden_iste(o: KopruOturumu, eylem: str, veri: dict | None = None,
                        zaman_asimi: float = 15.0) -> dict:
    """Köprüye istek gönderir ve yanıtı bekler.

    Bağlantı köprü tarafından açıldığı için merkez, hiçbir gelen port
    açmadan köprüye komut gönderebilir.
    """
    istek_id = secrets.token_hex(8)
    dongu = asyncio.get_running_loop()
    gelecek: asyncio.Future = dongu.create_future()
    o.bekleyen[istek_id] = gelecek
    paket = {"tur": "istek", "istek_id": istek_id, "eylem": eylem,
             "veri": veri or {}}
    try:
        await o.soket.send(json.dumps(paket, ensure_ascii=False))
        return await asyncio.wait_for(gelecek, timeout=zaman_asimi)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Köprü yanıt vermedi: {eylem}") from None
    finally:
        o.bekleyen.pop(istek_id, None)


def yanit_isle(o: KopruOturumu, m: dict) -> None:
    f = o.bekleyen.get(str(m.get("istek_id") or ""))
    if f is not None and not f.done():
        if m.get("hata"):
            f.set_exception(RuntimeError(str(m["hata"])))
        else:
            f.set_result(m.get("veri") or {})
