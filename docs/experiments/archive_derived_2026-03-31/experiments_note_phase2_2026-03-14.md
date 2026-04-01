# Phase-2 Experiments Note (2026-03-14)

## 0) 요약

- 목적: OpenNeuro `ds00*` 범위에서 성인 데이터를 모아 **최소 300명**으로 Phase-2 검증 수행.
- 결과: `ds000030 + ds000243` 조합으로 300명 수집 완료 후, n100/n200 경로 Phase-2 스윕/밸런스드 재실험/통계/그림 생성 완료.
- 핵심 산출물:
  - `artifacts/phase2_ds00_scan_20260314/reports/phase2_dataset_pick.json`
  - `artifacts/phase2_collect300_ds00_n100_20260314/logs/prepare_data.json`
  - `artifacts/phase2_collect300_ds00_n200_20260314/logs/prepare_data.json`
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_manifest.json`
  - `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_manifest.json`
  - `docs/experiments/phase2_report_2026-03-14.md`

## 1) 목표와 완료 기준

- 목표:
  - Phase-2 데이터 목표를 기존 150 수준에서 **>=300**으로 상향.
  - 공개 데이터만으로 재현 가능한 수집/학습/평가 경로 확보.
  - 핵심 ablation 축(희소도, 라우팅, template prior) 성능 비교.
- 완료 기준:
  - 성인 기준 300명 timeseries 생성.
  - sweep(seed=42) + top3 bal3(seed=42/43/44) 실행 완료.
  - 결과 CSV/manifest/요약 문서 생성 완료.

## 2) 실행 계획 (원안 대비)

- 원안:
  - 100/200 노드 동시 대규모 수집 및 전체 매트릭스 실행.
- 실제 실행:
  - 300명 수집 구간의 소요시간/자원 이슈를 고려해 **n100 우선 경로**로 Phase-2 완료.
  - `run_phase2.py`에 실행 파라미터를 추가해 노드/epoch를 제어 가능하게 변경.

## 3) 데이터셋 선정 (ds00* 스캔)

- 스캔 스크립트:
  - `scripts/scan_openneuro_ds00.py`
- 스캔 기준:
  - prefix: `ds00`
  - age filter: `>=18`
  - task filter: `rest,restingstate`
  - participants.tsv 존재/컬럼 가용성 확인
- 결과:
  - pick 파일: `artifacts/phase2_ds00_scan_20260314/reports/phase2_dataset_pick.json`
  - 선택 조합:
    - `ds000030` (adult 272, snapshot `1.0.0`)
    - `ds000243` (adult 120, snapshot `1.0.0`)
  - 추정 합계: 392 (목표 300 충족 가능)

## 4) 데이터 수집 실행

- 사용 config:
  - `configs/phase2_collect300_n100.yaml`
- 실행 명령:

```bash
./.venv/bin/python -m mobse.cli prepare_data \
  --config configs/phase2_collect300_n100.yaml \
  --mode openneuro \
  --subjects 300 \
  --min-age 18 \
  --openneuro-datasets "ds000030,ds000243" \
  --openneuro-task "rest,restingstate" \
  --no-progress
```

- 수집 결과:
  - `artifacts/phase2_collect300_ds00_n100_20260314/logs/prepare_data.json`
  - `collected_subjects=300`, `requested_subjects=300`
  - `os_stats.nodes_100=300`
  - timeseries 디렉토리 확인: `data/legacy_phase2/os_phase2_ds00_300_n100/timeseries/100` 하위 300 subject dir

## 5) Phase-2 실험 매트릭스

- 실행 스크립트:
  - `scripts/run_phase2.py`
- study id:
  - `phase2_ds00_adult300_n100_20260314`
- 실행 명령:

```bash
./.venv/bin/python scripts/run_phase2.py \
  --config configs/phase2_collect300_n100.yaml \
  --study-id phase2_ds00_adult300_n100_20260314 \
  --nodes 100 \
  --sparsities 0.1,0.2,0.3 \
  --routings soft,hard \
  --priors true,false \
  --quick-epochs 2 \
  --bal-epochs 4
```

- sweep 구성:
  - nodes=100만 사용
  - sparsity=0.1/0.2/0.3
  - routing=soft/hard
  - template_prior=true/false
  - 총 12 조합(seed=42)

## 6) 결과 요약

### 6.1 Sweep(seed=42)

- 결과 파일:
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv`
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_seed42.csv`
- Top-3:
  1. `n100_sp20_hard_prior` score `0.199765`
  2. `n100_sp20_soft_prior` score `0.198920`
  3. `n100_sp10_hard_prior` score `0.182302`

### 6.2 Top3 bal3(seed=42/43/44)

- 결과 파일:
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_seed_metrics.csv`
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_summary.csv`
- bal3 요약(스크립트 정렬 기준: `os_accuracy_mean`, `os_f1_macro_mean`):
  - best: `top_bal3_n100_sp10_hard_prior`
  - OS Accuracy `0.185577 ± 0.025149`
  - OS F1 `0.094829 ± 0.008173`
  - ETTh1 MAE `2.218275 ± 0.136640`
  - ETTh1 MSE `8.343863 ± 1.221771`
  - OS latency `2.965126 ms`, ETTh1 latency `2.725894 ms`

주의:
- sweep의 score 기준 top1(`sp20_hard_prior`)과 bal3 요약 top1(`sp10_hard_prior`)이 다를 수 있음.
- 이유: bal3 summary 정렬 기준이 score가 아니라 `accuracy/f1` 우선이기 때문.

## 7) 이슈와 대응

- 이슈 1: 대규모 OpenNeuro 인덱싱/다운로드 소요시간 증가
  - 대응: ds00* 사전 스캔으로 후보를 줄이고, 300명 충족 가능한 최소 조합(`ds000030+ds000243`) 확정.
- 이슈 2: 100/200 동시 수집 시 실험 완료 지연 위험
  - 대응: Phase-2 1차 완료를 위해 n100 우선 경로로 분리 실행.
- 이슈 3: 데이터셋 간 task 라벨 차이(`rest` vs `restingstate`)
  - 대응: `--openneuro-task "rest,restingstate"` 다중 task fallback 사용.

## 8) 재현 경로

### 8.1 데이터셋 스캔

```bash
./.venv/bin/python scripts/scan_openneuro_ds00.py \
  --max-datasets 160 \
  --target-subjects 300 \
  --out-dir artifacts/phase2_ds00_scan_20260314/reports
```

### 8.2 300명 수집(n100)

```bash
./.venv/bin/python -m mobse.cli prepare_data \
  --config configs/phase2_collect300_n100.yaml \
  --mode openneuro \
  --subjects 300 \
  --min-age 18 \
  --openneuro-datasets "ds000030,ds000243" \
  --openneuro-task "rest,restingstate" \
  --no-progress
```

### 8.3 Phase-2 실행

```bash
./.venv/bin/python scripts/run_phase2.py \
  --config configs/phase2_collect300_n100.yaml \
  --study-id phase2_ds00_adult300_n100_20260314 \
  --nodes 100 \
  --sparsities 0.1,0.2,0.3 \
  --routings soft,hard \
  --priors true,false \
  --quick-epochs 2 \
  --bal-epochs 4
```

### 8.4 최종 보고서 생성

```bash
./.venv/bin/python scripts/make_phase2_report.py \
  --study-id phase2_ds00_adult300_n100_20260314 \
  --scan-pick artifacts/phase2_ds00_scan_20260314/reports/phase2_dataset_pick.json \
  --out docs/experiments/phase2_report_2026-03-14.md
```

## 9) 요청된 다음 단계 적용 결과 (완료)

- 단계 1: 동일 데이터(300명) 기반 `n200` 경로 추가 실행
  - 완료:
    - 수집: `configs/phase2_collect300_n200.yaml`
    - 결과: `artifacts/phase2_collect300_ds00_n200_20260314/logs/prepare_data.json`
    - 실험: `phase2_ds00_adult300_n200_20260314`
    - 매니페스트: `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_manifest.json`
- 단계 2: bal3 통계 검정(p-value) 테이블 추가
  - 완료:
    - 스크립트: `scripts/phase2_stats.py`
    - n100 top3 pairwise: `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_pairwise_stats.csv`
    - n200 top3 pairwise: `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_top3_bal3_pairwise_stats.csv`
    - best(n100) vs best(n200):
      `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_best_vs_best_phase2_ds00_adult300_n100_20260314_vs_phase2_ds00_adult300_n200_20260314.csv`
- 단계 3: 논문/발표용 자동 그림 생성 확장
  - 완료:
    - 스크립트: `scripts/phase2_figures.py`
    - 산출물 디렉토리: `artifacts/phase2_figures_20260314_n100_n200/`
    - 포함 그림: accuracy-latency, mse-latency, accuracy-flops, routing entropy, routing usage

## 10) 핵심 관찰 (n100 vs n200)

- n100 best(`sp10 hard prior`) 대비 n200 best(`sp20 hard noprior`) 비교:
  - OS Accuracy: n100 우세 (`0.1856` vs `0.1620`)
  - ETTh1 MSE: n100 우세 (`8.3439` vs `10.2469`)
  - OS/ETTh1 latency: n100 우세 (`~3ms/~2.7ms` vs `~7.8ms/~6.9ms`)
  - FLOPs: n100 우세 (`22.9M` vs `92.8M`)
- 통계 해석:
  - seed=3 기준으로 성능 지표 p-value는 보수적 해석 필요(저검정력).
  - 효율 지표(지연/FLOPs)는 차이가 커서 우위가 일관되게 관찰됨.

## 11) 남은 후속 과제

- seed를 5~10으로 늘려 성능 지표의 검정력을 보강.
- n200에서 prior 성능 저하 원인 분석(라우팅 분포, 과적합/손실 스케일링 영향).
- 중간 노드(예: 150) 추가로 node-size tradeoff 곡선 정교화.
