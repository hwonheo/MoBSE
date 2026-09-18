# Redesign protocol figures (2026-09-17)

생성 시각(UTC): 2026-09-17T09:01:31Z

이 폴더는 재설계 프로토콜 v1.1 / 작업지침서 v1.0 의 **설계와 감사 현황**을 그린 figure 만 담는다. 모델 성능 결과는 아직 존재하지 않으므로 성능 figure 는 없다.

`docs/manuscript_final_2026-03-31/figures/` (2026-03-31 lock) 와 분리된 별도 폴더이며, 기존 `fig_f<N>_` 번호와 충돌하지 않도록 `fig_rd<N>_` 접두사를 쓴다.

| Key | 파일 | 역할 | 내용 |
|---|---|---|---|
| RD1 | `fig_rd1_factorial_design.{png,pdf}` | manuscript | 재설계의 2×2 요인 설계와 공통 forward 경로. |
| RD2 | `fig_rd2_analysis_pipeline.{png,pdf}` | manuscript | 분석 파이프라인과 fit 경계. |
| RD3 | `fig_rd3_timing_model.{png,pdf}` | manuscript | 시간축 모형과 확정된 native TR. |
| RD4 | `fig_rd4_g0_audit_status.{png,pdf}` | audit | Wave 1 이후의 cohort 규모와 G0 차단 항목 해소 현황. |

## 재현

```bash
PYTHONPATH=. python3 scripts/make_redesign_protocol_figures.py
```

각 figure 는 `figure_manifest_<key>.json` 에 스크립트/출력/입력 SHA256 과 git HEAD, 생성 시각을 기록한다. 기존 manifest 에는 hash·시각 필드가 없었으나 재설계 프로토콜이 모든 산출물의 hash 추적을 요구하므로 확장했다.

## 스타일

- `mobse.viz.set_nature_style()` 상속 (7.2 in 2단 폭, 8 pt, dpi 300, top/right spine 제거).
- 저장은 `mobse.viz.save_multi()` 로 PNG/PDF 쌍.
- `pdf.fonttype=42` 추가 — 기존 스크립트에는 설정이 없었다.
- 데이터 식별 색은 검증된 3색만 사용: `#10B981`(brain bank/proposed), `#4F46E5`(null bank/legacy), `#F59E0B`(대조 강조). routing 축은 색이 아니라 빗금으로 구분하고 모든 표식에 직접 라벨을 붙인다.
