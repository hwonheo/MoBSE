#!/usr/bin/env bash
# h197 전용 venv 구축 — 재설계 v2 실행 환경을 고정한다 (U13·U14 해소, G2 환경 lock).
#
# conda base 를 건드리지 않고 독립 venv 를 만든다. 설치 후 버전 대조와
# torch_geometric 부재 검사를 수행하고, pip freeze 를 lock 파일로 남긴다.
#
# 사용:
#   bash 04_setup_venv.sh --prefix /mnt/data/mp2026/MoBSE_dataset/venv-mobse-v2
#   bash 04_setup_venv.sh --prefix ... --torch cpu      # CPU 전용으로 강제
#   bash 04_setup_venv.sh --prefix ... --torch skip     # torch 없이 (WI-02 전처리만)
set -euo pipefail

PREFIX=""
TORCH_MODE="auto"          # auto | cuda | cpu | skip
TORCH_VERSION="2.10.0"
BASE_PY=""
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --torch) TORCH_MODE="$2"; shift 2 ;;
    --torch-version) TORCH_VERSION="$2"; shift 2 ;;
    --python) BASE_PY="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$PREFIX" ]] || { echo "--prefix 필요" >&2; exit 2; }

# --- 기반 인터프리터 선택: 3.11 우선 ---
if [[ -z "$BASE_PY" ]]; then
  for cand in python3.11 python3 python; do
    if command -v "$cand" >/dev/null; then
      v=$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
      if [[ "$v" == "3.11" ]]; then BASE_PY="$cand"; break; fi
      [[ -z "$BASE_PY" ]] && BASE_PY="$cand"
    fi
  done
fi
[[ -n "$BASE_PY" ]] || { echo "python 인터프리터 없음" >&2; exit 3; }
BASE_VER=$("$BASE_PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')
echo "[base] $BASE_PY ($BASE_VER)"
[[ "$BASE_VER" == 3.11.* ]] || echo "[warn] 3.11 이 아니다 ($BASE_VER). 핀 버전이 안 맞을 수 있다."

# --- venv 생성 ---
if [[ -d "$PREFIX" ]]; then
  echo "[venv] 이미 존재: $PREFIX (재사용)"
else
  "$BASE_PY" -m venv "$PREFIX"
  echo "[venv] 생성: $PREFIX"
fi
PY="$PREFIX/bin/python"
"$PY" -m pip install --upgrade pip setuptools wheel >/dev/null
echo "[pip] $("$PY" -m pip --version)"

# --- 과학 스택 (핀) ---
echo "[install] requirements-v2.txt"
"$PY" -m pip install -r "$HERE/requirements-v2.txt"

# --- torch ---
case "$TORCH_MODE" in
  auto) if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1;
        then TORCH_MODE=cuda; else TORCH_MODE=cpu; fi
        echo "[torch] auto -> $TORCH_MODE" ;;
esac
case "$TORCH_MODE" in
  cuda) echo "[install] torch==$TORCH_VERSION (CUDA 기본 휠)"
        "$PY" -m pip install "torch==$TORCH_VERSION" ;;
  cpu)  echo "[install] torch==$TORCH_VERSION (CPU 휠)"
        "$PY" -m pip install "torch==$TORCH_VERSION" \
              --index-url https://download.pytorch.org/whl/cpu ;;
  skip) echo "[torch] 건너뜀" ;;
  *)    echo "--torch 값이 잘못됨: $TORCH_MODE" >&2; exit 2 ;;
esac

# --- 검증 ---
echo
echo "[verify]"
"$PY" - <<'PYEOF'
import sys, importlib
EXPECT = {
    "numpy": "2.4.3", "scipy": "1.17.1", "sklearn": "1.8.0",
    "pandas": "3.0.1", "nibabel": "5.4.2", "nilearn": "0.13.1",
    "matplotlib": "3.10.9", "pytest": "9.0.2",
}
fail = []
for mod, want in EXPECT.items():
    try:
        m = importlib.import_module(mod)
        got = getattr(m, "__version__", "unknown")
    except Exception as e:
        fail.append(f"{mod}: import 실패 ({type(e).__name__})"); continue
    mark = "OK " if got == want else "MISMATCH"
    if got != want:
        fail.append(f"{mod}: 기대 {want}, 실제 {got}")
    print(f"  {mark} {mod:12s} {got}")

try:
    import torch
    print(f"  OK  {'torch':12s} {torch.__version__}  "
          f"cuda_available={torch.cuda.is_available()} "
          f"cuda={getattr(torch.version,'cuda',None)} "
          f"devices={torch.cuda.device_count() if torch.cuda.is_available() else 0}")
except Exception as e:
    print(f"  --  torch        미설치 ({type(e).__name__})")

# U21 guard: PyG 가 없어야 한다.
try:
    import torch_geometric  # noqa: F401
    fail.append("torch_geometric 이 설치되어 있다 — U21 guard 위반. "
                "mobse/models/mobse.py:93-98 이 backend 를 갈아탄다.")
    print("  FAIL torch_geometric 설치됨 (있으면 안 된다)")
except ImportError:
    print("  OK  torch_geometric 부재 (U21 guard 통과)")

if fail:
    print("\n[FAIL]"); [print("  -", f) for f in fail]; sys.exit(1)
print("\n[verify] 통과")
PYEOF

# --- lock 과 환경 기록 ---
LOCK="$PREFIX/environment_lock_h197.txt"
"$PY" -m pip freeze > "$LOCK"
echo "[lock] $LOCK ($(wc -l < "$LOCK") packages)"

ENVJSON="$HERE/h197_environment.json"
bash "$HERE/00_record_environment.sh" --python "$PY" --out "$ENVJSON" >/dev/null
echo "[env]  $ENVJSON"

cat <<MSG

다음:
  source $PREFIX/bin/activate
  python 01b_wave1_fetch_metadata.py --dest /mnt/data/mp2026/MoBSE_dataset/aomic_wave1 --dry-run

반입 대상: $LOCK, $ENVJSON
MSG
