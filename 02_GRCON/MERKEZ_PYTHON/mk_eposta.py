# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — e-posta gönderme ve adres doğrulama katmanı.

İki iş yapar:
  1. SMTP üzerinden e-posta gönderir (`gonder`).
  2. Doğrulama kodlarını üretir, doğrular ve tüketir.

ŞEMA SÖZLEŞMESİ (ölçüldü — `\d eposta_dogrulama`)
-------------------------------------------------
dogrulama_id, hedef_tur, hedef_id, eposta, kod_ozet, deneme,
gonderim, gecerli_ts, kullanildi_ts, olusma_ts

Kolon adları bellekten TAHMİN EDİLMEMELİ: `kod_ozet` (jeton_ozet değil),
`gecerli_ts` (bitis_ts değil), `kullanildi_ts` (kullanim_ts değil).
`sistem_yoneticileri` birincil anahtarı `yonetici_id`, ad alanı
`ad_soyad` (`ad` değil).

TASARIM KARARLARI
-----------------
* **Kod veritabanında YALNIZ SHA-256 özeti olarak saklanır.**
  Doğrulama bağı gelen kutusunda, sunucu günlüklerinde ve tarayıcı
  geçmişinde kalır. Veritabanı sızsa düz kodlar doğrudan hesap
  doğrulamak için kullanılabilirdi; özet sızarsa işe yaramaz.

* **`deneme` sayacı kaba kuvvete karşı.** Şemadaki bu kolon kullanılmasa
  saldırgan aynı hedefe sınırsız kod denemesi yapabilirdi. `MAKS_DENEME`
  aşılınca kayıt tüketilir.

* **`gonderim` sayacı** yeniden gönderim sayısını izler; kötüye kullanım
  ve SMTP kotası tüketimi görünür olur.

* **Doğrulama başarısız olduğunda hesap SİLİNMEZ.** Silinirse e-posta
  adresi bloke kalır ve kullanıcı hiç kayıt olamaz.

* **SMTP hatası kaydı geri almaz.** Kayıt ile gönderim ayrı başarısızlık
  alanlarıdır; SMTP geçici çökebilir. `gonder` istisna fırlatmaz,
  `(tamam, hata)` döner ve kullanıcı "yeniden gönder" ile ilerler.

* **Kod tek kullanımlıktır** (`kullanildi_ts`). E-posta iletilse bile
  aynı bağ ikinci kez çalışmaz.

* SMTP parolası `merkez_ayar.json` içinde tutulur, API yanıtlarında
  **asla** yayılmaz (`smtp_gorunum` maskeler). Gmail için hesap şifresi
  DEĞİL 16 haneli uygulama şifresi gerekir; Google 2022'den beri düz
  hesap şifresiyle SMTP erişimini kapatmıştır.
"""
from __future__ import annotations

import hashlib
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate

import mk_ayar as ayar
import mk_db as db

# --------------------------------------------------------------------------
# Sabitler
# --------------------------------------------------------------------------

# Doğrulama bağının ömrü. 48 saat: kullanıcı e-postayı ertesi gün
# görebilir; daha kısası gereksiz yeniden gönderim üretir.
KOD_OMUR_SN = 48 * 3600

# Aynı hedefe yeniden gönderim için beklenecek en az süre.
YENIDEN_GONDER_SN = 120

# Bir kayıt için en fazla başarısız deneme. Aşılınca kayıt tüketilir.
MAKS_DENEME = 8

# SMTP zaman aşımı. Uzun bekleme kayıt isteğini kilitler.
SMTP_ZAMAN_ASIMI_SN = 20

VARSAYILAN_SMTP = {
    "host": "smtp.gmail.com",
    "port": 465,            # 465 = örtük SSL (SMTPS); 587 = STARTTLS
    "kullanici": "admin@goktungu.com",
    "parola": "",           # Gmail UYGULAMA ŞİFRESİ (16 hane)
    "gonderen_ad": "GÖKTUNGU",
    "gonderen_adres": "admin@goktungu.com",
    "etkin": False,         # parola girilene kadar kapalı
}


def smtp_ayar() -> dict:
    """SMTP ayarlarını varsayılanlarla birleştirip döner."""
    a = ayar.ayar_oku()
    s = dict(VARSAYILAN_SMTP)
    mevcut = a.get("smtp")
    if isinstance(mevcut, dict):
        s.update(mevcut)
    return s


def smtp_gorunum() -> dict:
    """Arayüze gönderilebilir SMTP görünümü — parola MASKELİ.

    Parola alanı yerine yalnız `parola_var` bayrağı döner. Aksi halde
    16 haneli uygulama şifresi API yanıtıyla tarayıcıya sızardı.
    """
    s = smtp_ayar()
    return {
        "host": s.get("host") or "",
        "port": int(s.get("port") or 465),
        "kullanici": s.get("kullanici") or "",
        "gonderen_ad": s.get("gonderen_ad") or "",
        "gonderen_adres": s.get("gonderen_adres") or "",
        "etkin": bool(s.get("etkin")),
        "parola_var": bool(s.get("parola")),
    }


def smtp_kaydet(veri: dict) -> None:
    """SMTP ayarlarını günceller. Boş parola MEVCUDU SİLMEZ.

    NEDEN: arayüz parolayı maskeli gösterir; kullanıcı başka bir alanı
    düzenleyip kaydettiğinde parola alanı boş gelir. Boş değeri yazmak
    çalışan yapılandırmayı sessizce bozardı.
    """
    a = ayar.ayar_oku()
    s = dict(smtp_ayar())
    for k in ("host", "kullanici", "gonderen_ad", "gonderen_adres"):
        if k in veri and veri[k] is not None:
            s[k] = str(veri[k]).strip()
    if veri.get("port"):
        s["port"] = int(veri["port"])
    if veri.get("parola"):
        s["parola"] = str(veri["parola"]).strip()
    if "etkin" in veri:
        s["etkin"] = bool(veri["etkin"])
    a["smtp"] = s
    ayar.ayar_yaz(a)


def _alan_adi() -> str:
    return (ayar.ayar_oku().get("alan_adi") or "goktungu.com").strip()


# --------------------------------------------------------------------------
# Gönderme
# --------------------------------------------------------------------------

def gonder(alici: str, konu: str, metin: str,
           html: str | None = None) -> tuple[bool, str | None]:
    """E-posta gönderir. İstisna FIRLATMAZ; `(tamam, hata)` döner."""
    s = smtp_ayar()
    if not s.get("etkin"):
        return False, ("E-posta gonderimi yapilandirilmamis "
                       "(yonetim panelinden SMTP ayarlarini girin)")
    if not s.get("parola"):
        return False, "SMTP parolasi tanimli degil"

    ileti = EmailMessage()
    ileti["Subject"] = konu
    ileti["From"] = formataddr((s.get("gonderen_ad") or "GÖKTUNGU",
                                s.get("gonderen_adres") or s["kullanici"]))
    ileti["To"] = alici
    ileti["Date"] = formatdate(localtime=True)
    ileti.set_content(metin)
    if html:
        ileti.add_alternative(html, subtype="html")

    baglam = ssl.create_default_context()
    try:
        port = int(s.get("port") or 465)
        if port == 465:
            with smtplib.SMTP_SSL(s["host"], port, context=baglam,
                                  timeout=SMTP_ZAMAN_ASIMI_SN) as sm:
                sm.login(s["kullanici"], s["parola"])
                sm.send_message(ileti)
        else:
            # STARTTLS: düz başlar, şifreye yükseltilir. `starttls`
            # başarısız olursa gönderim YAPILMAZ; aksi halde kimlik
            # bilgileri düz metin giderdi.
            with smtplib.SMTP(s["host"], port,
                              timeout=SMTP_ZAMAN_ASIMI_SN) as sm:
                sm.ehlo()
                sm.starttls(context=baglam)
                sm.ehlo()
                sm.login(s["kullanici"], s["parola"])
                sm.send_message(ileti)
        return True, None
    except smtplib.SMTPAuthenticationError:
        # Gmail'de en sık neden: hesap şifresi kullanılmış.
        return False, ("SMTP kimlik dogrulamasi basarisiz. Gmail icin "
                       "hesap sifresi DEGIL, 16 haneli uygulama sifresi "
                       "(App Password) gerekir.")
    except Exception as e:
        return False, f"E-posta gonderilemedi: {type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# Kod üretimi ve doğrulama
# --------------------------------------------------------------------------

def _ozet(kod: str) -> str:
    return hashlib.sha256(kod.encode("utf-8")).hexdigest()


def _ts(v) -> float:
    """timestamptz veya sayısal değeri epoch saniyeye çevirir."""
    if v is None:
        return 0.0
    try:
        return v.timestamp()
    except AttributeError:
        return float(v)


def kod_uret(hedef_tur: str, hedef_id: int,
             eposta: str) -> tuple[str | None, str | None]:
    """Doğrulama kodu üretir, özetini saklar. Döner: (duz_kod, hata).

    Düz kod YALNIZ burada görülür; veritabanına özeti yazılır.
    """
    if hedef_tur not in ("kullanici", "yonetici"):
        return None, "Gecersiz hedef turu"

    # Hız sınırı: son kayıt çok yeniyse reddet.
    son = db.tek(
        "SELECT olusma_ts, gonderim FROM eposta_dogrulama "
        "WHERE hedef_tur = %s AND hedef_id = %s "
        "ORDER BY olusma_ts DESC LIMIT 1",
        (hedef_tur, int(hedef_id)))
    gonderim = 1
    if son:
        gecen = time.time() - _ts(son.get("olusma_ts"))
        if gecen < YENIDEN_GONDER_SN:
            kalan = int(YENIDEN_GONDER_SN - gecen)
            return None, f"Cok sik istek. {kalan} saniye sonra tekrar deneyin."
        gonderim = int(son.get("gonderim") or 0) + 1

    # Kullanılmamış eski kodlar iptal edilir: aynı hesap için birden
    # fazla geçerli bağ bırakmak saldırı yüzeyini genişletir.
    db.calistir(
        "UPDATE eposta_dogrulama SET kullanildi_ts = now() "
        "WHERE hedef_tur = %s AND hedef_id = %s AND kullanildi_ts IS NULL",
        (hedef_tur, int(hedef_id)))

    duz = secrets.token_urlsafe(32)
    db.calistir(
        "INSERT INTO eposta_dogrulama "
        "(hedef_tur, hedef_id, eposta, kod_ozet, gonderim, gecerli_ts) "
        "VALUES (%s, %s, %s, %s, %s, now() + make_interval(secs => %s))",
        (hedef_tur, int(hedef_id), eposta.strip().lower(),
         _ozet(duz), gonderim, KOD_OMUR_SN))
    return duz, None


def kod_dogrula(duz: str) -> tuple[dict | None, str | None]:
    """Kodu doğrular ve TÜKETİR. Döner: (kayit, hata)."""
    if not duz or len(duz) < 20:
        return None, "Gecersiz dogrulama bagi"

    k = db.tek(
        "SELECT dogrulama_id, hedef_tur, hedef_id, eposta, "
        "       deneme, kullanildi_ts, gecerli_ts "
        "FROM eposta_dogrulama WHERE kod_ozet = %s",
        (_ozet(duz),))
    if not k:
        # Özet bulunamadı: hangi hedefe ait olduğu bilinemez, bu yüzden
        # deneme sayacı artırılamaz. Kayıt bulunamaması zaten kaba
        # kuvvetin 2^256 alanda başarısız olduğunu gösterir.
        return None, "Dogrulama bagi gecersiz"

    if k.get("kullanildi_ts"):
        return None, "Bu dogrulama bagi zaten kullanilmis"

    if int(k.get("deneme") or 0) >= MAKS_DENEME:
        db.calistir("UPDATE eposta_dogrulama SET kullanildi_ts = now() "
                    "WHERE dogrulama_id = %s", (k["dogrulama_id"],))
        return None, ("Cok fazla basarisiz deneme. Yeni dogrulama bagi "
                      "isteyin.")

    if _ts(k.get("gecerli_ts")) < time.time():
        return None, "Dogrulama bagi suresi gecmis. Yeniden gonderin."

    # Tüketim: aynı bağ ikinci kez çalıştırılamaz.
    db.calistir(
        "UPDATE eposta_dogrulama SET kullanildi_ts = now() "
        "WHERE dogrulama_id = %s", (k["dogrulama_id"],))

    # Hedef kaydı işaretle.
    if k["hedef_tur"] == "kullanici":
        db.calistir(
            "UPDATE kullanicilar SET eposta_dogrulama_ts = now() "
            "WHERE kullanici_id = %s", (k["hedef_id"],))
    else:
        db.calistir(
            "UPDATE sistem_yoneticileri SET eposta_dogrulama_ts = now() "
            "WHERE yonetici_id = %s", (k["hedef_id"],))
    return dict(k), None


def deneme_artir(hedef_tur: str, hedef_id: int) -> None:
    """Başarısız denemeyi sayar. Etkin kayıt üzerinde çalışır."""
    db.calistir(
        "UPDATE eposta_dogrulama SET deneme = deneme + 1 "
        "WHERE hedef_tur = %s AND hedef_id = %s AND kullanildi_ts IS NULL",
        (hedef_tur, int(hedef_id)))


def dogrulandi_mi(hedef_tur: str, hedef_id: int) -> bool:
    if hedef_tur == "kullanici":
        k = db.tek("SELECT eposta_dogrulama_ts FROM kullanicilar "
                   "WHERE kullanici_id = %s", (int(hedef_id),))
    else:
        k = db.tek("SELECT eposta_dogrulama_ts FROM sistem_yoneticileri "
                   "WHERE yonetici_id = %s", (int(hedef_id),))
    return bool(k and k.get("eposta_dogrulama_ts"))


# --------------------------------------------------------------------------
# Doğrulama e-postası
# --------------------------------------------------------------------------

def dogrulama_gonder(hedef_tur: str, hedef_id: int,
                     eposta: str, ad: str = "") -> tuple[bool, str | None]:
    """Kod üretir ve doğrulama e-postasını gönderir."""
    duz, hata = kod_uret(hedef_tur, hedef_id, eposta)
    if hata or not duz:
        return False, hata or "Kod uretilemedi"

    bag = f"https://{_alan_adi()}/dogrula?k={duz}"
    saat = KOD_OMUR_SN // 3600
    selam = f"Sayin {ad}," if ad else "Merhaba,"

    metin = (
        f"{selam}\n\n"
        "GOKTUNGU hesabinizi etkinlestirmek icin asagidaki bagi "
        "tarayicinizda acin:\n\n"
        f"{bag}\n\n"
        f"Bag {saat} saat gecerlidir ve yalniz bir kez kullanilabilir.\n\n"
        "Bu kaydi siz yapmadiysaniz bu iletiyi yok sayabilirsiniz; "
        "dogrulama yapilmadan hesap kullanilamaz.\n\n"
        "Turkbey Teknoloji Anonim Sirketi\n"
        "Ahi Evren OSB Mah. Buyuk Selcuklu Cad. No:2/B Sincan/Ankara\n"
    )

    html = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#04070c;
             font-family:'IBM Plex Sans',Arial,sans-serif;color:#c8d4e3">
  <div style="max-width:560px;margin:0 auto;background:#0a1018;
              border:1px solid #16222f;border-radius:10px;padding:28px">
    <div style="font-family:'Chakra Petch',Arial,sans-serif;font-size:22px;
                font-weight:700;color:#5cc8ff;letter-spacing:.5px">GÖKTUNGU</div>
    <div style="height:1px;background:#16222f;margin:18px 0"></div>
    <p style="margin:0 0 14px">{selam}</p>
    <p style="margin:0 0 20px;line-height:1.6">
      GÖKTUNGU hesabınızı etkinleştirmek için aşağıdaki düğmeye basın.
    </p>
    <p style="margin:0 0 20px">
      <a href="{bag}" style="display:inline-block;background:#5cc8ff;
         color:#04070c;text-decoration:none;font-weight:700;
         padding:12px 24px;border-radius:6px">Hesabımı Doğrula</a>
    </p>
    <p style="margin:0 0 8px;font-size:13px;color:#7b8ea6">
      Düğme çalışmazsa bu bağı tarayıcınıza kopyalayın:
    </p>
    <p style="margin:0 0 20px;font-size:12px;font-family:monospace;
              color:#5cc8ff;word-break:break-all">{bag}</p>
    <p style="margin:0 0 6px;font-size:13px;color:#7b8ea6">
      Bağ {saat} saat geçerlidir ve yalnız bir kez kullanılabilir.
    </p>
    <p style="margin:0;font-size:13px;color:#7b8ea6">
      Bu kaydı siz yapmadıysanız iletiyi yok sayabilirsiniz.
    </p>
    <div style="height:1px;background:#16222f;margin:22px 0"></div>
    <p style="margin:0;font-size:12px;color:#5a6b80;line-height:1.5">
      Türkbey Teknoloji Anonim Şirketi<br>
      Ahi Evren OSB Mah. Büyük Selçuklu Cad. No:2/B Sincan/Ankara
    </p>
  </div>
</body></html>"""

    return gonder(eposta, "GÖKTUNGU — hesap doğrulama", metin, html)


def sinav_gonder(alici: str) -> tuple[bool, str | None]:
    """Yapılandırmayı sınamak için deneme iletisi gönderir."""
    return gonder(
        alici, "GÖKTUNGU — SMTP sınama iletisi",
        "Bu ileti GOKTUNGU SMTP yapilandirmasini sinamak icin "
        "gonderilmistir. Bu iletiyi aldiysaniz yapilandirma dogrudur.\n")


def temizle() -> int:
    """Süresi geçmiş ve kullanılmış kayıtları siler. Bakım işi."""
    return db.calistir(
        "DELETE FROM eposta_dogrulama "
        "WHERE gecerli_ts < now() - interval '7 days' "
        "   OR (kullanildi_ts IS NOT NULL "
        "       AND kullanildi_ts < now() - interval '7 days')")
