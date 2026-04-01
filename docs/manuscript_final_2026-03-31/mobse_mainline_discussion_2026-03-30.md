# MoBSE Mainline Discussion (2026-03-30)

## Why MoBSE Is the Mainline Model

MoBSE is the mainline model for this project because it balances interpretability, reproducibility, and operational simplicity through a fixed Yeo-7 base.

- Interpretability: model outputs can be mapped directly to known large-scale functional systems (`vis`, `sommot`, `dorsattn`, `salventattn`, `limbic`, `cont`, `default`).
- Reproducibility: fixed Yeo-7 taxonomy and stable 7-class formulation reduce run-to-run story drift.
- Engineering fit: template-based routing and OS classification can be compared consistently across datasets and runs.

In short, MoBSE uses Yeo-7 not as branding but as an interpretability coordinate that allows performance results to become neuroscience claims.

## Reproducibility Check

The `2026-03-31 rerun10` experiments reproduced the core storyline results from the original `2026-03-27` analysis.

- ETTh1 error metrics were stable across reruns: the four storyline conditions preserved the same MAE/MSE ordering and nearly identical means.
- OS classification metrics were also reproduced: accuracy and F1-macro stayed consistent with the original storyline values.
- FLOPs were unchanged across reruns, confirming that the model configuration and computational budget remained fixed.
- The main source of variation was profile latency, which shifted modestly across reruns and should be treated as runtime noise rather than a substantive change in model behavior.

This means the paper-grade conclusion is stable: the rerun10 results confirm the original core claims, while latency differences do not alter the interpretation of the main performance gap.

## Acknowledged Limitations (Updated after Robustness Wave)

1. Split risk (window-level random split)
- 기존 기본 split은 window-level random split이라 leakage 위험이 있었다.
- 다만 `2026-03-31 strict subject-level split (10 seeds)` 재검증에서 ABIDE vs simulation OS 격차는 유지되었고(accuracy/F1 차이 유의), 핵심 결론은 split 변경 후에도 유지되었다.

2. State-generation asymmetry between datasets
- ABIDE state files are generated via cohort-derived network partition masking, whereas simulation/public-proxy states are generated via temporal transforms/noise. Class separability differs by construction.

3. Cohort and acquisition heterogeneity
- ABIDE and development-fMRI proxy have different site/population/acquisition distributions. Cross-dataset comparisons should be interpreted as controlled benchmarks, not direct biological equivalence.

4. Preprocessing dependency
- `2026-03-31 nuisance sensitivity (paper/compcor_only/gsr_only, 10 seeds)`를 통해 1차 점검을 수행했다.
- 본 설정에서는 `paper_compcor_gsr`가 OS accuracy와 ETTh1 오차/지연시간에서 가장 안정적이었고, 단순 preset은 일부 지표 열화가 관찰되었다.
- 따라서 preprocessing 영향은 "존재함"으로 유지하되, 최소한 방향성은 정량적으로 확인된 상태다.

5. Efficiency noise
- Latency should be interpreted as an operational measurement with modest run-to-run variance. It is useful for profiling, but it should not be over-read as a primary scientific effect unless replicated under a fixed runtime harness.

## What Claim Is Still Valid

Even under these limitations, one claim remains robust and central:

> Human rs-fMRI modeling remains superior for mechanistic interpretation because it ties model behavior to node/network-level organization, enabling neuroscience-grounded explanation beyond accuracy-only comparisons.

This claim is bounded, not universal: it supports interpretation and hypothesis framing under controlled benchmarking conditions, but it does not by itself prove clinical generalization, causal biological validity, or preprocessing invariance.

## Robustness Update (2026-03-31)

두 보강 축의 상태는 다음과 같다.

1. H4 (strict split robustness): satisfied at first-pass level  
- subject-level strict split에서도 ABIDE 우위가 유지되며, latency/FLOPs 해석은 기존과 동일하다.

2. H5 (preprocessing robustness): partially satisfied  
- 주요 nuisance preset 3종 비교를 완료했고, paper stack 우위를 확인했다.
- 다만 site-stratified harmonization까지 포함한 확장 검증은 아직 남아 있다.

## Operational Position for Ongoing Analysis

- Keep MoBSE as the locked mainline model (with Yeo-7 base).
- Treat simulation as a matched control axis, not the primary source of scientific interpretation.
- Treat strict split and nuisance sensitivity as completed robustness layers for the current submission draft.
- Prioritize next robustness step as site-stratified/harmonization extension, not another same-setting rerun.
- Use the rerun10 storyline as the manuscript-facing result set; keep exploratory runs and runtime profiling secondary to the main claim.

## Theory-Evidence Gap Fill (Concept Note Comparison)

Concept note의 이론 주장과 현재 본문 증거의 대응은 다음처럼 정리된다.

1. "Brain template as routing prior, not causality"  
- 현재 상태: 본문에서 해석 경계는 명시됨(인과 주장 금지).  
- 보강 필요: 라우팅 패턴과 네트워크 해석의 정량 연결(예: network-wise activation consistency)을 추가 표로 제시.

2. "Efficiency via sparse specialization"  
- 현재 상태: matched FLOPs 조건에서 성능 차이를 확인하여 계산량 증가 가설을 배제했다.  
- 보강 필요: memory peak 및 고정 harness latency 반복 측정(하드웨어 고정)으로 효율 주장 완성.

3. "Robustness against preprocessing/site heterogeneity"  
- 현재 상태: denoising preset 민감도는 10-seed로 1차 검증 완료.  
- 보강 필요: site-stratified/harmonization 재실행으로 외적 타당성 강화.

4. "Generalization across data regimes"  
- 현재 상태: ETT-family 10-seed 확장으로 보조 일반화는 확보.  
- 보강 필요: strict split 추가 반복보다는 데이터 이질성(site partition) 축 확장.

논문 본문에서는 위 보강 필요 항목을 "future work"가 아니라 "claim hardening before submission"으로 표현하는 편이 안전하다.
