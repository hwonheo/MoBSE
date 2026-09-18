# MoBSE 재설계 작업 지침서

**버전 1.0 · 2026-09-17 · 적용 프로토콜 v1.1**

목적은 [재설계 프로토콜](mobse_redesign_protocol_2026-09-17.md)을 재현 가능하게 구현·검증·실행하는 것이다. 이 문서는 작업 명세이며 아래 v2 모듈, CLI, manifests, tests가 이미 구현되어 있다는 뜻이 아니다. 이번 작성 범위는 계획서와 지침서다. 대량 다운로드·학습·원고 수정은 수행하지 않았다.

## 1. 작업 원칙과 담당 역할

- 실행 담당: 데이터 provenance, v2 구현, smoke/acceptance tests, 잠긴 설정 실행, 모든 artifact 저장.
- 검토 담당: fit subject 경계·target 독립성·통계 단위·claim 연결을 독립적으로 확인. 하위 에이전트를 쓸 경우 해당 모듈 작성자와 검토자를 구분한다.
- 통합 담당: gate evidence와 버전을 취합하고 다음 작업을 배정한다. 문서상의 검토 기록은 별도 사용자 승인 요청을 뜻하지 않는다.
- 기존 tracked/untracked 변경·원자료·실험 결과를 보존한다. 과거 산출물을 v2 경로로 복사해서 새 결과처럼 보고하지 않는다.
- 작업 시작 시 git 상태와 기존 관련 파일 hash를 기록한다. 편집할 기존 파일은 archive에 원본을 보존한다. main 성능 접근 뒤 설계 변경은 새 exploratory version으로 분리한다.
- 환자/참가자 수준 자료는 로컬 분석 경로에 두고 공개 패키지는 집계·코드·비식별 허용 범위로 제한한다. 공개 가능 범위는 dataset 사용 조건을 따른다.

권장 작업 순서는 **WI-00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11**이다. WI-04와 WI-05 구현은 인터페이스 잠금 후 병렬 가능하나 WI-07 전 통합 테스트가 필수다.

## 2. 예정 경로와 artifact 계약

다음 경로는 새로 구현할 권장 구조다. 이미 존재하는 실행 명령으로 오인하지 않는다.

```text
mobse/v2/
  manifests.py      # schema, stable keys, source/fit provenance
  preprocess.py    # native timing, nuisance, resample, fixed windows
  splits.py        # pilot and immutable grouped folds
  features.py      # shrinkage FC, frozen scaler/PCA
  templates.py     # train-rest bank and joint permutation null
  models.py        # shared ROI encoder, gates, graph stack
  train.py         # inner selection, common epoch, final fits
  evaluate.py      # classification-only predictions and aggregation
  statistics.py    # paired subject/group bootstrap
  cli.py           # explicit subcommands; implementation pending
configs/redesign_v1/  # runtime configs, implemented schema required
results/redesign_v1/<release_id>/
  provenance/ qc/ splits/ locks/ fits/ predictions/ statistics/ reports/
tests/v2/           # dedicated tests, no dependency on broken legacy tests
```

`release_id`는 ASCII로 `YYYYMMDD_<short-code-hash>_<config-hash-prefix>` 형식을 사용한다. 같은 release 결과를 덮어쓰지 않는다. 실패 재시도는 attempt 번호를 추가한다. 경로·entity에 개인정보를 추가하지 않는다.

| Artifact | 필수 필드/내용 | 검증 |
|---|---|---|
| `source_runs.jsonl` | schema_version, run_key, dataset, canonical_subject, group_id, task, source/JSON/confounds/events paths+SHA256, native_tr, n_volumes, derivative_start_sec, discarded_volumes, event_origin, atlas_id/hash/ROI_order_hash | key 유일성, 원본 존재·hash, 시간축 대응 |

> **[개정 P5]** `canonical_subject` 는 `ds002785:sub-0001` 처럼 **dataset prefix 를 반드시 포함한다**. PIOP1/PIOP2 가 같은 `sub-0001…` 네임스페이스를 쓰므로 prefix 없이는 서로 다른 사람이 같은 키를 갖고, WI-08 subject independence 검사가 216건의 위양성을 낸다(차단 항목 U17). `mobse/v2/manifests.py::validate_canonical_subject()` 가 실행 시점에 강제하며, prefix 없는 값은 명시적 실패다 — 자동 보정하지 않는다.

| `preprocessing.jsonl` | run_key, code/env/config hash, nuisance_columns, design_rank, residual_dof, filter/resample 명세, original/derived grid, output hash | task별 TR; origin·coverage·rank |
| `windows.jsonl` | window_key, run_key, start/end sec, source_frame_range, target_grid, n_samples, ROI count, QC flags, data hash, observed label, label_source | label=실제 task; 4 windows/run |
| `exclusions.jsonl` | subject/run/window key, stage, all reasons, primary reason, rule_version | 제외 행 삭제 금지; flow counts 일치 |
| `subjects.jsonl` | subject/group, cohort, eligible, pilot/main/external, assignment reason | 가족/중복 분리 없음 |
| `folds.json` | schema/seed/hash, algorithm/version/tie-break, main IDs, outer train/test 및 inner train/val group IDs | 모든 경계 교집합 0 |
| `fit_manifest.json` | fit_id, parent_release, role, cell, folds, model_seed, bank_seed/null_seed, fit_subjects, scaler/PCA/bank IDs, code/env/config/source/split hashes | 허용 train IDs만 fit |
| `selection.json` | config별 inner loss/BA, best epochs, 실패 원인, selected config, tie rule, 공통 E | 모든 후보·cell·fold 완전성 |
| `window_predictions.jsonl` | subject/group, run/window, truth, p_class1, cell, model_seed, outer_fold 또는 external, checkpoint/fit hash | 예상 rows·범위·중복 검사 |
| `run_predictions.jsonl` | subject/run/truth, ensemble p, n_windows=4, n_seeds=3, threshold, prediction | window에서 정확 재계산 |
| `metrics.json` | subjects/groups/runs/windows, BA 및 contrasts, CI 수준/반복/seed/단위, scope | predictions에서 재계산 |
| `gate_evidence.json` | gate, status, checks, unresolved, timestamp, reviewer, artifact hashes | planned/running/pass/blocked 구분 |

Gate 초기값은 `planned`다. 파일 존재만으로 pass하지 않는다. 경로 추정이나 최신 glob으로 checkpoint/템플릿을 대신 찾지 않는다. ID와 hash가 맞지 않으면 실패시킨다.

## 3. 단계별 작업 카드

### WI-00 — 현재 상태 보존과 착수 기록

**입력:** 현재 repository, 기존 감사·문헌·프로토콜. **작업:** git status, commit, Python/torch/numpy/scipy/sklearn/nilearn 버전, 장비, 기존 변경 목록을 기록한다. 모든 파일을 무작정 읽거나 대용량 checkpoint를 일괄 로드하지 않는다. 기존 실험 inventory를 재사용한다.

**출력:** `provenance/workspace_snapshot.json`, `reports/implementation_map.md`, 계획한 신규 경로 목록. **완료 기준:** 수정 금지 기존 결과와 실제 편집 대상이 구분되어 있다. **중단:** current baseline을 식별하지 못하거나 기존 경로를 덮어써야만 진행되는 경우.

현재 환경 확인에 사용할 수 있는 읽기 명령은 `git status --short`, `.venv/bin/python --version`이다. 새 `mobse.v2` 명령은 아직 없으므로 예시 학습 명령을 복사 실행하지 않는다. 기존 전체 pytest에는 누락된 `mobse.data.hcp` import에 따른 collection 오류가 관측된 바 있으며, 신규 검증과 기존 suite 상태를 분리해 기록한다.

### WI-01 — 원본·TR·시간축 감사 (G0)

**입력:** 로컬 AOMIC 파일과 공개 source metadata/derivatives. **작업:** D1 및 실제 JSON/header를 대조하고 emo/WM/rest별 confounds·events를 대응시킨다. 다운로드 전에 필요한 파일만 inventory로 확정한다. WM 160/162 차이, 제거 volumes, PIOP2 rest duration, event origin을 run 수준에서 확인한다.

**출력:** `source_runs.jsonl`, `reports/timing_audit.md`, missing-source 목록, atlas 명세. **완료 기준:** 사용할 모든 run의 시간축과 원본 대응이 입증된다. **중단:** TR/offset 불명, 중복 key, confound alignment 미확인. 오래된 `.npy`의 모양이 맞다는 이유로 통과시키지 않는다.

### WI-02 — 올바른 추출·전처리·QC

**입력:** G0 통과 source manifest. **작업:** 먼저 소수 run에서 native-TR 처리와 2초 resampling을 검증한다. protocol의 [12,252) 구간을 원본 acquisition clock에서 선택한다. 처리 전후 길이·시간·PSD 및 confound rank를 점검하고 정확한 filter/edge 명세를 고정한다. 성능을 보며 필터를 선택하지 않는다.

**출력:** 재추출 ROI 시계열, `preprocessing.jsonl`, `windows.jsonl`, `exclusions.jsonl`, subject flow chart. **완료 기준:** 포함 subject마다 두 task+rest 각 4 windows, window shape [30,100], finite, 동일 ROI 순서, QC 규칙 충족. **중단:** 누락을 padding/다른 시점으로 대체해야 하거나 시간 정렬 오류가 남는 경우.

### WI-03 — Pilot·분할·정밀도·자원 잠금 (G1)

**입력:** QC eligible subjects/groups. **작업:** protocol seed로 pilot을 분리하고 main 5×3 folds를 저장한다. pilot에서만 구현·학습 가능성, 장비 비용, 기준선의 기술적 동작을 확인한다. paired error 시나리오와 pilot 불확실성을 이용해 δ=0.02 정밀도를 보고한다. 80% power를 확보했다고 근거 없이 적지 않는다.

**출력:** `subjects.jsonl`, `folds.json`, `reports/precision_scenarios.md`, `reports/resource_budget.md`, `locks/measurement_lock.json`. **완료 기준:** 실제 N과 분할 hashes가 고정되며 pilot은 모든 main/final fit에서 제외된다. **중단:** 관계 group 누출, fold 수 부족, pilot/main 경계 불명. 단지 작은 N이면 임의 증원 대신 제한을 보고한다.

### WI-04 — FC·bank·null 구현

**입력:** 해당 fit의 training-rest windows와 명시적 allowed_subjects. **작업:** shrinkage FC→Fisher-z→train scaler/PCA→K-means→원 correlation member mean→positive graph→normalize를 구현한다. 같은 PCA artifact를 gate에 제공한다. joint ROI permutation null은 bank 전체에 동일하게 적용한다.

**출력:** scaler/PCA, raw centroids, normalized bank, assignment, fit IDs와 hashes. **완료 기준:** 아래 T01–T05 통과. **중단:** val/test rest 접근, global-fit fallback, rank 부족 시 자동 축소, bank 해시 변동. 이 모듈에 task labels를 전달할 필요가 없다.

### WI-05 — A–D 및 최소 기준선 구현

**입력:** 고정된 tensor·feature·bank interface. **작업:** ROI encoder, dynamic/fixed gate, shared dense graph layer, classification head를 구현한다. A/B와 C/D는 같은 bank를 참조한다. no-graph FC fusion은 별도 comparator로 명명한다. 기존 MoBSE를 덮어쓰지 않는다.

**출력:** 신규 모듈, runtime config schema, model parameter/shape report. **완료 기준:** T06–T10과 손계산 graph 예제가 통과한다. **중단:** backend에 따라 연산 변화, fixed gate가 입력 의존, 학습되는 bank, 학습하지 않은 ETTh1 자동 평가.

### WI-06 — Train/evaluate 통합과 구현 잠금 (G2)

**입력:** WI-04/05, pilot 전용 fixtures. **작업:** 8-grid 공동 선택, inner early stopping, 공통 E, 3-seed ensemble, run aggregation, paired bootstrap을 연결한다. CLI에는 validate/prepare/fit/evaluate/report 등의 명시적 역할과 source/split/config 경로 필수를 설계한다. 숨은 latest-file 탐색을 금지한다.

**출력:** runnable CLI와 실제 `--help`, acceptance 결과, 환경 lock, code/config hashes, `locks/implementation_lock.json`. **완료 기준:** T01–T16 및 pilot end-to-end 통과. **중단:** outer test에 기반한 E/threshold 결정, 예측 누락, 불완전 grid를 정상 선택으로 처리. 이 gate 전에는 main 학습을 시작하지 않는다.

### WI-07 — Main nested CV와 내부 release (G3)

**입력:** G1/G2 잠금 artifact. **작업:** main inner 480 fits와 outer 60 fits를 계획대로 실행한다. FC/PCA/bank는 fit scope별 캐시를 쓰되 모든 scope hashes를 검증한다. 그 후 S 후보와 구조 비교를 실행한다. 실행 실패는 실패로 기록하고 결과가 나쁜 fit을 실패로 재분류하지 않는다.

**출력:** selection, checkpoints, 모든 window/run OOF predictions, metrics/CI, 실패·재시도 로그, provenance links. **완료 기준:** 각 main subject가 cell마다 정확히 한 outer-test fold에 있고 2 tasks×4 windows×3 seeds를 가진다. primary checkpoint 수=60; expected window prediction rows=main N×2×4×3×4 cells. **중단:** 결과 누락·hash 불일치·데이터 누출. 통계 비유의는 중단 사유가 아니다.

### WI-08 — PIOP2 잠근 replication (G4)

**입력:** 동일 target/QC의 PIOP2 paired cohort, PIOP1 main pool. **작업:** subject independence를 확인하고 PIOP1 main에서 96 inner fits로 config/E를 선택, 12 final fits를 만든다. 외부 prediction 접근 전에 hashes와 평가 명세를 잠근다. PIOP2 rest로 bank/PCA를 업데이트하지 않는다.

**출력:** `locks/external_lock.json`, 외부 예측/CI/flow/환경 차이 보고. **완료 기준:** PIOP1과 같은 endpoint·두 contrasts·해석 규칙. **중단:** 동일 task pairing 불가, 알려진 subject overlap, 외부 결과에 맞춘 재튜닝. 미확보 시 G4는 blocked로 기록하고 internal-only 결론으로 범위를 제한한다.

### WI-09 — 보조·민감도·효율

**입력:** 잠긴 primary 모델과 별도 analysis config. **작업:** primary와 구분하여 null 4개(C/D 120 outer fits), routing 고정/shuffle, nuisance/time 기준선, 비용을 평가한다. window/atlas/GSR/K 민감도는 각 설정의 cohort 교집합과 변경사항을 저장한다. primary와 다른 cohort 성능을 단순 차감하지 않는다.

**출력:** `reports/sensitivity.md`, intervention predictions, cost measurements. **완료 기준:** primary 선택에 역반영하지 않고 방향이 바뀐 결과도 포함한다. **중단:** 실측 없는 FLOPs/latency 우위, routing association의 인과 해석.

### WI-10 — 독립 수치 검토

**입력:** 저장된 predictions와 manifests; 학습 코드의 summary만 의존하지 않는다. **작업:** 별도 짧은 recomputation 경로로 run probabilities, BA, paired contrasts, CI를 재계산한다. 표본 수와 제외 flow, fit scope를 독립 점검한다.

**출력:** `reports/independent_recomputation.md`, 수치 차이 JSON, gate evidence. **완료 기준:** 정수 counts 일치, probability/metric 절대오차≤1e−8(동일 float serialization), bootstrap draws/seed가 같을 때 CI 일치. **중단:** 설명되지 않는 차이; 출력 표를 손으로 고쳐 맞추지 않는다.

### WI-11 — 연구 결과 패키지 (G5)

**입력:** 내부/외부 release와 제한. **작업:** claim–evidence 표, dataset flow, 모델별 비용, 핵심 2 contrasts 및 S 결과, 실험 실패·음성 결과를 취합한다. 재현 방법은 실제 구현된 명령으로만 작성한다.

**출력:** 최종 report, configs/environment, hash manifest, 사용 허용 범위의 재현 패키지. **완료 기준:** 각 표/그림이 prediction release로 연결되고 기존 실험과 신규 결과가 분리된다. 최초성·인지기전·효율·외부 일반화는 각각 근거가 있을 때만 사용한다.

## 4. 필수 acceptance tests

아래는 구현과 함께 만들어야 하는 검사다. 현재 통과했다고 주장하지 않는다.

| ID | 검증 입력/조작 | 기대 결과 |
|---|---|---|
| T01 Timing | TR 0.75/2초와 알려진 discarded volumes fixture | 원래 [12,252) 범위 보존, 120 target samples, guard 중복 없음 |
| T02 Provenance | TR 충돌·누락 confounds·중복 run key | 명시적 실패; 조용한 default 없음 |
| T03 Subject isolation | 금지 subject를 bank/PCA fit에 삽입 | 실패; 모든 fit IDs⊆허용 train, val/test 교집합 0 |
| T04 Frozen transform | val/test transform 전후 artifact 비교 | PCA/bank hash·parameters 불변 |
| T05 Graph/null | 손계산 소형 bank와 joint permutation | 대칭·finite·nonnegative, self-loop/정규화 일치; spectrum와 bank 거리 보존 |
| T06 ROI alignment | graph 전 한 ROI만 바꾸기 | 다른 ROI encoder 결과 불변(eval mode) |
| T07 FC information | 같은 평균·다른 correlation fixture | FC features 차이; 출력 차이를 강요하지 않음 |
| T08 Routing | fixed/dynamic 입력 바꾸기 및 backward | fixed weights 동일, dynamic finite·합1, 유한 gradient |
| T09 Mixture | one-hot/uniform/original override | 직접 template/평균 bank/원 logits와 각각 일치 |
| T10 Backend/checkpoint | save/reload, PyG 없는 환경 | 동일 명시 backend; eval logits 허용오차 내 동일 |
| T11 Target | cluster ID를 label로 넣거나 single class fold | 거부; label_source는 task metadata |
| T12 Selection boundary | test metric 접근 감지·정해진 inner scores | test 선택 금지; tie rule와 ceil median E 정확 |
| T13 Endpoint | 손계산 2-subject·2-task·4-window·3-seed fixture | aggregation, threshold tie, BA, paired 차이 일치 |
| T14 Statistical unit | family fixture와 bootstrap index 검사 | group 재표집·pair 유지; seed/window를 독립 N으로 쓰지 않음 |
| T15 Integrity | checkpoint/config hash 변경, 누락 seed/window | 실패; glob fallback·불완전 평균 없음 |
| T16 Scope | classification-only train/evaluate | ETTh1 등 미학습 task 자동 평가 없음 |

수치 tolerances는 연산 dtype별로 기록한다. deterministic CPU 소형 fixture는 우선 1e−6, GPU 저장/재로드는 해당 backend의 근거를 기록한다. test를 통과시키려고 주요 과학 규칙을 약화하지 않는다. 기존 suite failure와 신규 failure를 별도 표로 남긴다.

## 5. 기존 파일의 재사용 지도

| 현재 경로 | 재사용 범위 | 새 주분석에 그대로 쓰지 않을 부분 |
|---|---|---|
| `scripts/stream_aomic_extract.py` | source fetch/ROI 추출 구조 | dataset 공통 TR/default 0.75에 의존하는 처리 |
| `scripts/build_alltasks_windows.py` | 파일 I/O 참고 | centroid target 생성 |
| `mobse/data/dfc.py` | FC/clustering primitive 검토 | 전체 subject fit wrapper |
| `mobse/templates/builder.py` | graph serialization 아이디어 | global records template |
| `mobse/templates/dfc_bridge.py` | 명시적 schema 보완 후 serialization | provenance 없는 template 연결 |
| `mobse/data/os_data.py` | batch/loading, subject split 경험 | default window shuffle split |
| `mobse/models/mobse.py` | template mixing 구조 참고 | raw mean bottleneck, ROI 혼합, PyG-dependent fallback |
| `mobse/train.py` | optimizer/checkpoint/logging 원리 | 주분석 dual-task, sample entropy 목적 |
| `mobse/evaluate.py` | 저장·집계 원리 | 항상 두 task branch 평가 |
| `scripts/eval_routing.py` | 출력 형식 참고 | all-subject/default-seed pooled-window 해석 |
| `mobse/profiling.py` | timer 틀 | params×batch fallback을 실제 FLOPs로 보고 |
| `mobse/io.py` | 일반 I/O helper 검토 | glob으로 다른 artifact 대체 |

소스 경로는 repository root 기준이다. 원 코드 변경이 불가피하면 최소 adapter만 추가하고 기존 동작 보존 여부를 검사한다. 구조를 재사용했다는 사실과 과거 결과를 재현했다는 주장은 구분한다.

## 6. 작업 보고와 변경 관리

매 작업 보고에는 **완료한 WI, 증거 경로/hash, 실제 N/fit 수, 실패·미해결 항목, 다음 WI**를 기록한다. 장시간 실행은 진행 count와 실패 원인만 간결히 알리고 성능을 보고 설계를 바꾸지 않는다.

변경 기록 필드는 version, changed_rule, reason, data/outcome_access_scope, affected_artifacts, supersedes다. main outcome 접근 전 기술적 수정은 재잠금하고, 접근 후 연구 질문/분할/표현/선택 변경은 exploratory release로 분리한다. 버그 수정은 원 결과·버그 영향·재실행 범위를 모두 남긴다.

현재 인수인계 상태: **계획서와 지침서 작성 완료, WI-00 이후 실행 미착수**. 가장 먼저 할 일은 WI-01의 원본 metadata/시간축 확보 범위와 WI-00 workspace snapshot 작성이며, G0 해결 전 모델 sweep을 시작하지 않는다.
