# Figure captions — redesign protocol (2026-09-17)

- **RD1** (`fig_rd1_factorial_design`): RD1. 재설계의 2×2 요인 설계와 공통 forward 경로. (a) graph bank (training-rest brain vs joint ROI-permuted null)와 routing (FC 입력 의존 dynamic gate vs 입력 비의존 fixed mixture)의 교차로 A–D 네 cell을 정의한다. 주가설은 H1 (A−B>0, 입력 의존 routing의 이득)과 H2 (A−C>0, 정렬된 brain bank의 이득)이며 상호작용은 보조 분석이다. (b) 네 cell이 공유하는 forward 경로: ROI 공유 encoder, frozen bank, 혼합 후 재정규화 없는 S(x), graph layer 2개와 분류 head.

- **RD2** (`fig_rd2_analysis_pipeline`): RD2. 분석 파이프라인과 fit 경계. (a) G0–G5 gate별 필수 산출물과 현재 상태 — G0는 로컬 원본 부재로 blocked이며 이후 gate는 planned다. (b) fold 내부에서 scaler·PCA·K-means·bank가 오직 해당 fold의 training-rest로만 fit되고 pilot·outer test·inner validation은 모든 fit에서 제외됨을 보인다. 통계 단위는 subject이며 window·seed·fold 수를 N으로 세지 않는다.

- **RD3** (`fig_rd3_timing_model`): RD3. 시간축 모형과 확정된 native TR. (a) 원본 acquisition clock에서 12초 guard 이후 [12,252)초를 주분석 구간으로 하고 60초 window 4개(각 2초 grid 30 samples)를 고정 배치한다. (b) Wave 1에서 확보한 raw sidecar의 RepetitionTime으로 여섯 dataset×task 조합의 native TR이 모두 확정되었다(각 조합 내 분산 0). 두 primary target은 TR 2.0초이며, PIOP1 restingstate만 0.75초(multiband)다. 모든 조합이 252초 요건을 충족하므로 window 설계는 개정 없이 유지된다. 기존 추출은 모든 run에 TR 0.75초를 적용했고, 이는 PIOP1 restingstate에서만 우연히 옳다 — 두 primary target은 2.67배 잘못된 rate로 필터링되었으므로 해당 파생물은 재사용하지 않는다.

- **RD4** (`fig_rd4_g0_audit_status`): RD4. Wave 1 이후의 cohort 규모와 G0 차단 항목 해소 현황. (a) fMRIPrep confounds가 존재하는 run 수 — PIOP2가 emomatching 222 run을 보유하므로 외부 검증 cohort가 구성 가능하다. (b) 차단 항목의 해소 여부. U1·U2·U4·U5·U11·U13·U14·U15가 Wave 1으로 해소되었고, U3(보관 전 dummy 제거 여부)·U6(target BOLD)·U10(가족/중복 metadata)·U26(Wave 2 용량)이 남는다. 이 그림은 감사 보고용이며 논문 figure가 아니다.
