# MoBSE Project Status and Workstreams (2026-03-23)

## 1) 현재 상태 판단

- 현재 단계는 `PoC 완성 -> public OpenNeuro 기반 Phase 2 1차 대규모 검증 완료 -> claim hardening 전`으로 판단한다.
- 완료된 범위:
  - end-to-end CLI 파이프라인(`prepare_data`, `build_templates`, `train`, `evaluate`, `report`)
  - Phase 1 closeout (`HC127`, `100/200-node`, balanced 3-seed, 비교표/통계/재현 패키지)
  - Phase 2 public OpenNeuro adult 300 (`ds000030 + ds000243`) 기준 `n100/n200` sweep, top3 bal3, 통계표, figure 생성
- 미완료 범위:
  - roadmap상 목표인 HCP-scale validation의 본격 재현
  - seed 수 확장에 따른 성능 지표 검정력 확보
  - 300-subject 스케일 baseline 비교
  - Phase 3 method extension

## 2) 로컬 기준으로 확인한 사실

- Phase 2 데이터는 로컬에 존재한다.
  - `data/legacy_phase2/os_phase2_ds00_300_n100/timeseries/100`: subject dir 300개
  - `data/legacy_phase2/os_phase2_ds00_300_n100/timeseries/200`: subject dir 300개
- Phase 2 요약 산출물도 로컬에 존재한다.
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_summary.csv`
  - `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_top3_bal3_summary.csv`
  - `artifacts/phase2_figures_20260314_n100_n200/`
- 현재 `.venv`는 `Python 3.11.15`이나 `pytest`는 설치되어 있지 않다.
  - 따라서 재현성 검증용 테스트 실행은 아직 바로 되지 않는다.

## 3) 즉시 수정해야 할 재현성/이식성 이슈

### A. config archive 경로 불일치

- 현재 repo에는 `configs/2026-03-13/`가 있으나, 관련 manifest와 문서는 `configs/archive/2026-03-13/`를 참조한다.
- 영향:
  - 문서 기준 재현 경로가 깨진다.
  - archive bundle의 신뢰성이 떨어진다.

### B. phase2 manifest 절대경로 고정

- `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_manifest.json`
- `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_manifest.json`
- 위 두 파일은 `/Users/hwon/GitHub/MoBSE/...` 절대경로를 포함한다.
- 영향:
  - 현재 workspace(`/Users/hwon/Documents/Git/MoBSE`)에서는 manifest 기반 참조가 이식되지 않는다.

### C. n200 config의 데이터 루트 네이밍 혼선

- `configs/phase2_collect300_n200.yaml`은 `n200` 설정이지만 `data/legacy_phase2/os_phase2_ds00_300_n100`을 root/timeseries_dir로 사용한다.
- 실제 데이터는 `timeseries/100`과 `timeseries/200`을 함께 담아 실험 자체가 성립할 수 있으나, 관리/청소/재실행 관점에서 혼란을 유발한다.

### D. README의 timeseries layout 설명과 실제 구현 차이

- README는 `<timeseries_dir>/<subject>/...` 형태로 설명한다.
- 실제 `prepare_data`는 `<timeseries_dir>/<num_nodes>/<subject>/...` 형태를 생성한다.
- 영향:
  - 외부 사용자가 README만 보고 실행하면 입력 경로를 잘못 가정할 수 있다.

### E. 환경 계약 미정리

- `pyproject.toml`에는 `pytest`가 `.[dev]` extra에만 있다.
- 현재 `.venv`에는 `pytest`가 없다.
- 영향:
  - "현재 venv가 있으니 바로 검증 가능" 상태가 아니다.
  - 테스트/검증을 표준 절차로 쓰려면 dev dependency 설치 단계를 문서화해야 한다.

## 4) 병렬 워크스트림

### Track 1. Repro/Path Hygiene

- 목표: 문서와 manifest, config 네이밍을 현재 repo 상태와 일치시킨다.
- 작업:
  - archive 경로 불일치 정리
  - phase2 manifest 절대경로 제거 또는 상대경로화
  - `phase2_collect300_n200.yaml` 데이터 루트 명명 정리
  - README data layout 설명 수정
- 성격: 코드/문서 정리
- 병렬 가능 여부: 바로 가능

### Track 2. Environment/Test Baseline

- 목표: `.venv`를 재현성 검증 가능한 표준 환경으로 만든다.
- 작업:
  - `.[dev]` 설치 또는 최소 `pytest` 설치
  - 전체 테스트 실행
  - 실패 테스트가 있으면 환경 문제와 코드 문제 분리
- 성격: 환경 검증
- 병렬 가능 여부: 바로 가능

### Track 3. Claim Hardening Experiments

- 목표: 현재 결론(`n100` 우세, 효율 우세)을 통계적으로 더 단단하게 만든다.
- 작업:
  - `n100 best vs n200 best`를 `5~10 seeds`로 확장
  - 300-subject 스케일 baseline 비교(`transformer`, `sparse_transformer`, `moe`)
  - `ds000030` vs `ds000243` cross-dataset generalization
- 성격: 실험
- 병렬 가능 여부: Track 1과 병렬 가능, Track 2가 선행되면 더 안전

### Track 4. Scale/Robustness Validation

- 목표: public OpenNeuro를 넘어 roadmap 수준의 일반화/강건성 공백을 메운다.
- 작업:
  - HCP-accessible cohort 재현
  - intermediate nodes(`128` 또는 `150`) 추가
  - nuisance pipeline sensitivity 실험
- 성격: 후속 확장
- 병렬 가능 여부: Track 3 일부와 병렬 가능

## 5) 실행 우선순위

1. Track 1에서 재현성/경로 혼선을 먼저 줄인다.
2. Track 2에서 `.venv` 테스트 기준선을 만든다.
3. Track 3에서 seed 확장부터 시작한다.
4. Track 3의 baseline/cross-dataset을 병렬로 진행한다.
5. Track 4는 Track 3의 초기 결과를 본 뒤 착수한다.

## 6) 이번 세션에서 바로 시작할 항목

- [x] status 문서 추가 및 README 연결
- [x] `.venv`에서 dev/test 실행 가능 여부 확인
- [x] reproducibility/path 이슈를 수정할 첫 패치 세트 정의 및 적용
- [x] 이후 seed 확장 실험을 위한 실행 명령/설정 후보 정리

## 7) 이번 세션에서 완료한 즉시 조치

- [x] `scripts/run_phase2.py`가 `phase2_manifest.json`에 절대경로 대신 상대경로를 기록하도록 수정
- [x] 기존 Phase-2 manifest 2개를 상대경로 형식으로 정리
- [x] `configs/phase2_collect300_n200.yaml`에 shared collection root 재사용 의도를 주석으로 명시
- [x] `.venv`에 `.[dev]` 설치
- [x] `mobse/report.py`에서 headless/temp-dir 환경에서도 `report`가 동작하도록 Matplotlib 설정 보완
- [x] 전체 테스트 재실행

검증 결과:

- Python: `.venv` 기준 `3.11.15`
- 명령: `./.venv/bin/python -m pytest -q`
- 결과: `16 passed`

## 8) 다음 실행 자산 준비 상태

추가로 아래 follow-up 자산을 준비했다.

- multiseed follow-up 공용 런너:
  - `scripts/run_multiseed_followup.py`
- `n100 best` 5-seed config:
  - `configs/2026-03-23/phase2_best5_n100.yaml`
- `n200 best` 5-seed config:
  - `configs/2026-03-23/phase2_best5_n200.yaml`

즉시 실행 명령:

```bash
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-23/phase2_best5_n100.yaml --no-progress
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-23/phase2_best5_n200.yaml --no-progress
```

이 두 런은 서로 다른 `run_id`를 사용하므로 병렬 실행이 가능하다.

## 9) 5-seed Follow-up 결과 반영

`n100 best` vs `n200 best` follow-up을 `5` seeds로 확장해 완료했다.

- 비교 노트:
  - `docs/experiments/phase2_followup_2026-03-23.md`
- 비교 산출물:
  - `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_ds00_adult300_n200_best5_20260323/reports/followup_summary.csv`
  - `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_ds00_adult300_n200_best5_20260323/reports/followup_paired_stats.csv`

핵심 반영:

- `n100` 우세 방향은 유지됨
- 성능 차이는 여전히 비유의
- 효율 차이(latency/FLOPs)는 더 강하게 유지됨
- 따라서 다음 메인라인은 `n100` 기준 baseline 비교가 적절함

## 10) Baseline Wave 시작 상태

자동 baseline wave를 `n100` 기준으로 시작했다.

- `transformer`:
  - config: `configs/2026-03-23/phase2_baseline_transformer_n100.yaml`
  - status: running
- `sparse_transformer`:
  - config: `configs/2026-03-23/phase2_baseline_sparse_transformer_n100.yaml`
  - status: running
- `moe`:
  - config: `configs/2026-03-23/phase2_baseline_moe_n100.yaml`
  - status: completed

`moe` partial comparison 결과:

- compare outputs:
  - `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_baseline_moe_n100_20260323/reports/followup_summary.csv`
  - `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_baseline_moe_n100_20260323/reports/followup_paired_stats.csv`
- summary:
  - MoE는 OS accuracy와 ETTh1 MSE에서 수치상 우세
  - MoBSE는 OS F1과 ETTh1 MAE에서 수치상 우세
  - MoE는 latency/FLOPs에서 큰 폭으로 우세

현재 의미:

- baseline wave의 첫 결과만 보면 `MoE`가 강한 경쟁 후보로 올라왔음
- 최종 판정은 `transformer` / `sparse_transformer` 완료 후 내려야 함

## 11) Baseline Wave 완료 및 Mainline 재선정

- baseline wave는 모두 완료됐다.
- 상세 문서:
  - `docs/experiments/baseline_benchmark_2026-03-23.md`
- 결론:
  - `MoE n100`이 현재 public-data mainline candidate가 됨
  - `MoBSE n100`은 comparator로 유지

검증 기준:

- `.venv` 기준 전체 테스트 재실행
- 결과: `17 passed, 3 warnings`

## 12) Cross-Dataset Generalization 완료

Stage D를 위해 subject-prefix 기반 split을 추가했다.

## 13) OpenNeuro Extension Track 시작

HCP nuisance confirmation은 현재 raw input 부재로 막혀 있다.

그래서 다음 메인라인 확장 축은 기존 OpenNeuro code path를 그대로 사용하는 public cohort extension으로 잡는다.

- 근거 문서:
  - `docs/experiments/openneuro_extension_2026-03-24.md`
- scan basis:
  - `artifacts/phase2_ds00_scan_20260314/reports/ds00_scan.csv`
- next dataset mix:
  - `ds000030 + ds000243 + ds001461`
- next mainline config:
  - `configs/2026-03-24/phase2_openneuro450_gsr_moe_n100.yaml`

현재 의도:

- best current stack인 `MoE n100 + gsr_only`를 유지
- adult `450` subject 확장 wave를 기존 자동화 경로(`prepare_data -> build_templates -> multiseed`)로 실행
- 완료 후 현재 public mainline `phase2_nuis_gsr_only_moe_n100_20260324`와 paired comparison 수행

추가 진행:

- `450` wave는 완료됨
- broad `ds*` scan 결과를 바탕으로 `600` subject 확장 wave를 새 메인라인 후보로 시작
- target dataset mix:
  - `ds000030 + ds000243 + ds001461 + ds000208 + ds000245 + ds000210`

strict-usable 재평가:

- raw `600`은 strict usable `600`이 아님
- observed strict usable count는 `443`
- 새 planning artifact:
  - `docs/experiments/openneuro_usable_plan_2026-03-24.md`
  - `artifacts/openneuro_usable_plan_20260324/reports/openneuro_usable_yield_table.csv`
- current strict keep set projected usable total: `458`
- 따라서 다음 collector는 raw target이 아니라 usable target semantics로 바뀌어야 함

- 코드 변경:
  - `subject_ids` 저장/로드 지원
  - `train_subject_prefixes` / `val_subject_prefixes` / `test_subject_prefixes` config 추가
- 상세 문서:
  - `docs/experiments/cross_dataset_2026-03-23.md`

실행 방향:

1. `train ds000030 -> test ds000243`
2. `train ds000243 -> test ds000030`

핵심 결과:

- `MoE n100`은 두 방향 모두에서 public-data mainline 대비 harmful transfer drop이 관찰되지 않음
- `MoBSE n100`은 일부 OS metric에서 강하나, ET forecasting과 효율에서 `MoE`가 더 안정적

판정:

- Stage D: `pass`

## 13) HCP-Accessible Validation 완료

로컬에서 확인한 HCP 계열 데이터:

- `data/reference_raw/openneuro_abide127/timeseries/100`: `127` subjects
- `data/reference_raw/openneuro_abide152/timeseries/100`: `152` subjects

이번 턴에서는 `hc127` cohort로 Stage E를 먼저 실행한 뒤, 곧바로 `152-subject` recovery rerun까지 이어갔다.

- 상세 문서:
  - `docs/experiments/hcp_validation_2026-03-23.md`
- 실행 run:
  - `phase2_openneuro_abide127_moe_n100_20260323`
  - `phase2_openneuro_abide127_mobse_n100_20260323`

핵심 결과:

- `hc127` first pass:
  - `MoE n100`이 HCP cohort에서도 `MoBSE n100`보다 나은 operating point를 유지
  - ETTh1 MAE는 public-data mainline 대비 `+0.0289`로 target band 안에 있음
  - latency / FLOPs 방향도 그대로 유지됨
  - 그러나 OS accuracy는 public-data mainline 대비 `-0.0299`로 떨어져 threshold(`<= 0.02`)를 넘김
- `hcp152` recovery rerun:
  - `MoE n100` OS accuracy는 public-data mainline 대비 `-0.0133`로 회복
  - ETTh1 MAE delta는 `+0.0051`
  - ETTh1 MSE delta는 `+0.3287`
  - Stage E band 안으로 들어옴

판정:

- Stage E: `pass after recovery rerun`

## 14) 현재 프로젝트 상태와 다음 순서

현재 판단:

- reproducibility gate: `pass`
- seed follow-up: `done`
- baseline benchmark gate: `done`
- cross-dataset gate: `pass`
- HCP-accessible validation gate: `pass`

OpenNeuro strict-usable track 기준으로는 아래가 추가로 확정됐다.

- `usable_target_subjects` + `dataset_chunk_size` collector redesign 구현 완료
- strict collector는 이제 raw count가 아니라 accepted usable subject count를 기준으로 멈춤
- `ds000172` strict pilot 결과는 `0 / 13 accepted`
  - 실패 사유는 전부 `node_mismatch`
  - 따라서 `ds000172`는 keep 후보가 아니라 drop 후보로 재분류하는 편이 맞음
- `250`-dataset broad scan은 raw rest-like adult 후보를 더 찾았지만, 아직 strict usable evidence는 없음
  - 신규 pilot 우선 후보:
    - `ds001747`
    - `ds001796`
    - `ds001386`
    - `ds001771`
  - broad-scan selected set raw adult 합계는 `877`

따라서 현재 다음 순서는 아래처럼 정리된다.

1. `ds001747`, `ds001796`, `ds001386`, `ds001771`에 strict usable pilot 적용
2. strict usable yield table 갱신
3. projected usable total이 `600+`가 되는 mix가 확인될 때만 full rerun 착수

즉, 지금 상태는:

- public benchmark claim은 상당히 단단해짐
- cross-dataset generalization도 통과
- HCP-accessible validation도 recovery rerun까지 포함하면 목표 band 안으로 들어옴

다음 순차 작업:

1. `128` / `150` intermediate node sweep
2. locked `MoE n100` 기준 nuisance sensitivity matrix 실행
3. 필요 시 epoch-budget sensitivity를 별도 축으로 분리

## 15) Nuisance Sensitivity 완료

관련 문서:

- `docs/experiments/nuisance_sensitivity_2026-03-24.md`

실행 결과:

- `paper_compcor_gsr` baseline 유지
- `compcor_only` 추가 실행 완료
- `gsr_only` 추가 실행 완료

핵심 판정:

- 두 단순화 variant 모두 predictive metric을 크게 흔들지 않음
- `gsr_only`는 baseline 대비 latency 개선이 가장 뚜렷함
- 따라서 nuisance 축에서는 `gsr_only`가 다음 confirmation candidate가 됨

추가 제약:

- 계획했던 `128` / `150` node sweep은 Schaefer atlas 지원 범위 밖이라 현재 pipeline에서는 불가
- 다음 feasible node 확장은 `300`

현재 남은 순차 작업:

1. `gsr_only` nuisance candidate로 public or HCP confirmation rerun
2. 필요하면 Schaefer `300` node 확장 또는 atlas 변경 검토
3. 이후에만 node-axis claim을 재개

추가 확인:

- public `gsr_only` confirmation은 완료
- HCP `gsr_only` confirmation은 현재 로컬에 raw HCP NIfTI/manifest가 없어 blocked

따라서 실질적인 다음 순서는:

1. HCP raw input 확보 또는 manifest 작성
2. 또는 node-axis를 Schaefer `300` / atlas 변경 트랙으로 분기
