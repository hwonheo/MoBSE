# MoBSE 재설계 프로토콜 — 독립 target에서 graph prior와 routing의 기여 검증

작성: 2026-09-17. 상태: **설계안 완료, 데이터 감사·실험 실행 전**. 현재 결과를 검증 완료한 새 결과로 해석하지 않음. 기존 코드·결과·원고는 보존함. 수치 기준과 계산 예산은 아래의 연구 설계 제안이며 문헌이 정한 보편적 기준이 아님.

근거 문헌과 공개 상태: [최근 문헌 검토](mobse_literature_review_2026-09-17.md). 대괄호 R1–R10, D1은 해당 문서의 문헌 ID임.

## 0. 기존 실험 감사 반영 — 2026-09-17 추가

이 계획은 기존 검증이 없다는 전제에서 시작하지 않음. 후속 artifact 감사에서 **352개 학습 요약, 624개 seed 결과 및 checkpoint**를 확인함. [기존 실험 감사 보고서](mobse_existing_experiments_audit_2026-09-17.md)에 실행·수치·해석 범위를 정리함.

이미 수행된 내용은 ABIDE/SIM strict subject classifier split 각10seed, nuisance3조건 각10seed, prior/no-prior·soft/hard·규모·밀도48조건 sweep, 5seed baseline·양방향030↔243 전이, ds000243 modelcomp228실행(5seed×5epoch80실행 포함), ETTh1 mean/GRU×single/dual-task 각10seed, ABIDE dFC pilot과 PIOP1 Exp E 등임.

새로운 검증은 **실제 관측 task target + training-only template/PCA + matched frozen null + learned fixed mixture**의 결합임. 기존 strict classifier split을 미수행이라고 표현하지 않음. 기존 no-prior는 학습 가능한 랜덤 graph이므로 새 fixed-null과 다르며, soft/hard는 fixed-mixture 대조를 대신하지 않음. 기존 ds000243 rest단일class 정확도100%를 classification validation으로 사용하지 않음. 기존 ETTh1 GRU 결과는 StandardMoE forecasting branch의 근거이며 fMRI temporal encoder 검증으로 바꾸어 부르지 않음.

따라서 아래 실행 단계에서는 기존 코드와 검증된 reporting/split 도구를 먼저 재사용하고, 같은 목적의 sweep을 일괄 반복하지 않음. 현재의 대규모 재설계 대신 기존 자산으로 최소 추가 비교를 구현할 수 있는지 먼저 평가해야 함.

## 1. 연구 질문과 주장 범위

**주질문:** 뇌 유래 FC template의 해부학적 정렬과 입력 의존 routing은, 같은 자료·예측 목표·학습 조건에서 각각 추가적인 예측 가치를 제공하는가?

제안 제목: *Testing the contribution of brain-derived graph priors and input-dependent routing to cross-cohort fMRI task discrimination*.

주 target은 PIOP1의 **emotion matching 대 working memory run identity**. 이는 cluster pseudo-label과 독립적인 관측값이나 인지부하의 정답은 아님. 주장이 허용되는 범위는 미사용 피험자의 task-associated signal discrimination임. 서로 다른 task에서 관측한 차이는 감각·반응·촬영 맥락까지 포함하므로 인지 기전으로 해석하지 않음.

PIOP2에서 같은 두 task를 사용한 잠근 cohort/acquisition replication을 계획함. 같은 연구 환경의 다른 cohort이므로 cross-site replication이라고 부르지 않음. subject overlap 여부는 별도 확인함. ds000030은 다른 task 집합·집단이므로 같은 label의 직접 외부 검증에 사용하지 않음.

유보할 기존 주장: brain-state MoE 최초 제안, atlas-free, cognitive load marker, sparse computation에 의한 효율 향상, scatter masking의 범용 gradient 해결책, ABIDE 대 simulation 성능 차이로 brain prior 우월성 입증. [R6–R10]

## 2. 실행 전 데이터 감사 — 첫 번째 중단 조건

2026-09-17 로컬 Schaefer-100 시계열 census:

| 자료 | 로컬 확인 수 | 해석 |
|---|---:|---|
| PIOP1 전체 subject directory | 216 | QC 후 분석 N이 아님 |
| emomatching | 207 | 파일 보유 subject 수 |
| workingmemory | 204 | 파일 보유 subject 수 |
| restingstate | 210 | 파일 보유 subject 수 |
| 두 target task 교집합 | 202 | task 예측 후보 최대 수 |
| 두 task+rest 교집합 | 196 | 주분석 complete-case 후보 최대 수 |
| PIOP2 target task pair | 0 | 현재 replication 데이터 준비 안 됨; rest/WM만 있는 1명 확인 |

주분석 후보는 rest와 두 task가 있는 196명에서 시작하되 최종 N은 원본 대조·QC 후 결정. 동일 complete-case 집합을 모든 모델에 적용. 196명을 달성해야 한다고 QC를 완화하지 않음. rest 없는 6명을 task 평가에 포함하는 분석은 template 학습 자격 규칙을 별도로 고정한 민감도 분석으로만 실시.

직접 확인된 문제: `scripts/stream_aomic_extract.py`의 필터링 함수는 전달된 `tr`를 사용하며 기본값은 0.75초. PIOP2 manifest는 240 volumes의 rest를 TR 0.75, 180초로 기록함. D1의 PIOP2 rest는 TR 2초, 480초임. 저장된 추출 이력과 현재 코드에 불일치가 있으므로 이 결과를 그대로 재사용하지 않음. 과거 실행 코드 hash를 확보하지 못했으므로 모든 파일의 잘못된 필터링을 재현 확정한 것은 아님. PIOP1도 task별로 TR이 다르므로 함께 감사.

필수 manifest는 `dataset + subject + session + task + run + acquisition`을 키로 원본 BOLD/JSON/confounds/events 경로와 hash, 실제 TR, volumes, 시작시간, 제거 volumes, event offset, preprocessing version, atlas checksum, 움직임, 사용 가능 구간, 누락 사유를 저장해야 함. 참가자 ID만으로 join하지 않음.

현재 data/aomic에서 events·BOLD JSON·confounds 원본을 찾지 못함. 공개 원본 metadata와 대응 derivatives의 재확보 및 과제별 TR에 맞춘 ROI 재추출이 선행되어야 함. 연구 수행 허가·배포 조건도 해당 dataset 정책을 확인함. 이 설계 작성 중 대용량 BOLD 다운로드는 실행하지 않음.

D1상 두 주 target의 TR은 모두 2초. 로컬 WM 160 volumes와 원문 162 volumes의 차이는 discarded volumes/event origin으로 설명 가능한지 확인. 임의로 2 TR를 shift하지 않음. 잘못된 시간축을 나중에 resampling하는 것으로 기존 필터 오류를 복구할 수 없음.

**Gate 0:** run provenance, 올바른 TR·시간축, confounds와 두 task pairing을 확보하지 못하면 주실험을 시작하지 않음. PIOP2를 'short scan'으로 제외했던 판단은 철회 대상이며 원본 기준 재평가함. [D1]

## 3. 표현과 시간척도

주분석은 sustained task/run discrimination이며 moment-to-moment cognition decoding이 아님. 30초 emotion/control block이나 빠른 working-memory/gstroop trial을 60초 FC window의 단일 인지 label로 배정하지 않음. [R1–R3]

사전 고정 후보:

- atlas: Schaefer-100, 정확한 버전·ROI 순서 고정. 이는 atlas-free 방법이 아님.
- 두 task에서 실제 TR 2초 확인 후 **60초 비중첩 window**(30 volumes)를 사용. 두 task 모두 같은 규칙의 onset guard 후 공통 240초 구간에서 4개 window를 얻도록 함. onset guard 제안값은 12초이며 실제 non-steady-state 처리와 event origin 감사 후, 성능을 보기 전에 고정.
- task마다 같은 사용 길이·window 수를 적용. 주분석은 두 task의 고정된 4개 window가 모두 유효한 complete-case subject만 포함. 불량 window를 다른 시간대 window로 바꾸거나 남은 window만 평균하지 않음. window 내 허용 motion 비율·nonfinite/zero-variance 제외 규칙을 성능 확인 전에 동결. 주분석에서 frame를 잘라 이어 붙이지 않으며, motion spike 회귀와 run/window QC를 사용. censoring은 별도 민감도로 구분.
- 원본 TR와 window seconds는 항상 저장. 주분석에서는 각 run을 올바른 native TR로 nuisance 처리한 뒤 명시적 anti-aliasing resampling으로 모두 2초 간격에 맞춤. PIOP1 rest의 0.75초→2초 변환과 task의 native 2초 유지 과정을 구분해 기록. 따라서 template와 task 모두 60초당 30 samples로 FC를 추정. native-rate 60초 FC는 민감도 분석. 이 처리가 획득 방식 차이를 없앤다고 주장하지 않으며, 같은 TR를 함수에 전달하는 것을 resampling으로 간주하지 않음.
- 작은 표본 길이의 FC에는 shrinkage covariance/correlation을 주표현으로 사용. Pearson은 민감도 비교. estimator 선택은 학습 데이터 안에서만 수행.
- task에 따라 달라지는 band-pass, padding, run 길이, 파일명, subject ID, acquisition index, absolute time를 predictive feature로 주지 않음.
- nuisance 회귀는 사전 명시한 motion 확장항과 aCompCor를 사용하고 GSR 유무를 민감도로 평가. confounds가 없으면 임의 대체 후 동일 전처리라고 쓰지 않음. run 단위 독립 전처리와 training-population 기반 학습 변환을 구분.

QC 후보값은 mean FD 0.2 mm, frame FD 0.5 mm 초과 비율 및 유효 연속 구간을 함께 검토하는 것으로 두되, 성공 N과 목표 정밀도를 metadata-only 감사에서 평가한 뒤 수치와 예외 규칙을 동결. 이 값들은 본 설계의 초안으로 문헌의 유일한 정답이 아님. QC 수정이 필요하면 성능 확인 전에 protocol 버전을 남김.

## 4. template와 target의 독립성

주 template bank는 **training subjects의 rest만**으로 작성. outer-test 및 PIOP2의 rest를 사용해 bank를 만들지 않음. 주 목적은 새 피험자의 task만으로 inference 가능한 inductive 모델임.

rest FC → training-only scaling/PCA → clustering → 고정 template bank. inner CV에서도 validation subject를 제외해 다시 fit. PCA 차원, K, 그래프 밀도를 전체 데이터 silhouette나 test 성능으로 선택하지 않음. K는 생리적 상태 수가 아니라 모델 차원임.

초기 주분석 K=3을 고정하고 K={2,5}는 사전 명시 민감도. PCA/threshold 등 소규모 선택은 inner CV 안에서만 수행. train subject별 window 기여를 균등하게 하여 긴 rest가 bank를 지배하지 않게 함. centroid를 fold 간 비교할 때는 train-template 유사도만으로 matching하며 task 효과가 커지도록 번호를 재배열하지 않음.

Graph 연산에는 주설계상 training centroid의 양의 FC만 사용하고 off-diagonal 상위 20%를 고정 규칙으로 보존한 뒤 self-loop와 degree normalization을 적용. signed FC 전체는 gate feature에 보존하되, 음수 degree로 인한 normalization 오류를 피함. signed graph propagation은 별도 구현 검증을 거친 민감도이며 primary와 혼합하지 않음. Null bank에도 동일 규칙을 적용하고 sparse edge 수를 sparse runtime 이득으로 해석하지 않음.

현재 centroid pseudo-label accuracy는 기술적 sanity check/teacher approximation 부록으로 이동. 주평가 label은 실제 task identity. gate에 FC를 넣고 FC-derived label을 맞힌 것을 독립 상태 검증으로 취급하지 않음.

## 5. 최소 모델 변경과 필수 대조

제안 모델 v2: 각 ROI의 짧은 시계열을 같은 작은 encoder로 처리해 ROI 대응 node embedding을 만들고, window FC의 training-only 저차원 표현으로 gate를 구성. template의 가중합을 하나의 shared graph stack에 넣는 구조는 유지. 복잡한 transition model·대규모 Transformer는 첫 실험에 추가하지 않음.

주 routing은 soft all-expert mixture로 시작. top-k와 개별 sample entropy 최대화는 주효과에 섞지 않음. batch balance가 필요하면 inner-validation으로 선택하고 개별 균일 혼합과 전문가 기능을 혼동하지 않음. FC gate와 no-graph baseline에 같은 feature 정보를 제공함.

| ID | Bank | Routing | 구분할 설명 |
|---|---|---|---|
| A | Training-rest brain bank | 입력 의존 | 제안 구성 |
| B | 동일 brain bank | 모든 표본에 공통인 학습된 soft mixture | A–B: routing의 추가 이득 |
| C | 구조를 맞춘 null bank | 입력 의존 | A–C: brain bank의 정렬·구조 이득 |
| D | 동일 null bank | 공통 학습 mixture | 2×2 interaction 및 기준 |

주 null은 **bank 전체에 동일한 ROI permutation을 적용**하되 실제 입력 ROI는 고정하여 template–해부학 대응을 끊음. 이는 전체 edge weight 분포·spectrum·template 간 관계를 보존하지만 ROI별 degree는 재배정하므로 '각 ROI degree 보존'이라고 쓰지 않음. 사전 지정된 하나의 null seed를 주비교에 사용하고 추가 4개 permutation으로 민감도 평가. null 실현을 독립 피험자로 세지 않음. 별도의 degree/strength-constrained rewiring은 구현 검증 후 탐색 비교이며 같은 null이라고 혼합하지 않음.

필수 기준선:

1. temporal mean·variance → regularized logistic regression / 작은 MLP.
2. FC upper triangle → regularized logistic 또는 linear SVM. [R8–R10]
3. 동일 FC feature → 작은 MLP 및 BQN. BQN은 공식 구현·튜닝 예산 대조 후 채택하며 현재 재현 완료로 간주하지 않음.
4. 동일 node encoder와 head를 가진 no-graph 모델, single average-FC graph 모델. 모델 capacity가 다르면 수치와 parameter-matched 민감도를 함께 보고.
5. 기존 mean-only MoBSE를 독립 target으로 재학습한 historical architecture control. 과거 centroid 정확도와 직접 비교하지 않음.
6. dFCExpert는 가장 가까운 정식 선행. 주파이프라인 확인 후 동일 split/target으로 적응한 비교를 추가. 원논문의 HCP/진단 정확도를 MoBSE 결과 옆에 직접 비교하지 않음. [R6]

A/B의 raw parameter 수를 완전히 동일하다고 주장하지 않음. 고정-mixture는 본질적으로 더 단순한 구성임. 실제 parameter/compute와 비슷한 크기의 non-routing control을 보고하여 단순 capacity 차이 설명을 점검.

## 6. 분할·튜닝·외부 검증

- 기본은 PIOP1 **outer 5-fold grouped CV, inner 3-fold grouped CV**, group=canonical subject. 같은 사람의 두 task·rest·모든 window는 항상 같은 그룹. 알려진 가족·중복 관계도 한 그룹으로 묶음.
- 5×3은 본 연구의 현실적 설계 선택이지 문헌이 정한 최적값이 아님. 피험자 수 감소 시 metadata-only 단계에서 수정·동결. fold manifest와 hashes를 저장.
- architecture family별 최대 8개 사전 정의 config, 동일 early stopping 예산. 모든 family에 같은 splits를 사용. 초기 3개 seed의 예측을 평균하여 각 outer-test subject에 하나의 모델별 예측 집합을 생성. seed variance는 별도 보고.
- 각 fold의 scaling, PCA, K/template, nuisance population transforms, calibration, model selection은 해당 train/inner 데이터만 사용. test를 보며 threshold·모델·window를 고르지 않음. [R4]
- PIOP2는 metadata/QC만 먼저 확인하고 성능에 접근하기 전에 protocol와 PIOP1 선택을 잠금. PIOP1 전체로 train-only 변환과 모델을 최종 fit한 뒤 적용. primary replication에서 PIOP2 labels, rest-derived templates 또는 target-domain adaptation을 사용하지 않음.
- PIOP2의 두 task pairing 수·QC와 subject independence 확인 후 최종 replication N 확정. 현재 확보 N=0이므로 replication 완료를 전제한 power/성능 주장을 하지 않음.
- PIOP2 수집이 불가능하면 cross-cohort 주장은 삭제하고 internal validation 연구로 범위를 축소. ds000030으로 자동 교체하여 '동일 재현'이라고 하지 않음.

## 7. endpoint와 통계 — window 수는 표본 수가 아님

각 피험자의 각 task에서 4개 window 확률을 평균해 run probability를 얻음. binary threshold는 0.5로 고정하며 변경 시 inner train에서만 선택. 각 피험자는 두 task를 동일 가중치로 기여.

주 metric: subject-equal-weighted balanced accuracy. 주효과는 A–B와 A–C의 paired 차이. 보조: log loss, macro-F1, AUROC, calibration, worst-subgroup 성능. 단일 run별 task-associated discrimination을 평가하며 개인 biomarker를 측정한다고 하지 않음.

사전 판단 제안:

- 실질적으로 의미 있는 개선 크기 δ=0.02 balanced accuracy를 설계 목표로 명시. 이는 선택한 최소 효과이지 알려진 사실이 아님.
- 내부 결과: 두 주 contrast 모두 점추정 ≥δ이며 family-wise 95% 구간의 하한 >0일 때 다음 확인 단계로 진행. practical superiority가 입증되었다고 하려면 하한 자체가 δ를 넘어야 함.
- primary family 두 contrast에는 paired subject bootstrap의 동시 구간(예: 각 contrast 97.5% 구간의 Bonferroni 조합)을 사용. 피험자 전체 pair를 재표집하고 모든 모델에 같은 재표집을 적용. window/seed/fold를 독립 표본으로 t-test하지 않음.
- OOF subject bootstrap은 고정된 학습 결과에 조건부인 불확실성으로 표기하며, training-set 변동을 완전히 반영한다고 주장하지 않음. 잠근 PIOP2 paired 결과가 confirmatory 근거. 반복 CV 민감도를 하더라도 fold 수를 표본수로 쓰지 않음.
- permutation 검정이 필요하면 subject 안에서 run-level task label을 뒤집고 전체 fitting/tuning pipeline을 다시 수행. 고정 예측만으로 label을 바꾼 값은 전체 학습 null 검정으로 보고하지 않음.
- metadata 단계에서 피험자 단위 상관구조를 고려한 power/precision simulation을 수행. QC 후 N과 목표δ에서 충분한 정밀도가 없으면 'no effect'가 아니라 inconclusive. window를 늘려 표본수를 부풀리지 않음.

단순 모델 대비 효용은 별도 사전 보조 endpoint A–S로 평가. S는 mean/FC 선형·작은 MLP 중 inner-validation에서 정한 최강 기준선이며 outer-test 결과로 고르지 않음. 외부 평가 S는 PIOP1에서만 선택. A–S의 paired 차이·95% 기술적 CI·실측 비용을 보고하고 이를 두 primary contrast와 같은 confirmatory family의 유의성으로 포장하지 않음. A가 단순 모델보다 추가 이득을 보이지 않으면 복잡한 구조의 필요성은 미지지; 통계적 비유의를 동등성으로 해석하지 않음. 단순 모델로 충분하다는 적극적 동등성 결론에는 사전 margin ±δ 안에 CI가 들어가는 별도 equivalence 평가가 필요. 실용적 우월성까지 confirmatory로 주장하려면 실행 전에 A–S를 포함한 다중검정·power 계획을 별도 잠금.

PIOP2에서도 두 contrast를 같은 정의로 보고. CI가 0을 가로지르면 재현 불확실, 반대방향이 정밀하면 해당 가설에 반하는 근거. PIOP2에 맞춰 재튜닝한 결과는 독립 replication과 분리.

## 8. routing의 의미를 따로 검증

routing heatmap과 entropy만으로 전문화를 선언하지 않음. 다음을 서로 다른 증거로 보고:

- association: heldout subject별 task 간 mixture 차이. entropy는 support 상한 log(k)를 고려. expert 번호의 fold별 임의성을 처리. seed 평균을 독립 N으로 세지 않음.
- model dependence: inference에서 routing을 training 평균으로 고정하거나, heldout 표본 간 label을 보지 않고 shuffle했을 때 예측 성능 변화. label별로 shuffle하지 않음. 이는 모델 내부 의존성 검증이며 뇌의 인과기전 검증이 아님.
- brain alignment: ROI-permuted bank, 평균 graph, no-graph와 비교해 해부학적 정렬 이득을 식별.
- nuisance alternative: FD, DVARS, tSNR, ROI mean/variance 및 가용 acquisition 정보만 사용하는 기준선을 별도 평가. raw run index처럼 task를 직접 드러내는 항목은 classifier 입력에서 제외하며 그 완전 confounding은 설계 한계로 기록.
- timing control: 공통 길이와 동일 window onset 분포, time-only baseline, window별 결과. 동일 scan order의 task 차이를 모두 인지 차이로 부르지 않음. Run 내부 time-only 성능이 chance라도 run 간 촬영 순서·acquisition 맥락의 교란이 배제되는 것은 아님. PIOP2 순서 변화가 일부 대안을 점검하나 모든 acquisition confounding을 없애지는 않음.

인지 해석을 유지하려면 별도 사전 가설이 필요. gstroop congruent/incongruent처럼 무작위 trial 조건은 HRF-aware event/activation 모델로 탐색하되 긴 dFC window와 동일 endpoint로 묶지 않음. emotion/control alternating blocks 또는 WM의 공통 trial 순서는 schedule-only 예측을 통제해야 함. 이를 통과하지 못하면 cognitive load 주장을 하지 않음. 테스트 정답 events로 회귀한 feature를 독립 blind classifier의 입력으로 사용하지 않음.

## 9. 동역학·효율 및 민감도 주장

본 주분석은 window마다 template를 달리 혼합할 수 있는 모델이지, 상태 전환 동역학을 검증한 모델은 아님. 시간순서가 필요한지 주장하려면 정적 run FC, window 순서 shuffle, 시간구조를 보존하는 stationary surrogate를 별도 비교해야 함. stationary multivariate surrogate는 spectrum/static FC 보존 정도를 먼저 검증하며 단순 무작위 시간 shuffle을 유일한 null로 사용하지 않음. [R1–R3]

60초 주분석 뒤 40/80초, Pearson/shrinkage, GSR±, Schaefer-200, K={2,5} 및 가능하면 다른 방법 계열의 bank를 제한적 사전 민감도로 평가. 그중 잘 나온 설정을 새 primary로 바꾸지 않음. 모델 순위 또는 effect 방향이 바뀌면 robustness 제한을 보고.

효율은 보조 측정. 동일 하드웨어·batch·precision에서 end-to-end feature construction(FC/PCA 포함), 모델 latency, peak memory, 실제 지원된 operation count를 기록. dense zero matrix를 sparse execution으로 부르지 않음. FLOPs 추정 fallback을 실제 연산수로 표기하지 않음. 동등 성능의 대조보다 측정 비용이 낮지 않으면 효율 우위 주장을 삭제.

## 10. 단계별 실행과 판단

| 단계 | 산출물 | 다음 단계 조건 / 실패 시 해석 |
|---|---|---|
| 0. Provenance·TR·QC | run manifest, exclusions, event offsets, 후보 N, 보정 추출 결과 | 시간축·confound provenance 미해결이면 중단 |
| 1. Measurement feasibility | 개발/inner 데이터에서만 mean/FC/nuisance/time 기준선, 정밀도 계획, representation check | outer-OOF를 보고 QC·window·표현을 수정하지 않음. 별도 개발 subject는 confirmatory outer 평가에서 제외. 정보가 확인 안 되면 모델 복잡화하지 않고 feasibility 결과로 보고 |
| 2. Minimal 2×2 | A–D의 동일 OOF predictions·주 contrast·ablation | A–B 실패: dynamic routing 이득 미지지. A–C 실패: brain alignment 이득 미지지 |
| 3. Locked replication | PIOP2 결과와 cohort QC | 미확보/불확실이면 외부 일반화 주장 보류 |
| 4. Mechanism·sensitivity | routing 교란·nuisance·window/방법 민감도 | routing association만 있으면 인지 기전으로 확대하지 않음 |
| 5. Manuscript | claim-evidence 표, 재현 configs, results manifest | 유리한 결론을 유지하기 위해 endpoint를 사후 교체하지 않음 |

첫 2×2 outer fits는 4 cells×5 folds×3 seeds=60회이며 inner tuning·기준선·null 민감도는 별도 비용. 기존 실험 크기만으로 wall time을 보장하지 않음. 소규모 engineering pilot은 개발 subject에만 제한하고 실행·메모리 오류 점검용으로 사용하며 confirmatory 효과 선택에 쓰지 않음.

필요 코드 변경은 새 v2 경로에서 구현: task별 metadata를 읽는 extraction, immutable subject split, fold-local template fitting, 실제 task label builder, ROI-preserving encoder/FC gate, fixed-mixture/null-bank controls, subject-level evaluation. 현재 파일의 dirty changes를 덮어쓰거나 과거 artifact를 새 결과로 대체하지 않음.

## 11. 기존 결과의 역할

ABIDE 대 simulation은 서로 다른 state 생성 난이도를 가진 historical PoC로 남김. PIOP1 centroid 분류·Exp C/D/E는 exploratory development이며 새 hypothesis의 confirmatory 증거에 합산하지 않음. ETTh1은 이번 task-associated fMRI 질문의 주논리에서 제외하여 별도 연구선 또는 부록으로 보존함. 기존 그림·DOCX·lock 문서는 자동 수정하지 않음.

가능한 최종 결론은 세 가지 모두 허용해야 함: (a) brain alignment와 routing 둘 다 추가 가치가 있음, (b) 한 요소만 유효함, (c) 단순 FC/mean 모델로 충분함. 세 경우를 구분할 수 있는 설계가 목표이며 새 모델의 승리를 전제하지 않음.
