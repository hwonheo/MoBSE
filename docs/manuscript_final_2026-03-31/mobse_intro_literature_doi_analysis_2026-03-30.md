# MoBSE Intro Literature: 최신 DOI + 본문 분석 (2026-03-30)

## 1) 최근 논문 우선 DOI 리스트 (2021-2025)

아래는 기존 고전 인용을 대체하기 위한 **recent-first** 세트다. (스토리라인: `Human Real Network -> Base (Yeo-7) -> MoBSE`)

## A. Real Human Network (복잡성/재현성)

1. Marek et al., 2022, Nature  
- DOI: `10.1038/s41586-022-04492-9`  
- Link: https://pubmed.ncbi.nlm.nih.gov/35296861/  
- 핵심: brain-behavior 연관은 소표본에서 과대추정되기 쉽고, 대규모 표본이 필요함.

2. Bethlehem et al., 2022, Nature  
- DOI: `10.1038/s41586-022-04554-y`  
- Link: https://doi.org/10.1038/s41586-022-04554-y  
- 핵심: 12만+ 스캔 기반 lifespan brain chart로 normative reference 필요성을 강화.

3. Lee et al., 2025, Molecular Autism  
- DOI: `10.1186/s13229-025-00641-9`  
- Link: https://doi.org/10.1186/s13229-025-00641-9  
- 핵심: autism에서 connectome hierarchy의 비정형 발달을 보고, 연령-발달 축 해석의 중요성을 제시.

4. Horien et al., 2022, Biological Psychiatry  
- DOI: `10.1016/j.biopsych.2022.04.008`  
- Link: https://pubmed.ncbi.nlm.nih.gov/35690495/  
- 핵심: autism FC predictive modeling에서 biological insight와 clinical utility를 분리해 설계해야 함.

## B. Base (Yeo-7 해석 좌표의 현대화)

5. Du et al., 2024, Journal of Neurophysiology  
- DOI: `10.1152/jn.00308.2023`  
- Link: https://pubmed.ncbi.nlm.nih.gov/37609246/  
- 핵심: within-individual 네트워크 조직이 재현 가능하며, 고정된 대네트워크 좌표를 개인 수준으로 확장 가능.

6. Li et al., 2025, Communications Biology  
- DOI: `10.1038/s42003-025-08509-7`  
- Link: https://doi.org/10.1038/s42003-025-08509-7  
- 핵심: individualized homologous parcellation이 group atlas 대비 행동예측 성능/해석 해상도를 개선.

7. Markello et al., 2022, Nature Methods (neuromaps)  
- DOI: `10.1038/s41592-022-01625-w`  
- Link: https://pubmed.ncbi.nlm.nih.gov/36203018/  
- 핵심: 다양한 brain map 간 표준화 비교 프레임 제공(해석 재현성 향상).

8. Zhang et al., 2025, Nature Neuroscience  
- DOI: `10.1038/s41593-024-01812-2`  
- Link: https://doi.org/10.1038/s41593-024-01812-2  
- 핵심: 기능 connectome의 세포유형 기반을 제시해 network-level 해석의 생물학적 연결 고리 강화.

## C. Preprocessing / Denoising / Harmonization (신뢰성)

9. Hu et al., 2023, NeuroImage (review)  
- DOI: `10.1016/j.neuroimage.2023.120125`  
- Link: https://pubmed.ncbi.nlm.nih.gov/37084926/  
- 핵심: harmonization 방법군(통계/딥러닝)과 평가 지표를 정리, 재현성 프레임을 제공.

10. Chen et al., 2022, NeuroImage  
- DOI: `10.1016/j.neuroimage.2022.119198`  
- Link: https://pubmed.ncbi.nlm.nih.gov/35421567/  
- 핵심: scanner effect가 community detection/network metric에 직접 영향.

11. Honnorat et al., 2024, Medical Image Analysis  
- DOI: `10.1016/j.media.2023.103043`  
- Link: https://pubmed.ncbi.nlm.nih.gov/38029722/  
- 핵심: connectome SPD 구조를 보존하는 Riemannian harmonization이 중요함을 실증.

12. Mao et al., 2024, Imaging Neuroscience  
- DOI: `10.1162/imag_a_00151`  
- Link: https://pubmed.ncbi.nlm.nih.gov/40800460/  
- 핵심: resting-state global activity가 motion estimate 자체에 bias를 유도 가능.

13. Doubovikov & Aksenov, 2025, NeuroImage (review)  
- DOI: `10.1016/j.neuroimage.2025.121334`  
- Link: https://pubmed.ncbi.nlm.nih.gov/40554035/  
- 핵심: filtering/sampling/autocorrelation이 FC 통계 유의성 과대추정 위험을 키울 수 있음을 체계화.

14. Ingalhalikar et al., 2021, IEEE TBME (ABIDE harmonized)  
- DOI: `10.1109/TBME.2021.3080259`  
- Link: https://pubmed.ncbi.nlm.nih.gov/33989150/  
- 핵심: site harmonization을 포함한 ABIDE 분류 파이프라인의 실증 사례.

15. Retico et al., 2023, Brain Informatics  
- DOI: `10.1186/s40708-023-00210-x`  
- Link: https://doi.org/10.1186/s40708-023-00210-x  
- 핵심: harmonization 스킴 선택이 성능과 feature importance 해석을 바꾼다는 점을 강조.

---

## 2) 본문(Full Text/Abstract) 기반 핵심 분석

### 2-1. 왜 “real human network”가 필수인가
- Marek 2022: 소표본 고성능은 재현성 위험이 크므로, 대규모 실데이터 중심 검증이 필요.
- Bethlehem 2022: normative chart 관점에서 개인 데이터를 population reference에 위치시켜야 해석력이 생김.
- Lee 2025: autism의 네트워크 발달 궤적 자체가 비정형이므로, 연령/발달 축 통제가 필수.

### 2-2. 왜 Yeo-7 기반 base가 여전히 실용적인가
- Du 2024: 개인별 네트워크 구조가 반복 측정에서 재현됨을 보여, 고정 scaffold + 개인차 모델링 전략을 뒷받침.
- Li 2025: individualized parcellation이 예측에 유리하지만, 대네트워크 좌표는 여전히 비교/해석 기준점으로 필요.
- neuromaps 2022: atlas/표현 간 정렬 가능한 공통 비교 프레임을 제공.

### 2-3. 왜 preprocessing/denoising/harmonization이 성능만큼 중요인가
- Chen 2022, Retico 2023: harmonization 방식이 네트워크 metric과 feature ranking 자체를 바꿀 수 있음.
- Honnorat 2024: FC 행렬의 기하학적 제약(SPD)을 무시하면 왜곡이 생길 수 있음.
- Mao 2024, Doubovikov 2025: motion 추정과 필터링-샘플링 결합에서 통계적 bias가 발생 가능.

### 2-4. MoBSE 주장의 안전한 방향
- Horien 2022, Ingalhalikar 2021 기준으로, 주장을 accuracy-only가 아니라 아래로 전환:
  - network-level biological insight
  - site/harmonization robustness
  - external validity 가능성

---

## 3) Intro 매핑 (최신 버전)

1. 왜 시뮬레이션보다 human rs-fMRI인가?  
-> 최근 대규모/재현성 문헌(Marek, Bethlehem)이 실데이터 검증의 필요성을 직접 지지.

2. 왜 Yeo-7 base인가?  
-> 최신 개인화 문헌(Du, Li)을 수용하되, 비교 가능한 공통 좌표로서 Yeo-7은 여전히 practical baseline.

3. 왜 MoBSE expert가 필요한가?  
-> 고정 base 위에서 이질성(사이트/개인/발달)을 전문가 분화로 흡수하면서 network 해석 좌표를 유지.

4. 결과 신뢰성은 어떻게 확보하나?  
-> preprocessing-harmonization 민감도(Hu, Chen, Honnorat, Mao, Doubovikov)를 robustness 실험으로 병행.

---

## 4) 인용 정책 (이번 업데이트 반영)

- 본문 메인 인용: 위 **2021-2025 recent-first** 세트 사용.
- 고전 원전(Yeo 2011, ABIDE I/II, fMRIPrep 2019)은 `Methods/Background`의 최소 앵커로만 제한.

---

## 5) Introduction Draft (Paper-ready)

현대의 resting-state fMRI 분석은 단순한 분류 정확도 경쟁으로는 충분하지 않다. 대규모 표본에서조차 brain-behavior 연관은 쉽게 과대추정될 수 있으며(Marek et al., 2022), 개인별 발달 궤적과 네트워크 조직의 이질성 또한 매우 크다(Bethlehem et al., 2022; Lee et al., 2025). 따라서 본 연구는 "더 높은 정확도" 자체를 목표로 두기보다, 해석 가능한 네트워크 좌표계 위에서 실제 인간 뇌 신호의 복잡성을 어떻게 안정적으로 모델링할 것인가를 질문한다.

이 질문에 대한 실용적 출발점으로 우리는 Yeo-7 대네트워크 스캐폴드를 사용한다. Yeo-7은 개별 피험자의 변이를 모두 흡수하는 완전한 표현은 아니지만, 비교 가능한 공통 좌표를 제공한다는 점에서 여전히 강력한 해석 기준점이다. 최근의 개인화 parcellation 및 네트워크 재현성 문헌은 더 세밀한 개인차 반영의 가능성을 보여주지만(Du et al., 2024; Li et al., 2025), 그 자체가 곧바로 더 나은 비교 가능성을 의미하지는 않는다. 실제로 집단 수준 atlas는 개인 수준의 해석을 제한하는 동시에, 여러 데이터셋과 실험 조건을 관통하는 공통 언어를 제공하는 장점도 갖는다(Neuromaps; Zhang et al., 2025). 본 연구는 이 공통 언어를 유지한 채, 그 위에서 routing 기반 specialization을 학습하는 방향을 택한다.

MoBSE는 이러한 스캐폴드 위에서 동작하는 expert routing architecture이다. 핵심 아이디어는 고정된 Yeo-7 좌표를 버리지 않고, 그 위에 조건부 라우팅을 얹어 사이트 차이, 피험자 차이, 발달 차이, preprocessing 차이를 전문가 분화로 흡수하는 것이다. 이 접근은 "모든 변이를 하나의 단일 표현에 압축"하는 대신, 해석 가능한 base를 보존하면서 필요한 경우에만 전문가가 활성화되도록 설계한다. 따라서 MoBSE의 목적은 단순한 성능 향상이 아니라, network-level biological insight를 유지한 채 유연성을 확보하는 데 있다.

또한 본 연구는 방법론적으로도 보수적이다. 우리는 preprocessing, denoising, harmonization이 성능뿐 아니라 feature ranking과 network metric의 해석 자체를 바꿀 수 있다는 점을 전제로 한다(Hu et al., 2023; Chen et al., 2022; Honnorat et al., 2024; Mao et al., 2024; Doubovikov & Aksenov, 2025). 따라서 본문은 단일 실험 결과를 과장하지 않고, 전체 10-seed rerun을 통해 주요 결론이 재현되는지 먼저 확인한다. 실제로 본 연구의 full-line rerun에서는 ETTh1 오차 지표와 OS 분류 지표의 핵심 결론이 기존 결과와 동일하게 재현되었고, 차이는 주로 runtime latency 수준의 변동에 국한되었다. 이 재현성 확인은 MoBSE가 특정 seed에 우연히 맞아떨어진 결과가 아니라는 점을 보여준다.

본 연구의 기여는 세 가지로 요약된다.

1. Yeo-7 해석 스캐폴드 위에서 동작하는 MoBSE routing 프레임을 제안한다.  
   고정 atlas를 유지하면서도 expert specialization을 통해 인간 네트워크의 이질성을 모델링하는 구조를 제시한다.

2. routing-centered modeling이 해석 가능성과 유연성을 동시에 제공할 수 있음을 보인다.  
   성능만이 아니라 network-level interpretation, efficiency profile, preprocessing 민감도를 함께 고려하는 평가 축을 사용한다.

3. full-line rerun10으로 주요 결과의 재현성을 확인한다.  
   ETTh1 스토리라인의 핵심 오차 및 분류 결론이 기존 결과와 일치했고, 추가 ETT-family 실험에서도 동일한 평가 절차 아래 일반화 경향을 확인했다.

이상의 설정은 본 논문의 중심 주장을 분명하게 만든다. 인간 rs-fMRI는 본질적으로 복잡하고, Yeo-7은 그 복잡성을 읽기 위한 실용적 공통 좌표이며, MoBSE는 그 좌표 위에서 필요한 만큼만 분화하는 routing model이다. 본 연구는 이 세 층위를 하나의 실험 설계로 연결해, 해석 가능성과 실용성을 동시에 만족하는 네트워크 수준 모델링의 가능성을 제시한다.

## 6) Theory-to-Test Bridge (Concept Note Alignment)

컨셉 노트의 핵심 이론을 본문 가설로 명시하면 아래와 같다.

1. H1: `statistical-prior routing` 가설  
   fMRI connectivity는 인과 경로가 아니라 통계적 공분산 구조이므로, MoBSE는 이를 "인과 모사"가 아닌 "라우팅 prior"로 사용한다. 검증 기준은 정확도 단독이 아니라 라우팅 분화(엔트로피/안정성)와 해석 가능성의 동시 관찰이다.

2. H2: `complexity under constraint` 가설  
   MoBSE의 이론적 장점은 sparse routing(`O(E)`) 가능성에 있으나, 본문 실험은 공정 비교를 위해 FLOPs를 맞춘 상태에서 정보 구조 차이만 평가한다. 즉 "더 많은 연산"이 아니라 "같은 연산에서의 구조적 이점"을 검증한다.

3. H3: `reproducible specialization` 가설  
   전문가 분화 이점이 seed 의존 우연이 아니라면, 10-seed 재실행에서도 핵심 결론이 유지되어야 한다. 본문은 rerun10을 1차 증거선으로 잠근다.

현재 본문에서 아직 남은 검증은 두 축이다.
- subject-level strict split 기반 OS 재검증
- preprocessing/harmonization 민감도(denoising preset, site effect) 정량 비교

이 두 항목이 채워지면, 컨셉 노트의 "이론 -> 실증" 사슬이 reviewer 기준에서 더 강해진다.
