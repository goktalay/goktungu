# GÖKTUNGU Derleme Rehberi (GRCOFF paketleri)

GRCOFF Linux `.deb` ve Windows `.exe` paketleri **aynı kaynak revizyonundan** üretilir. Her iki platform da aynı değişiklik setini taşımalıdır.

## Üreticiler

| Dosya | Çıktı |
|---|---|
| `01_GRCOFF/KAYNAK/deb_merkez_uret.py` | `dagitim/goktungu-merkez_<sürüm>_all.deb` |
| `01_GRCOFF/KAYNAK/setup_merkez_uret.py` | `dagitim/GOKTUNGU-Merkez-Setup-<sürüm>.exe` (NSIS) |
| `01_GRCOFF/KAYNAK/paketle_merkez.py` | ortak paket ağacı (`--agac-birak`) |
| `01_GRCOFF/KAYNAK/gomulu_merkez_hazirla.py` | gömülü Windows Python çalışma zamanı (bir kez) |

## Gerekli araçlar

- `python3.11`, `dpkg-deb`, `fakeroot`, `makensis` (NSIS 3.x)
- Windows kurucusu için **gömülü Python çalışma zamanı** kaynakta hazır olmalıdır (`gomulu_merkez/calisma/`). Depoda bu dizin **yoktur** (büyük ikili); `gomulu_merkez_hazirla.py` ile bir kez üretilir.

## Konteyner içinde derleme (önerilen)

Ana makineyi kirletmemek için Debian 12 konteyneri kullanılır (build kutusuyla aynı araç sürümleri):

```bash
cat > Dockerfile <<'EOF'
FROM debian:12
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv dpkg-dev fakeroot nsis nsis-common \
      binutils xz-utils zip p7zip-full ca-certificates file \
    && rm -rf /var/lib/apt/lists/*
RUN ln -sf /usr/bin/python3 /usr/local/bin/python3.11
WORKDIR /src
EOF
docker build -t grcoff-build:deb12 .
```

Kaynağı bir çalışma kopyasına alın (teslim/depo ağacında derleme koşturmayın):

```bash
cp -a 01_GRCOFF/KAYNAK /tmp/grcoff_src
# gömülü Windows Python çalışma zamanı hazır değilse bir kez üretin:
#   (kaynak kökünde) python3.11 gomulu_merkez_hazirla.py
```

**Köprü ikonları zorunlu mount.** Yoksa `.deb` sessizce ikonsuz üretilir:

```bash
KOPRU=$(pwd)/03_BRDIMG/ORTAK_KOPRU_KAYNAGI
docker run --rm -v /tmp/grcoff_src:/src -v "$KOPRU":/root/goktungu_kopru:ro \
  -w /src grcoff-build:deb12 python3.11 deb_merkez_uret.py
docker run --rm -v /tmp/grcoff_src:/src -v "$KOPRU":/root/goktungu_kopru:ro \
  -w /src grcoff-build:deb12 python3.11 setup_merkez_uret.py
# çıktılar: /tmp/grcoff_src/dagitim/
```

## Sürüm kapısı

Sürüm artışında bu **üç yer** birlikte güncellenir; uyuşmazlıkta build durur:

1. `js/surum.js` → `GCS_SURUM` (+ `GCS_SURUM_GECMISI` girişi)
2. `goktungu/paket_surum.py` → `PAKET_SURUM` ve `UYGULAMA_SURUM`
3. `goktungu/__init__.py` → `_SON_BILINEN` (dosya okunamazsa düşülen yedek)

`main.py` ve iki build betiği paket/uygulama sürümünü `paket_surum.py`'den okur; ikinci bir sürüm kaynağı açılmaz.

## Derleme sonrası doğrulama

- `.deb` iç denetimi build betiğinde koşar (24 kontrol): sürüm, bağımlılıklar, systemd birimi, ikonlar, Windows dosyası sızmamış, `__pycache__` yok, maintainer script sözdizimleri.
- Bir önceki sürümle içerik farkını alın (`dpkg-deb -c`); beklenmeyen eksik/yeni dosya olmamalı.
- Her iki dosyanın **SHA-256** değerini kaydedin; yayın aracına bu değerler girilir (kör yayın koruması).

## Notlar

- Kurulum paketleri şu an **Authenticode imzasız**; Windows SmartScreen uyarısı beklenir.
- Kaydırılmış portlar build betiğinde tanımlıdır: `VIDEO_PORT=8811`, `AI_PORT=8910` (Windows'ta NSIS ortam değişkenleri; Linux'ta systemd `Environment`).
