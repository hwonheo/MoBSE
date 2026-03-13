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
