#!/usr/bin/env bash
# GÖKTUNGU Merkez — NVIDIA Jetson (JetPack 6.x) için GPU hızlandırmalı AI kurulumu
# v2.4.218. Kullanım:  sudo bash /opt/goktungu/merkez/jetson_ai_kur.sh
#
# Ne yapar:
#   1) L4T/JetPack sürümünü okur (/etc/nv_tegra_release).
#   2) Merkez'in venv'ine NVIDIA'nın Jetson için derlediği onnxruntime-gpu
#      tekerleğini kurar (CUDA / TensorRT sağlayıcıları). PyPI'daki
#      onnxruntime yalnız CPU'dur; Jetson GPU'su onunla kullanılamaz.
#   3) Sağlayıcıları doğrular ve sonucu yazar.
# Merkez'in AI işçisi (assets/python/ai_sunucu.py) CUDA > TensorRT > CPU
# sırasıyla sağlayıcı seçer; kurulum sonrası "Isci hazir ... dedektor=YOLO-GPU"
# görülmelidir (ai_isci.log).
set -u
HEDEF="${HEDEF:-/opt/goktungu/merkez}"
PY="$HEDEF/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "HATA: $PY yok. Merkez paketi kurulu mu?" >&2; exit 1
fi
if [ ! -f /etc/nv_tegra_release ]; then
  echo "UYARI: /etc/nv_tegra_release yok; bu makine Jetson görünmüyor. CPU onnxruntime kurulacak."
  "$PY" -m pip install --quiet onnxruntime && "$PY" -c "import onnxruntime as o; print('onnxruntime', o.__version__, o.get_available_providers())"
  exit $?
fi
L4T="$(head -1 /etc/nv_tegra_release | sed -n 's/.*R\([0-9]*\).*REVISION: \([0-9.]*\).*/\1.\2/p')"
echo "L4T sürümü: ${L4T:-bilinmiyor}  ($(head -1 /etc/nv_tegra_release))"
case "${L4T%%.*}" in
  36) DIZINLER="https://pypi.jetson-ai-lab.dev/jp6/cu126 https://pypi.jetson-ai-lab.dev/jp6/cu122" ;;
  35) DIZINLER="https://pypi.jetson-ai-lab.dev/jp5/cu114" ;;
  *)  DIZINLER="https://pypi.jetson-ai-lab.dev/jp6/cu126" ;;
esac
# Mevcut CPU onnxruntime GPU paketiyle çakışır; kaldır.
"$PY" -m pip uninstall -y -q onnxruntime >/dev/null 2>&1 || true
TAMAM=0
for D in $DIZINLER; do
  echo "Deneniyor: $D"
  if "$PY" -m pip install --quiet --index-url "$D" --extra-index-url https://pypi.org/simple onnxruntime-gpu; then
    TAMAM=1; break
  fi
done
if [ "$TAMAM" != "1" ]; then
  echo "UYARI: Jetson onnxruntime-gpu kurulamadı (ağ/JetPack uyumsuzluğu). CPU onnxruntime kuruluyor." >&2
  "$PY" -m pip install --quiet onnxruntime || true
fi
"$PY" - <<'PYEOF'
try:
    import onnxruntime as o
    s = o.get_available_providers()
    print("onnxruntime", o.__version__, "saglayicilar:", s)
    print("GPU:", "EVET" if any(p in s for p in ("CUDAExecutionProvider", "TensorrtExecutionProvider")) else "HAYIR (CPU)")
except Exception as e:
    print("onnxruntime yuklenemedi:", e)
PYEOF
echo "Bitti. Merkez servisini yeniden başlatın:  sudo systemctl restart goktungu-merkez"
