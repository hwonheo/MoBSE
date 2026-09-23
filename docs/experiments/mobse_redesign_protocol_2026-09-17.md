# MoBSE 재설계 프로토콜 — 독립 target에서 graph prior와 routing의 기여 검증

**버전 1.1 · 2026-09-17 · 실행 전 계획서**

이 문서는 연구 설계와 분석 규칙을 구체화한 계획서다. 새 데이터 추출·모델 구현·학습·외부 검증은 수행하지 않았다. 아래 수치 기준은 이번 연구의 설계 선택이며 문헌이 정한 보편적 기준이 아니다. 실제 데이터 provenance 확인 후 변경이 필요한 항목은 main 성능 접근 전에 버전과 이유를 남겨 동결한다.

연결 문서: [작업 지침서](mobse_redesign_work_instructions_2026-09-17.md), [기존 실험 감사](mobse_existing_experiments_audit_2026-09-17.md), [문헌 검토](mobse_literature_review_2026-09-17.md), [이전 설계 v1.0](archive_redesign/mobse_redesign_protocol_2026-09-17_v1.0.md). R1–R10, D1은 문헌 검토의 ID다. 본 버전은 이전 설계의 후보값·선택 규칙을 아래와 같이 구체화하며, 충돌 시 본 버전을 적용한다.

## 1. 목적과 검증 가능한 주장

**질문:** training-rest에서 만든 graph bank의 해부학적 정렬과 입력 의존 routing은, cluster와 독립적인 실제 task 분류에서 각각 추가 가치를 제공하는가?

주 target은 AOMIC PIOP1의 `emomatching=0`, `workingmemory=1` run identity다. 미사용 피험자의 task-associated signal discrimination을 평가한다. 인지부하 정답, 개별 뇌 상태, 인과적 인지기전을 측정한다고 하지 않는다. 감각·운동·촬영 순서 차이가 task와 함께 바뀌는 한계를 명시한다. [R1–R3]

PIOP2의 같은 task pair를 잠근 cohort/acquisition replication으로 사용한다. 같은 연구 환경이므로 cross-site라고 부르지 않는다. PIOP2 미확보 시 internal validation으로 연구 범위를 축소하며 ds000030의 다른 task를 같은 외부 target으로 대체하지 않는다.

주가설은 H1: A−B>0(입력 의존 routing의 이득), H2: A−C>0(정렬된 brain bank의 이득)이다. 최소 관심 효과 δ=0.02 balanced accuracy(BA)를 사전 선택한다. 두 요인의 상호작용 `(A−B)−(C−D)`는 보조 분석이다. 단순 모델 대비 실용성은 별도 보조 endpoint다.

최초 brain MoE, atlas-free, cognitive load marker, sparse-compute 우위는 본 연구의 기본 주장이 아니다. dFCExpert와 MoRE-Brain 등 직접 선행을 반영한다. [R6–R10]

## 2. 기존 자료와 새 검증의 경계

기존 감사에서 352개 학습 요약, 624개 seed 결과와 checkpoint를 확인했다. 이는 독립 연구 624개를 뜻하지 않는다. ABIDE/SIM strict subject split, nuisance 비교, prior/no-prior·soft/hard sweep, baseline·전이, ds000243, ETTh1, ABIDE dFC 및 PIOP1 실험이 이미 있다.

새로 필요한 결합은 **실제 task target + fold 내부 template/PCA + frozen matched null + learned fixed mixture**다. 기존 strict classifier split은 인정하되 template의 train 경계는 별도로 검증한다. 기존 learned random graph는 frozen null이 아니고 soft/hard routing은 dynamic/fixed 비교가 아니다. 단일 rest class 정확도 100%와 ETTh1 forecasting 개선은 새 fMRI task 검증을 대신하지 않는다. 상세 수치와 제한은 감사 문서를 따른다.

| 로컬 PIOP1/PIOP2 확인값 | 수 | 분석상 의미 |
|---|---:|---|
| PIOP1 subject directory | 216 | 분석 N 아님 |
| PIOP1 emo / WM / rest 보유 | 207 / 204 / 210 | 파일 보유 수 |
| PIOP1 emo∩WM / emo∩WM∩rest | 202 / 196 | QC 전 후보 |
| PIOP2 두 target pair | 0 | 외부 검증 미준비 |

TR provenance가 첫 차단 요인이었다. 기존 추출 코드는 모든 run에 기본 TR 0.75초를 적용했고, 이는 task별 실제 획득과 맞지 않는다. **[개정 P2]** native TR은 2026-09-17 Wave 1 에서 OpenNeuro sidecar JSON 을 직접 읽어 6개 dataset×task 조합 전부 확정했다(조합 내 분산 0): PIOP1 emomatching 2.00초/135 vol, PIOP1 workingmemory 2.00초/162 vol, PIOP1 restingstate 0.75초/480 vol, PIOP2 emomatching 2.00초/135 vol, PIOP2 workingmemory 2.00초/160 vol, PIOP2 restingstate 2.00초/240 vol. 근거는 문헌 검토 D1이 아니라 이 sidecar 측정이다 — D1 행에는 TR·volume 수치가 없다. 따라서 기존 추출은 PIOP1 rest 에서만 우연히 옳고 두 target task 는 실제의 2.67배 속도로 필터링되었다. 정확한 추출 근거가 없는 기존 `.npy`는 주분석에 재사용하지 않는다. 잘못 필터링한 시계열을 resample하는 것은 복구가 아니다. **[개정 P1]** 앞서 "로컬 WM 160 대 문헌 162"로 적은 차이는 제거 volume 기록의 문제가 아니라 **cohort 간 차이**다 — PIOP1 workingmemory 는 로컬 204명 전원이 162 vol 이고, 160 은 PIOP2 의 값이다. smoke 트리에 남은 240 vol 기록(E7)은 PIOP2 restingstate 이며 target task 가 아니다.

## 3. 자료 단위·전처리·QC

### 3.1 Provenance와 시간축

run key는 `dataset/subject/session/task/run/acquisition`이다. 없는 BIDS entity도 정해진 빈값으로 직렬화하며 조용히 합치지 않는다. **[개정 P5]** `canonical_subject`는 **dataset prefix 를 반드시 포함한다**(예: `ds002785:sub-0001`). PIOP1 과 PIOP2 가 같은 `sub-0001…` 네임스페이스를 쓰기 때문에 prefix 없이는 서로 다른 사람이 같은 키를 갖는다 — 문자 교집합 216명, 전 열 일치 0/216 으로 확인했다(U17). prefix 를 강제하지 않으면 WI-08 의 subject independence 검사가 216건의 위양성을 낸다. `mobse/v2/manifests.py`의 `validate_canonical_subject()` 가 이 규칙을 실행 시점에 강제한다. 원본 BOLD/header/JSON, confounds, events, derivative 버전, atlas와 ROI 순서의 경로·SHA256을 보존한다. acquisition TR, volume 수, 제거 volume 수, 원본 acquisition 기준 첫 sample 시간, events 기준점, nuisance 열과 rank를 기록한다. JSON/header 불일치는 수동 근거 없이 한쪽을 선택하지 않는다.

native TR에서 nuisance 및 주파수 처리를 수행한 후, anti-aliasing을 명시해 2초 grid로 resample한다. 원본 acquisition 시간의 **[12,252)초**를 주분석 구간으로 한다. 12초 guard를 derivative 시작점에서 다시 더하지 않는다. 예를 들어 앞 2 volumes가 이미 제거되었다면 남은 sample의 원래 시간을 복원해 선택한다. 시간 원점이 불명확하면 해당 run은 실패다.

고정 window는 [12,72), [72,132), [132,192), [192,252)초로, 각각 30 samples다. rest에도 같은 규칙을 적용해 subject당 4개 rest FC만 bank 학습에 기여하게 한다. 원본 coverage나 필터 edge 처리가 이 구간을 지원하지 못하면 임의 이동·padding하지 않는다. 전처리 전체 run은 사용 가능하지만 평가 대상은 이 고정 구간이다.

### 3.2 주전처리 명세

- Schaefer-100: atlas release, 공간, 해상도, interpolation, 100 ROI 순서와 checksum을 고정한다. atlas 정보의 실제 값은 provenance 단계에서 채운다.
- motion 6개, 그 시간 미분, 각 12개 항의 제곱으로 24 motion regressors를 구성한다. WM/CSF noise 영역에서 유래한 aCompCor 5개를 metadata의 설명분산 순서로 선택한다. 선택 정의에 맞는 5개가 없으면 임의 다른 열로 대체하지 않는다.
- FD>0.5 mm 원본 frame에 spike regressor를 추가한다. frame 삭제 후 연결은 하지 않는다. 첫 frame의 구조적 FD 결측만 별도 표시하며 그 외 결측은 실패 처리한다. 미분 첫 행 처리도 구현 명세와 manifest에 남긴다.
- 주 band-pass는 0.008–0.1 Hz **[개정 P9: 0.008–0.2 Hz]**, GSR off다. nuisance와 filter를 일관되게 처리하는 하나의 검증된 구현·버전을 고정하고 drift/intercept 중복으로 rank를 늘리지 않는다. filter 종류·차수·padding·regression 순서는 pilot 기술 검증에서 기록하고 main 전에 동결한다. **[개정 P9]** regression 순서는 동시 회귀로 결정. 통과대역 상한은 0.2 Hz 로 결정 (2026-09-23, §11).
- **[개정 P6-a] filter 적용 단위를 명시한다.** band-pass 는 **전체 run 을 native grid 에서** 필터링한다. 60초 window 는 필터링 뒤에 잘라내는 분석 구간이지 필터 단위가 아니다. 따라서 0.008 Hz 성분의 분해 여부는 run 길이(270–480초)로 판단하며, 60초의 주파수 분해능 1/60 ≈ 0.0167 Hz 로 판단하지 않는다. 다만 0.008 Hz 는 60초 안에서 0.48 cycle 에 그치므로 **window 내부에서는 진동이 아니라 추세로 나타난다**. 이 성질을 제거하지 않고 그대로 둔다(추가 detrend 를 도입하지 않는다). 고역 차단을 0.01 Hz 또는 0.0167 Hz 로 올리는 대안은 WI-09 민감도 분석에서만 평가하며 주분석 명세를 바꾸지 않는다.
- run 내 ROI별 z-score를 사용한다. 전체 run을 이용하는 offline endpoint임을 명시하며 실시간·미래 예측으로 주장하지 않는다. events의 task 정답을 회귀한 feature를 classifier에 넣지 않는다.
- 2초 grid로 변환할 때 BOLD와 confound의 시간 대응을 보존한다. motion QC는 원본 시간축에서 구간에 포함된 frame들로 계산한다. 보간한 FD로 motion을 희석하지 않는다.

### 3.3 QC와 모집단

각 run 전체 mean FD≤0.2 mm, 전체 및 각 고정 window에서 FD>0.5 mm 비율≤10%를 주 기준으로 한다. FD 비율 분모는 해당 구간의 관측 가능한 원본 frame 수이며 구조적 첫 FD 결측은 제외하고 수를 보고한다. task의 30 원본 frames 구간에서는 최대 3개까지 허용한다. rest는 native frame 수로 계산한다. **[개정 P7]** 이 "최대 3개"는 **30 원본 frame 창에서의 비율 규칙을 개수로 표현한 것**이다(3/30 = 0.10 으로 비율 상한과 정확히 같다). 따라서 창의 원본 frame 수가 다르면 같은 비율이 되도록 **비례 조정한다** — `허용 = 3 × (관측 frame 수 / 30)`. PIOP1 restingstate 는 TR 0.75초라 60초 창이 **80 frame** 이므로 허용이 8 이다. 절대 3개를 그대로 적용하면 실효 비율이 3.75% 로 10% 기준의 **2.7배 엄격**해져 rest 가 부당하게 제외된다. TR 2초 창(30 frame)의 판정은 개정 전과 동일하다.

BOLD/FC nonfinite, constant ROI, 100 ROI 불일치, confound 정렬 오류, 잔차 자유도 부족, 필요한 구간 누락은 run 제외다. **[개정 P6-b] residual DOF 정의를 동결한다.** filter 로 잃는 자유도를 포함해

```
residual_dof = min( n_volumes - rank(design),
                    floor( 2 * (f_high - f_low) * T_run_sec ) )
```

로 정의하고 `residual_dof <= 30` 이면 run 을 제외한다. 두 번째 항은 통과대역 [0.008, 0.1] Hz 가 길이 `T_run_sec` 의 run 에서 남기는 실수 자유도(각 유지 주파수당 sin/cos 2개)다. 확정된 6개 조합의 filter 항 값은 PIOP1 emo 49, PIOP1 WM 59, PIOP1 rest 66, PIOP2 emo 49, PIOP2 WM 58, PIOP2 rest 88 로 전부 30을 넘는다 — 즉 실제로는 `n_volumes - rank(design)` 항이 아니라 이 항이 하한을 준다는 사실만 기록하고, 기준 자체는 완화하지 않는다. **[개정 P10] 위 `min(…)` 식은 P9 구현과 함께 정확식으로 대체된다:**

```
residual_dof = n_volumes - rank([design, dct_stopband_basis])
```

`dct_stopband_basis` 는 P9 의 차단대역 DCT-II 기저다. 제외 기준 `residual_dof <= 30` 은 그대로다. 위 P6-b 식과 그 filter 항 값은 개정 기록으로 남긴다. residual DOF는 전처리 전체 run 기준이다. ROI를 임의 삭제하거나 유효 window를 다른 시점으로 바꾸지 않는다. 두 task와 rest의 각 4개 window가 모두 유효한 subject만 primary complete-case에 포함한다. 제외 사유는 중복 사유와 우선 사유를 모두 저장한다.

196명은 상한 후보이고 최종 N이 아니다. QC를 통과한 수 N을 확인한 후 아래 pilot을 분리한다. 분석 가능성이 낮으면 모델 복잡화 대신 feasibility 결과를 보고한다. 기준 변경은 main 성능을 보기 전에만 새 버전으로 허용한다.

## 4. 개발·분할·접근 경계

1. canonical subject와 알려진 가족/중복 관계를 연결한 `group_id`를 만든다. PIOP1/2 중복은 가능한 metadata로 검사하며 확인 불가능한 범위도 보고한다.
   **[개정 P4] 실제로 쓸 수 있는 관계 metadata 가 없다.** 2026-09-17 Wave 1 로 내려받은 PIOP1/PIOP2 participants.tsv 와 sidecar 어디에도 가족·쌍둥이·중복참여 식별 열이 없다(차단 항목 U10). 따라서 `group_id`는 **1 subject = 1 group 으로 퇴화**시키고, 그 사실과 다음 미검증 범위를 결과에 함께 적는다: (a) 같은 dataset 안의 가족·반복 참여자는 서로 다른 fold 에 배정될 수 있으며 이를 배제할 근거가 없다, (b) PIOP1/PIOP2 사이의 동일인 참여는 subject ID 로 판정할 수 없다 — 두 dataset 이 같은 `sub-0001…` 네임스페이스를 쓰기 때문이다(U17, 개정 P5 참조). 이 퇴화는 group 단위 재표집(§8)에도 그대로 적용되어 bootstrap 의 group 이 subject 와 같아진다. 관계 metadata 를 공식 경로로 확보하면 새 탐색 버전으로 다시 분할한다 — 기존 결과를 사후 수정하지 않는다.
2. QC 후 pilot 목표 인원은 `min(32, floor(0.2N))`이다. seed 20260917로 group 순서를 정하고 목표를 넘기지 않는 전체 group만 배정한다. 실제 수와 미달 이유를 기록한다. pilot은 구현·설정 점검용이며 **main 및 최종 external 모델/template fit에서도 제외**한다.
3. 남은 main pool에 outer 5-fold, 각 outer train에 inner 3-fold grouped CV를 적용한다. outer seed 20260918, inner seed `20261000+outer_fold`(fold 0–4), external 최종 선택 seed 20262000을 사용한다. 각 subject가 두 task를 모두 가지므로 task별 window stratification은 하지 않는다. group 수가 부족하면 분할을 자동 축소하지 않고 설계를 갱신한다.
4. Fold 배정은 NumPy PCG64의 지정 seed로 group tie-break 순서를 만든 뒤 group 인원수 내림차순(동률은 그 순서)으로, 현재 subject 수가 가장 적은 fold에 배정한다. fold 인원 동률은 작은 fold index를 택한다. inner는 해당 outer train에서만 같은 알고리즘을 적용한다. library/algorithm 버전과 실제 배정을 저장하며 확정된 `folds.json`과 hash가 실행의 최종 기준이다. split manifest를 먼저 저장하고 모든 모델이 같은 split을 읽는다. pilot·outer test·inner validation의 rest도 해당 fit에서 제외한다. validation transform 시 refit하지 않는다.
5. metadata/QC 확인과 model outcome 접근을 구분한다. PIOP2 파일명의 task 정보까지 완전 blind라고 주장하지 않되 성능·예측은 모델 선택에 쓰지 않는다. main OOF를 본 뒤 QC, feature, grid, threshold를 변경하면 새 탐색 버전이다.

## 5. Fold 내부 FC 변환과 graph bank

각 30×100 window에서 Ledoit–Wolf covariance를 correlation으로 변환한다. 상수 ROI는 사전에 거부한다. signed upper triangle 4,950개를 `clip(−1+1e−6,1−1e−6)` 후 Fisher-z 변환한다. training-rest 4 windows/subject에서만 StandardScaler와 PCA 10차원(whiten=false, full SVD)을 fit한다. 유효 rank<10이면 실패하며 몰래 차원을 줄이지 않는다. 같은 변환 artifact를 clustering과 task gate 입력에 공유한다.

PCA rest features에 K-means K=3, n_init=50, max_iter=500을 사용한다. seed는 `30000+100*outer_fold+inner_fold`로 정하며 outer fit은 inner_fold=9, external inner는 outer_fold=9, external final은 (9,9)를 쓴다. RNG를 모델 seed와 분리한다. A–D 및 모델 seed 42–44는 해당 fit의 같은 bank를 사용한다. cluster는 모델 구성 요소이며 생리적 상태 정답이 아니다.

cluster별 원래 correlation matrices의 평균이 raw centroid다. PCA를 inverse-transform한 값을 centroid로 쓰지 않는다. 각 centroid의 diagonal을 0으로 만들고 전체 가능한 upper-triangle edge 4,950개의 20%=990개를 목표로 가장 큰 양수 edge를 보존한다. 양수가 부족하면 있는 양수만 보존한다. 동률은 ROI index 순으로 처리하고 실제 density를 기록한다. 대칭 복원 후 self-loop I를 추가해 `S_k=D^(−1/2)(A_k+I)D^(−1/2)`를 저장한다.

주 null은 seed 1729로 100 ROI permutation P 하나를 생성해 모든 k에 동일하게 `P S_k Pᵀ`를 적용한다. 입력 ROI 순서는 그대로다. 전체 spectrum·weight 분포·bank 간 관계는 보존하나 각 해부학 ROI의 degree는 보존하지 않는다. 추가 null seeds 1730–1733은 민감도다. primary graph는 양의 FC만, gate는 signed FC를 사용한다.

## 6. 모델·대조군 명세

| ID | 고정 bank | Routing | 주 비교 |
|---|---|---|---|
| A | training-rest brain | FC 입력 의존 | 제안 구성 |
| B | A와 동일 | 모든 입력에 공통인 학습 logits 3개 | A−B |
| C | 공동 ROI-permuted null | A와 같은 gate | A−C |
| D | C와 동일 | B와 같은 fixed mixture | interaction |

ROI encoder는 각 ROI에 동일하게 Conv1d(1→16→32, kernel=3, padding=1), 각 층 GELU·dropout을 적용한다. Conv 후 시간축 mean 및 std(correction=0)를 결합한 64차원을 Linear(64→32)로 줄인다. graph 전에는 ROI 간 혼합이나 ROI ID embedding이 없다.

Dynamic gate는 PCA 10→Linear32→GELU→Linear3→softmax(temperature=1)다. Fixed gate는 학습 logits 3개의 softmax이며 uniform과 다르다. top-k, sample entropy loss, balance loss는 모두 off다. gate의 FC bypass를 prediction head에 추가하지 않는다.

`S(x)=Σ_k π_k(x) S_k`이며 혼합 뒤 다시 normalize하지 않는다. 공유 graph layer 2개는 `H_next=LayerNorm(H+Dropout(GELU(S(x)HW+b)))`다. ROI mean pooling 후 Linear(32→2)로 분류한다. 명시적인 dense tensor backend 하나를 사용하며 PyG 설치 유무로 연산을 바꾸지 않는다. bank는 optimizer에서 제외한다.

필수 비교의 실행 우선순위:

| 묶음 | 구성 | 역할 |
|---|---|---|
| S 후보 1 | raw ROI mean/variance(200 features) + logistic regression | 저차 통계 기준선 |
| S 후보 2 | 동일 200 features + 32-hidden MLP | 비선형 저차 기준선 |
| S 후보 3 | signed Fisher-z FC 4,950 + logistic regression | 강한 FC 기준선 |
| S 후보 4 | 위 FC + 32-hidden MLP | 비선형 FC 기준선 |
| 구조 비교 | ROI encoder pooled feature + PCA FC10 fusion MLP | 같은 종류의 정보에 접근하는 no-graph comparator; 완벽한 구조 ablation은 아님 |
| 구조 비교 | training-rest single average graph + 동일 encoder/head | 여러 template의 필요성 |
| Historical | mean-only MoBSE를 실제 target으로 재학습 | 기존 구조와 연결 |
| 문헌 비교 | BQN, dFCExpert 동일 split/target 적응 | 공식 구현·라이선스·입력 차이 검토 후 별도 versioned 계획 |

S 후보의 StandardScaler는 해당 training task에만 fit한다. logistic C는 {0.001,0.01,0.1,1,10,100,1000,10000}, L2·intercept 사용, solver와 tolerance를 고정한다. **[개정 P11]** 미수렴 설정은 빼고 나머지 grid에서 고르되, 뺀 설정 수를 보고한다 (§11). MLP는 아래 8개 grid와 같은 예산이다. S는 각 outer fold에서 inner subject-equal log loss가 가장 낮은 후보/설정으로 고른다. 외부 S도 PIOP1 main pool의 inner 결과로만 고른다. BQN/dFCExpert는 재현 완료로 쓰지 않으며, 구현 전 별도 비교 명세가 필요하다.

B/D가 FC feature를 계산하더라도 예측에 직접 사용하는 경로는 없다. 따라서 A−B는 입력 의존 FC routing 경로 전체의 추가 가치를 뜻하며 동일 feature 접근을 유지한 순수 parameter-only 효과는 아니다. no-graph FC comparator와 실제 parameter/비용을 함께 보고한다.

## 7. 학습·선택·계산 예산

공통 grid는 learning rate {0.001,0.0003} × dropout {0.1,0.3} × weight decay {0.0001,0.001}=8개다. 순서는 위 나열 순 Cartesian product의 config_id 0–7로 고정한다. AdamW, batch 32, cross-entropy, max 50 epochs, gradient norm clip 1.0을 사용한다. **[개정 P8]** 최소 1,500 update 보장·상한 200 epoch·최소치 이후 early stopping 으로 대체 (§11). 학습 window는 균등 shuffle하며 각 subject는 task별 4개로 같은 기여를 한다.

Inner seed=42, early stopping은 run 확률로 계산한 subject-equal validation log loss, patience=5, min_delta=0.0005다. log loss는 확률을 [1e−7,1−1e−7]로 clip한다. selected best checkpoint의 epoch를 기록한다.

**A–D는 공통 config 하나를 공동 선택**한다. 각 config의 inner OOF run loss를 subject별 동일 가중으로 합산하고 A–D 네 cell에 같은 가중을 주어 최소화한다. 동률(차이≤1e−6)은 공동 BA가 높은 것, 이후 config_id가 작은 것으로 정한다. 이는 동일 recipe에서의 요인 비교이며 각 cell을 독립 최적화한 최고 성능 비교가 아니다.

선택 config의 4 cells×3 inner folds best epochs 중앙값을 올림해 공통 E(1–50)를 정한다. outer train 전체로 bank/변환을 다시 fit하고 각 cell을 seeds 42,43,44에서 정확히 E epochs 학습한다. outer test로 early stopping하지 않는다. 모델 전용 RNG stream으로 같은 seed의 공통 encoder 초기화를 맞추고 RNG 차이를 기록한다. Baseline의 epoch는 해당 선택 모델의 3개 inner best epochs 중앙값 올림이다.

| 비용 묶음 | 계산 | Fits |
|---|---|---:|
| A–D main inner | 8 configs×3 folds×4 cells×5 outer | 480 |
| A–D main outer | 4 cells×5 outer×3 seeds | 60 |
| 추가 null 민감도 | 4 nulls×2 cells(C/D)×5 outer×3 seeds | 120 |
| External 최종 선택 | 8×3×4, PIOP1 main pool 내부 | 96 |
| External 최종 fit | 4 cells×3 seeds | 12 |

추가 null은 primary의 config·E를 재사용하는 조건부 민감도이며 재튜닝하지 않는다. baseline·pilot·mechanism·다른 민감도 비용은 별도다. 표는 실행 횟수 계획이고 소요시간 보장이 아니다. pilot에서 peak memory·시간을 측정해 자원 계획을 만든다.

## 8. 평가·통계·결론 규칙

각 window의 세 seed 확률을 평균하고, 각 task의 네 window를 평균해 subject당 두 run probability를 얻는다. threshold=0.5이며 동일값은 class 1로 정한다. subject i의 `b_i=(I[emo correct]+I[WM correct])/2`, BA는 `mean_i(b_i)`다. 두 task complete-case이므로 통상 binary BA와 같고 각 subject에 동일 가중을 준다.

주 contrast는 같은 subject의 b 차이로 계산한다. seed 9001, 10,000회 paired bootstrap을 사용하며 모든 cell에 같은 재표집을 적용한다. 두 contrast 각각 percentile 97.5% CI(1.25–98.75 percentiles)를 보고해 family-wise 95%를 보수적으로 제어한다. 가족/중복 group이 있으면 group 전체를 재표집하고 반복 추출된 subject에 동일 가중을 적용한다. window·seed·fold 수를 N으로 세지 않는다.

- 하한>0: 해당 추가 기여 지지. 점추정≥δ이더라도 하한≤δ이면 실질적 우월성 확정은 아님.
- 하한>δ: 선택한 최소 효과 이상의 우월성 지지.
- CI가 0을 포함: 불확실. 비유의를 효과 없음·동등성으로 바꾸지 않는다.
- 두 primary가 모두 지지되어야 brain alignment와 routing이 모두 기여한다는 결론을 쓴다.
- 내부 OOF bootstrap은 고정된 학습 결과에 조건부이며 training-set 변동을 완전히 반영하지 않는다. 외부 고정 모델 평가는 새 cohort에서의 조건부 성능이다.

A−S, interaction, macro-F1, AUROC, log loss, calibration, subgroup, routing diagnostics는 보조이며 95% 기술적 CI로 표시한다. subgroup N을 함께 보고한다. 동등성은 사전 ±δ margin을 이용한 별도 계획 없이는 선언하지 않는다.

정밀도 계획은 QC 후 N과 사전 paired-error discordance/상관 시나리오로 simulation하며, 분리된 pilot의 추정은 불확실성과 함께 보조적으로 사용한다. metadata만으로 paired effect power를 추정했다고 하지 않는다. 목표δ를 검출할 정밀도가 부족하면 inconclusive 가능성을 명시한다. main OOF 후 δ나 분석 N을 유리하게 바꾸지 않는다.

**유의성은 실행 gate가 아니다.** 내부 결과가 음성이어도 데이터와 설계가 잠겨 있으면 외부 검증을 수행하고 같은 가설을 보고한다. 데이터 오류·leakage는 중단 사유지만 가설 미지지는 실패한 실행으로 숨기지 않는다.

## 9. 외부 검증과 보조 분석

PIOP1 main pool(pilot 제외)에서 같은 3-fold selection 규칙으로 config/E를 정하고 bank·변환·모델을 최종 fit한다. PIOP2 rest·labels·성능으로 fit/선택/calibration하지 않는다. PIOP2는 같은 QC·window 규칙과 task pairing을 적용하고 cohort 차이·제외 수를 보고한다. 파일·설정·checkpoint hash를 잠근 뒤 한 번의 주평가 release를 만든다. 코드 버그 재평가는 원 결과와 수정 사유를 보존한다.

보조 분석은 main을 대체하지 않는다: routing을 training 평균으로 고정하거나 label을 보지 않는 shuffle, FD/DVARS/tSNR nuisance-only 모델, time-only 기준선, window별 결과, no-graph/average graph, 추가 null 4개. routing intervention은 모델 의존성이지 뇌 인과성 검증이 아니다. fixed acquisition order 교란은 time-only chance로 해소되지 않는다.

선택적 민감도는 40/80초 window(같은 240초에서 각각 6/3개), Pearson, GSR on, native-rate FC, Schaefer-200, K=2/5다. 각 변경의 QC 집합과 pairing을 명시하며 결과가 좋은 설정으로 primary를 교체하지 않는다. stationary surrogate와 trial-level HRF 분석은 추가 명세 없이는 본 계획에 포함된 완료 작업으로 쓰지 않는다. 본 연구는 전환 동역학을 입증하지 않는다.

효율 측정은 동일 장비/batch/precision에서 FC·PCA 포함 end-to-end latency, 모델 latency, peak memory, parameter 수를 분리한다. 지원되지 않는 FLOPs는 NA다. dense 0 edge를 sparse 실행이라고 하지 않는다.

## 10. 실행 순서와 최종 산출물

| Gate | 필수 산출물 | 다음 단계 조건 |
|---|---|---|
| G0 Provenance | source manifest, 시간축 대조, atlas/confound 근거 | 미해결 TR·offset·원본 대응 0 |
| G1 Measurement lock | 재추출/QC, pilot/main IDs, split hashes, 정밀도·자원 계획 | 고정 rule와 실제 N, pilot 경계 확인 |
| G2 Implementation lock | acceptance tests, config/code/environment hashes | leakage·연산·endpoint 검증 통과 |
| G3 Internal release | 모든 OOF 예측·선택 이력·CI·실패 로그 | 완전성과 정합성 통과; 유의성 불요 |
| G4 External release | 최종 PIOP1 fit, 잠금 기록, PIOP2 결과 또는 미확보 사유 | target/QC·중복 확인, 외부 선택 없음 |
| G5 Interpretation | claim–evidence 표, 비용·제한·재현 패키지 | 각 주장과 원 artifact 연결 |

현재 G0–G5는 **미완료**다. 기존 감사는 새 pipeline gate 통과를 뜻하지 않는다. 구현은 별도 v2 경로에서 진행하고 기존 dirty changes·checkpoint·문서·원고를 보존한다. 각 작업의 입력/출력/검증/중단 조건은 작업 지침서를 따른다.


## 11. 개정 기록

사전 등록 문서이므로 본문을 조용히 고치지 않는다. 각 개정은 아래 표에 원문·개정문·근거를
남기고, 본문의 해당 위치에는 `[개정 Pn]` 표시를 붙인다. **모든 개정은 main 성능을 보기 전에
이루어졌다** — 이 문서의 어떤 개정도 결과를 본 뒤의 결정이 아니다.

| ID | 위치 | 개정 전 | 개정 후 | 근거 | 날짜 |
|---|---|---|---|---|---|
| P1 | §2 | "로컬 WM 160 대 문헌 162 volumes 차이는 실제 제거 volume 기록으로 설명해야 한다" | cohort 간 차이로 정정. PIOP1 WM은 로컬 204명 전원 162 vol, 160은 PIOP2 값. smoke 트리의 240은 PIOP2 rest | Wave 1 sidecar 측정 (`provenance/h197_wave1/wave1_runs.jsonl`, 1,295 run) | 2026-09-17 |
| P2 | §2 | "D1에서 두 target TR은 2초이며 PIOP2 rest 240 volumes는 480초다" | 근거를 문헌 D1에서 **sidecar 직접 측정**으로 교체. 6개 dataset×task 조합 전부 확정(조합 내 분산 0) | D1 행에 TR·volume 수치가 없음. Wave 1 에서 OpenNeuro sidecar JSON 직접 판독 | 2026-09-17 |
| P3 | §3.1 | `[12,252)` 구간 동결 조건부화 제안 | **철회.** 6개 조합의 run 길이가 270–480초로 전부 252초를 넘어 `[12,252)` 가 무조건 성립 | Wave 1 로 TR 확정 후 재계산 | 2026-09-17 |
| P4 | §4-1, §8 | `group_id`, group 단위 재표집 | 관계 metadata 부재(U10)로 **1 subject = 1 group 퇴화**를 명시하고 미검증 범위 2항을 기록 | Wave 1 participants.tsv·sidecar 전수 확인 | 2026-09-17 |
| P5 | §3.1, 지침서 §2 | `canonical_subject` | **dataset prefix 필수화**. `ds002785:sub-0001` 형식 — 구분자는 `:` 다. run_key 가 `/` 로 나뉘므로 prefix 를 `/` 로 붙이면 키 분해가 모호해진다. prefix 는 별칭(piop1)이 아니라 OpenNeuro accession 을 쓴다 | U17: 두 dataset 이 같은 subject 네임스페이스 사용, 문자 교집합 216 / 전 열 일치 0 | 2026-09-17 |
| P6-a | §3.2 | band-pass 0.008–0.1 Hz (적용 단위 미기재) | **전체 run 을 native grid 에서 필터링**함을 명시. 60초 window 는 필터 뒤 잘라내는 분석 구간. 0.008 Hz 가 window 내에서 0.48 cycle 로 추세처럼 나타나는 성질을 기록하고 detrend 를 추가하지 않음. 고역 차단 대안은 WI-09 민감도로 이관 | 60초 분해능 1/60 ≈ 0.0167 Hz 와 run 길이 270–480초의 구분 | 2026-09-17 |
| P6-b | §3.3 | `residual_dof = n_volumes − rank(design)` | `min(n_volumes − rank(design), floor(2·(f_high−f_low)·T_run))` 로 동결. 6개 조합의 filter 항 = 49/59/66/49/58/88 | filter 로 잃는 자유도를 세지 않으면 residual DOF 를 과대 보고함 | 2026-09-17 |
| P7 | §3.3 | "task의 30 원본 frames 구간에서는 최대 3개까지 허용한다" 를 창 길이와 무관한 절대 개수로 구현 | **관측 frame 수에 비례 조정**: `허용 = 3 × (n_observed / 30)`. 80 frame 창(PIOP1 rest, TR 0.75)에서 허용 8 | 3/30 = 0.10 으로 비율 상한과 동일 — 절대 3개는 30 frame 창에서의 비율 규칙 표현이다. 절대 적용 시 rest 에 2.7배 엄격 | 2026-09-17 |
| P8 | §7 | "max 50 epochs", "early stopping … patience=5, min_delta=0.0005" | **최소 1,500 optimizer update 보장, 상한 200 epoch, early stopping 은 최소치 이후에만.** 선생님 결정 원문(2026-09-23): "P8 - 최소 1,500 update 보장, 상한 200 epoch, early stopping은 최소치 이후에만 ok (필요하다면 epoch 수를 더 늘려도 됨. 최소 수치 조정도 가능)". patience·min_delta 값 자체는 이 결정이 바꾸지 않았다. 상한·최소치의 조정은 **main OOF 전에 pilot 측정으로만** 하고 그 값과 근거를 이 표에 추가 행으로 남긴다 | pilot 기술 검증(보고서 부록 W): 원인은 epoch 이 아니라 update 수. batch 32 에서 200 update 는 train BA 0.5, 800 update 는 1.0. main inner 50 epoch = 850 update 로 탈출 경계 | 2026-09-23 (구현 2026-09-23: `train.MIN_UPDATES=1500`, `MAX_EPOCHS=200`, config `train.min_updates` 잠금. 구현 선택(결정 아님): 최소 epoch = ceil(1500 / ceil(n_train/32)); inner 는 최소 epoch 전 epoch 를 best 후보·인내 계산에서 제외하므로 best epoch ≥ 최소 epoch; 최소 epoch 이 상한을 넘거나 outer 공통 E 가 최소 update 를 못 채우면 fit 거부. 상한·최소치 값은 바꾸지 않음) |
| P9 | §3.2 | "filter 종류·차수·padding·regression 순서는 pilot 기술 검증에서 기록하고 main 전에 동결한다" | **regression 순서 = 동시 회귀**: nuisance 설계행렬과 통과대역 밖 주파수 기저를 하나의 설계행렬로 한 번에 회귀한다. 선생님 결정 원문(2026-09-23): "band-pass - 동시 회귀 ok". 기저 종류(DCT-II 후보)·**통과대역 상한**은 이 결정의 범위 밖이며 아래 "보류" 참조. **통과대역 상한 결정 원문(2026-09-23 14:21 KST): "통과대역 0.2 Hz로"** → 주 band-pass 0.008–0.2 Hz. 하한 0.008 Hz 는 바꾸라는 말이 없어 그대로다. 기저는 DOF 실측에 쓴 DCT-II 로 구현했다(결정이 아니라 측정과 맞춘 구현 선택). 2초 목표 격자 Nyquist 0.25 Hz 아래라 anti-aliasing 조건 유지 | Hallquist et al. 2013 (NeuroImage, PMID 23747457), Lindquist et al. 2019 (Hum Brain Mapp, PMID 30666750): 순차 처리가 제거한 잡음을 되돌려 넣음 | 2026-09-23 (구현; 전 창 재추출 전) |
| P10 | §3.3 | P6-b `residual_dof = min(n_volumes − rank(design), floor(2·(f_high−f_low)·T_run_sec))` | **`residual_dof = n_volumes − rank([design, dct_stopband_basis])`** (정확식). `MIN_RESIDUAL_DOF = 30`·제외 규칙은 불변 | P9 동시 회귀(결정 2 원문 "band-pass - 동시 회귀 ok")의 귀결: 한 설계행렬로 회귀하면 잔차 자유도는 결합 설계의 rank 로 정확히 정해진다. P6-b 식은 nuisance 와 filter 가 같은 자유도를 이중으로 쓰지 않는다고 가정해 과대 보고했다(상한 0.1 Hz 에서 emo·WM ok run 783건 전부 30 이하). 상한 0.2 Hz 실측: 탈락 0건, 최소 DOF PIOP1 emo/WM/rest 66/82/80, PIOP2 67/87/145 (`MoBSE_dataset/recovery_20260923/checks/dof_probe_hi0.2.json`) | 2026-09-23 (구현) |
| P11 | §6 | "logistic C는 {0.001,0.01,0.1,1,10,100,1000,10000}, L2·intercept 사용, solver와 tolerance를 고정한다" (미수렴 처리 규칙 없음) | **"미수렴 설정은 빼고 나머지 grid에서 고르되, 뺀 설정 수를 보고합니다."** 선생님 결정 원문(2026-09-23 21:5x KST): 권고 "main pool을 쓰지 않는 pilot 창으로 수렴 여부부터 재고, 그 결과를 보고 (a)를 사전 등록하는 것입니다" 에 "ok". solver·tol·max_iter·C grid 는 바꾸지 않는다. 한 outer fold 의 모든 설정이 미수렴이면 선택을 멈춘다(구현 선택) | pilot 측정 (보고서 부록 AG.1; main pool 미소비): pilot 기술 분할 5 outer × 3 inner = 15 fold × S1·S3 × C 8 = **240 fit, 미수렴 0**. 반복 수 최대 S1 73 · S3 35 (max_iter 10000). 학습 창 104–112. 수렴 판정은 sklearn lbfgs 의 tol 기준이다 — 분리 가능한 자료에서 유한한 최적해가 있다는 뜻은 아니다. main 학습 창(528–544)으로 외삽하지 않는다 (`MoBSE_dataset/derivatives_v3/pilot_tech_p8/logistic_convergence/`) | 2026-09-23 (사전 등록, main OOF 전) |

### 철회·보류

* **[결정됨 2026-09-23 14:21 KST — P9 행·P10 행 참조] ~~P9 의 통과대역 상한은 보류다 (선생님 결정 대기, 2026-09-23).~~** 아래는 결정 전 기록으로 남긴다. 동시 회귀로 정확히 센 residual DOF `n − rank([nuisance, 차단대역 기저])` 는 P6-b 의 `min(…)` 식보다 작다 — P6-b 는 nuisance 와 필터가 같은 자유도를 이중으로 쓰지 않는다고 가정해 **과대 보고한다**. confounds 만으로 전 ok run 을 실측한 결과(DCT-II, 하한 0.008 Hz, `MIN_RESIDUAL_DOF = 30`), 상한 0.1 Hz 에서는 **emomatching·workingmemory ok run 783건 전부**가 30 이하(emo 최대 20, WM 최대 29), PIOP1 rest 29/202 건이 30 이하다. 상한 0.15 / 0.2 / 0.25 Hz 에서는 탈락 0건, 최소 DOF 39 / 66 / 92. 산출물: `MoBSE_dataset/recovery_20260923/checks/dof_*.json`. **P6-b 는 P9 구현 시 정확식으로 대체된다** (별도 행으로 기록 예정). 2026-09-23 추천안 표의 "DOF = n − p_nuis − p_freq 로 P6-b 회계와 정확히 일치" 는 틀린 서술이었다 — 정확식은 P6-b 와 다르다.

* **P3 철회.** 계획서 §3.1 의 `[12,252)` 는 수정 없이 유지한다.
* P6-b 는 기준을 더 엄격하게 만든다. **P7 은 rest 에 한해 완화 방향이지만, 이는 기준 완화가 아니라 계획서가 정한 10% 비율 기준을 정확히 적용하는 것이다** — 종전 구현이 그 기준보다 엄격했다. TR 2초 창의 판정은 변하지 않는다.
* **P5 미반영 산출물이 하나 있다.** WI-01 감사본 `provenance/source_runs.jsonl`(schema `wi01-source-runs-0.1`, 1,228 run)은 개정 이전에 생성되어 `canonical_subject` 가 `sub-0001` 형식이고 `run_key` prefix 도 별칭(`piop1/…`)이다. 이 파일은 **원자료 미확보 상태의 기록**이므로 소급 수정하지 않고, WI-02 재추출이 만드는 release 산출본부터 P5 형식을 적용한다. release 스키마 검증기(`manifests.validate_record`)가 그 시점에 강제한다.
