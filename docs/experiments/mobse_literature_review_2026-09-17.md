# MoBSE 최근 문헌 검토 및 설계에 대한 함의

검토일: 2026-09-17. 범위: 2024-01-01 이후 공개된 관련 연구를 우선하고, 데이터 정의에는 AOMIC 2021 원문을 사용함. PubMed, arXiv, 공식 저널 및 학회 proceedings를 검색함. 체계적 문헌고찰이나 전체 문헌의 망라를 주장하지 않는 목적 지향 검토임.

세 검토자가 개념·측정 타당성, 모델·선행기여, 데이터·평가 설계를 나누어 검토하고 상호 반론을 교환함. 출판 상태는 검색엔진의 상대 날짜 대신 공식 날짜와 버전을 기준으로 구분함. 논문이 보고한 결과와 아래의 설계 제안은 구분해야 함. 논문 코드·데이터의 독립 재현은 수행하지 않음.

## 1. 핵심 문헌과 근거의 범위

| ID | 논문·공개 상태 | 확인한 내용 | MoBSE에 반영할 사항 |
|---|---|---|---|
| R1 | Laumann, Snyder & Gratton. **Challenges in the measurement and interpretation of dynamic functional connectivity**. Imaging Neuroscience, 2024-11-19. DOI 10.1162/imag_a_00366. 게재 Perspective. [PubMed](https://pubmed.ncbi.nlm.nih.gov/40800298/) | 표본오차, 생리, 각성 및 과제 효과를 dFC 변동에서 구분해야 한다는 비판적 논의. 새로운 실증 benchmark 결과와 구분함. | 군집을 곧바로 인지 상태로 명명하지 않음. 신호 평균·움직임·시간척도 및 stationary surrogate 대조를 별도로 둠. |
| R2 | Torabi et al. **On the variability of dynamic functional connectivity assessment methods**. GigaScience, 2024-04-08. DOI 10.1093/gigascience/giae009. 게재 연구. [원문](https://academic.oup.com/gigascience/article/doi/10.1093/gigascience/giae009/7642158) | HCP 395명, 7개 방법에서 방법 선택에 따른 상당한 차이. | PCA+k-means의 silhouette만으로 생물학적 최적성을 선언하지 않음. 핵심 결과에 window 및 다른 추정법 민감도를 적용함. |
| R3 | Torabi, Poline & Mitsis. **When Can Brain Connectivity Track the Working Mind? A Large-Scale Benchmark of Dynamic Functional Connectivity Across Cognitive Paradigms**. 2026-06-29 bioRxiv **preprint**. DOI 10.64898/2026.06.28.735101. [PubMed](https://pubmed.ncbi.nlm.nih.gov/42427772/) · [본문](https://pmc.ncbi.nlm.nih.gov/articles/PMC13345305/) | 16 datasets, 1,500명 이상, 28 실험 설정과 7개 방법의 single-TR task/rest 해독을 비교. 많은 조합에서 낮은 성능, 긴 규칙적 block에서 더 유리한 결과를 보고함. | 빠른 사건의 인지 상태를 긴 FC window로 해독한다는 목표를 주평가로 삼지 않음. 이 preprint를 모든 dFC 또는 지속적 task 분류의 불가능 증거로 확대하지 않음. |
| R4 | Rosenblatt et al. **Data leakage inflates prediction performance in connectome-based machine learning models**. Nature Communications, 2024-02-28. DOI 10.1038/s41467-024-46150-w. [PubMed](https://pubmed.ncbi.nlm.nih.gov/38418819/) · [원문](https://www.nature.com/articles/s41467-024-46150-w) | 네 가지 데이터셋에서 feature selection, covariate 처리, 피험자 의존성 등 누수 경로를 조사. 반복 피험자와 feature selection 누수는 큰 성능 과장을 유발할 수 있음. | subject split을 먼저 고정. PCA, centroid, feature scaling, nuisance 학습 및 모든 선택을 training fold 안에서 수행. seed/window를 독립 표본으로 세지 않음. |
| R5 | Rai et al. **How do tasks impact the reliability of fMRI functional connectivity?**. Human Brain Mapping, online 2024-02-13. DOI 10.1002/hbm.26535. [PubMed](https://pubmed.ncbi.nlm.nih.gov/38348730/) | MSC 10명의 고밀도 관측에서 task와 영역에 따른 FC 신뢰도 차이를 조사. | task-associated discrimination과 connectivity-specific mechanism을 구분. temporal mean/variance와 전처리 민감도 대조 필요. |
| R6 | Chen et al. **dFCExpert: Learning Dynamic Functional Connectivity Patterns With Modularity and State Experts**. IEEE TMI, online 2025-10-03; 45(3):1088–1098, 2026-03. DOI 10.1109/TMI.2025.3617310. [최종 PubMed](https://pubmed.ncbi.nlm.nih.gov/41042640/) · [최종 본문](https://pmc.ncbi.nlm.nih.gov/articles/PMC12828913/) | MoE-GIN의 modularity experts와 prototype 기반 state experts를 결합. HCP·ABCD·ABIDE 평가. | 가장 직접적인 선행연구. brain-state experts 또는 dFC+MoE의 최초 제안 주장 제외. 같은 target으로 적응한 비교와 명시적 mechanism ablation이 필요. 이전 preprint PMID39764022와 최종 논문을 혼합하지 않음. |
| R7 | Wei et al. **MoRE-Brain: Routed Mixture of Experts for Interpretable and Generalizable Cross-Subject fMRI Visual Decoding**. NeurIPS 2025 정식 proceedings; arXiv 2505.15946 v3, 2025-10-07. [학회](https://papers.nips.cc/paper_files/paper/2025/hash/50ea4dbd1cff6bd3daef939eff10c092-Abstract-Conference.html) · [방법](https://arxiv.org/html/2505.15946v3) | 계층형 experts와 subject-specific router를 이용한 fMRI 시각 재구성. | 뇌 기반 routing 자체의 새로움은 제한됨. 서로 다른 출력 공간의 성능을 직접 비교하지 말고, 분할·ablation·입력 의존성 검증 설계를 참고함. |
| R8 | Yang et al. **Do We Really Need Message Passing in Brain Network Modeling?** ICML 2025, PMLR 267:70873–70887. [공식 proceedings](https://proceedings.mlr.press/v267/yang25r.html) | Pearson FC에 대한 message passing을 재검토하고 Brain Quadratic Network를 제안·평가. | GNN이 필요하다고 가정하지 않음. FC+선형 모델, FC+MLP 및 BQN을 대조군으로 포함. 논문 abstract의 우월성은 해당 실험 범위의 저자 보고임. |
| R9 | Kirova et al. **Dynamic Functional Connectivity Features for Brain State Classification: Insights from the Human Connectome Project**. arXiv 2510.05325 v1, 2025-10-06. 확인한 페이지에 정식 게재 표기 없음. [본문](https://arxiv.org/html/2510.05325v1) | 주요 classifier 입력은 제목에서 예상되는 dFC sequence가 아니라 ROI temporal mean이며 선형 모델을 사용. split 설명 확인에는 한계가 있음. | 보고 정확도를 확정 benchmark로 채택하지 않음. mean-only baseline을 반드시 포함해야 한다는 설계 근거로 사용. |
| R10 | Santoro et al. **Charting higher-order models of brain function beyond pairwise interactions**. Nature Communications 17:9207, 2026-07-29. DOI 10.1038/s41467-026-75959-w. [원문](https://www.nature.com/articles/s41467-026-75959-w) | HCP unrelated 100명에서 여러 higher-order 표현을 비교. task decoding에서는 pairwise FC도 경쟁력 있음. | 표현 복잡도 증가를 곧바로 이득으로 간주하지 않음. 목표별로 간단한 FC 기준선의 추가 이득을 측정. |
| D1 | Snoek et al. **The Amsterdam Open MRI Collection, a set of multimodal MRI datasets for individual difference analyses**. Scientific Data, 2021. DOI 10.1038/s41597-021-00870-6. [원문](https://www.nature.com/articles/s41597-021-00870-6) | PIOP1/2 과제, TR, 촬영 순서 및 event·행동 변수 정의. | emomatching/workingmemory는 두 cohort에서 비교 가능한 task 후보. PIOP2는 새 site 검증으로 부르지 않음. |

읽은 범위: R1–R5는 초록 및 접근 가능한 본문/방법/결과 section, R6는 최종 서지·초록·그림과 검색 색인에 제공된 최종 본문, R7·R9는 arXiv HTML 방법, R8는 공식 proceedings 초록, R10은 공식 본문, D1은 task·acquisition 정의. 일부 PMC 직접 열기는 CAPTCHA로 제한되어 색인된 원문 section을 사용함. Supplement 전체 검토 또는 논문 재현 완료로 표현하지 않음.

## 2. 검색 기록과 선정 원칙

대표 검색문:

- `site.pubmed.ncbi.nlm.nih.gov 2024 2025 dynamic functional connectivity brain states reliability task confounds`
- `site.arxiv.org 2025 2026 fMRI brain graph mixture experts functional connectivity`
- `site.pubmed.ncbi.nlm.nih.gov 2024 2025 brain graph neural network classification benchmarking leakage`
- `site.arxiv.org brain connectivity graph neural networks benchmark 2025 2026 simple baselines`
- 제목 확인 검색: `dFCExpert`, `MoRE-Brain`, `Do We Really Need Message Passing in Brain Network Modeling?`, `When Can Brain Connectivity Track the Working Mind?`

방법 타당성, 직접 선행, 데이터 정의와 평가에 영향을 주는 연구를 우선함. 환자 진단 성능만 제시하는 다수 모델, 미확인 2차 요약, task가 다른 논문의 높은 정확도 수치만을 근거로 하는 비교는 핵심 근거에서 제외함. R1의 Perspective와 R3·R9 preprint를 동료심사 실증 연구와 같은 증거로 취급하지 않음.

## 3. Discussion 합의와 남는 선택

합의: centroid pseudo-label 학습은 적법한 규칙 근사 실험이나 독립 생물학적 검증은 아님. 새로운 주목표는 독립 target에서 brain-derived prior와 입력 의존 routing의 추가 기여를 분리하는 것임. 복잡한 모델·데이터 규모를 먼저 늘리지 않음.

처음에는 within-task cognitive condition을 주평가로 고려했으나, 짧은 trial과 긴 FC window의 시간척도 불일치 및 고정된 조건 순서가 문제가 됨. 실행가능성을 함께 검토한 최종 제안은 **PIOP1의 emomatching 대 workingmemory task-associated discrimination을 주평가**, PIOP2의 동일 target을 잠근 cohort/acquisition replication으로 두는 것임. 선택은 로컬 BIDS metadata/QC 확인을 전제로 하며, cognition 발견·인지부하 추정으로 명명하지 않음.

새로움은 아직 입증되지 않음. 가능한 기여는 **고정된 뇌 유래 graph prior의 해부학적 정렬과 입력별 routing이 어떤 조건에서 실제 예측 이득과 모델 내부 기능을 가지는지 검증하는 연구**임. 효율 향상·임상 biomarker·인과적 뇌 회로 해석은 기본 주장에서 제외함.

실행 설계: [MoBSE 재설계 프로토콜](mobse_redesign_protocol_2026-09-17.md).
