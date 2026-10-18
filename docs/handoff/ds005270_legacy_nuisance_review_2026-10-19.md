# 기존 nuisance 정의 유지 가능 여부

2026-10-19 KST. 최종 결론: **완료된 fMRIPrep 산출물만으로 기존 AFNI 침식 마스크 정의를 그대로 유지할 수는 없다. 보존된 AFNI 마스크를 함께 쓰는 파일럿 혼합 후보에서는 voxel 집합과 계산 순서를 유지할 수 있다.** 어떤 후보도 최종 채택하지 않았다. sub-003 보류·sub-006 제외 유지.

## 실제 기존 정의

- 입력 해부: AFNI 정규화 T1 anat_final, 1mm MNI2009c 격자. 3dSeg -mask AUTO -classes 'CSF ; GM ; WM'.
- class mask마다 3dmask_tool -dilate_input -1: 설치된 도구 도움말에서 face/edge 18-이웃 침식임을 확인. 침식은 1mm 격자에서 먼저 시행했다.
- 그 결과를 최종 BOLD 2mm 격자에 NN 재표본화한 mask_WMe_resam / mask_CSFe_resam을 보존 중. 추출 때 각각 기존 full_mask와 교집합. 모든 포함 voxel의 비가중 평균.
- WM/CSF와 ROI 평균에 run 평균 PSC 적용, 절편·선형 추세·motion6·차분6(첫행0)·제곱12·WM/CSF 2 =28열 OLS를 전체266 frame에 적합. smoothing/bandpass/CompCor/global signal/censor 회귀자/창별 z-score 없음. FD로 부적격 창만 통째 제외.
- proc의 3dDetrend -polort4는 별도 TSNR 진단용 복사본이며, ROI 추출 입력 pb02 volreg를 필터링하는 단계가 아니다.

## 보존된 마스크를 사용한 제한 검증

기존 mask 및 full_mask 파일을 그대로 읽었다. 새 segmentation·침식·재표본화 없음. 4명 모두 fMRIPrep BOLD와 shape/affine 일치. 기존 Q6 기록과 교집합 voxel 수 정확히 일치. WM/CSF 신호와 후보 ROI 잔차 모두 유한·분산>0, 설계 rank28. 전체 frame 및 이전 어댑터의 시간축/창 규칙 유지. 원본 해시 재확인.

| 대상 | WM voxel | CSF voxel | 제공 WM 평균과 r | 제공 CSF 평균과 r |
|---|---|---|---|---|
| sub-001 | 51109 | 7195 | 0.810 | 0.927 |
| sub-002 | 46178 | 7285 | 0.601 | 0.876 |
| sub-004 | 44499 | 11860 | 0.515 | 0.842 |
| sub-013 | 46587 | 3872 | 0.888 | 0.917 |

마스크 voxel 유지가 해부학적 동등성을 보증하지는 않는다. AFNI와 fMRIPrep의 정규화 변형이 달라 동일 MNI 좌표의 조직 대응이 다를 수 있다. 기존 support의 fMRIPrep 동종 조직 확률 평균은 WM 0.913–0.940, CSF 0.805–0.842(기술값, 통과 기준 아님). CSF support 중 sub-002 1 voxel, sub-004 5 voxel이 fMRIPrep brain mask 밖이다. 임의 제거하지 않아 기존 voxel 집합을 보존했고 이 차이를 기록했다.

## 동일하게 유지 가능한 부분과 불가능한 부분

시간축·평균→PSC→OLS 순서·28열 구성·censor/창 규칙은 유지 가능하다. 그러나 새 motion은 fMRIPrep MCFLIRT 추정값이고 BOLD도 SyN/정합/보간이 달라 과거 결과와 숫자가 같아지는 것은 기대하지 않는다. 회전 단위는 명시 변환했다.

fMRIPrep 조직 분할은 native T1의 FSL FAST이고 기존 것은 정규화 T1의 AFNI 3dSeg이다. 분할 도구·분할 공간·변형이 다르다. native/2mm FAST mask를 침식한 뒤 옮기는 방법은 기존 1mm 정규화 공간 침식 후 NN 변환과 교환 가능하지 않다. fMRIPrep 제공 regional WM/CSF 평균에는 기존 침식 조건을 보증하는 metadata가 없다. CompCor mask 설명을 regional mean의 근거로 대신 쓸 수 없다. 따라서 pure fMRIPrep에서 기존 정의와 같다고 표시하지 않는다.

## 최소 선택지·권고

1. **기존 nuisance 정의를 엄밀히 유지:** 보존된 AFNI 조직 마스크 경로를 함께 사용한다. 이번 4명 후보는 계산 가능한 참조가 됐다. 다만 새로운 대상의 기존 방식 마스크 확보와 새 BOLD의 해부 대응 검증이 필요하므로 pure fMRIPrep 파이프라인이 아니며, 이번에 전체 대상 처리를 시작하지 않는다.
2. **pure fMRIPrep으로 통일:** WM/CSF 마스크·공간·침식·평균 정의의 방법 변경을 명시하고 사용자 승인을 받아 개정한다. 제공 평균을 쓰는 방안도 방법 변경이지 동등한 대체가 아니다. 새로운 mask 역치/침식 사양은 지금 정하지 않았다.

권고: 기존 조건 유지가 우선인 이번 단계에서는 1번 혼합 후보를 참조로 보존하고 nuisance 결정을 보류한다. pure fMRIPrep 통일을 원할 때만 2번을 명시적으로 승인받는다. 상관이나 모델 성능으로 후보를 선택하지 않는다. 새 수치 기준·ROI 변경·보간·영상 전처리 재실행·코호트/학습 실행 없음.

## 산출

Codex task-7의 ds005270_legacy_nuisance_validation_a1/에 summary.json, source_sha256.json 및 대상별 wm_csf_frozen_legacy_support.npy, design_hybrid_candidate.npy, roi_clean_hybrid_candidate.npy를 별도 저장했다. 실행 스크립트는 verify_legacy_nuisance.py이며 기존 출력 경로를 거부한다. 모든 결과는 검증 후보이며 최종 입력 승격은 하지 않았다.
