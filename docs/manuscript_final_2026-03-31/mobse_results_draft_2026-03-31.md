# MoBSE Results Draft (2026-03-31)

## Results

### R1. Main benchmark under matched compute (ABIDE vs fair simulation)

우리는 ABIDE 성인 대조군(`n=143`)과 공정 비교 시뮬레이션(`n=150`)에서, 동일한 모델/연산 조건(`nodes=200`, `experts=7`, `states=7`, OS task, FLOPs/latency scale matching)으로 성능을 비교했다. 비교 결과, 시간창 단위 뇌 상태 분류(OS)에서 ABIDE 조건이 시뮬레이션 대비 현저히 우수한 분류 성능을 보였다(Table 1, Fig2). 구체적으로 loss는 `0.0033` 대 `1.9671`, accuracy는 `1.0000` 대 `0.1324`, F1-macro는 `1.0000` 대 `0.1072`였다.

연산 효율 관점에서는 두 조건이 사실상 동일한 계산량을 유지했다(FLOPs `86.38M` vs `86.38M`; Fig3). 평균 추론 지연시간도 `2.4946 ms` 대 `2.4907 ms`로 거의 차이가 없었다. 즉, 본 결과는 단순한 계산량 증가에 따른 성능 향상이 아니라, 동일한 연산 제약 하에서 human rs-fMRI 축이 제공하는 정보 구조의 차이를 반영한다.

### R2. Mechanism-level interpretation from expert routing

성능 차이와 함께, 전문가 라우팅 특성에서도 해석 가능한 분화가 관찰되었다(Fig5). 라우팅 엔트로피는 ABIDE에서 더 낮았으며(`0.6098` vs `0.6692`), 이는 전문가 선택이 더 집중된 방향으로 형성되었음을 시사한다. 반면 라우팅 안정성은 시뮬레이션 조건이 더 높게 나타났으나(`0.8738` vs `0.7537`), 이는 상태 생성 방식과 클래스 분리 구조가 더 균질한 시뮬레이션 조건의 특성을 반영할 가능성이 있다.

핵심적으로, MoBSE는 고정 Yeo-7 좌표 위에서 전문가 분화를 학습하므로, 성능 지표를 네트워크 수준 해석과 연결할 수 있다. 이 점은 정확도 중심 비교를 넘어, 모델 동작을 신경과학적 좌표계 안에서 읽을 수 있게 한다.

### R3. Supporting context (auxiliary panel)

보조 패널(ETTh1)에서는 ABIDE와 시뮬레이션 간 차이가 OS만큼 크지 않았다(Fig4). ETTh1에서 loss/MAE/MSE는 각각 `8.5571/9.0553/90.0482`(ABIDE), `8.5042/9.0023/89.1771`(simulation)로 유사 범위였다. 또한 latency와 FLOPs는 동일 수준을 유지했다(`2.0813 ms` vs `2.0795 ms`, `86.38M` vs `86.38M`).

이 결과는 본 논문의 1차 주장 축이 ETTh1 보조 과제가 아니라, OS 기반 human-network 해석 축임을 뒷받침한다. 따라서 ETTh1 결과는 모델 일반 동작 맥락을 제공하는 보조 증거로 제시하고, 주된 결론은 OS 성능 및 라우팅 해석 결과에서 도출한다.

### Summary of findings

본 연구의 결과는 다음 세 가지로 요약된다.  
첫째, 동일 연산 제약에서 ABIDE 기반 MoBSE가 시뮬레이션 대비 월등한 OS 분류 성능을 보였다.  
둘째, ABIDE 조건에서 더 집중된 라우팅 엔트로피 패턴이 나타나, 전문가 분화의 메커니즘 해석 가능성을 강화했다.  
셋째, 보조 패널(ETTh1)에서는 대규모 성능 역전이 나타나지 않아, 본 논문의 주된 기여가 human rs-fMRI 기반 해석 축에 있음을 재확인했다.

### R4. ETTh1 completion and ETT-family extension (2026-03-31)

ETTh1 storyline 핵심 그림(F1-F5)은 최신 아티팩트 구조 기준으로 재생성했다. 추가 일반화 점검으로 ETT-family(ETTh2/ETTm1/ETTm2)를 동일 `moe n100` 설정에서 소규모 멀티시드(`seeds=[42,43,44]`)로 테스트했다.

`s=3` 요약 결과:
- ETTh1: `MAE 2.1744`, `MSE 8.1966`
- ETTh2: `MAE 5.3991`, `MSE 47.6898`
- ETTm1: `MAE 1.3060`, `MSE 3.1910`
- ETTm2: `MAE 4.1037`, `MSE 27.0113`

ETT-family 간 latency/FLOPs는 사실상 동일 스케일(`~0.33ms`, `2,960,608 FLOPs`)로 유지되어, 데이터셋 난이도 차이가 오차 스케일 차이로 반영됨을 확인했다.

### R4-Update. Full-line rerun with 10 seeds (paper-grade)

위 R4의 `s=3` 확장은 예비 점검으로 유지하고, 본문 보고용 수치는 `10-seed full-line rerun`으로 교체했다.

- Storyline 4-run(ETTh1-only/dual-task x mean/GRU) 모두 `seeds=[42..51]`로 재실행
- ETT-family 확장(ETTh2/ETTm1/ETTm2)도 동일 10-seed로 재실행

`s=10` ETT-family 요약:
- ETTh1: `MAE 2.2621`, `MSE 8.6578`
- ETTh2: `MAE 5.4920`, `MSE 49.2933`
- ETTm1: `MAE 1.3126`, `MSE 3.1803`
- ETTm2: `MAE 4.1289`, `MSE 27.1469`

### R5. Reproducibility check (old vs rerun10)

기존 2026-03-27 결과와 2026-03-31 `rerun10` 결과를 정면 비교한 결과, 핵심 결론 지표는 재현되었다.

- 4개 storyline 조건에서 ETTh1 `MAE/MSE` 평균값은 기존과 동일했다.
- 4개 storyline 조건에서 OS `accuracy/F1` 평균값도 기존과 동일했다.
- `FLOPs`는 동일했고, 차이는 주로 `profile latency`에만 국한되었다.

따라서 본문의 결론은 아래처럼 고정한다.

1. 성능/통계 결론은 기존 결과와 일관적으로 재현되었다.
2. latency 차이는 런타임 프로파일 변동으로 해석하며, 주된 주장 축(오차/분류 성능)은 변하지 않는다.
3. 본문 본표/본문 수치는 `rerun10`을 기준으로 보고하고, `s=3`은 보조/예비 결과로만 유지한다.

### R6. Hypothesis-linked statistical evidence (added)

컨셉 노트의 "전문가 분화" 가설을 수치로 연결하면 다음과 같다.

1. Mean encoder에서 dual-task vs etth1-only  
- ETTh1 `MSE`는 dual-task가 개선되었다(`-0.7982`, paired t-test `p=0.0186`, Wilcoxon `p=0.0098`).  
- OS `accuracy`는 dual-task에서 낮아졌다(`-0.0228`, paired t-test `p=0.00156`).  
-> 해석: 멀티태스크 결합은 forecasting 측면 이점이 있으나, OS 분류에서는 trade-off가 존재한다.

2. GRU encoder vs mean encoder  
- ETTh1 `MAE/MSE`는 GRU가 크게 개선되었다(예: etth1-only 기준 `MAE -0.8035`, `p=2.60e-08`; `MSE -4.9466`, `p=2.77e-08`).  
- 동시에 ETTh1 profile latency는 증가했다(`+2.2458 ms`, `p=1.83e-18`).  
-> 해석: 정확도-효율 Pareto 상의 구조적 trade-off가 명확하다.

3. ETT-family 10-seed extension  
- 동일 FLOPs(`2,960,608`) 조건에서 데이터셋별 오차 스케일이 분화되었다(ETTm1 best, ETTh2 hardest).  
-> 해석: 연산량 차이 없이 데이터셋 난이도/구조 차이가 성능을 결정한다는 본문 축과 정합적이다.

현재 증거선으로 강하게 지지되는 것은 `H2/H3`이고, `H1`은 라우팅 해석 축에서 부분 지지다. `H4/H5`는 2026-03-31 robustness wave로 1차 검증을 완료했다.

### R7. Robustness wave (strict split + nuisance sensitivity)

`2026-03-31`에 수행한 robustness wave는 두 축으로 구성된다.

1. Strict subject-level split (ABIDE vs fair simulation, 10 seeds)
- ABIDE strict: accuracy `0.9998 ± 0.0004`, F1 `0.9998 ± 0.0004`, loss `0.00265 ± 0.00053`
- Simulation strict: accuracy `0.1448 ± 0.0019`, F1 `0.0915 ± 0.0110`, loss `1.9500 ± 0.0020`
- Paired 결과(ABIDE - Simulation):
  - accuracy diff `+0.8550`, `p=1.21e-25` (ttest), `p=0.00195` (Wilcoxon)
  - F1 diff `+0.9083`, `p=9.16e-19` (ttest), `p=0.00195` (Wilcoxon)
  - latency diff `+0.0417 ms`, `p=0.429` (ns)
- 해석: window-level leakage 우려를 제거한 strict split에서도 핵심 OS 격차는 유지되며, 계산량(FLOPs)은 동일하다.

2. Nuisance sensitivity (MoBSE n100, 10 seeds)
- paper stack(`paper_compcor_gsr`) vs compcor_only:
  - OS accuracy/F1 및 ETTh1 MAE/MSE는 유의 차이 없음
  - OS latency는 compcor_only가 느림(diff `-0.0770 ms`, `p=0.0242`)
- paper stack vs gsr_only:
  - OS accuracy는 paper stack이 높음(diff `+0.0252`, `p=0.00293`)
  - ETTh1 MAE/MSE는 paper stack이 더 낮음(diff `-0.1628`, `p=0.0123`; diff `-1.1258`, `p=0.0236`)
  - ETTh1 latency도 paper stack이 더 낮음(diff `-0.0404 ms`, `p=0.0113`)
- 해석: 본 설정에서는 paper stack이 가장 안정적인 주 실험선이며, 단순화 preset은 “대체 가능”보다는 “민감도 경계 확인” 용도로 해석하는 것이 타당하다.

## Table 1. Main OS metrics under matched setting

| Metric | ABIDE (n=143) | Simulation (n=150) |
|---|---:|---:|
| Loss | 0.0033 | 1.9671 |
| Accuracy | 1.0000 | 0.1324 |
| F1-macro | 1.0000 | 0.1072 |
| Routing entropy | 0.6098 | 0.6692 |
| Routing stability | 0.7537 | 0.8738 |
| Latency (ms) | 2.4946 | 2.4907 |
| FLOPs | 86.38M | 86.38M |

## Figure mapping (locked)

- Fig1: storyline framework
- Fig2: OS core results (classification)
- Fig3: OS profile (latency/FLOPs)
- Fig4: ETTh1 auxiliary context
- Fig5: OS routing usage by network
- Fig6: mainline quality summary dashboard

## Source artifacts used

- `artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/abide_vs_simul_eval_report.md`
- `artifacts/current_canonical/abide_mobse_mainline_20260330/reports/mobse_mainline_summary.csv`
- `artifacts/current_canonical/mobse_paper_lock_20260330/figures/`
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/`
- `artifacts/current_canonical/ett_family_extension_20260331/reports/ett_family_summary_s3.csv`
- `docs/experiments/archive_derived_2026-03-31/etth1_ett_family_extension_2026-03-31.md`
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/`
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv`
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv`
- `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv`
- `docs/experiments/archive_derived_2026-03-31/etth1_full_line_rerun_2026-03-31.md`
- `artifacts/current_canonical/strict_split_wave_20260331/reports/strict_split_summary.csv`
- `artifacts/current_canonical/strict_split_wave_20260331/reports/strict_split_paired_stats.csv`
- `artifacts/current_canonical/nuisance_wave_mobse_20260331/reports/nuisance_benchmark_summary.csv`
- `artifacts/current_canonical/nuisance_wave_mobse_20260331/reports/paired_stats_paper_vs_compcor_only.csv`
- `artifacts/current_canonical/nuisance_wave_mobse_20260331/reports/paired_stats_paper_vs_gsr_only.csv`
