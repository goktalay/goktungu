# BRDTLM — Faz 5 Notlari

BRDTLM (telemetri/cihaz koprusu), BRDIMG (goruntu koprusu) ile AYNI
cekirdegi paylasir: `../03_BRDIMG/ORTAK_KOPRU_KAYNAGI` (bkz.
`KAYNAK_KONUMU.txt`). Ayri bir kaynak agaci tutulmaz; ayrim yalnizca
**urun profili** ile yapilir.

## Urun profili

- Kaynak: `GOKTUNGU_KOPRU_URUN` ortam degiskeni; o yoksa kurulum
  kokundeki `URUN` dosyasi.
- Profil eslemesi (`kopru/servisler.py`):
  - `brdimg` -> `video`, `ai`
  - `brdtlm` -> `dron`, `m50`, `radar`, `gcsdual`
- **Geriye uyumluluk:** degisken/dosya AYARSIZ iken profil YOKTUR
  (`aktif_urun()` -> `None`), tum servisler gorunur ve davranis mevcut
  BRDIMG kurulumlariyla BYTE-AYNI kalir.

## Paketleme

Ince sarmalayici: `paketle_brdtlm.py`

- `python3.11 paketle_brdtlm.py --deb` -> `deb_uret.py --urun brdtlm`
  (paket `goktungu-kopru-tlm`, servis `goktungu-kopru-tlm.service`,
  panel portu 8791, systemd `Environment=GOKTUNGU_KOPRU_URUN=brdtlm`,
  ikon `goktungu-kopru-tlm.png`, kurulum `/opt/goktungu/kopru-tlm`).
- `python3.11 paketle_brdtlm.py --win` -> `makensis` uygun `-D`
  tanimlariyla (servis `GoktunguKopruTlm`, kurulum `...\Goktungu\KopruTlm`,
  `$INSTDIR\URUN=brdtlm`).

`--urun` verilmeyen `deb_uret.py` ve `-D` verilmeden derlenen
`setup.nsi`, BRDIMG ciktisini BYTE-AYNI uretir.

## Dron protokolleri

`kopru/servis_dron.py` bir protokol soyutlamasi tasir:

- **MAVLink / ArduPilot** — mevcut yol, KORUNDU.
- **Betaflight / MSP v1** — Faz 5'te EKLENDI, **SALT-OKUNUR**
  (`kopru/betaflight_msp.py`, `kopru/protokol_algilama.py`; GRCOFF
  surucusunun birebir esidi). Yazma komutu (ARM/motor/RC/SET/reboot/CLI)
  ne tanimli ne uretilebilir.
- Oto-algilama: `protokol_algila()` once CRC'li MAVLink HEARTBEAT dinler,
  yoksa yalniz salt-okunur `MSP_API_VERSION` sorgusuyla Betaflight'i ayirt
  eder.

### ATLANDI — DJI Onboard SDK / DJI Windows SDK

Masaustu DJI uygulama anahtarlari HENUZ YOK ve bu SDK'lar native baglama
gerektiriyor. DJI yolu bilerek eklenmedi; **anahtar + SDK bekliyor**.
Saglaninca protokol soyutlamasina `dji_onboard` / `dji_windows` olarak
eklenecek.

## Sinavlar

- `../12_TESTLER/BRDTLM/sinav_urun_profil.py` (profil + geriye uyumluluk)
- `../12_TESTLER/BRDTLM/sinav_betaflight_msp.py` (MSP + algilama, salt-okunur)
