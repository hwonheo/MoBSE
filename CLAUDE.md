# CLAUDE.md — MoBSE Project Context

> 최종 갱신 2026-09-25 22:4x KST (HEAD `1e399ec` 위 작업트리, gate evidence rev61 기준 — rev60·rev61 은 부록 BH·BI 기록만, 판정 수는 rev59 와 같음). 모든 수치는 실측값이며 출처를 함께 적음.
> 이전판(2026-09-18)은 `.backup/CLAUDE_20260925_201635.md` 에, 2026-04-17판은 `.backup/CLAUDE.md_20260918_*.md` 에 보존됨.
> **현행 상태의 정본은 이 파일이 아님** — claude.ai Project "MoBSE" 의 인수인계 문서 `claude/mobse_redesign_g0_handoff_2026-09-17.md` (선생님 결정 원문·남은 작업·마감 절차) 와 가장 높은 revision 의 `gate_evidence.json`. 이 파일은 저장소에 들어온 사람을 위한 방향 안내다.

## Project
MoBSE (Mixture of Brain-State Experts): fMRI 시계열을 dFC 유래 전문가 하위망으로 라우팅하는 그래프 신경망. PI: Dr. Hwon Heo, Asan Medical Center Seoul.

## Current Phase: 재설계 v1 (Redesign v1)

2026-09-17 문헌 검토와 기존 실험 감사를 거쳐 **연구 질문과 평가 target을 교체함.**

- **질문**: training-rest에서 만든 graph bank의 해부학적 정렬과 입력 의존 routing은, 군집과 독립인 실제 task 분류에서 각각 추가 가치를 주는가.
- **주 target**: AOMIC PIOP1 `emomatching=0` / `workingmemory=1` 의 run identity. 미사용 피험자에서 평가.
- **주가설**: H1 = A−B > 0 (입력 의존 routing의 이득), H2 = A−C > 0 (정렬된 brain bank의 이득). 최소 관심 효과 δ = 0.02 balanced accuracy (이 연구의 설계 선택이지 문헌 기준이 아님).
- **보조 비교** (primary 아님, 95% 기술적 CI): S 후보 4종 (logistic 2 + 32-hidden MLP 2), 구조 비교 NG (no-graph fusion MLP)·SG (single average graph).
- **복제**: PIOP2 같은 task pair를 잠근 cohort/acquisition replication으로 사용. **cross-site라고 부르지 않음** (같은 연구 환경).

정본 문서: [프로토콜 v1.1](docs/experiments/mobse_redesign_protocol_2026-09-17.md) (본문의 "계획서", 개정 행 P1–P11·P6-a/b·P8-b 포함) · [작업 지침서 v1.0](docs/experiments/mobse_redesign_work_instructions_2026-09-17.md) · [기존 실험 감사](docs/experiments/mobse_existing_experiments_audit_2026-09-17.md) · [문헌 검토](docs/experiments/mobse_literature_review_2026-09-17.md) · 실행 보고서 `results/redesign_v1/20260917_3c458d507e82_nocfg/reports/` (부록 A–BG) · 자원 계획 같은 폴더 `resource_budget.md`

### 주장하지 않는 것
최초 brain MoE, atlas-free, cognitive load marker, sparse-compute 우위는 기본 주장이 아님. dFCExpert(IEEE TMI 45(3), 2026-03)와 MoRE-Brain(NeurIPS 2025)이 직접 선행연구임. 인지부하 정답·개별 뇌 상태·인과적 인지기전을 측정한다고 하지 않음. 합성·단일 장비 비용 측정을 효율 우위 근거로 쓰지 않음.

## 확정된 자료 사실 (Wave 1 감사, 1,295 run)

| cohort / task | runs | native TR | volumes |
|---|---:|---:|---:|
| ds002785 (PIOP1) / emomatching | 208 | **2.0** | 135 |
| ds002785 / workingmemory | 207 | **2.0** | 162 |
| ds002785 / restingstate | 210 | 0.75 | 480 |
| ds002790 (PIOP2) / emomatching | 222 | **2.0** | 135 |
| ds002790 / workingmemory | 224 | **2.0** | 160 |
| ds002790 / restingstate | 224 | 2.0 | 240 |

- 전건 분석 window 성립. TR은 조합마다 단일값이라 추정할 자리가 없음.
- **두 cohort의 rest가 서로 다른 TR을 씀** — target TR을 rest에서 유추하면 안 됨.

### ⚠️ 기존 파생 시계열은 주분석에 재사용 금지
기존 추출이 **모든 run에 0.75초를 적용**해 두 primary target이 2.67배 잘못된 rate로 필터링됨 (gate evidence `existing extraction TR correctness` = fail, rev59 에도 그대로). `data/aomic`, `data/current_canonical`, `data/legacy_*` 의 시계열은 이 사유로 주분석에서 제외됨. **잘못 필터링한 시계열을 resample하는 것은 복구가 아님.**

### 현행 추출 (v3)
- 통과대역 **0.008–0.2 Hz** (개정 P9, 결정 원문 "통과대역 0.2 Hz로"), 차단대역 DCT 기저를 nuisance 와 **동시 회귀** (`mobse/v2/extract.py` `BANDPASS_LOW_HZ`·상한). 산출물은 `derivatives_v3*`. `derivatives_v2*` 는 대체됨 (단 `derivatives_v2/pilot_tech/splits/folds.json` 은 pilot 측정이 씀).
- 동시 회귀 설계는 1,291 run 전수에서 rank 결손 0, 분석 run 수치적으로 안정 (보고서 부록 BG, rev59).
- pilot 31명 창 372 에서 0.2–0.25 Hz 잔여 전력 비율 중앙 약 0.004 — 필터 적용 기대값 수준, 누락 기대값 (약 0.19) 과 겹치지 않음 (보고서 부록 BH, rev60).

## Cohort·분할 (WI-03, 잠김)

| cohort | 전체 | 적격 | 역할 |
|---|---:|---:|---|
| ds002785 (PIOP1) | 216 | **157** | 주 (pilot 31 / main 126, outer test 26/25/25/25/25) |
| ds002790 (PIOP2) | 226 | **189** | 외부 hold-out (분할 없음) |

- 적격 규칙은 프로토콜 §3.3, 세 task 전부 보유 요구. group_id 는 1 subject = 1 group (관계 metadata 부재, 개정 P4).
- split_hash `ace5f4a4…` (불변). 외부 최종 선택용 main pool 3-fold (seed 20262000) 는 별도 `external_folds.json` (42/42/42, external_split_hash `40e50350…`, 결정 17).
- h197 경로 (data root 상대): subjects `derivatives_v3/cohort_piop1/subjects.jsonl`, 분할 `derivatives_v3/splits_piop1_p7/{folds.json, external_folds.json}`.

## Gate 현황 (gate_evidence.json revision 61 — 판정은 rev59 와 같음, 2026-09-25 재측정)

| Gate | 상태 |
|---|---|
| G0 Provenance | **conditionally_cleared** (검사 10건: pass 7 · fail 2 — 기존 추출 TR 정확성, 주 target BOLD 존재 · undetermined 1 — dummy volume 제거) |
| G1 Measurement lock | **in_progress** (검사 8건: pass 4 · fail 4 — group_id 구성, subject ID 네임스페이스, δ=0.02 정밀도, pilot 측정 기반 자원 계획) |
| G2 Implementation lock · G5 Interpretation | planned (검사 0건) |
| G3 Internal release · G4 External release | planned (검사 각 1건, pass) |

- 정본은 `results/redesign_v1/20260917_3c458d507e82_nocfg/gate_evidence.json` 이며 **revision이 올라가면 이전 판정표를 인용하지 말 것.** 순서는 revision 번호로만 봄 (`timestamp_utc` 는 거꾸로 간 적 있음).
- "pilot 측정 기반 자원 계획" 은 rev58 에서 pilot 실측 예산을 만들었으나 **판정은 fail 그대로** — 바꿀지는 선생님 결정 대기 (인수인계 문서). rev61 (부록 BI): 칸당 3회 반복 — 같은 인자에서 s/epoch 최대 2.7 배 변동 (칸 차이 아님), pilot 규모 k=4 동시 실행 처리량 2.23 배, 순차 학습 상한 34.0 h.
- 측정 잠금 현행 `78ddd887253f…` (locked_at 2026-09-25T07:23:32Z), 옛 판 35개는 `locks/superseded/` 에 보존. 잠금은 `mobse/v2/*.py` 를 해시한다 — **`mobse/v2` 를 바꾸면 잠금 재생성 + gate evidence 새 revision** (`scripts/h197/18_build_measurement_lock.py --overwrite --reason "..."`). `scripts/h197/`·`tests/v2` 만 바꾸면 잠금 재생성은 불요, gate evidence 해시만.

## 실행 호스트와 경로

- **정본 저장소는 Mac** `/Users/hwon/projects/Git/Manuscript/MoBSE` (branch `redesign-v1`) — 편집·커밋은 Mac. **푸시하지 않음.**
- **실행 호스트는 h197** (`ssh -o BatchMode=yes h197`). 사본 `/mnt/data/code/MoBSE`, venv `/mnt/data/mp2026/MoBSE_dataset/venv-mobse-v2`. 최종 판정(마감)은 h197.
- Mac → h197 동기화: `cd /Users/hwon/projects/Git/Manuscript && rsync -a --exclude=/data/ --exclude=/artifacts/ --exclude=/nilearn_cache/ --exclude=__pycache__/ --exclude='*.pyc' MoBSE/ h197:/mnt/data/code/MoBSE/` — **`--delete` 금지, `__pycache__`·`*.pyc` 제외 필수** (2026-09-24 stale pyc 사고).
- data root: `h197:/mnt/data/mp2026/MoBSE_dataset`
  - `aomic_wave1/` — 메타데이터 (sidecar·confounds·events)
  - `aomic_wave2/` — BOLD 본체
  - `derivatives_v3/`, `derivatives_v3_piop2/` — v3 추출 파섬 창·manifest·코호트·분할 (**정본**)
  - `atlas_2009c/` — Schaefer-100 MNI152NLin2009cAsym (ROI 순서 규정)
- Mac `.venv` (python 3.11, torch 2.10) 에서도 v2 시험이 돈다 — **`.venv/bin/python` 을 직접 부를 것** (activate 후 `python` 은 torch 없는 다른 python 으로 풀림).
- 물리 경로 전체는 Notion `🗄️ Data Assets` 에 등록됨 (시리즈 `MOBSE`).

> **아틀라스 주의**: `~/nilearn_data/schaefer_2018` 은 FSLMNI152 공간이고 h197 `atlas_2009c` 는 MNI152NLin2009cAsym 공간임. **섞어 쓰면 안 됨.**

## v2 구현 현황 (2026-09-25 20:1x KST 실측, HEAD `cbbbb40`)

- `mobse/v2/` 파일 18개 · 8,984줄 — manifests · preprocess · splits · features · templates · models · train · fitting · baselines · evaluate · statistics · cli · cohort · config · extract · labels · locks (+ `__init__`)
- `tests/v2/` 시험 파일 40개 · 12,244줄 · **1,166 시험 수집** (Mac collect-only). **수치가 슬롯마다 바뀌니 인용하지 말고 다시 잴 것.** 마감 결과는 인수인계 문서 "현행".
- CLI 하위 명령 11개 (`mobse/v2/cli.py` `SUBCOMMANDS`): `validate`·`prepare`·`split`·`fit`(A–D + NG·SG)·`fit-s`·`select-ad`·`select-comparator`·`select-s`·`evaluate`·`report`·`report-comparison`
- 학습 규칙 (P8-b, 결정 15): `train.MIN_UPDATES = 5000`, `MAX_EPOCHS = 400`, early stopping 은 최소치 이후에만, inner 평가는 best checkpoint. `INNER_SEED = 42`, `MODEL_SEEDS = (42, 43, 44)` (fit·선택 CLI 가 잠긴 seed 밖을 거부). A–D 모델 구조는 변경 보류.
- `configs/redesign_v1/` — `main.yaml` · `pilot.yaml` · `external.yaml`. **config는 코드 상수를 다시 적어 잠그는 문서임.** 값을 바꿔 동작을 바꾸는 용도가 아니며, `mobse/v2/config.py` 검증기가 상수와 대조해 어긋나면 실패시킴. 미지의 키는 오타로 보고 거부함. 잠긴 키 39개 ↔ 소비 함수 대응표는 `tests/v2/test_config_consumption.py`.

### v2 실행
```bash
PYTHONPATH=. python -m mobse.v2.cli <하위 명령> --help
PYTHONPATH=. python -m pytest tests/v2 -q
```
**경로는 전부 명시해야 함 — glob fallback 없음.** fit 이웃 파일(`fit_report.json`·`window_predictions.jsonl` 등)과 `external_folds.json` 만 고정 이름으로 옆에서 읽는다.

### 마감 5단계 (h197, 매 변경마다 전부 rc=0 일 때만 커밋)
```bash
cd /mnt/data/code/MoBSE; R=results/redesign_v1/20260917_3c458d507e82_nocfg; D=/mnt/data/mp2026/MoBSE_dataset
PYTHONPATH=. python -m pytest tests/v2 -q
python scripts/h197/17_verify_gate_hashes.py $R
python scripts/h197/22_crosscheck_reported_numbers.py $R
python scripts/h197/19_verify_measurement_lock.py --data-root $D --repo-root . --release $R
python scripts/h197/25_verify_window_files.py --data-root $D --lock $R/locks/measurement_lock.json
```

### artifact 계약
`results/redesign_v1/<release_id>/` 아래 `provenance/ qc/ splits/ locks/ fits/ predictions/ statistics/ reports/`.
`release_id` = `YYYYMMDD_<short-code-hash>_<config-hash-prefix>`. **같은 release 결과를 덮어쓰지 않으며** 실패 재시도는 attempt 번호를 덧붙임. 데이터·run 단위 provenance 는 커밋하지 않음.

## 고정 운영 규칙
- **잠긴 분할(main pool)을 소비하는 fit 을 시작하지 않음** — 선생님의 main OOF 착수 승인 원문이 인수인계 문서에 생기기 전까지. 결정 17 (외부 분할) 도 외부 선택·최종 fit 실행 승인이 아님.
- 공용 저장소(NAS, bmc-storage 등)에 쓰지 않음. `/tmp` 에 정본 산출물을 두지 않음.
- 돌연변이 시험은 bytecode 없이 (`python -B` + `PYTHONDONTWRITEBYTECODE=1`), 돌연변이 뒤·rsync 전·잠금 재생성 전에 `find mobse scripts tests -name '*.pyc'` 0 확인.
- 커밋 메시지는 Conventional Commits (영문), 파일로 써서 `git commit -F` (zsh heredoc 사고).

## Code Conventions
- Python 3.9+, type hints, Google-style docstrings, snake_case
- `PYTHONPATH=.` 로 스크립트 실행
- **편집 전 백업**: `cp file .backup/file_$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S).ext`
- 과거 산출물을 새 경로로 복사해 새 결과처럼 보고하지 않음
- main 성능 접근 뒤의 설계 변경은 새 exploratory version으로 분리

## 기록 체계
- 재설계 진행 상태·선생님 결정 원문: claude.ai Project "MoBSE" 인수인계 문서 (위).
- 작업 기록은 Notion `📓 Work Logs` 시리즈 **`MOBSE`** 에 남김 (`/bmc-records:bmc-work-log`). 물리 경로는 `🗄️ Data Assets` 에만 기재하고 Work Log 본문에는 쓰지 않음 (리포 상대 경로는 예외).

## Legacy (v1) — 참고용

재설계 이전 코드와 산출물은 보존되어 있으나 **주분석 근거로 쓰지 않음.**

- 기존 실험 자산: 학습 요약 352개, seed result 624개, checkpoint 624개 (`artifacts/`)
- 이미 수행된 것: strict subject split(ABIDE·simulation 각 10 seed), nuisance 민감도 3조건, prior/routing sweep, baseline 4종 비교, ds000030↔ds000243 전이, ETTh1 temporal encoder 통제
- **이 수치는 독립 가설 검증 352건을 뜻하지 않음** — 재실행·smoke test·탐색 튜닝 포함

### v1 구현 세부 (해당 코드 수정 시에만)
- `load_template_bank(path, states)` 는 인자 2개 필요
- YAML은 `0.001` 형식 사용 (`1e-3` 은 safe_load가 문자열로 파싱)
- `use_amp: True` 는 CUDA에서만 활성 (CPU는 graceful fallback)
- `_canonical_task()` 가 `"hcp"` → `"os"` 매핑
- `routing_k` 기본 2, `routing_mode` 기본 `"soft"`
- expert collapse 수정: `_routing_weights()` 의 `scatter_(values)` → `weights * mask`

## Next Steps
정본은 인수인계 문서 "남은 작업". 2026-09-25 20:1x 기준 요지:
1. **결정 대기 2건** — 구조 비교 A−NG·A−SG paired contrast 추가 여부, G1 "resource plan from pilot measurement" 판정 변경 여부.
2. **main OOF 착수 승인 대기** — 승인 전에는 합성 시험·pilot 창 측정만.
3. 결정 불요 후보: 재추출 창의 통과대역 밖 잔여 전력 점검 (범위 확인 먼저), h197 정리 (삭제는 선생님 확인 뒤).

## Excluded Datasets (and why)
- **HCP**: DUA 필요, 데이터 접근 불확실
- **AOMIC-ID1000 (ds003097)**: resting-state 없음 → low-demand routing anchor 없음
- **ds000030 (UCLA CNP)**: 주 target의 대체 후보로 쓰지 않음. 과거 cross-site 전이 실험의 입력이었고 데이터는 `data/ds000030/` 에 남아 있음

> **PIOP2는 더 이상 제외 대상이 아님.** 2026-04-17판은 "짧은 스캔 → dFC 창 부족"을 이유로 제외했으나, Wave 1 실측 결과 emomatching 222 run · workingmemory 224 run이 전건 분석 window를 만족했고 적격 189명으로 **외부 hold-out에 채택됨.**
