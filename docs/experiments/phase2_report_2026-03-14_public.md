# Phase-2 결과 설명서 (일반인용, 업데이트)

## 1) 이번에 추가로 한 일

- 이전에 하기로 했던 3가지를 실제로 끝냈습니다.
  - 200-node 경로 추가 실험
  - p-value 통계표 생성
  - 성능-속도/라우팅 자동 그림 생성
- 데이터는 동일하게 성인 300명(공개 fMRI) 조건을 사용했습니다.

## 2) 100-node vs 200-node 결과를 쉽게 보면

- 100-node 최고 조합:
  - 정답률(Accuracy): `0.1856`
  - 예측오차(MSE): `8.3439`
  - 속도(latency): 약 `3 ms`
- 200-node 최고 조합:
  - 정답률(Accuracy): `0.1620`
  - 예측오차(MSE): `10.2469`
  - 속도(latency): 약 `8 ms`

쉽게 말하면, 이번 PoC 조건에서는 **100-node가 더 빠르고(훨씬), 정확도/오차도 더 유리**했습니다.

## 3) 통계표는 무엇을 보여주나요?

- seed 3개(42/43/44)로 반복해서 숫자 흔들림을 확인했습니다.
- p-value 표를 만들었고, 보정(Holm/FDR)도 같이 계산했습니다.
- 성능 지표(정확도/오차)는 seed 수가 3개라서 통계적으로 강하게 단정하기 어렵습니다.
- 하지만 속도/연산량(FLOPs)은 차이가 매우 커서, 효율 면에서는 n100 우세가 명확했습니다.

## 4) “생물학적 템플릿 정보를 활용하는 방식” 설명 (추가)

- 템플릿은 모델이 처음부터 참고하는 “뇌 연결 지도 초안”입니다.
- 장점:
  - 모델이 완전 랜덤 출발보다, 의미 있는 후보 연결을 먼저 보게 됩니다.
  - 적은 학습 단계에서도 수렴이 안정적인 경우가 있습니다.
- 이번 실험에서 본 점:
  - n100 sweep 상위권은 template prior 사용 조합이 차지했습니다.
  - 다만 n200 top3에서는 noprior 조합이 올라왔습니다.
- 결론:
  - 템플릿 prior가 항상 절대 우세하다고 단정할 수는 없고,
  - **노드 수/표현 복잡도에 따라 prior 효과가 달라질 수 있음**을 보여줍니다.

## 5) 자동으로 생성된 결과물

- 통계표:
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_best_vs_best_phase2_ds00_adult300_n100_20260314_vs_phase2_ds00_adult300_n200_20260314.csv`
- 그림:
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_tradeoff_accuracy_vs_latency.png`
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_tradeoff_mse_vs_latency.png`
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_tradeoff_accuracy_vs_flops.png`
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_routing_entropy_by_nodes_task.png`
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_routing_usage_best_runs.png`

## 6) 다음에 무엇을 하면 좋은가?

- seed를 5~10개로 늘려 성능 지표 통계 검정의 신뢰도를 높이기
- n200에서 prior가 불리해진 원인(라우팅 분포/과적합) 추가 분석
- 필요하면 150-node 같은 중간 해상도도 추가해 U-shape 경향 확인

---

기술 상세 보고서: `docs/experiments/phase2_report_2026-03-14.md`
