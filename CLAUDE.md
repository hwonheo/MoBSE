# CLAUDE.md — MoBSE Project Context

> 최종 갱신 2026-09-18. 모든 수치는 실측값이며 출처를 함께 적음.
> 2026-04-17판은 `.backup/CLAUDE.md_20260918_*.md` 에 보존됨.

## Project
MoBSE (Mixture of Brain-State Experts): fMRI 시계열을 dFC 유래 전문가 하위망으로 라우팅하는 그래프 신경망. PI: Dr. Hwon Heo, Asan Medical Center Seoul.

## Current Phase: 재설계 v1 (Redesign v1)

2026-09-17 문헌 검토와 기존 실험 감사를 거쳐 **연구 질문과 평가 target을 교체함.**

- **질문**: training-rest에서 만든 graph bank의 해부학적 정렬과 입력 의존 routing은, 군집과 독립인 실제 task 분류에서 각각 추가 가치를 주는가.
- **주 target**: AOMIC PIOP1 `emomatching=0` / `workingmemory=1` 의 run identity. 미사용 피험자에서 평가.
- **주가설**: H1 = A−B > 0 (입력 의존 routing의 이득), H2 = A−C > 0 (정렬된 brain bank의 이득). 최소 관심 효과 δ = 0.02 balanced accuracy (이 연구의 설계 선택이지 문헌 기준이 아님).
- **복제**: PIOP2 같은 task pair를 잠근 cohort/acquisition replication으로 사용. **cross-site라고 부르지 않음** (같은 연구 환경).

정본 문서: [프로토콜 v1.1](docs/experiments/mobse_redesign_protocol_2026-09-17.md) · [작업 지침서 v1.0](docs/experiments/mobse_redesign_work_instructions_2026-09-17.md) · [기존 실험 감사](docs/experiments/mobse_existing_experiments_audit_2026-09-17.md) · [문헌 검토](docs/experiments/mobse_literature_review_2026-09-17.md)

### 주장하지 않는 것
최초 brain MoE, atlas-free, cognitive load marker, sparse-compute 우위는 기본 주장이 아님. dFCExpert(IEEE TMI 45(3), 2026-03)와 MoRE-Brain(NeurIPS 2025)이 직접 선행연구임. 인지부하 정답·개별 뇌 상태·인과적 인지기전을 측정한다고 하지 않음.

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
기존 추출이 **모든 run에 0.75초를 적용**해 두 primary target이 2.67배 잘못된 rate로 필터링됨 (gate evidence rev22 `existing extraction TR correctness` = fail). `data/aomic`, `data/current_canonical`, `data/legacy_*` 의 시계열은 이 사유로 주분석에서 제외됨. **잘못 필터링한 시계열을 resample하는 것은 복구가 아님.**

## Cohort 확정 (WI-03)

| cohort | 전체 | 적격 | 역할 |
|---|---:|---:|---|
| ds002785 (PIOP1) | 216 | **157** | 주 (pilot 31 / main 126) |
| ds002790 (PIOP2) | 226 | **189** | 외부 hold-out |

적격 규칙은 프로토콜 §3.3, 세 task(emomatching·workingmemory·restingstate) 전부 보유 요구. 탈락은 대부분 평균 FD 초과와 구간별 spike 비율 초과.

## Gate 현황 (gate_evidence.json revision 22, 2026-09-18T08:40Z)

| Gate | 상태 |
|---|---|
| G0 Provenance | **conditionally_cleared** (검사 10건 중 2건 fail) |
| G1 Measurement lock | planned (검사 2건 fail — group_id 구성, subject ID 네임스페이스) |
| G2–G5 | planned |

- 정본은 `results/redesign_v1/<release_id>/gate_evidence.json` 이며 **revision이 올라가면 이전 판정표를 인용하지 말 것.**
- 미해결: `locks/measurement_lock.json`(00:45, G1 잠금)과 rev22(08:40, G1 planned)가 어긋남. 사람 판단 필요.

## 실행 호스트와 경로

- **실행 호스트는 h197** (`~/.ssh/config`에 등록). 로컬 맥북에는 torch·sklearn·scipy가 없음.
- data root: `h197:/mnt/data/mp2026/MoBSE_dataset`
  - `aomic_wave1/` — 메타데이터 (sidecar·confounds·events), 6,063 파일 · 1.1 GB
  - `aomic_wave2/` — BOLD 본체, 2,590 파일 · 209.7 GiB (수급 완료, 실패 0)
  - `derivatives_v2/`, `derivatives_v2_piop2/` — v2 추출 파섬 창 (**정본**)
  - `atlas_2009c/` — Schaefer-100 MNI152NLin2009cAsym (ROI 순서 규정)
  - `venv-mobse-v2/` — 분석 환경
- 물리 경로 전체는 Notion `🗄️ Data Assets` 에 등록됨 (시리즈 `MOBSE`).

> **아틀라스 주의**: `~/nilearn_data/schaefer_2018` 은 FSLMNI152 공간이고 h197 `atlas_2009c` 는 MNI152NLin2009cAsym 공간임. **섞어 쓰면 안 됨.**

## v2 구현 현황 (2026-09-18 실측)

- `mobse/v2/` 모듈 16개 · 4,114줄 — manifests · preprocess · splits · features · templates · models · train · evaluate · statistics · cli (지침서 명세) + cohort · config · extract · labels · locks (추가)
- `tests/v2/` — 개발 진행 중. 2026-09-18 10:30 실측 22파일 · 5,001줄 · 테스트 492개
- 로컬 실행 시 **451 passed / 26 failed / 17 skipped** (같은 날 오전 앞선 측정은 470개 기준 439/26/7 — **수치가 시간 단위로 바뀌니 인용하지 말고 다시 측정할 것**) — 실패 26건은 전부 `ModuleNotFoundError`(sklearn 22, scipy 2, torch 2)이며 **결함이 아니라 로컬 환경 문제**. h197 환경에서 돌릴 것.
- `configs/redesign_v1/` — `main.yaml`(redesign_v1_main) · `pilot.yaml`(redesign_v1_pilot) · `external.yaml`(redesign_v1_external_piop2)
- **config는 코드 상수를 다시 적어 잠그는 문서임.** 값을 바꿔 동작을 바꾸는 용도가 아니며, `mobse/v2/config.py` 검증기가 상수와 대조해 어긋나면 실패시킴. 미지의 키는 오타로 보고 거부함.

### v2 실행
```bash
PYTHONPATH=. python -m mobse.v2.cli {validate,prepare,split,fit,evaluate,report} --help
PYTHONPATH=. python -m pytest tests/v2 -q
```
**경로는 전부 명시해야 함 — glob fallback 없음.**

### artifact 계약
`results/redesign_v1/<release_id>/` 아래 `provenance/ qc/ splits/ locks/ fits/ predictions/ statistics/ reports/`.
`release_id` = `YYYYMMDD_<short-code-hash>_<config-hash-prefix>`. **같은 release 결과를 덮어쓰지 않으며** 실패 재시도는 attempt 번호를 덧붙임.

## Code Conventions
- Python 3.9+, type hints, Google-style docstrings, snake_case
- `PYTHONPATH=.` 로 스크립트 실행
- **편집 전 백업**: `cp file .backup/file_$(date +%Y%m%d_%H%M%S).ext`
- 로컬에 torch 없음 — torch 불필요한 작업은 standalone 스크립트로
- 과거 산출물을 새 경로로 복사해 새 결과처럼 보고하지 않음
- main 성능 접근 뒤의 설계 변경은 새 exploratory version으로 분리

## 기록 체계
작업 기록은 Notion `📓 Work Logs` 시리즈 **`MOBSE`** 에 남김 (`/bmc-records:bmc-work-log`).
물리 경로는 `🗄️ Data Assets` 에만 기재하고 Work Log 본문에는 쓰지 않음 (리포 상대 경로는 예외).

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

## Next Steps (2026-09-18)

1. **G1 불일치 해소** — measurement lock과 gate evidence rev22의 G1 판정 정리
2. G1 fail 검사 2건 처리 — group_id 구성 근거, 두 cohort subject ID 네임스페이스
3. WI-04 이후 진행 (인터페이스 잠금 후 WI-04/05 병렬 가능, WI-07 전 통합 테스트 필수)
4. **v2 구현물 커밋** — 현재 `mobse/v2/`·`tests/v2/`·`configs/redesign_v1/` 전부 untracked (HEAD `7787ae0`)
5. 프로토콜/지침서에 추가 모듈 5종(cohort·config·extract·labels·locks) 반영

## Excluded Datasets (and why)
- **HCP**: DUA 필요, 데이터 접근 불확실
- **AOMIC-ID1000 (ds003097)**: resting-state 없음 → low-demand routing anchor 없음
- **ds000030 (UCLA CNP)**: 주 target의 대체 후보로 쓰지 않음. 과거 cross-site 전이 실험의 입력이었고 데이터는 `data/ds000030/` 에 남아 있음

> **PIOP2는 더 이상 제외 대상이 아님.** 2026-04-17판은 "짧은 스캔 → dFC 창 부족"을 이유로 제외했으나, Wave 1 실측 결과 emomatching 222 run · workingmemory 224 run이 전건 분석 window를 만족했고 적격 189명으로 **외부 hold-out에 채택됨.**
