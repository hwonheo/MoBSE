# MoBSE — 결과 해석 근거 · PIOP2 계획 정리 (2026-09-29, 대화 세션)

> 선생님 질문 (09-29, 원문): "질문: MoBSE가 현재 연결성 값 + 작은 신경망 모델 보다 많이 떨어지는 것으로 보임. 이 결과를 쉽게 해석해 주길 / 남은 질문: 외부 코호트(PIOP2) 검증 계획은? H2가 왜 불확실하게 나왔는지 판단할 근거를 기존 실험 결과 및 레퍼런스를 찾아보길.."
> 실행 기록·결정 원문은 `claude/mobse_main_oof_2026-09-28.md`. 이 문서는 새 분석 없이 기존 산출물·코드·문헌만 읽고 정리한 것이다. [코드 근거] [기존 결과] [문헌] [추정] 을 구분한다.

## 1. MoBSE (A 87.7%) < S (FC 4,950 + MLP/logistic, 100%) — 해석

- [코드 근거] `mobse/v2/models.py`: `ROIEncoder` 는 모든 ROI 에 같은 1D conv 를 적용하고 ROI 간 혼합이 없다 (ROI 식별 embedding 없음). graph layer 는 `bmm(s, h)` + 공유 Linear, readout 은 `h.mean(dim=1)` (ROI 평균). → 본체는 "어느 ROI 인지" 를 쓰지 못하고, FC 패턴은 gate 입력 PCA 10 차원 → routing weight 3 개를 거쳐서만 들어온다.
- [기존 결과] NG (ROI 평균 encoder 특징 ‖ PCA10 → MLP) 0.889 ≈ A 0.877 (A−NG −0.012 [−0.052, +0.028]). FC 입력 경로가 없는 B·D 는 0.722·0.790. S (FC 4,950 전부) 1.000.
- [추정] A 의 상한은 "FC 를 10 개 숫자로 줄인 요약" 이 정하고, S 는 전체 FC 를 직접 본다. 이번 target (emomatching 대 workingmemory run identity) 은 FC 전체로 완벽히 갈린다.
- [문헌] Shirer et al. 2012 Cereb Cortex: whole-brain FC 로 4 상태 84% (독립 cohort 85%), 30–60 s 로도 유의 — 과제 상태는 FC 로 잘 갈린다. Han et al. 2026 npj AI: graph deep learning 이 LR·MLP 등 단순 모델보다 낫지 않고, message aggregation 이 늘수록 성능이 떨어짐 (over-smoothing, FC 저차원 구조). Yang et al. ICML 2025 (문헌 검토 R8), Santoro et al. Nat Commun 2026 (R10) 도 같은 방향.
- 계획서 §6 (126 행) 이 이미 "A−B 는 입력 의존 FC routing 경로 전체의 추가 가치이며 parameter-only 효과가 아니다" 라고 적어 두었다 — 이번 구조에서 A−B 는 사실상 "FC 입력 경로가 있느냐 없느냐" 에 가깝다 [추정].

## 2. H2 (A−C −0.016 [−0.052, +0.020]) 가 불확실한 이유 — 근거

1. [코드·계획서] 주 null 은 ROI 순서 하나를 섞어 `P S_k Pᵀ` 로 모든 bank 에 같은 순열 — spectrum·weight 분포·bank 간 관계 보존, 해부학 배치만 바꿈 (계획서 §5). 모델이 ROI 식별을 쓰지 못하고 (1 절) readout 이 ROI 평균이면, 그래프는 "평활화 연산자" 로만 작동하고 그 성질은 null 이 보존한다. task 정보가 들어오는 gate 입력은 A·C 가 같다 → 구조상 A≈C 가 예상된다 [추정].
2. [기존 결과] main subject 별: 126 명 중 A·C 점수 같음 108, A 우세 7, C 우세 11. pilot end-to-end (09-26, pilot 기술 분할 25 명): A−C 0.00 [−0.12, +0.10], A = C = 0.86.
3. [기존 결과] legacy v1 prior sweep (audit 4.2, proxy target — 새 target 과 다름): template prior 대 학습형 random graph, 같은 설정 24 쌍 평균 차이 −0.003 (중앙 −0.009, prior 우세 8/24). 새 null (고정·구조 보존) 과 다른 대조라 직접 비교는 아님.
4. [기존 결과] 구조 비교: SG (평균 그래프 1 개) 0.810 < A (A−SG +0.067 [+0.016, +0.119]), NG (그래프 없음) ≈ A. → "입력에 따라 여러 그래프 중 고르는 것" 은 도움, "그래프가 뇌 배치를 따르는 것" 과 "message passing 자체" 의 이득은 보이지 않음.
5. [문헌] Han et al. 2026 (위), Váša & Mišić 2022 Nat Rev Neurosci (null model 은 무엇을 보존하느냐가 검정 대상을 정한다 — 여기서는 해부학 배치만 검정).
- 결론 [추정]: H2 의 불확실은 "뇌 정렬이 쓸모없다" 는 증거라기보다, (a) 모델이 ROI 식별을 쓰지 못하는 구조와 (b) FC 요약만으로 충분한 쉬운 target 때문일 가능성이 크다. 확정하려면 새 분석이 필요하고 계획 밖. 계획 안의 null 민감도 (seed 1730–1733, WI-09) 는 null 간 편차를 보여 줄 수 있다.

## 3. PIOP2 외부 검증 계획 (계획서 §9 · WI-08) 과 구현 상태

- 절차: PIOP1 main pool 126 을 외부 선택용 3-fold (`external_folds.json` 42/42/42, 결정 17, 잠김) 로 나눠 A–D inner 96 fit → config/E 선택 → 126 명 전체로 bank·변환·모델 최종 fit (4 칸 × seed 3 = 12) → `locks/external_lock.json` 으로 hash 잠금 → PIOP2 (적격 189) 에 한 번 평가. PIOP2 rest·label·성능으로 fit·선택·calibration 금지. 같은 endpoint·두 contrast·해석 규칙. 외부 S 도 PIOP1 inner 결과로만 선택 (§6).
- 구현 상태: 외부 분할·잠금 (rev50), `fit`·`fit-s` outer 9 (rev51), 선택 CLI 3종 outer 9 (rev52) 완료. **남은 것**: (9,9) external final fit 배선 (`fitting.resolve_fold_subjects` 가 현재 거부), PIOP2 평가 경로 (고정 모델로 PIOP2 창 예측·evaluate·report), `external_lock.json` 생성·검증, 시험·돌연변이, `mobse/v2` 변경에 따른 측정 잠금·구현 잠금 새 판과 gate revision.
- 데이터: h197 `derivatives_v3_piop2/cohort_piop2/subjects.jsonl` 226 행 (적격 189 — CLAUDE.md 기록). G4 `unresolved` U17 "실제 overlap 은 공식 문서로만 판정": AOMIC 논문 (Snoek 2021) 은 모집 기간이 다르고 (PIOP1 2015-05~2016-04, PIOP2 2017-03~07) "train/test 분할로 쓸 수 있다" 고 쓰지만, 참가자가 겹치지 않는다는 문장은 명시적으로 없다 (09-29 WebFetch 확인).
- 비용 [추정]: 외부 inner 96 + final 12 는 main 실측 (fit 당 약 80 s, 4 개 동시) 기준 30 분 안팎. 구현·시험·잠금 새 판이 더 큰 일 (슬롯 1–2 개 분량).
- 선생님 결정 필요: 외부 평가는 PIOP2 를 한 번만 여는 되돌리기 어려운 단계라 착수 승인 원문이 필요. 외부 S·NG·SG 포함 여부. U17 을 논문 기록으로 해소로 볼지.

## 출처

- Shirer WR et al. 2012, Cereb Cortex 22(1):158–165 — https://pubmed.ncbi.nlm.nih.gov/21616982/
- Han et al. 2026, npj Artificial Intelligence — https://www.nature.com/articles/s44387-025-00067-x
- Váša F, Mišić B 2022, Nat Rev Neurosci — https://www.nature.com/articles/s41583-022-00601-9
- Yang et al. ICML 2025 (문헌 검토 R8) — https://proceedings.mlr.press/v267/yang25r.html
- Santoro et al. 2026 Nat Commun (R10) — https://www.nature.com/articles/s41467-026-75959-w
- Snoek et al. 2021 Sci Data (AOMIC) — https://www.nature.com/articles/s41597-021-00870-6
- 저장소: `mobse/v2/models.py`, 계획서 §5·§6·§9, 지침서 WI-08, `docs/experiments/mobse_existing_experiments_audit_2026-09-17.md` 4.2, `audit_2026-09-17/legacy_experiment_inventory.json`, h197 `pilot_e2e/20260926_1515c/report/statistics.json`, `main_oof/…_main_a2/evaluate/evaluation.json`, `main_oof/…_aux_a1/report_comparison/comparison_statistics.json`
