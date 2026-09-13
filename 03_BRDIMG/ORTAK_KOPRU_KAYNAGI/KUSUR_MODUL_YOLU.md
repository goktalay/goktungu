# Kusur — alt servis `kopru` paketini bulamıyor (v1.4.1 sahada)

## Sahadaki iz

```
C:\Program Files\Goktungu\Kopru\python\python.exe: Error while finding module
specification for 'kopru.servis_dron' (ModuleNotFoundError: No module named 'kopru')
Servis sonlandi (cikis kodu 1)
```

Yorumlayıcı artık DOĞRU (`python\python.exe`) — v1.4.1 düzeltmesi tuttu.
Yeni kusur bir sonraki katmanda.

## Kök neden — ÖLÇÜLDÜ (Wine, gerçek gömülü dağıtım)

`servisler.py` alt sürece paket kökünü **`PYTHONPATH`** ile veriyor
(satır 359) ve `cwd=kok` ayarlıyor (satır 387).

**Gömülü (embeddable) Python dağıtımı `PYTHONPATH`'i YOK SAYAR.**
Dizinde `python311._pth` dosyası bulunduğunda CPython "isolated"
benzeri kipe geçer: `sys.path` yalnızca `._pth` içeriğinden kurulur,
`PYTHONPATH` ve mevcut çalışma dizini eklenmez.

Ölçüm (`/tmp/svc_sinav`, gerçek gömülü python 3.11 + Wine):

```
$ PYTHONPATH=Z:\tmp\pp_sinav wine python/python.exe -c "import paketX"
ModuleNotFoundError: No module named 'paketX'
sys.path:
   ...\python311.zip
   ...\python
   ...\python\Lib\site-packages
   ...\python\Lib\site-packages\win32
   ...\python\Lib\site-packages\win32\lib
   ...\python\Lib\site-packages\Pythonwin
```

PYTHONPATH'te verilen dizin `sys.path`'e **hiç girmiyor**. `._pth`
içeriği:

```
python311.zip
.
# Uncomment to run site.main() automatically
Lib\site-packages
import site
```

`.` girdisi **python.exe'nin dizinini** (yani `...\Kopru\python`)
gösterir, `cwd`'yi değil. `kopru` paketi ise bir üst dizinde
(`...\Kopru\kopru`). Bu yüzden bulunamıyor.

Aynı kusur konsol kipinde görünmezdi: geliştirici makinesinde sistem
Python'u kullanılır, `._pth` yoktur, `PYTHONPATH` normal çalışır.
Kusur yalnızca **gömülü Python + setup kurulumu** birleşiminde çıkar.

## Sabit

- `._pth` dosyası varsa: `PYTHONPATH` yok sayılır, `cwd` eklenmez
- Bu davranış tasarım gereğidir (embeddable dağıtımın amacı yalıtım)
- Dolayısıyla ortam değişkeni ile paket kökü **verilemez**

## Çözüm — ÖLÇÜLDÜ (Wine, gerçek gömülü dağıtım)

`._pth` dosyasına `..` (üst dizin = kurulum kökü) satırı eklendiğinde:

```
python311.zip
.
..
Lib\site-packages
import site
```

Sonuç:

```
$ wine python/python.exe -c "import kopru; print(kopru.__file__)"
OK ice alindi: Z:\tmp\svc_sinav\kopru\__init__.py
```

`..` göreli yolu, `._pth` dosyasının bulunduğu dizine (yani
`...\Kopru\python`) göre çözülür → `...\Kopru` = kurulum kökü.
Kurulum dizini nereye taşınırsa taşınsın doğru çalışır.

### Uygulanacak katmanlar (tek noktaya güvenmemek için)

1. **`gomulu_hazirla.py`** — dağıtım hazırlanırken `._pth` dosyasına
   `..` eklenir. Asıl düzeltme burada; setup'a giren gömülü Python
   zaten doğru yapılandırılmış gelir.
2. **`servisler.py`** — alt süreç komutuna `sys.path` ekleme kalkanı.
   `PYTHONPATH` gömülü Python'da işlemediği için modül adı (`-m`)
   yerine doğrudan dosya yolu + kök ekleyen kısa sarmalayıcı kullanmak
   ikinci savunmadır.
3. **`setup.nsi`** — kurulum sonrası `._pth` doğrulaması (dosya
   beklenen satırı içermiyorsa kurulum uyarır).

### Neden `PYTHONPATH` düzeltmesi yeterli değil

`servisler.py` satır 359'daki `PYTHONPATH` ataması gömülü Python'da
hiçbir etki yapmıyor ama Linux'ta (sistem Python'u) çalışıyor.
Kaldırmak Linux'u bozar; korumak Windows'u düzeltmez. Bu yüzden
`._pth` düzeltmesi asıl çözüm, sarmalayıcı ise platformdan bağımsız
kalkan.
