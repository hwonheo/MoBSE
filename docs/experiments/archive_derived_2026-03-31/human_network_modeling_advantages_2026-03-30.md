# Human Network Modeling의 장점 (Limitation 인정 버전)

## 핵심 결론

현재 파이프라인의 한계(예: state 생성 규칙, split 방식, 전처리 편차)를 인정하더라도, **실제 human rs-fMRI 기반 모델링**은 시뮬레이션 대비 다음의 본질적 장점을 가진다.

1. **신경과학적 해석 가능성(가장 중요한 장점)**
2. 임상/질환 연구로의 전이 가능성
3. 데이터셋 간 재현성 검증 가능성
4. 전처리-노이즈-모션에 대한 현실적 견고성 평가

---

## 1) 왜 “노드/네트워크 단위 해석”이 결정적 장점인가

### 1-1. 모델 출력을 뇌 기능 체계와 직접 연결할 수 있음

Yeo 7-network는 resting-state의 거시 네트워크(visual, somatomotor, dorsal attention, ventral attention/salience, limbic, frontoparietal/control, default mode)를 제공한다. 이 좌표계 위에서 결과를 읽으면:

- 어떤 네트워크가 class 분리에 기여했는지
- 어떤 network-to-network coupling이 변했는지
- 변화가 attention/control/default 계열 중 어디에서 발생하는지

를 **기능적 가설**로 바로 번역할 수 있다.

이것이 단순 “분류 정확도”와 다른 점이다. 정확도는 성능 지표지만, 네트워크 단위 해석은 **메커니즘 지표**다.

### 1-2. “휴먼 뇌의 공통 조직 원리” 위에서 설명 가능

Yeo parcellation과 resting network 문헌은, 휴식 상태 네트워크가 단순 잡음이 아니라 과제 활성 네트워크와 강하게 대응한다는 근거를 제공한다. 즉, rs-fMRI 기반 해석은 생물학적 근거가 있는 해석 단위다.

### 1-3. 해석 가능한 해상도 선택(Atlas granularity)

CC200/CC400 같은 파셀레이션은 해상도-안정성 trade-off를 제공한다.

- CC200: 상대적으로 안정적/저차원
- CC400: 더 미세한 세부 패턴 포착 가능(대신 분산 증가 가능)

따라서 “어떤 해상도에서 효과가 재현되는가?”를 검증하며 해석의 신뢰도를 올릴 수 있다.

---

## 2) Limitation을 인정해도 성립하는 실질적 장점

### 2-1. 현실적 변이(heterogeneity)를 학습함

시뮬레이션은 통제된 분포를 제공하지만, 실제 인간 데이터는 사이트/개인/모션/생리 변이를 포함한다. 이 변이를 견디는 모델은 실제 적용 가능성이 높다.

### 2-2. 질환 모델과 직접 연결됨

ABIDE I/II는 대규모 다기관 autism 코호트이며, 휴먼 네트워크 연구의 표준 벤치마크로 사용된다. 즉, 모델이 학습한 패턴을 기존 임상 연결성 문헌과 직접 비교할 수 있다.

### 2-3. “계산량 동일” 조건에서도 데이터의 의미 차이를 드러냄

공정 비교(노드 수/전문가 수/FLOPs/latency 매칭)에서도 OS 지표 차이가 크다면, 이는 연산량 차이가 아니라 **데이터 구조와 라벨 의미의 차이**가 결과를 좌우한다는 증거가 된다.

---

## 3) 신경과학적 해석을 더 깊게 만드는 프레임 (권장)

### 3-1. 세 가지 해석 층위

1. **Node level**: 어떤 ROI가 일관되게 기여하는가?
2. **Network level**: Yeo7 내부/간 연결 중 어떤 축이 변하는가?
3. **Gradient level**: 변화가 sensorimotor ↔ transmodal(DMN) 축에서 어디에 위치하는가?

### 3-2. Triple-network 가설과의 접합

최근 autism/connectome 문헌에서도 DMN-SN-CEN 축의 분화/통합 이상이 반복적으로 보고된다. 따라서 triple-network 프레임을 사용하면, 결과를 정신질환/인지 제어 문헌과 연결하기 쉽다. 예: salience-mediated switching 실패, DMN 과/저결합, executive 제어 저하 등.

### 3-3. “재현성 있는 해석”의 정의

해석은 단일 run에서 예쁜 그림이 아니라,

- atlas를 바꿔도(CC200 ↔ CC400) 방향성이 유지되고
- split/seed/site를 바꿔도 유지되며
- confound 처리 전략을 바꿔도 핵심 결론이 유지될 때

강한 해석으로 간주해야 한다.

---

## 4) 논문 기반 근거 (최신 레퍼런스 중심)

### 데이터 규모/재현성

- 대규모 brain-behavior 재현성 요구: Marek et al., 2022, Nature (DOI: `10.1038/s41586-022-04492-9`)  
  https://pubmed.ncbi.nlm.nih.gov/35296861/
- lifespan normative chart: Bethlehem et al., 2022, Nature (DOI: `10.1038/s41586-022-04554-y`)  
  https://doi.org/10.1038/s41586-022-04554-y
- autism connectome 발달 이상(최근): Lee et al., 2025, Molecular Autism (DOI: `10.1186/s13229-025-00641-9`)  
  https://doi.org/10.1186/s13229-025-00641-9

### 네트워크/파셀레이션 해석 축 (Yeo-7 현대화)

- 개인 내 네트워크 재현성: Du et al., 2024, J Neurophysiol (DOI: `10.1152/jn.00308.2023`)  
  https://pubmed.ncbi.nlm.nih.gov/37609246/
- individualized homologous parcellation: Li et al., 2025, Communications Biology (DOI: `10.1038/s42003-025-08509-7`)  
  https://doi.org/10.1038/s42003-025-08509-7
- brain map 표준 비교 프레임(neuromaps): Markello et al., 2022, Nat Methods (DOI: `10.1038/s41592-022-01625-w`)  
  https://pubmed.ncbi.nlm.nih.gov/36203018/
- 기능 connectome의 세포유형 기반: Zhang et al., 2025, Nat Neurosci (DOI: `10.1038/s41593-024-01812-2`)  
  https://doi.org/10.1038/s41593-024-01812-2

### 예측/일반화 (autism FC 모델링)

- autism FC predictive modeling 프레임: Horien et al., 2022, Biological Psychiatry (DOI: `10.1016/j.biopsych.2022.04.008`)  
  https://pubmed.ncbi.nlm.nih.gov/35690495/
- site-harmonized ABIDE 예측: Ingalhalikar et al., 2021, IEEE TBME (DOI: `10.1109/TBME.2021.3080259`)  
  https://pubmed.ncbi.nlm.nih.gov/33989150/

### 전처리/denoising/harmonization 중요성

- harmonization 방법론 리뷰: Hu et al., 2023, NeuroImage (DOI: `10.1016/j.neuroimage.2023.120125`)  
  https://pubmed.ncbi.nlm.nih.gov/37084926/
- scanner effect와 community detection 왜곡: Chen et al., 2022, NeuroImage (DOI: `10.1016/j.neuroimage.2022.119198`)  
  https://pubmed.ncbi.nlm.nih.gov/35421567/
- Riemannian harmonization: Honnorat et al., 2024, Med Image Anal (DOI: `10.1016/j.media.2023.103043`)  
  https://pubmed.ncbi.nlm.nih.gov/38029722/
- rs-fMRI motion estimate bias: Mao et al., 2024, Imaging Neuroscience (DOI: `10.1162/imag_a_00151`)  
  https://pubmed.ncbi.nlm.nih.gov/40800460/
- 통계적 과대유의 위험 리뷰: Doubovikov & Aksenov, 2025, NeuroImage (DOI: `10.1016/j.neuroimage.2025.121334`)  
  https://pubmed.ncbi.nlm.nih.gov/40554035/

### 주석 (고전 원전 처리)

- Yeo 2011, ABIDE I/II, fMRIPrep 2019는 본문 메인 주장 근거가 아니라 `Methods/Background`의 최소 앵커로만 유지 권장.

---

## 5) 논문에 넣기 좋은 한 문장(요약)

> Even under acknowledged preprocessing and split limitations, human rs-fMRI modeling provides a biologically grounded and mechanistically interpretable axis by linking predictive signals to node- and network-level organization (e.g., Yeo7 and CC200/CC400), enabling clinically meaningful and reproducible neuroscience interpretation beyond accuracy-only gains.
