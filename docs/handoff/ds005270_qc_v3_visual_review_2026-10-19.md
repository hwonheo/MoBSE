# ds005270 fMRIPrep v3: 잔여 ROI·국소 정합 검토 완료

2026-10-19 KST. sub-001/002/004/013의 기존 저포함 ROI 25개를 직접 검토했다. 권고는 **4명 모두 국소 신호·부분 ROI 대표성 제한을 기록하고 유지**다. 검토 절편에서 새 대상자 제외를 뒷받침하는 뚜렷한 전역 정합 실패나 실제 획득 FOV 부족은 확인되지 않았다. 이는 최종 포함 승인이나 전체 실행 승인을 대신하지 않는다.

검토 범위: 9개 ROI 패널, ROI당 최대 면적의 축상·관상·시상 절편(총 75개 절편의 EPI/T1 쌍), 각 ROI 266-frame 원시 PSC·v3 잔차, 4명 fMRIPrep 원본 coreg/normalization/SDC SVG 양 상태. 노랑은 atlas ROI, 청록은 기능 마스크 경계다. 기존 공통 격자 영상의 표시만 수행했고 재표본화하지 않았다. 검토 절편은 전 체적의 모든 절편을 대체하지 않는다.

전역 QC: EPI/T1 뇌 윤곽·뇌실·중심 구조에서 뚜렷한 이동·회전·좌우반전 징후는 보이지 않았다. T1/template 전반적 대응은 유지되며 국소 고랑 차이는 남는다. SDC 그림은 저신호 복원을 입증하지 않는다. 안와전두·측두부 감쇠는 susceptibility 영향과 부합하는 모양이지만 원인을 확정하지 않았다.

정량 대조: 25 ROI의 all-volume acquired support는 모두 100%. 원시/잔차 분산은 모두 양수이며 포함 voxel의 비유한값·0분산 voxel은 0개. 각 대상자의 주 창은 4/4/4이다. 평균과 분산은 마스크에 남은 voxel의 평균 시계열 값이며, tSNR은 선형 detrend 후 voxel별 값의 중앙값이다. 원시 신호 단위는 임의 단위이므로 대상자 간 절대 강도로 품질을 서열화하지 않는다. 수치 통과는 ROI 전체의 대표성을 보장하지 않는다.

| 대상 | 개별 판단 |
|---|---|
| sub-001 | 유지 권고. ROI33 및 양측 OFC의 국소 감쇠, ROI91 주변부 경계 차이. 원시 추세가 잔차에서 감소하나 감쇠 부위가 복구된 것은 아님. |
| sub-002 | 제한 명시 후 유지 권고. ROI32/33과 OFC 감쇠가 두드러짐. ROI33 포함률 55.19%, tSNR 11.65. 큰 급변은 기존 FD 표시·주 창 밖임을 확인. |
| sub-004 | 제한 명시 후 유지 권고. ROI33 포함률 50.51%, OFC 감쇠 및 ROI91 경계 불확실성이 가장 주의할 부분. 후방 ROI4는 실제 FOV 절단이 아님. |
| sub-013 | 유지 권고. 비교적 안정적인 시계열이지만 ROI33 감쇠(포함률 61.51%)와 OFC 기저부 감쇠는 남음. |

남은 사람 판단은 **이 4명의 국소 감쇠·부분 ROI 대표성 제한을 받아들이고 Schaefer100 공통 입력으로 포함할지** 한 가지다. 우선 확인 그림은 각 대상자의 ROI33과 sub-004 ROI91이다. 기술 검토 자체는 완료했으며 모든 QC를 다시 사람에게 넘기는 상태가 아니다. 새 tSNR/포함률 제외선, ROI 삭제·보간, 전처리 재실행, 코호트 처리·학습은 하지 않았다.

시계열 급변 대조: sub-002 ROI33 volume177(354초), raw PSC 11.137, FD 1.498 mm; sub-004 ROI4/31 volume264(528초), raw PSC −15.998/8.231, FD 2.109 mm. 모두 기존 FD flag가 있으며 모든 주 창 밖이다. 잔차에서 급변이 작아졌다는 사실은 신호 복원 또는 다른 artifact 부재의 증거가 아니다.

아래 수치는 원시 평균·원시 분산(임의 단위²), 잔차 분산(PSC²; 모두 ddof=0)이며 제외 임계값으로 쓰지 않았다. 모든 행의 FOV는 100%다.

| 대상/ROI | 마스크 % | 평균 | 원시 분산 | tSNR | 잔차 분산 | 직접 관찰 |
|---|---:|---:|---:|---:|---:|---|
| sub-001/31 | 86.10 | 437.33 | 63.089 | 14.24 | 0.3161 | 안와전두 하부·후방의 EPI 감쇠와 하부 마스크 경계 차이. 원시 시계열의 느린 추세는 잔차에서 감소. |
| sub-001/32 | 87.79 | 476.67 | 61.612 | 15.22 | 0.1757 | 측두극 하연의 경계 차이와 부분 감쇠. ROI 전체 소실은 아님. |
| sub-001/33 | 72.97 | 454.85 | 11.266 | 18.74 | 0.1402 | T1 조직이 보이는 하외측 부위에서 뚜렷한 EPI 감쇠. ROI 일부가 기능 마스크 밖으로 연장. |
| sub-001/79 | 79.84 | 377.33 | 24.249 | 14.77 | 0.1791 | 기저부 EPI 감쇠와 하부 경계 차이. |
| sub-001/80 | 84.75 | 469.01 | 11.395 | 19.25 | 0.1081 | 하연의 경계 차이·제한적 감쇠. ROI 대부분에는 신호가 보임. |
| sub-001/91 | 76.47 | 537.58 | 12.921 | 26.10 | 0.0927 | 외측·하부 주변부의 atlas/mask 경계 차이. 검토 절편에서 뚜렷한 내부 신호 공백은 없음. |
| sub-002/31 | 75.60 | 313.38 | 15.115 | 12.95 | 0.3419 | 안와전두 하부 EPI 감쇠와 경계 차이. |
| sub-002/32 | 64.44 | 335.72 | 15.567 | 13.69 | 0.3028 | 하부 측두극 감쇠와 안쪽으로 들어온 기능 마스크 경계. |
| sub-002/33 | 55.19 | 235.06 | 17.775 | 11.65 | 0.3809 | 넓은 하외측 감쇠와 부분 마스크 포함. 354초 원시 신호 급변은 FD 표시 및 주 창 밖임을 대조. |
| sub-002/79 | 83.80 | 303.84 | 16.693 | 13.32 | 0.2156 | 안와전두 하부 EPI 감쇠와 경계 차이. |
| sub-002/80 | 74.35 | 316.76 | 8.065 | 18.03 | 0.1516 | 측두극 하연의 감쇠와 경계 차이. |
| sub-002/91 | 86.75 | 406.09 | 4.952 | 27.86 | 0.0977 | 주로 외측·하연 경계 차이. 내부 신호 유지. 공통 원시 급변이 잔차에서는 감소. |
| sub-004/4 | 83.77 | 346.97 | 24.688 | 27.40 | 0.2422 | 후방 atlas/mask 주변부 경계 차이. 조직과 신호가 있으며 sub-003과 같은 후방 획득 FOV 절단은 아님. 528초 급변은 주 창 밖. |
| sub-004/31 | 71.06 | 312.77 | 9.361 | 16.68 | 0.2064 | 안와전두 하부의 뚜렷한 감쇠와 경계 차이. 528초 급변은 주 창 밖. |
| sub-004/32 | 79.85 | 397.89 | 9.651 | 24.67 | 0.1154 | 측두극 하연의 경계 차이 및 부분 감쇠. 내부 신호 유지. |
| sub-004/33 | 50.51 | 306.07 | 25.637 | 18.93 | 0.1550 | 넓은 하외측 감쇠와 안쪽 마스크 경계. ROI의 약 절반만 평균에 포함되어 전체 ROI 대표성 제한이 가장 큼. |
| sub-004/79 | 65.92 | 275.87 | 11.453 | 17.94 | 0.3061 | 안와전두 기저부의 뚜렷한 감쇠와 경계 차이. |
| sub-004/80 | 81.40 | 388.90 | 4.967 | 25.26 | 0.1257 | 하연 경계 차이. ROI 대부분의 조직·신호 유지. |
| sub-004/91 | 69.02 | 363.69 | 8.247 | 25.11 | 0.1114 | 비교 대상보다 큰 외측·하연 경계 불일치. 국소 변형과 감쇠의 기여를 이 절편만으로 분리할 수 없음; 전역 정합 실패로 판정하지 않음. |
| sub-013/31 | 79.81 | 510.12 | 10.425 | 28.63 | 0.1969 | 마스크 내부 tSNR과 별개로 안와전두 기저부의 국소 EPI 감쇠가 보임. |
| sub-013/32 | 86.99 | 526.92 | 10.160 | 29.94 | 0.1368 | 측두극 하연 경계 차이 및 부분 감쇠. 내부 신호 유지. |
| sub-013/33 | 61.51 | 414.00 | 3.596 | 23.79 | 0.1445 | T1 조직이 남아 있는 하부의 넓은 EPI 감쇠. 부분 ROI 대표성 제한. |
| sub-013/79 | 79.40 | 517.79 | 7.159 | 35.95 | 0.1050 | 안와전두 기저부 국소 감쇠와 경계 차이. |
| sub-013/80 | 86.81 | 575.09 | 6.382 | 36.32 | 0.0778 | 측두극 주변부 경계 차이. 내부 신호 유지. |
| sub-013/91 | 86.51 | 618.21 | 3.082 | 43.39 | 0.0661 | 얇은 외측·하연 경계 차이. 내부 신호 유지. 시계열에 큰 공통 급변이 두드러지지 않음. |

ROI 명칭: 4=LH Vis4, 31=LH Limbic OFC1, 32=LH Limbic TempPole1, 33=LH Limbic TempPole2, 79=RH Limbic OFC1, 80=RH Limbic TempPole1, 91=RH Default Temp1. atlas 명칭은 해부학적 위치를 정밀 보증하는 명칭이 아니다.

근거·추적: 같은 검토 폴더의 `visual_review_completed.json`에 25 ROI 분류, 정확한 수치, 그림 행, 원본 수치/검증 파일 및 그림 SHA-256을 기록했다. 최초 `*_fmriprep_qc.png`는 SVG 영상층이 누락된 실패 중간물로 근거에서 제외했다. 수정된 `*_fmriprep_qc_fixed.png`만 사용했다. 기존 v3 정책/대상자 결정 파일은 당시 승인 상태를 보존하고, 이 문서와 JSON을 후속 검토 완료 기록으로 추가한다.

검토 그림:
- [sub-001_roi_panel_1.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-001_roi_panel_1.png>)
- [sub-001_roi_panel_2.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-001_roi_panel_2.png>)
- [sub-002_roi_panel_1.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-002_roi_panel_1.png>)
- [sub-002_roi_panel_2.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-002_roi_panel_2.png>)
- [sub-004_roi_panel_1.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-004_roi_panel_1.png>)
- [sub-004_roi_panel_2.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-004_roi_panel_2.png>)
- [sub-004_roi_panel_3.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-004_roi_panel_3.png>)
- [sub-013_roi_panel_1.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-013_roi_panel_1.png>)
- [sub-013_roi_panel_2.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-013_roi_panel_2.png>)
- [sub-001_fmriprep_qc_fixed.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-001_fmriprep_qc_fixed.png>)
- [sub-002_fmriprep_qc_fixed.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-002_fmriprep_qc_fixed.png>)
- [sub-004_fmriprep_qc_fixed.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-004_fmriprep_qc_fixed.png>)
- [sub-013_fmriprep_qc_fixed.png](</Users/hwon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Codex/2026-10-16/task-7/ds005270_targeted_visual_review_a1/sub-013_fmriprep_qc_fixed.png>)
