# R2T T1 실제 자료 pilot 설계 · 잠금 (결정 91 후보) · 2026-10-17

> **탐색적 pilot.** 같은 31 명은 v1 · I3 · PIOP2 진단 등에서 이미 분석된 자료이며 R2T 방법 (F1–F4R1) 은 합성으로 개발했다 — **독립 확인 결과로 주장하지 않는다.**
> 결과를 본 뒤 튜닝 · 표본 추가 · 외부 자료 평가 · 전체 코호트 확장은 하지 않는다. 유료 API · 외부 업로드 · 커밋 · push · Notion 변경 없음.
> 이 문서와 `results/r2t/t1_pilot_real/lock.json` 은 **실제 자료로 모델을 적합 · 평가하기 전에** 고정한다.

## 1. 범위와 주장 한계

- 과제: PIOP1 emomatching, 전처리된 신호의 15 frame 창에서 ROI 20 % 를 가리고 복원 (T1 모델 단계).
- **full-run 전처리 뒤 복원이다.** nuisance 회귀 · 차단대역 (0.008–0.2 Hz DCT 동시 회귀) · ROI z-score 를 run 전체 (135 frame) 로 한 뒤 창을 자른다. 관측 ROI 의 처리값에도 창 밖 frame 정보가 들어 있다. → **짧은 촬영 · 온라인 · 실시간 복원으로 주장하지 않는다.**
- rest (학습 전용) 는 원 TR 0.75 s 에서 run 단위 처리 · z-score 뒤 2 s 격자로 선형 보간한 60 s 창 4 개 (30 frame) 를 15 frame 씩 나눈 것이다. task (원 TR 2 s) 와 표본화 · 보간이 다르다 — 두 방법 모두 같은 rest 를 쓰므로 비교는 공정하지만 절대 성능에는 영향이 있다.
### 1.1 전처리 이력 — 근거와 남는 한계 (이번 승인의 최소 실제 자료 접근으로 확인한 범위)

**평가가 가능하다고 보는 근거 (로컬에서 확인)**
- task 입력 (31 명): 로컬 fMRIPrep preproc BOLD 의 sha 가 추출 manifest 와 같고 (31/31), 추출 산출 (full-run npz) 의 sha 가 I3 잠금과 같으며 (31/31), 추출 코드 4 개가 I3 잠금과 같다 → **원 BOLD → 추출 코드 → 시계열** 연결이 해시로 닫힌다. 추출 단계 (nuisance 설계 · 차단대역 · parcel 평균 · ROI z-score) 는 코드로 확인했다 (§2).
- rest 입력 (31 명 × 4 창): 로컬에는 원 rest BOLD 가 없고 창 파일만 있다. 창 sha 124/124 가 I3 잠금과 같고, 만든 코드 (`scripts/h197/10_wi02_extract.py` · `mobse/v2/*`) 가 I3 잠금 · 측정 잠금 판과 같다. 원 BOLD → rest 창 연결은 기존 기록 (gate 부록 BJ: h197 에서 pilot ok run 93 을 원 TR 로 재계산해 저장 창과 바이트 동일 372/372) 에 기댄다 — **이번에 로컬에서 다시 확인하지는 않았다.**
- T1 평가는 이 전처리 산출 자체를 입력 · 정답으로 쓰는 모델 단계 복원이고, 두 방법 (BEST-T · F4R1) 이 같은 산출을 쓰므로 비교 자체에 필요한 이력은 위 해시 연결로 충분하다고 판단한다.

**남는 상위 전처리 한계 (평가를 막지는 않지만 해석을 제한)**
- 로컬 fMRIPrep 산출은 사람별 confounds · preproc BOLD (sidecar: TR 2 · SkullStripped false) · brain mask · events 뿐이다. **fMRIPrep 보고서 · 로그 · dataset_description · 실행 설정은 로컬에 없다** → slice timing · 왜곡 보정 · 보간 방식 등 상위 단계는 공개 문헌 기록 (앞 문서: fMRIPrep 1.4.1, slice timing 미적용, 한 번의 Lanczos 보간) 으로만 안다.
- 영상 단위 처리 (움직임 보정 · 공간 정규화 · Lanczos 보간 · aCompCor) 는 가린 ROI 와 관측 ROI 의 신호를 공간적으로 섞을 수 있다 (계획서 §2.1 섞임 경로). 복원 성능의 일부가 이 섞임에서 올 수 있으며, 이번 pilot 은 경계 완충 민감도를 하지 않는다.
- full-run 처리 · rest 2 s 보간 한계는 위 두 항목.
- 이번 작업에서 새 다운로드 · 전처리 재실행은 하지 않았다.

## 2. 사전 점검 결과 (`results/r2t/t1_pilot_real/preflight.json`, 모델 적합 없음)

| 점검 | 결과 |
|---|---|
| A 명단 · 파일-사람 대응 | `folds.json` pilot 31 명 (접두어 ds002785) = `pilot_ids.txt`, 31 명 모두 추출 manifest 에 있음. 파일 이름이 사람 id 를 담고, 아래 B 의 해시가 I3 잠금 당시 이름-파일 대응을 고정한다 |
| B 입력 파일 sha256 대 I3 잠금 (`1bc3622dcd85`) | task full-run npz 31 · rest 창 124 · folds.json · manifest = **157/157 일치** |
| C 원 BOLD 대 추출 manifest | 31/31 — 로컬 fMRIPrep preproc BOLD 의 sha 앞 12 자리가 manifest `bold_sha12` 와 같고 status ok · TR 2.0 · 135 frame · 시작 4 s · WI-02 QC 통과 |
| D 추출 코드 대 I3 잠금 | `mobse/v2/extract.py` · `preprocess.py` · `scripts/h197/10_wi02_extract.py` · `scripts/h1h2_scope/i3_extract_pilot.py` 4/4 일치 |
| E 값 수준 | task (135, 100) 유한, ROI 평균 최대 7e−9 · SD−1 최대 1e−8 (run 단위 z-score), 시각 간격 2.0 s · 첫 시각 4 s. rest (30, 100) 유한, 4 창 평균 최대 0.09 (보간 · 구간 때문에 0 이 아님) |
| 설계 정보 범위 (코드) | nuisance = motion 24 + aCompCor 5 (combined) + spike + intercept + drift + 차단대역 DCT. global_signal · tCompCor 없음. 회귀 · z-score 는 ROI 별 |
| F 분할 · 누출 | 사람 단위 5 fold (seed 20261017) 크기 [7, 6, 6, 6, 6], 각 사람 test 한 번, fold 마다 inner (seed 20261018, 20 %) 와 test 분리 · inner train ∪ val = train. 공통 mask 10 개 (seed 20261019) 각 20 ROI · 반구 10/10 |
| G 자원 | 14 코어 · 부하 약 2.4 · 다른 R2T 작업 없음. 합성 같은 규모 257 s · 299 MB [측정, 합성], oracle 제외라 더 짧을 것 [추정]. 단일 프로세스 OMP 2 |

## 3. 고정 설정 (`configs/r2t/t1_pilot_real.json`)

- 비교: **BEST-T (43 후보: RIDGE λ 13 · G1-λ 30)** 대 **F4R1 고정** (`scripts/r2t/t1_rel1.py`; EM a 4 × λ 5 × τ 3 × h 4 = 240 조합, 주성분 20 초기화, K 3). 둘 다 fold train rest 만으로 적합, inner val task 창으로 선택, 분모는 train task 창. 원래 BEST (7) 도 계산 (F4R1 fallback 과 보조 비교에 필요).
- **oracle (test 전 후보 평가) 은 주평가에서 제외** (`selection_audit` false). test 정답으로 고르는 경로 없음.
- **주지표**: Δ = NMSE(BEST-T) − NMSE(F4R1), 31 명 전원 (fallback 사람 포함), 사람 단위 bootstrap 10,000 (seed 20261020) 95 % CI · 사람 간 SD. 양수 = F4R1 이 나음.
- 보조: Δ(BEST − F4R1) (원래 7 후보), 성공 fold 한정 Δ (참고), MIX-p − F4R1 (기전), fold 별 선택값 · τ̂.
- **실패 정책 (F4R1 고정 규칙)**:
  - 정상 실패 (비수렴 · 점유율) 로 혼합이 안 된 fold → BEST (원래 7) 예측으로 fallback (R3). fallback 사람의 주지표 Δ = NMSE(BEST-T) − NMSE(BEST) 이며 0 이 아닐 수 있다. fallback fold 수 · 사람 수를 보고한다.
  - **pilot 수치 오류 정책 (실행 wrapper, F4R1 고정본은 바꾸지 않음)**: 어떤 적합 restart 에서든 수치 실패 (비 SPD · 선형대수 예외 · 비유한) 가 **한 건이라도** 나오면 그 restart 직후 즉시 멈춘다 (restart 함수를 wrapper 가 감쌈) — 그 후보의 남은 restart · 다른 후보 · 후속 fold · 평가 · 결과 저장 없이 위치 (fold · inner/train 단계 · EM a · restart seed) 와 원인을 `numeric_stop.json` 에 남기고 exit 1. F4R1 의 R5 (일부 restart 수치 실패를 경고하고 진행) 와 R4 (fold 단위 중단 후 나머지 진행) 는 이 pilot 에서 쓰지 않는다. BEST · BEST-T 적합 중 예외 · 비유한 입력 · 예측도 중단 (원인 기록).
  - 정리: **정상 비수렴 · 점유율 실패만** 고정 fallback (R3) 을 적용한다.
- 판단 (탐색 기술값, 성공 판정 아님): 점추정 · 95 % CI · SD 를 보고한다. Δ 상한 < 0 이면 "K>1 경로 중단 권고", 성공 fold 모두 τ̂ = 0 이면 "적응 경로 중단 권고" 플래그를 그대로 적는다. δ (0.01) 는 보고용.
- 저장: 사람별 산출 `data/r2t_pilot_real/run/pilot31.{json,npz}` (gitignore 영역 — 사람별 점수 · 명단 · 선택 설정 · 점수 · 적합 · 실패 기록 · 예측 배열 · Δ SD). 잠금 · 사전 점검 · 요약 · manifest 는 `results/r2t/t1_pilot_real/`. 기존 결과 · 고정본은 쓰지 않는다. h197 이동 · Data Asset 등록은 이번 범위 밖 (외부 업로드 금지) — 로컬 보존만.
- 실행 뒤 검증: F4R1 엄격 검증 (`verify_prefix`) 에 실제 task 를 다시 읽어 사람별 점수 · 예측 재계산. 실행 로그의 마지막 줄 ("완료") 을 쓴 **뒤** 결과 · 로그 · 잠금 파일의 sha256 으로 결과 manifest 를 만든다 (manifest 해시는 로그에 쓰지 않음 — 순환 없음).

## 4. 실행 순서

1. 잠금 생성 (`lock.json`: 코드 · 설정 · 설계 문서 · 사전 점검 보고 · 입력 파일 sha256 · 환경).
2. 실행기 `scripts/r2t/run_t1_pilot_real.py` 가 시작 전에 잠금을 다시 대조 (하나라도 다르면 실행 안 함, exit 2).
3. 실제 자료 적재 (`t1.load_real`, 승인 플래그) → F4R1 pipeline → 저장 → 엄격 검증 → 결과 manifest. 검증 실패 · 중단은 exit 1 과 원인 기록.
4. 결과 보고 뒤 멈춘다.

## 5. 잠금 전 시험 (합성 자료만)

- `tests/r2t/test_r2t_pilot_real_policy.py` 7 passed: pilot 설정 (oracle 제외 · 예측 보존 · BEST-T · 주지표 · gitignore 출력), 수치 실패가 없으면 F4R1 과 같은 결과, **restart 하나만 수치 실패 → 그 restart 직후 중단** (restart 호출 3 회에서 멈춤, fold 0 의 BEST · BEST-T 평가 뒤 F4R1 평가 · 다른 fold 없음, 위치 · 원인 기록), ok 인데 비유한 → 중단, train 재적합 단계 수치 실패 위치 기록, 정상 실패 → 고정 fallback (분모 유지, fallback Δ = BEST-T − BEST), 로그 마지막 줄 → manifest 순서 · manifest 뒤 로그 쓰기 없음.
- `tests/r2t` 전체 109 passed (563 s), `.pyc` 0. F4 · F4R 고정본 불변.
