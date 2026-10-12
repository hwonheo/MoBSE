#!/usr/bin/env bash
# h197 을 실행 호스트로 확정하기 위한 환경 기록 (U13·U14·U16 해소용).
# 산출 JSON 을 MoBSE 저장소의 workspace_snapshot.json 에 병합한다.
#
# 사용: bash 00_record_environment.sh --python /path/to/python --out h197_environment.json
set -euo pipefail

PY="python3"; OUT="h197_environment.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PY="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
command -v "$PY" >/dev/null || { echo "interpreter not found: $PY" >&2; exit 3; }

"$PY" - "$OUT" <<'PYEOF'
import json, platform, shutil, subprocess, sys, os, datetime

def ver(mod):
    try:
        m = __import__(mod)
        return getattr(m, "__version__", "unknown")
    except Exception as e:
        return {"import_error": f"{type(e).__name__}: {e}"}

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=30).stdout.strip() or None
    except Exception:
        return None

out = {
  "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "host": platform.node(),
  "role": "execution host for MoBSE redesign v2 (WI-02 onward)",
  "python": {"executable": sys.executable, "version": sys.version,
             "implementation": platform.python_implementation()},
  "packages": {m: ver(m) for m in
      ["numpy","scipy","sklearn","pandas","nibabel","nilearn","torch",
       "torch_geometric","matplotlib","seaborn","pytest"]},
  "torch_runtime": None,
  "platform": {"system": platform.system(), "release": platform.release(),
               "machine": platform.machine(), "processor": platform.processor()},
  "cpu_count": os.cpu_count(),
  "nvidia_smi": sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
  "mem_total": sh("free -h | awk 'NR==2{print $2}'") or sh("sysctl -n hw.memsize"),
  "disk": sh("df -h . | tail -1"),
  "aws_cli": sh("aws --version"),
  "egress_probe": {},
}
try:
    import torch
    out["torch_runtime"] = {
        "version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }
except Exception as e:
    out["torch_runtime"] = {"import_error": f"{type(e).__name__}: {e}"}

for name, url in [("openneuro", "https://openneuro.org"),
                  ("openneuro_s3", "https://s3.amazonaws.com/openneuro.org"),
                  ("pypi", "https://pypi.org")]:
    code = sh(f"curl -s -o /dev/null -w '%{{http_code}}' -m 12 {url}")
    out["egress_probe"][name] = code

path = sys.argv[1]
with open(path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print(json.dumps({"host": out["host"], "python": out["python"]["version"].split()[0],
                  "torch": out["torch_runtime"], "egress": out["egress_probe"]},
                 indent=2, ensure_ascii=False))
print(f"\nwritten: {path}")
PYEOF
