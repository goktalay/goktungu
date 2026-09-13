#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF 2.5.20 pasif takip regresyon testi; fiziksel cihaz/ağ kullanmaz."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

# Kaynak agaci GORELI cozulur. Onceki surumde uretim makinesine ozgu
# mutlak yol sabitti (`/home/ubuntu/faz20/...`) ve teslim arsivinde
# yol bulunamadigi icin test HIC calismiyordu. Sozlesme/assertion'lar
# DEGISMEDI; yalniz kaynak konumu tasinabilir hale getirildi.
KOK = (pathlib.Path(__file__).resolve().parent.parent.parent
       / '01_GRCOFF' / 'KAYNAK')
sys.path.insert(0, str(KOK))

from goktungu.ai_yonetici import AIYonetici, _gorevleri_sinirla  # noqa: E402
from ai_sunucu import IZINLI_SINIFLAR, gorevleri_sinirla  # noqa: E402


def assert_esit(gercek, beklenen, ad):
    if gercek != beklenen:
        raise AssertionError(f'{ad}: {gercek!r} != {beklenen!r}')


def konsol(*_args, **_kwargs):
    return None


def calistir():
    assert_esit(set(_gorevleri_sinirla('insan,yuz,kara_araci,plaka,hava_araci')),
                {'insan', 'kara_araci', 'hava_araci'}, 'yönetici görev filtresi')
    assert_esit(gorevleri_sinirla(['yuz', 'plaka']), set(), 'işçi reddedilen görevler')
    assert_esit(gorevleri_sinirla(None), set(IZINLI_SINIFLAR), 'işçi varsayılan görevler')

    with tempfile.TemporaryDirectory(prefix='grcoff-track-test-') as td:
        yol = os.path.join(td, 'track_verisi.ndjson')
        yonetici = AIYonetici(konsol, {})
        yonetici._track_yol = yol
        yonetici._kamera_dron_uid = lambda kamera_id: 'drn-test-01' if kamera_id == 7 else None
        yonetici.takipler[7] = {'tur': 'insan', 'track_id': 'k7-test'}

        olay_sonuc = yonetici.takip_isle({
            'kamera_id': 7, 'tur': 'insan', 'ts': 1726100000.25,
            'kutu': [10, 20, 30, 40], 'merkez': [25.0, 40.0],
            'kare_boyutu': [1280, 720], 'guven': 0.87, 'kayip': False,
        })
        if not olay_sonuc.get('tamam'):
            raise AssertionError(f'aktif olay yazılamadı: {olay_sonuc!r}')
        with open(yol, 'r', encoding='utf-8') as dosya:
            olay = json.loads(dosya.readline())
        assert_esit(olay['sinif'], 'insan', 'olay sınıfı')
        assert_esit(olay['dron_uid'], 'drn-test-01', 'olay dron UID')
        assert_esit(olay['kare_boyutu'], [1280, 720], 'olay kare boyutu')
        assert_esit(olay['durum'], 'aktif', 'olay durumu')
        if any(k in olay for k in ('komut', 'joystick', 'mavlink', 'angajman')):
            raise AssertionError('olay sözleşmesinde yasak komut alanı bulundu')
        if os.stat(yol).st_mode & 0o077:
            raise AssertionError('NDJSON dosya izni yerel-kısıtlı değil')

        dinleyici = subprocess.run(
            [sys.executable, str(KOK / 'track_verisi_dinleyici.py'),
             '--dosya', yol, '--gecmis', '--adet', '1'],
            check=True, text=True, capture_output=True, timeout=5)
        assert_esit(json.loads(dinleyici.stdout.strip())['track_id'], 'k7-test',
                    'dinleyici çıktısı')

        yonetici.takipler[8] = {'tur': 'insan', 'track_id': 'k8-test'}
        red = yonetici.takip_isle({'kamera_id': 8, 'tur': 'yuz', 'kutu': [1, 2, 3, 4]})
        if red.get('tamam'):
            raise AssertionError('yasak sınıf takip olayı kabul edildi')

    dinleyici_kaynak = (KOK / 'track_verisi_dinleyici.py').read_text(encoding='utf-8').lower()
    dinleyici_importlari = '\n'.join(
        satir.strip() for satir in dinleyici_kaynak.splitlines()
        if satir.lstrip().startswith(('import ', 'from ')))
    for yasak in ('socket', 'requests', 'urllib', 'joystick', 'pymavlink', 'manual_control', 'mavlink'):
        if yasak in dinleyici_importlari:
            raise AssertionError(f'dinleyicide yasak bağımlılık bulundu: {yasak}')
    yonetici_kaynak = (KOK / 'goktungu' / 'ai_yonetici.py').read_text(encoding='utf-8').lower()
    parca = yonetici_kaynak[yonetici_kaynak.index('def _track_dosyaya_yaz'):yonetici_kaynak.index('def son_takip_konum')]
    for yasak in ('joystick', 'pymavlink', 'manual_control', 'mavlink', 'gonder_komut'):
        if yasak in parca:
            raise AssertionError(f'takip dışa aktarımında yasak yol bulundu: {yasak}')
    print('PASIF_TAKIP_REGRESYON: 16/16 geçti')


if __name__ == '__main__':
    calistir()
