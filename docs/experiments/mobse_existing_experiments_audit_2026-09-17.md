# 기존 MoBSE 실험 산출물 감사 및 재설계와의 대응

확인일: 2026-09-17. 사용자 요청에 따라 기존 결과를 먼저 확인함. 세 검토자가 strict/nuisance, ds000243 비교, legacy prior/cross-dataset을 나누어 읽었고 주검토자가 전체 inventory, ETTh1 및 April dFC 결과를 확인함. 모델 재학습·전체 checkpoint 추론·원본 fMRI 재처리는 수행하지 않음. 기존 artifact와 코드는 수정하지 않음.

## 1. 먼저 정정할 점

기존 검증이 없었던 것이 아님. **피험자 분리, seed 반복, nuisance 민감도, prior 유무, routing 방식, baseline 모델, 데이터셋 간 전이, 시간 encoder 비교가 이미 수행되었음.** 앞선 검토는 최근 PIOP1 실행선에 치우쳐 전체 실험 자산을 충분히 반영하지 못했음.

단, 기존 실험이 수행되었다는 사실과 새 독립 target에 대한 가설이 검증되었다는 사실은 다름. 새 계획은 처음부터 반복하는 것이 아니라, 기존 구현·대조·음성 결과를 재사용하면서 target 독립성과 template 학습 경계를 강화하는 것으로 수정함.

## 2. 전체 inventory

`artifacts/**/logs/train_summary.json` 352개를 읽어 resolved config와 seed 결과 및 같은 실행 폴더의 checkpoint 존재를 확인함.

| 항목 | 수 |
|---|---:|
| 학습 요약을 보유한 실행 폴더 | 352 |
| 대응 resolved config | 352 |
| 저장된 seed result record | 624 |
| 해당 폴더 내 `.pt` checkpoint 파일 | 624 |
| config의 model.arch=mobse | 154 |
| moe | 82 |
| transformer / sparse_transformer | 58 / 58 |

이는 **독립적인 352개 가설 검증이나 624개 독립 표본을 뜻하지 않음**. 동일 데이터·seed의 재실행, smoke test, 단일 class 실행, 탐색 튜닝을 포함함. 모든 weight의 무결성·추론 재현까지 확인한 것은 아님.

기계 판독용 목록: [legacy_experiment_inventory.json](audit_2026-09-17/legacy_experiment_inventory.json). 각 실행의 config, target states, seed, prior/routing, 저장된 training-test 평균, 원본 경로를 기록함. inventory의 평균은 train_summary에서 계산한 것으로 별도 eval report와 자동 동일시하지 않음.

## 3. 수행 내용과 검증 범위

| 실험군 | 직접 확인한 기존 수행 | 새 계획에서의 의미 |
|---|---|---|
| Phase 1 atlas scale | 100/200 nodes 각각 3 seed 학습·평가 | 규모 비교 구현 재사용. window 분할 결과를 새 피험자 일반화로 확대하지 않음 |
| Strict classifier split | ABIDE와 simulation 각각 10 seed, 실제 NPZ subject ID의 split 겹침 0 | 피험자 독립 classifier 평가 **이미 수행**. training-only template 검증과 구분 |
| Nuisance sensitivity | CompCor+GSR / CompCor only / GSR only 각각 10 seed | 전처리 민감도 **이미 수행**. 새 target의 subject-independent 평가로 확장 |
| Prior/routing sweep | 2026-03-14 seed42 grid 48개, 후속 top-balanced 3-seed 실행 9개 폴더 | prior 유무·soft/hard·규모·밀도 탐색 **이미 수행** |
| Baseline comparison | MoBSE/MoE/Transformer/SparseTransformer 5-seed 비교 | 비교 구현·실패/성공 패턴 보존. matched capacity/compute와 독립 target은 별도 |
| Cross-dataset | ds000030↔ds000243 양방향, MoBSE/MoE 5-seed | 데이터셋 전이 평가 **이미 수행**. proxy label 목표이므로 새 과제 검증과 다름 |
| ds000243 model suites | 전체 modelcomp train summary 228개: 1 epoch 148개, 5 epochs 80개 | 광범위한 실행·profiling·forecasting 기록. OS는 rest 단일 class |
| ETTh1 temporal control | mean/GRU × ETTh1-only/dual-task, 각 10 seed | 시간 encoder 효과 실험 **이미 수행**. arch=StandardMoE이며 fMRI encoder 결과가 아님 |
| ETT family | ETTh1/ETTh2/ETTm1/ETTm2 10-seed 요약·실행선 | auxiliary forecasting 자산 보존. 새 fMRI 주가설의 독립 근거는 아님 |
| ABIDE dFC | 다수 PCA/normalization/clustering 결과와 20260415_164915 3-seed 학습 | ABIDE dFC bridge는 **미착수가 아니라 일부 구현·실행됨**. atlas 대 dFC의 엄밀한 동일조건 비교 완료로 확대하지 않음 |
| PIOP1 dFC | rest/all-task, balance 0/.1/1, temperature 1/3, k2/3; Exp E도 완료 | 기존 탐색과 중복 실행을 피함. 전처리·분할 감사 후 새 target 평가 필요 |

## 4. 핵심 결과를 원본과 대조

### 4.1 Strict split과 nuisance

ABIDE strict split은 143명을 train100/val21/test22로 나누고 실제 windows에서도 겹침 0. Simulation은 150명을 105/22/23으로 나누며 겹침 0. 둘 다 **같은 고정 분할의 10-seed 학습**이지 10-fold CV는 아님.

개별 저장 eval을 재집계한 accuracy: ABIDE 0.99982363±0.00037181, simulation 0.14480923±0.00186124. 보고서와 일치.

근거: `artifacts/current_canonical/strict_split_wave_20260331/reports/strict_split_summary.csv`, `abide_control_cc200_mobse_adult150_strictsplit10_20260331/logs/`, `simul_public_proxy150_mobse_fair_strictsplit10_20260331/logs/`.

이 실행들은 3월30일 사전 제작 template/windows를 사용. 원본 생성 config에 train-subject 제한이 없고 현재 builder는 전체 발견 records로 template를 만듦. 당시 bank의 모든 원본 hash·피험자 목록까지 재생성하지는 않았으므로, **classifier subject split은 확인되나 bank까지 inductive임은 확인되지 않음**이라고 구분. ABIDE/SIM의 label 생성 비대칭은 strict split으로 해결되지 않음.

Nuisance 10-seed accuracy 재집계: CompCor+GSR 0.18222390, CompCor only 0.18645991, GSR only 0.15703480. `nuisance_wave_mobse_20260331/reports/nuisance_benchmark_summary.csv`와 일치. CompCor/GSR-only NPZ 각각 249명·8810 windows이며 seed42 기본 split에서 train-test 245명 겹침. 다른 arm에는 subject_ids가 없어 동등한 검사를 하지 못함. 따라서 전처리 민감도 실험은 존재하되 피험자 일반화에 대한 민감도는 아님.

### 4.2 Prior·baseline·cross-dataset

48개 sweep은 두 데이터 실행선(HC127/combined300) × nodes100/200 × sparsity .1/.2/.3 × soft/hard × prior/noprior. 개별 eval 및 train 파일 확인.

`use_template_prior=False`는 **학습 가능한 랜덤 초기화 graph**임. 새 제안의 고정된 구조 보존 null bank와 다름. soft/hard는 입력 의존 routing을 사용하는 조건들로, 모든 표본에 공통인 learned fixed mixture 대조를 대신하지 않음.

기존 5-seed 기본 비교 보고 평균 accuracy: MoBSE 0.18336, MoE 0.18169, Transformer 0.16369, SparseTransformer 0.16097. 기록된 FLOPs는 약22.885M/2.961M/3.483M/3.483M으로 matched compute 비교가 아님. 숫자는 기존 proxy target에 대한 것으로 새 과제 정확도로 사용하지 않음.

전이 NPZ에서 ds000030 218명/6535 windows와 ds000243 31명/2275 windows 및 균형적인 5개 proxy label 확인. source/target prefix 분리가 있고 source 내부 validation은 window split.

| 방향 | MoBSE accuracy / macro-F1 | MoE accuracy / macro-F1 |
|---|---:|---:|
| 030→243 | 0.20105 / 0.16140 | 0.19930 / 0.10560 |
| 243→030 | 0.20000 / 0.12555 | 0.20043 / 0.10765 |

저장자료의 대표 1개 subject(ds000243_sub-028)에서 wm.npy가 rest.npy를 시간축으로 2칸 roll한 것과 정확히 일치함(최대 차이0). 이는 proxy label임을 보여주는 실물 대조이나 전체 자료의 기원·변환을 모두 재검증한 것은 아님.

이는 약 chance 수준의 accuracy를 보인 기존 전이 결과로 보존해야 함. 새 외부 평가가 필요하다는 이유로 이미 수행된 전이 실험을 삭제하거나 무시하지 않음. 평균은 저장된 followup/summary 보고서, 대표 seed42는 train-test와 eval 일치 확인. 전체 seed 재추론은 아님.

근거 root: `artifacts/legacy_phase2/phase2_cross_mobse_train030_test243_20260323/`, 반대 방향 및 MoE 대응 폴더, `phase2_cross_full_n100_20260323/templates/os_windows_nodes100.npz`.

### 4.3 ds000243 비교는 1-epoch 실행만 있는 것이 아님

9개 기본/FC suite 144개는 1seed·1epoch. 추가 smoke 4개와 **tangent dual-task 16조건×5seed×5epoch=80 실행**이 있으며 전체 modelcomp 실행 폴더는 228개임.

OS는 rest 단일 class, MoBSE expert=1이므로 accuracy/F1=1.0은 자명함. 이 결과는 routing의 선택 능력이나 다중 class 분류 우위를 검증하지 않음.

5-seed·5-epoch tangent 결과의 16조건에서 OS accuracy 및 ETTh1 MAE/MSE 총48개 summary 값을 개별 eval JSON으로 재집계해 모두 일치함. 예를 들어 nodes100/sp.1의 ETTh1 MAE는 MoBSE 2.55858, MoE 2.24886. 이것만으로 보편적 순위를 선언하지 않으며 이 실험선에서 단순 MoE가 더 낮은 오차를 보였다는 결과로 보존.

주의: OS-only 실행의 eval에도 ETTh1가 들어갈 수 있으나 train의 test_etth1는 비어 있음. `evaluate.py`가 두 task를 항상 평가하기 때문이며 이 값은 미학습 forecasting head 평가임. 또한 FC MAE/MSE/correlation은 모델 출력이 아니라 template와 첫 최대256 windows의 empirical FC 평균 비교임. holdout 모델 예측 정확도로 해석하면 안 됨.

CPU profiling은 batch forward 시간으로 feature extraction 전체 비용이 아님. 기본 correlation 16행의 acc/F1/latency/FLOPs 64항목은 eval JSON과 일치함. 다른 suite의 전체 수치까지 재집계한 것은 아님.

근거: `artifacts/current_canonical/ds000243_modelcomp_connectivity_tangent_dualtask_s5e5_20260402/reports/`; [재집계 기록](audit_2026-09-17/ds000243_s5e5_recomputation.json).

### 4.4 ETTh1의 temporal bottleneck은 이미 실험됨

| StandardMoE 설정 | 10-seed MAE | 10-seed MSE |
|---|---:|---:|
| ETTh1-only, mean | 2.26209 | 8.65779 |
| Dual-task, mean | 2.20585 | 7.85959 |
| ETTh1-only, GRU | 1.45857 | 3.71114 |
| Dual-task, GRU | 1.41690 | 3.57913 |

40개 seed별 eval JSON에서 8개 평균을 다시 계산했으며 `etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv`와 차이0. 이는 저장된 평가값의 집계 검증이며 학습·추론 재현이 아님.

시간평균 병목을 실험적으로 점검한 자산이 이미 있음. 단 **arch=moe, temporal encoder=ETTh1 branch**이므로 PIOP1 fMRI에서 ROI-preserving temporal encoder/FC gate를 검증한 것과는 다름. 새 연구에서 시간 정보 보존을 시도할 근거로 활용하되 동일 결과라고 하지 않음.

[재집계 기록](audit_2026-09-17/etth1_saved_eval_recomputation.json).

### 4.5 ABIDE·PIOP1 dFC 및 반복 실행의 경계

ABIDE PCA/normalization 탐색은 `artifacts/abide_dfc_*` 아래12개 report와 bank를 보유. full 자료의 report는 used102명·19630 windows이며 일부 `n_subjects_input:0`은 used 수와 구분해야 함. v2에서 원래200 ROI 중9개를 제외해191개로 처리한 기록이 있음.

`20260415_164915`는 `mobse_dfc_abide/os_windows_nodes191.npz`를 사용한 3-seed 학습이며 저장된 평균 OS accuracy0.48387, macro-F1 0.43181. 따라서 ABIDE dFC 연결은 이미 pilot까지 수행됨.

PIOP1 report는 Schaefer100/200 각각 resting210명·29610 FC windows, 생성 설정45초/stride2초. 후속 all-task 학습은64TR/stride16TR의15817 windows이며 서로 다른 window 정의임. 두 수를 혼합하지 않음.

| PIOP1 all-task 실행 | balance / temperature / routing k | 3-seed accuracy | macro-F1 |
|---|---|---:|---:|
| 20260416_102453 | 0 / 1 / 2 | 0.58295 | 0.47259 |
| 20260416_110408 | .1 / 1 / 2 | 0.58814 | 0.46795 |
| 20260416_133322 | 1 / 1 / 2 | 0.58913 | 0.47080 |
| 20260416_134500 (C) | 1 / 3 / 2 | 0.58871 | 0.45297 |
| 20260416_141348 (D) | 1 / 3 / 3 | 0.58660 | 0.45497 |
| 20260416_142556 (E) | .1 / 3 / 3 | 0.58674 | 0.45520 |

저장된 train_summary에서 재집계. E는 완료되어 있으며 여러 balance 조건도 실행됨. C가 모든 성능 지표에서 최선은 아님. 134049/134500/140117은 seed별 시간정보를 제외한 전체 history hash가 같음. 실행 폴더가 다르다는 이유로 독립적인 새로운 재현 증거로 세지 않음. 당시 코드 hash가 없는 상태에서 이 로그만으로 scatter/mask 변경의 인과 효과를 판정하지 않음.

## 5. 재설계에 반영할 수정

1. **재사용:** subject-prefix split 검증, nuisance 비교, baseline 실행기, prior ablation 구현, cross-dataset 평가 흐름, ETTh1 temporal control, dFC export/bridge 및 로그/보고 코드.
2. **새로운 핵심 비교:** 독립 task target, training-only template와 전체 fold-local 변환, matched frozen null bank, learned fixed mixture, mean/FC 단순 기준선, 올바른 task별 TR 전처리, subject-level paired inference.
3. **이미 실행된 항목을 재요청하지 않기:** Exp E, ABIDE dFC pilot, 일반적인 prior/no-prior와 baseline/전이 실험 자체. 새 실행 시 어떤 target·분할·대조가 달라지는지 먼저 명시.
4. **연구 범위 결정 전 기존 음성 결과 활용:** cross-dataset accuracy가 약 chance인 점, 단순 MoE가 일부 forecasting 설정에서 우세한 점, balance로 entropy가 높아져도 macro-F1가 개선되지 않는 점을 설계 근거에 포함.

종합 판정: **많은 실험이 수행되었고 재사용할 자산이 충분함. 남은 작업은 실험량 추가보다, 이미 있는 증거가 답하는 질문을 분리하고 새 가설에 필요한 비교만 추가하는 것임.**
