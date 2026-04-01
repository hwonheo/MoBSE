# MoBSE Remaining Tasks (2026-03-31)

## A. Manuscript Writing (priority)

1. Discussion 본문 확정
- `rerun10` 재현성 결과를 한 단락으로 명시
- latency 변동은 보조 관찰로 제한, 핵심 결론은 error/classification 축으로 고정
- limitation 문구(윈도우 split, state-generation 비대칭, preprocessing 민감도) 최종 삽입

2. Introduction 작성 완료
- 문제정의: 해석 가능한 routing 필요성
- 기여 3점 고정:
  - Yeo-7 scaffold 기반 해석축
  - MoBSE routing specialization
  - rerun10 재현성 확인

3. Methods 보강
- ETTh1 source URL(ETDataset raw) 명시
- seed/repeats 및 selection metric/early stopping 조건 표기
- main(10-seed) vs exploratory(3-seed) 구분 문장 추가

## B. Figures/Tables Lock

1. 본문 사용 그림 lock
- ETTh1 storyline: `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/*`
- ETT-family 비교: `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/fig_ett_family_mae_mse_s10.png`

2. 표 lock
- storyline summary: `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv`
- pairwise stats: `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv`
- ETT-family summary: `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv`

## C. Final QC

1. 경로/이름 최종 검수
- 본문에서 `yeo7` 잔존 문자열, 구 경로, `s3` 주분석 표기 제거

2. 숫자 일치 점검
- 본문 수치와 CSV 수치 1:1 대응 확인

3. 제출 패키지 생성
- 본문, 표, 그림, 캡션, 실행 로그 경로를 한 페이지 인덱스로 묶기
