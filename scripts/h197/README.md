# h197 실행 스크립트 — MoBSE 재설계 자료 확보와 환경 구축

실행 호스트: **h197** (`bmcws`, Ubuntu 20.04) · 계획: [`docs/experiments/h197_acquisition_plan_2026-09-17.md`](../../docs/experiments/h197_acquisition_plan_2026-09-17.md)

conda `base` 를 건드리지 않고 **전용 venv** 를 만든다. 재설계 프로토콜은 G2 에서 환경 lock 을 요구하므로, 공용 env 를 쓰면 그 lock 이 의미를 잃는다.

## 순서

```bash
cd /mnt/data/mp2026/MoBSE_dataset/h197

# 1) 전용 venv 구축 + 검증 + lock. 끝나면 h197_environment.json 도 갱신된다.
bash 04_setup_venv.sh --prefix /mnt/data/mp2026/MoBSE_dataset/venv-mobse-v2
#    GPU 없으면 자동으로 CPU 휠. 강제하려면 --torch cpu / --torch cuda / --torch skip

source /mnt/data/mp2026/MoBSE_dataset/venv-mobse-v2/bin/activate

# 2) Wave 1 목록·용량만 (다운로드 없음). awscli 불필요 — 표준 라이브러리만 쓴다.
python 01b_wave1_fetch_metadata.py --dest /mnt/data/mp2026/MoBSE_dataset/aomic_wave1 --dry-run

# 3) Wave 1 실제 다운로드 (메타데이터만, BOLD 제외)
#    SSH 가 끊겨도 죽지 않도록 반드시 nohup 또는 tmux 로 띄운다.
nohup python -u 01b_wave1_fetch_metadata.py \
  --dest /mnt/data/mp2026/MoBSE_dataset/aomic_wave1 --jobs 8 \
  > /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/fetch.log 2>&1 &
tail -f /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/fetch.log   # Ctrl-C 로 보기만 중단

# 4) 감사 — 표준 라이브러리만 사용
python 02_wave1_audit.py \
  --root /mnt/data/mp2026/MoBSE_dataset/aomic_wave1 \
  --out  /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/wave1_audit

# 5) (Wave 1 판정 후에만) BOLD 용량 실측 — 다운로드 없음
python 03b_wave2_size_probe.py \
  --listing-cache /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/s3_listing_cache.json
```

awscli 가 이미 있다면 2·3 대신 `bash 01_wave1_fetch_metadata.sh --dest …`, 5 대신 `bash 03_wave2_size_probe.sh` 를 써도 받는 파일 집합과 로컬 레이아웃이 같다.

## 파일

| 파일 | 역할 |
|---|---|
| `04_setup_venv.sh` | 전용 venv 생성, 핀 설치, 버전 대조, **U21 guard**, `environment_lock_h197.txt` 생성 |
| `requirements-v2.txt` | 과학 스택 핀 (torch 는 별도, torch_geometric 은 의도적 제외) |
| `00_record_environment.sh` | 인터프리터·패키지·GPU·디스크·egress 기록 → `h197_environment.json` |
| `01b_wave1_fetch_metadata.py` | S3 REST 로 메타데이터만 확보 (권장). `--jobs` 병렬, 중단 후 재실행하면 이어받음 |
| `01_wave1_fetch_metadata.sh` | 같은 작업의 awscli 판 |
| `02_wave1_audit.py` | run 단위 TR·volume·confounds·events 판정, `blocker_verdicts` 산출 |
| `03b_wave2_size_probe.py` / `03_wave2_size_probe.sh` | BOLD 용량 실측 (다운로드 없음) |

## 중단과 재개

다운로드는 **재실행하면 이어받는다**. 크기가 정확히 일치하는 파일만 완료로 보고 건너뛰며, 그 외에는 다시 받는다. 각 파일은 `.part` 로 받은 뒤 `os.replace` 로 이름을 바꾸므로 프로세스가 도중에 죽어도 최종 경로에 절반짜리 파일이 남지 않는다. S3 목록도 `s3_listing_cache.json` 에 있어 재나열하지 않는다.

개별 파일 실패는 전체를 멈추지 않고 `failed` 로 집계되어 `wave1_fetch_report.json` 에 기록된다. 실패가 있으면 같은 명령을 한 번 더 돌리면 된다.

## `04_setup_venv.sh` 의 guard

설치 후 다음을 검사하고, 하나라도 어긋나면 **exit 1 로 멈추며 lock 파일을 쓰지 않는다**:

- 핀한 8개 패키지의 버전이 정확히 일치하는가
- torch 가 import 되는가, `cuda_available` 과 device 수는 얼마인가
- **`torch_geometric` 이 부재한가** — 있으면 실패. `mobse/models/mobse.py:93-98` 이 PyG 설치 여부로 `DenseGCNConv` / `DenseGraphLayer` 를 갈아타므로(차단 항목 U21), 설치하지 않는 것이 backend 고정의 가장 확실한 수단이다. 지침서 T10 이 이를 검사한다.

## 4)의 출력에서 볼 것

`blocker_verdicts` 다섯 항목:

| 키 | 의미 |
|---|---|
| `U1_native_tr_targets` | emomatching·workingmemory 의 native TR 확보 여부 |
| `U2_discarded_volumes` | `non_steady_state_outlier*` 로 제거 volume 확정 가능 여부 |
| `U4_nuisance_constructible` | 24 motion + aCompCor 5 + FD 구성 가능 여부 |
| `U5_events_origin` | events onset 원점 확보 여부 |
| `window_12_252_supported_for_targets` | `[12,252)` 구간이 두 target 에서 성립하는지 |

마지막 항목이 `still_blocked` 면 **BOLD 를 받기 전에 프로토콜 §3.1 window 설계를 먼저 개정**한다.

`resolved` 는 "정보가 존재한다"는 뜻이며 QC 통과가 아니다.

## 반입

`wave1_audit/` 3종, `h197_environment.json`, `environment_lock_h197.txt` 를 MoBSE 저장소의
`results/redesign_v1/<release_id>/provenance/h197_wave1/` 로 복사한다. BOLD 본체는 h197 에 둔다.
