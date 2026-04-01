# MoBSE Experiments Note (1차 정리, 2026-03-13)

## 1) 목적과 범위

- 목적: MoBSE PoC v1의 end-to-end 재현 파이프라인(prepare/build/train/evaluate/report) 구축 및 HC127 기준 100/200-node 비교.
- 범위: 단일 GPU(MPS) 기준 실행, OpenNeuro `ds000030` 기반 HC 필터, 이중 태스크(`os` + `etth1`) 학습/평가.

## 2) 시간대별 수행 기록 (KST)

| 시간(KST)   | run_id                                                                          | 수행 내용                                        | 결과                                 |
| ----------- | ------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------ |
| 01:24~01:27 | `20260313_012448`, `progress_smoke`                                         | 초기 골격 검증(build/train/eval/report)          | 파이프라인 기본 동작 확인            |
| 01:32~01:34 | `mps_2sub_test`                                                               | MPS 2-sub 스모크 E2E                             | 전 명령 성공                         |
| 01:35~02:11 | `20260313_013540`, `20260313_021111`                                        | OpenNeuro fetch/prepare 반복 점검                | 데이터 준비 완료                     |
| 02:41~02:43 | `poc1_hc127_mps100`                                                           | HC127 100-node 1차 학습/평가                     | 성능 저조, 개선 필요 확인            |
| 08:32~08:38 | `poc1_hc127_mps100_full`, `poc1_hc127_mps200_full`, `poc1_hc127_analysis` | 100/200-node baseline 비교 및 리포트             | 200-node는 비용 증가, 분류 성능 약세 |
| 19:48~20:09 | `os_fetch_smoke_real`                                                         | 실제 fetch 병목 수정 후 E2E 재검증               | 인덱싱 병목 해소, E2E 정상           |
| 20:15~20:18 | `poc1_hc127_mps100_balanced`                                                  | loss 안정화 패치 검증 런                         | 분류 지표 개선 확인                  |
| 20:22~20:42 | `poc1_hc127_mps100_balanced3`, `poc1_hc127_mps200_balanced3`                | 3-seed(42/43/44) 비교 실험                       | mean/std 비교 완성                   |
| 21:46~21:48 | `os_fetch_regression_check`                                                   | nuisance regression 적용 후 재준비 + 템플릿 빌드 | 적용 로그/출력 확인                  |

## 3) 코드 적용 사항 (핵심)

### A. 파이프라인/네이밍 정리

- `hcp_*` 중심 키를 `os_*`로 리팩토링 + 하위 호환 alias 유지.
- CLI 4종(`build_templates`, `train`, `evaluate`, `report`) 및 진행 로그 표준화.

### B. OpenNeuro fetch 병목 해결

- 증상: 전체 트리 전수 순회로 `tree_calls` 급증.
- 적용: `participants.tsv` 선조회 후 선택 subject만 재귀 스캔, 중복 key 방문 방지.
- 결과: 스모크 기준 인덱싱 호출 수 대폭 감소(1000+ -> 약 10대 수준).

### C. 학습 loss 안정화(이중 태스크)

- ETTh1 손실 함수 선택형 도입(`huber|mse|mae`, 기본 `huber`).
- 태스크별 초기 loss scale 정규화 후 가중 합산.
- checkpoint 선택 기준을 `weighted_normalized_loss`로 변경.
- early stopping 도입(`patience=3`, `min_delta=0.0005`).
- 최종 test는 항상 best checkpoint 로드 후 평가.

### D. 아티팩트 오염 방지

- 문제: `glob latest`가 다른 run의 템플릿/윈도우를 잡는 케이스 발생.
- 적용: 현재 `run_id` 경로 우선 해석 후 fallback glob.
- 테스트 추가: run-local 우선 선택 보장.

### E. nuisance regression (최근 근거 기반)

- 기본 전략: `paper_compcor_gsr`
  - CompCor-like(high variance confounds, 기본 5)
  - GSR
  - confound derivative + quadratic 확장
  - detrend + band-pass(0.008~0.1 Hz)
- 적용 경로: `openneuro_hc`, `public_proxy`, manifest 기반 추출.
- 설정 키: `data.os.nuisance_*`.

## 4) 극복한 사항(문제 -> 대응)

1. HCP 직접 접근 제약

- 대응: OpenNeuro `ds000030` + participants 필터(`CONTROL`, `age>=18`, `rest`)로 대체.

2. fetch 시간 과다

- 대응: subject-restricted 인덱싱 + visited/queued key 제어로 병목 제거.

3. 분류 신호가 예측 손실에 묻힘

- 대응: 정규화 기반 멀티태스크 loss + Huber + early stopping.

4. 실험 재현성 오염(run 간 입력 섞임)

- 대응: template/windows 입력 경로를 run-local 우선으로 고정.

5. raw ds000030에서 confounds TSV 부재

- 대응: 완전 24P/36P 대체는 불가하므로 CompCor-like+GSR+filter로 근사 적용.

## 5) 1차 결과 요약

### Balanced 3-seed 비교 (HC127)

- 결과 파일:

  - `artifacts/poc1_hc127_balanced3_compare/reports/summary_mean_std.csv`
  - `artifacts/poc1_hc127_balanced3_compare/reports/seed_metrics.csv`
  - `artifacts/poc1_hc127_balanced3_compare/reports/delta_200_minus_100.json`
- 요약:

  - 100-node: OS Accuracy `0.1469 ± 0.0239`, OS F1 `0.1141 ± 0.0087`
  - 200-node: OS Accuracy `0.1099 ± 0.0049`, OS F1 `0.0949 ± 0.0093`
  - ETTh1 MSE는 200-node 평균이 소폭 낮지만 분산이 큼.
  - 분류 기준으로 1차 결론은 100-node 우세.

### nuisance 적용 후 데이터 체크

- 실행: `os_fetch_regression_check`
- 로그: `artifacts/os_fetch_regression_check/logs/prepare_data.json`
- 시계열 점검: `artifacts/os_fetch_regression_check/reports/data_check_timeseries.json`
- 확인:
  - nuisance 설정값이 결과 JSON에 기록됨.
  - NaN 없음.
  - 일부 subject에서 atlas 라벨 소실로 ROI 수가 100보다 작아질 수 있음(예: 96).

## 6) 아카이브 및 최종 YAML

- 사용 config 아카이브:
  - `configs/archive/2026-03-13/source_configs/`
  - `configs/archive/2026-03-13/resolved_configs/`
  - `configs/archive/2026-03-13/manifest.json` (SHA256 포함)
- GitHub 업로드용 일반화 최종 설정:
  - `configs/config.yaml`

## 7) 2026-03-14 Phase-1 잔여 작업 진행 결과

### 실행 런

- `phase1_nr_hc127_mps100_bal3_20260314`
- `phase1_nr_hc127_mps200_bal3_20260314`

### 비교 산출물

- `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/seed_metrics.csv`
- `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/summary_mean_std.csv`
- `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/significance_paired_ttest.csv`
- `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/delta_200_minus_100.json`
- `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/repro_manifest.json`

### 요약 (3-seed, mean±std)

- 100-node: Accuracy `0.1469±0.0239`, F1 `0.1141±0.0087`, MAE `2.2257±0.0168`, MSE `8.8458±0.1782`
- 200-node: Accuracy `0.1099±0.0049`, F1 `0.0949±0.0093`, MAE `2.2380±0.1987`, MSE `8.7316±1.7394`
- latency(평균): OS `2.54ms -> 8.80ms`, ETTh1 `2.23ms -> 7.80ms` (100 -> 200)

### 통계(paired t-test, seed=42/43/44)

- 분류 지표(Accuracy/F1) 차이는 p<0.05 미달.
- 예측 지표(MAE/MSE) 차이는 p<0.05 미달.
- latency 증가는 유의함:
  - `os_latency_ms_mean`: p=`0.0093`
  - `etth1_latency_ms_mean`: p=`0.0165`

### 운영 이슈 및 대응

- `prepare_data --mode openneuro_hc --subjects 127` 재실행 시 OpenNeuro GraphQL index 단계가 장시간 소요되어 본 실험은 기존 HC127 timeseries로 진행.
- 평가 중 `Too many open files in system` 발생 시, 비실험 VSCode Python language-server 프로세스 정리 후 seed 평가 재개.
- MPS 환경에서 `peak_memory_mb`가 0으로 보고될 수 있어, 현재 해석은 FLOPs/latency 중심으로 수행.

## 8) 2026-03-14 OpenNeuro 다중 데이터셋 대응(Child 포함 데이터 회피)

### 코드 변경

- `prepare_data` CLI에 `--openneuro-datasets "dsA,dsB,..."` 추가.
- `--openneuro-task`에 다중 task 이름(`rest,restingstate`) 허용 추가.
- 다중 dataset 순차 수집 로직 추가:
  - 앞 dataset 실패/부적합 시 skip하고 다음 dataset으로 진행.
  - 목표 subject 수를 채울 때까지 반복.
- multi-dataset subject 충돌 방지:
  - 저장 키를 `{dataset_id}_{participant_id}`로 통일.
- 진단 라벨 매칭 유연화:
  - `CONTROL`, `HEALTHY CONTROL`, `HC` 등 표기 변형 대응(콤마/파이프 multi-token 허용).

### 실제 fetch 스모크 결과

- 테스트 1 (strict HC + fallback):
  - 명령: `--mode openneuro_hc --openneuro-datasets "ds002785,ds000030" --openneuro-task rest --subjects 2`
  - 결과: `ds002785`는 `diagnosis/group` 컬럼 부재로 skip, `ds000030`에서 성인 HC 2명 수집 성공.
- 테스트 2 (adult-only on alternative dataset):
  - 명령: `--mode openneuro --openneuro-dataset ds002790 --openneuro-task restingstate --min-age 18 --subjects 2`
  - 결과: 성인 2명 수집 성공(`participants.tsv` age 필터 적용).

### 해석

- child 포함 dataset이라도 `openneuro` 모드에서 `--min-age`로 성인 선별은 가능.
- HC 라벨이 필요한 경우(`openneuro_hc`)에는 dataset의 `participants.tsv`에 진단/그룹 컬럼이 반드시 있어야 함.

## 9) 2026-03-14 Phase-2 목표 상향 (최소 300명)

- 목표 변경: Phase-2 수집 목표를 `150`에서 `>=300`으로 상향.
- ds00* 스캔 결과 산출물:
  - `artifacts/phase2_ds00_scan_20260314/reports/ds00_scan.csv`
  - `artifacts/phase2_ds00_scan_20260314/reports/phase2_dataset_pick.json`
- 자동 선택 결과(성인, rest/restingstate 기준):
  - `ds000030` (adult 272)
  - `ds000243` (adult 120)
  - 추정 합계: 392 (300 목표 충족)

## 10) 2026-03-14 Phase-2 실행 완료 (300명, n100 경로)

- 데이터 준비:
  - config: `configs/phase2_collect300_n100.yaml`
  - 실행: `prepare_data --mode openneuro --subjects 300 --openneuro-datasets "ds000030,ds000243" --openneuro-task "rest,restingstate" --min-age 18`
  - 결과: `collected_subjects=300`, `timeseries/100` subject dir 300개 확인.
- Phase-2 러너:
  - study id: `phase2_ds00_adult300_n100_20260314`
  - 실행 옵션: `--nodes 100 --quick-epochs 2 --bal-epochs 4`
  - 산출물:
    - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv`
    - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_summary.csv`
    - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_manifest.json`
- 최종 분석 보고서:
  - `docs/experiments/phase2_report_2026-03-14.md`
  - 핵심(best run, bal3): OS Accuracy `0.1856 ± 0.0251`, OS F1 `0.0948 ± 0.0082`, ETTh1 MAE `2.2183 ± 0.1366`, MSE `8.3439 ± 1.2218`.
