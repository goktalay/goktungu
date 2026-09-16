# -*- coding: utf-8 -*-
"""v2.4.53 merkez sunucu arayuzu i18n anahtarlarini ekler.

TR ve EN bloklarina AYNI anahtar kumesini ekler; denge bozulmaz.
Var olan anahtar tekrar eklenmez (yeniden calistirilabilir).
"""
import io
import re
import sys

YOL = "js/i18n.js"

TR = {
    "bagYeniMerkez": "Merkezden Sunucu Seç",
    "bagDuzenleMerkez": "Merkez Bağlantısını Düzenle",
    "lblBagMerkezSunucu": "Açık sunucular",
    "bagMerkezAciklama": (
        "Merkez sunucuya kayıtlı ve o an açık olan saha sunucuları "
        "listelenir. Sunucular merkeze kendileri bağlanır; sabit IP "
        "gerekmez. Liste boşsa ilgili saha sunucusu kapalıdır."
    ),
    "merkezSunucuYukleniyor": "Sunucular alınıyor…",
    "merkezSunucuHata": "Sunucu listesi alınamadı",
    "merkezSunucuYok": "Açık sunucu yok",
    "merkezSunucuBosAciklama": (
        "Merkeze kayıtlı hiçbir saha sunucusu şu an açık değil. "
        "Saha sunucusunu açıp listeyi yenileyin."
    ),
    "merkezSunucuAdet": "sunucu",
    "merkezSunucuSecUyari": "Listeden bir sunucu seçin.",
    "merkezSunucuBaglantiYok": "Merkez hesabı tanımlı değil",
    "merkezSunucuBilinmiyor": "Bilinmeyen sunucu",
    "merkezKayitliSunucu": "Kayıtlı sunucu",
    "merkezNabizSimdi": "şimdi",
    "merkezNabizSn": "sn önce",
    "merkezNabizDk": "dk önce",
    "merkezDron": "dron",
    "merkezDogrulaTamam": "Merkez bağlantısı doğrulandı",
    "merkezDogrulaHata": "Merkez bağlantısı doğrulanamadı",
    "progAyarMerkez": "MERKEZ SUNUCU",
    "progAyarMerkezAcik": "Merkez sunucu bağlantısı",
    "progAyarMerkezKapali": "Kapalı",
    "progAyarMerkezAdres": "Merkez adresi",
    "progAyarMerkezEposta": "Merkez e-postası",
    "progAyarMerkezSifre": "Merkez şifresi",
    "progAyarMerkezSifrePlaceholder": "Değiştirmek için yazın",
    "progAyarMerkezSifreVar": "Kayıtlı şifre var; boş bırakırsanız korunur.",
    "progAyarMerkezSina": "Bağlantıyı sına",
    "progAyarMerkezSiniyor": "Sınanıyor…",
    "progAyarMerkezDogrula": "Doğrula",
    "progAyarMerkezAciklama": (
        "Merkez sunucu açıkken bağlantı yöneticisinde MERKEZ düğmesi "
        "görünür ve firmanıza ait açık saha sunucuları listelenir. "
        "Kimlik bilgileri yalnızca bu bilgisayarda saklanır."
    ),
}

EN = {
    "bagYeniMerkez": "Select Server from Centre",
    "bagDuzenleMerkez": "Edit Centre Connection",
    "lblBagMerkezSunucu": "Online servers",
    "bagMerkezAciklama": (
        "Lists field servers registered with the central server that are "
        "currently online. Servers connect to the centre themselves; no "
        "static IP is required. An empty list means the field server is off."
    ),
    "merkezSunucuYukleniyor": "Fetching servers…",
    "merkezSunucuHata": "Server list could not be fetched",
    "merkezSunucuYok": "No online server",
    "merkezSunucuBosAciklama": (
        "No field server registered with the centre is currently online. "
        "Start the field server and refresh the list."
    ),
    "merkezSunucuAdet": "server(s)",
    "merkezSunucuSecUyari": "Select a server from the list.",
    "merkezSunucuBaglantiYok": "Centre account is not configured",
    "merkezSunucuBilinmiyor": "Unknown server",
    "merkezKayitliSunucu": "Saved server",
    "merkezNabizSimdi": "now",
    "merkezNabizSn": "s ago",
    "merkezNabizDk": "min ago",
    "merkezDron": "drone(s)",
    "merkezDogrulaTamam": "Centre connection verified",
    "merkezDogrulaHata": "Centre connection could not be verified",
    "progAyarMerkez": "CENTRAL SERVER",
    "progAyarMerkezAcik": "Central server connection",
    "progAyarMerkezKapali": "Off",
    "progAyarMerkezAdres": "Centre address",
    "progAyarMerkezEposta": "Centre e-mail",
    "progAyarMerkezSifre": "Centre password",
    "progAyarMerkezSifrePlaceholder": "Type to change",
    "progAyarMerkezSifreVar": "A password is stored; leave blank to keep it.",
    "progAyarMerkezSina": "Test connection",
    "progAyarMerkezSiniyor": "Testing…",
    "progAyarMerkezDogrula": "Verify",
    "progAyarMerkezAciklama": (
        "When the central server is enabled, the CENTRE button appears in "
        "the connection manager and lists your company's online field "
        "servers. Credentials are stored only on this computer."
    ),
}


def kacis(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def var_mi(metin, anahtar):
    return re.search(r'^\s*(?:"%s"|%s)\s*:' % (anahtar, anahtar),
                     metin, re.M) is not None


def main():
    metin = io.open(YOL, encoding="utf-8").read()
    if set(TR) != set(EN):
        raise SystemExit("TR ve EN anahtar kumeleri farkli — denge bozulur")

    satirlar = metin.splitlines()
    tr_son = en_son = None
    for i, l in enumerate(satirlar):
        if re.match(r'^\s{2}EN:\s*\{', l):
            tr_son = i - 1          # TR blogunu kapatan "  },"
        elif re.match(r'^\};', l):
            en_son = i - 1          # EN blogunu kapatan "  },"
    if tr_son is None or en_son is None:
        raise SystemExit("i18n.js yapisi taninamadi")

    eklenecek = [a for a in TR if not var_mi(metin, a)]
    if not eklenecek:
        print("Tum merkez anahtarlari zaten var; degisiklik yok.")
        return 0
    eklenecek.sort()

    def blok(sozluk):
        satir = ['    "%s": "%s",' % (a, kacis(sozluk[a])) for a in eklenecek]
        return ["    // --- v2.4.53 merkez sunucu ---"] + satir

    # Sondan basa ekle ki satir indeksleri kaymasin
    yeni = list(satirlar)
    yeni[en_son:en_son] = blok(EN)
    yeni[tr_son:tr_son] = blok(TR)

    io.open(YOL, "w", encoding="utf-8").write("\n".join(yeni) + "\n")
    print("Eklenen anahtar sayisi (her dile): %d" % len(eklenecek))
    for a in eklenecek:
        print("  +", a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
