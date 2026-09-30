# WI-01 — 원본·TR·시간축 감사 (G0)

> **[ERRATA 2026-09-17]** 이 문서의 일부 결론은 이후 독립 재검토에서 정정되었다. 정정본은
> [`wi00_wi01_execution_report_2026-09-17.md`](wi00_wi01_execution_report_2026-09-17.md) 이며,
> 충돌 시 그 문서를 적용한다. 주요 정정: (E1) AOMIC 원본 restingstate BOLD 9개가
> `data/legacy_phase2/` 아래에 존재하므로 "원본 NIfTI 0건"은 거짓이다. (E2) 그 헤더로
> PIOP1 rest TR = 0.75 s, PIOP2 rest TR = 2.00 s 가 확정되므로 U1은 두 target task로 범위가
> 좁혀진다. (E3) sub-0167은 emomatching 하나가 아니라 anticipation·emomatching·faces·gstroop
> 4개 run 전부가 nuisance 회귀 없이 저장되었다. 원문은 기록 보존을 위해 그대로 둔다.

**작성일 2026-09-17 · release_id `20260917_3c458d507e82_nocfg` · git HEAD**

범위: 로컬 연결 폴더(`/Users/hwon/projects/Git/Manuscript/MoBSE`) 안에서 실제로 실행한 명령의 출력만 기록한다. 원격 다운로드는 시도하지 않았다. 확인하지 못한 값은 null 로 두고 사유를 남겼다. 추론값은 쓰지 않는다.

실행 환경 주의: 계획된 `.venv/bin/python` 은 이 셸에서 **사용 불가**다. `.venv/bin/python3.11` 이 `/opt/homebrew/opt/python@3.11/bin/python3.11` 로 가는 심볼릭 링크인데 그 경로가 이 실행 환경에 없다(`bash: .venv/bin/python: No such file or directory`). 따라서 모든 측정은 시스템 `python3` (3.10.12, `/usr/bin/python3`)로 했다. 이 인터프리터에서 `numpy 2.2.6`·`pandas 2.3.3` 은 실제로 import 에 성공했고(WI-00 snapshot 의 `environment.sandbox_note` 는 시스템 python3 에 의존성이 없다고 적었으나, 이번 실행에서 두 패키지는 사용 가능했다), `nibabel`·`nilearn` 은 `ModuleNotFoundError` 다. 그래서 NIfTI 는 gzip 해제 후 NIfTI-1 헤더를 `struct` 로 직접 파싱했다.

---

## 1. 문헌값(D1) vs 로컬 실측값 대조

### 1.1 먼저: 문헌값의 출처 문제

`docs/experiments/mobse_literature_review_2026-09-17.md:21` 의 **D1 항목에는 TR·volume 수의 숫자가 하나도 적혀 있지 않다.** D1 행의 서술은 "PIOP1/2 과제, TR, 촬영 순서 및 event·행동 변수 정의"와 "emomatching/workingmemory는 두 cohort에서 비교 가능한 task 후보"뿐이다(같은 문서 23행의 읽은 범위 서술도 "D1은 task·acquisition 정의"라고만 한다).

숫자는 **계획서 본문에만** 있다 — `mobse_redesign_protocol_2026-09-17.md` §2:

> "D1에서 두 target TR은 2초이며 PIOP2 rest 240 volumes는 480초다. … 로컬 WM 160 대 문헌 162 volumes 차이는 실제 제거 volume 기록으로 설명해야 한다."

즉 이번 감사에서 쓸 수 있는 문헌값은 계획서가 D1에서 인용했다고 **주장하는** 세 값(target TR 2초 / PIOP2 rest 240 volumes = 480초 / WM 162 volumes)뿐이며, 문헌 검토 문서에서 그 인용을 직접 대조할 수는 없다. 이것 자체가 G0의 미해결 항목이다(U7).

### 1.2 대조표

| 대상 | 문헌 주장값(계획서 §2가 D1 인용) | 로컬 실측값 | 실측 근거 | 판정 |
|---|---|---|---|---|
| PIOP1 emomatching TR | 2초 | **null** | 로컬에 sidecar JSON·NIfTI 헤더 없음 | 미확인 |
| PIOP1 workingmemory TR | 2초 | **null** | 동일 | 미확인 |
| PIOP1 restingstate TR | (언급 없음) | **null** | 동일 | 미확인 |
| PIOP2 restingstate TR | 2초(240 vol=480초로부터) | **null** | 동일 | 미확인 |
| PIOP1 emomatching volumes | (언급 없음) | **135** (207/207 파일 전부) | `.npy` shape 전수 | 실측 |
| PIOP1 workingmemory volumes | 162 | **162** (204/204 파일 전부) | `.npy` shape 전수 | **일치** |
| PIOP1 restingstate volumes | (언급 없음) | **480** (210/210) | `.npy` shape 전수 | 실측 |
| PIOP2 restingstate volumes | 240 | **240** (1/1) | `.npy` shape | **일치** |
| PIOP2 workingmemory volumes | (언급 없음) | **160** (1/1) | `.npy` shape | 실측 |
| PIOP2 rest 지속시간 | 480초 | **null** (저장된 값은 180.0초) | 아래 §2 | **불일치(저장값이 오류)** |
| 기타 PIOP1 task volumes | (언급 없음) | anticipation 200, faces 330, gstroop 245 | `.npy` shape 전수 | 실측 |

전수 shape 집계(파일 2,456개, 비정상 0개):

```
$ python3 -c "... np.load(f, mmap_mode='r').shape ..."   # 전 파일
piop1 anticipation  (200,100)x197  (200,200)x197
piop1 emomatching   (135,100)x207  (135,200)x207
piop1 faces         (330,100)x203  (330,200)x203
piop1 gstroop       (245,100)x205  (245,200)x205
piop1 restingstate  (480,100)x210  (480,200)x210
piop1 workingmemory (162,100)x204  (162,200)x204
piop2 restingstate  (240,100)x1    (240,200)x1
piop2 workingmemory (160,100)x1    (160,200)x1
```

task별 length 분포는 **분산이 0**이다(각 task 안에서 모든 subject가 동일 길이, 100/200 node 트리 동일). 전수 검사이며 파일 크기로 유도한 값이 아니다.

### 1.3 지속시간을 계산할 수 없는 이유

volume 수는 실측되지만 지속시간은 TR이 있어야 한다. 로컬에 TR의 **acquisition 근거가 하나도 없다**. 유일한 로컬 TR 기록은 추출 manifest의 `"tr": 0.75` 인데, 이는 §2에서 보이듯 CLI 기본값이지 획득값이 아니다.

---

## 2. 기존 추출 코드의 실제 TR 처리 — 코드 근거

계획서 §2의 "기존 추출 코드의 기본 TR 0.75초" 주장은 **코드에서 사실로 확인된다.** 더 나아가 **task별 TR 분기, JSON/헤더 조회가 전혀 없다**는 점까지 확인된다.

| 근거 | 내용 |
|---|---|
| `scripts/stream_aomic_extract.py:485-486` | `parser.add_argument("--tr", type=float, default=0.75, help="Repetition time in seconds (AOMIC default: 0.75)")` |
| `scripts/stream_aomic_extract.py:303` | `process_one_subject(..., tr: float = 0.75, ...)` |
| `scripts/stream_aomic_extract.py:219` | `extract_roi_timeseries(..., tr: float = 0.75, high_pass=0.008, low_pass=0.1)` |
| `scripts/stream_aomic_extract.py:394-398` | subject의 **모든 task** loop 안에서 같은 `tr=tr` 를 그대로 전달 — task 분기 없음 |
| `scripts/stream_aomic_extract.py:230-237` | `NiftiLabelsMasker(labels_img=atlas.maps, standardize="zscore_sample", t_r=tr, detrend=True, high_pass=0.008, low_pass=0.1)` — band-pass가 이 `t_r` 에 의존 |
| `scripts/stream_aomic_extract.py:452` | `scan_duration_sec=n_tp * tr, tr=tr` — 저장된 duration도 같은 상수에서 나옴 |

**JSON을 읽는 코드는 없다.** `RepetitionTime` 문자열은 `scripts/stream_aomic_extract.py` 전체에 존재하지 않는다(grep 0건). `discover_bold_files`(:247-293)는 `*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz` 만 찾고 sidecar를 수집하지 않는다.

**저장된 artifact에서의 직접 증거:** `data/aomic/piop2/manifests/extraction_manifest_20260415_144627.json` 의 restingstate 레코드는
`"n_timepoints": 240, "tr": 0.75, "scan_duration_sec": 180.0` 이다. 계획서가 D1에서 인용한 값은 240 volumes = **480초**다. 저장된 값은 그 **0.375배**다. 즉 TR 오적용은 가설이 아니라 로컬 artifact 안에 기록으로 남아 있다.

`data/aomic/piop1/manifests/extraction_manifest_20260416_071901.json` 전수: ok 2,452건 / excluded_motion 10건, `tr` 값 분포는 `{0.75: 2452, None: 10}` — **단일 값 0.75** 이며 task별 차이가 없다.

**조건부 산술(가정을 명시):** *만약* 두 target의 native TR이 계획서가 인용한 2초라면, nilearn butterworth는 차단주파수를 `t_r` 로 정규화하므로 실제 시간축 기준 통과대역은 `0.008–0.1 Hz × (0.75/2)` = **0.003–0.0375 Hz** 가 된다. 이 문장은 TR=2초라는 가정 아래의 산술이며, TR 자체를 확정한 것이 아니다.

### 2.1 코드에서 함께 확인된 confound 처리 결함

| 근거 | 내용 | 계획서 §3.2와의 충돌 |
|---|---|---|
| `:61-78` | `CONFOUND_COLS_24P`(24개) + `CONFOUND_COLS_COMPCOR = [a_comp_cor_00..04]` | aCompCor를 **이름 순서**로 고정 선택. 계획서는 "metadata의 설명분산 순서" 요구 → 불일치 |
| `:185-190` | 열의 50% 미만일 때만 **warning**, 그대로 진행 | 계획서 "정의에 맞는 5개가 없으면 대체하지 않는다"와 충돌(조용한 축소) |
| `:198` | `np.nan_to_num(arr, nan=0.0)` | 미분 첫 행 NaN을 **0으로 치환**. 계획서는 첫 frame 구조적 결측만 별도 표시하고 그 외 결측은 실패 처리 요구 |
| `:279-285` | `func_dir.glob(f"*task-{task_name}*desc-confounds_regressors.tsv")` 의 `[0]` 채택 | run/acq entity가 여러 개일 때 **다른 run의 confounds** 가 붙을 수 있음(정렬 미검증) |
| `:305, 370-382` | `mean_fd_threshold = 0.5` 로 run 통째 제외 | 계획서 주기준은 mean FD≤0.2 + window별 FD>0.5 비율 — 다른 규칙 |
| `:306, 418-428` | `min_timepoints = 100` | 시간 기준이 아니라 sample 수 기준 |
| `:455 주석` | `# tmpdir is auto-cleaned here (NIfTI deleted)` | 원본 NIfTI가 로컬에 남지 않은 이유 |
| `scripts/build_alltasks_windows.py:87-90, 122-124` | `window_len=64`, `stride=16`, tukey taper, centroid 기반 label | **시간(초)이 아니라 sample 수** 기준 window. `[12,252)`초 규칙과 무관하며 label도 centroid pseudo-label |

---

## 3. 계획서 §2 표 7개 수치 검증

기준 트리: `data/aomic/piop1/timeseries/100` (200-node 트리도 동일 결과).

| # | 항목 | 계획서 주장값 | 실측값 | 검증 명령 | 일치 |
|---|---|---:|---:|---|---|
| 1 | PIOP1 subject directory | 216 | **216** | `ls -1 data/aomic/piop1/timeseries/100 \| wc -l` | ✅ |
| 2 | PIOP1 emomatching 보유 | 207 | **207** | `ls -1 data/aomic/piop1/timeseries/100/*/emomatching.npy \| wc -l` | ✅ |
| 3 | PIOP1 workingmemory 보유 | 204 | **204** | `ls -1 .../*/workingmemory.npy \| wc -l` | ✅ |
| 4 | PIOP1 restingstate 보유 | 210 | **210** | `ls -1 .../*/restingstate.npy \| wc -l` | ✅ |
| 5 | PIOP1 emo∩WM | 202 | **202** | `comm -12 <(ls .../*/emomatching.npy \| awk -F/ '{print $(NF-1)}' \| sort) <(ls .../*/workingmemory.npy \| awk -F/ '{print $(NF-1)}' \| sort) \| wc -l` | ✅ |
| 6 | PIOP1 emo∩WM∩rest | 196 | **196** | 위 결과를 restingstate 목록과 다시 `comm -12` | ✅ |
| 7 | PIOP2 두 target pair | 0 | **0** | `ls -1 data/aomic/piop2/timeseries/100/*/emomatching.npy \| wc -l` → 0; `comm -12` emo/WM → 0 | ✅ |

**7/7 재현.** 다만 이 수치는 **파일 보유 수**이지 분석 N이 아니며(계획서도 그렇게 명시), 아래 §7의 이유로 이 파일들은 주분석 재사용 대상이 아니다.

참고로 함께 세어진 값: anticipation 197, faces 203, gstroop 205 (계획서 미기재).

### 3.1 파일 수와 manifest의 대조에서 나온 추가 사실

- manifest(20260416) 기준 `ok` 레코드 수는 100-node에서 task별 197/207/203/205/210/204 로 **파일 수와 정확히 일치**한다.
- `excluded_motion` 10건(mean FD>0.5): sub-0001 WM(0.659), sub-0013 anticipation, sub-0083 WM(0.594), sub-0120 anticipation·WM, sub-0124 emomatching(0.525), sub-0130/0143/0149/0200 anticipation.
- **`ok` 인데 `mean_fd`가 null 인 run이 8 레코드(=run 4개 × atlas 2개) 있다: sub-0167 의 anticipation/emomatching/faces/gstroop.** 코드 경로상 `mean_fd is None`은 confounds 파일을 찾지 못했다는 뜻이며(`:366-369`), 그 경우 `confounds_arr=None` 으로 **nuisance 회귀를 전혀 하지 않은 채** `.npy`가 저장된다(`:384-398`). sub-0167 은 rest(FD 0.204)·WM(FD 0.192)은 confounds가 있었고 emomatching만 없었다. **sub-0167은 196명 후보 집합에 포함되어 있다.** 즉 후보 집합 안에 전처리 이력이 서로 다른 run이 섞여 있다.
- manifest의 mean FD(전체 run 기준) 분포: emomatching n=206 중앙값 0.1076 최대 0.4371, >0.2 인 run 15개 / workingmemory n=204 중앙값 0.1088 최대 0.4796, >0.2 24개 / restingstate n=210 중앙값 0.1009 최대 0.4195, >0.2 4개. 이는 **참고값일 뿐** 계획서 §3.3의 판정에는 쓸 수 없다(원본 frame별 FD가 없어 window별 FD>0.5 비율을 계산할 수 없음).

### 3.2 기존 `.npy` 의 기술적 상태(통과 근거로 쓰지 않음)

target 3개 task의 100-node 파일 621개 전수: nonfinite 0건, constant ROI 0건, 전체 평균 1.24e−08, 전체 표준편차 0.9974(= `standardize="zscore_sample"` 의 흔적). **계획서가 금지한 대로, 이 결과를 "shape·유한성이 맞으니 통과"로 쓰지 않는다.** 추출 시간축이 입증되지 않았으므로 주분석 재사용 불가 판정은 그대로다.

---

## 4. 로컬 자료 인벤토리 — 형태별

| 종류 | 개수 | 위치 | 비고 |
|---|---:|---|---|
| 파생 ROI 시계열 `.npy` | **2,456** | `data/aomic/{piop1,piop2}/timeseries/{100,200}/sub-*/` | `data/aomic` 총 **371 MB** (`du -sh`) |
| 원본 NIfTI `.nii.gz` (PIOP1/2) | **0** | — | 저장소 전체에 AOMIC NIfTI 없음 |
| confounds `.tsv` (PIOP1/2) | **0** | — | `find . -name '*confounds*'` 에 AOMIC 항목 0건 |
| events `.tsv` (PIOP1/2) | **0** | — | `find . -name '*events*'` 0건 |
| sidecar `*_bold.json` | **0** | — | **로컬에 원본 JSON 없음** |
| participants `.tsv` | 3 | piop1(216행), piop2(226행), id1000 | 열: age/sex/BMI/handedness/education_category/raven/NEO 5종 (+piop1 `religious_now`) |
| 추출 manifest `.json` | 4 | `data/aomic/*/manifests/` | 유일한 TR·FD 기록처 |
| atlas 캐시 | 6 파일 | `data/cache/_atlas_probe/schaefer_2018` | §6 참조 |

**`RepetitionTime`·`TaskName`·`SliceTiming`·`NumberOfVolumes` 를 전수 집계할 sidecar JSON이 로컬에 하나도 없다. 이것이 G0를 차단한다.**

confounds TSV 판정: **행 수(=volume 수)도 열 이름도 확인할 수 없다.** 따라서 24 motion regressors / aCompCor 5 / FD 열이 실제로 구성 가능한지는 **판정 불가**다. 남은 것은 run당 스칼라 mean FD 하나뿐이고, 계획서 §3.2가 요구하는 열 단위 검증·design rank·residual DOF 계산의 입력이 되지 못한다.

events TSV 판정: 파일이 없으므로 **onset 원점 확인 불가**.

PIOP2 세부: subject 디렉터리 1개(sub-0001), restingstate(240×N)·workingmemory(160×N)만 존재, emomatching 0건 → target pair 0건.
`data/aomic/id1000` 은 `participants.tsv` 와 manifest 1개만 있고 시계열은 0건이다(manifest status `no_bold`: "No matching BOLD files in fMRIPrep derivatives").

---

## 5. WM 160 vs 162 volumes — 판정

**판정: 현재 근거로 설명 불가(blocked). 추가로, 계획서 §2의 문제 서술 자체가 로컬 사실과 맞지 않는다.**

실측 사실:

1. **PIOP1 workingmemory 는 204개 파일 전부 162 volumes** 이다. 로컬 PIOP1에 160-volume WM 파일은 **0개**다.
2. 160 volumes 인 WM은 **PIOP2 sub-0001 단 1건**이다.
3. 추출 manifest도 PIOP1 WM `n_timepoints: 162` 로 일치한다.

따라서 계획서 §2의 "로컬 WM 160 대 문헌 162 volumes 차이"는 **PIOP1 로컬 대 문헌의 차이가 아니라, PIOP2(160) 대 PIOP1/문헌(162)의 cohort 간 차이**로 정정되어야 한다. 계획서 문장을 그대로 두면 존재하지 않는 불일치를 추적하게 된다.

남은 실제 질문 — **PIOP2 WM 이 왜 160인가** — 는 현재 근거로 답할 수 없다:

- 제거 volume 기록이 어디에도 없다(추출 코드는 volume을 버리지 않으며 manifest에도 `discarded_volumes` 필드가 없다).
- sidecar JSON이 없어 PIOP2 WM 의 `NumberOfVolumes`·TR 을 확인할 수 없다.
- 표본이 PIOP2 subject 1명뿐이라 cohort 차이인지 개별 run 차이인지 구분할 수 없다.

해소 조건: PIOP2 WM 의 `*_bold.json` 과 원본(또는 fMRIPrep) NIfTI 헤더, 그리고 PIOP2 WM 을 최소 수십 subject 확보해 volume 수 분포를 보는 것.

---

## 6. Atlas 명세

`data/cache/_atlas_probe/schaefer_2018` 에서 **파일을 직접 읽어** 측정했다(gzip 해제 후 NIfTI-1 헤더 파싱 + 라벨 전수 집계). 전체 값은 `provenance/atlas_spec.json`.

Schaefer2018 100Parcels 7Networks FSLMNI152 2mm:

- 파일: `Schaefer2018_100Parcels_7Networks_order_FSLMNI152_2mm.nii.gz`
- SHA256 `101cb2e643531826e5d52d35751f3cf7134c394b08b8ce0affa259a224350f67` (52,328 bytes)
- shape 91×109×91, voxel 2.0×2.0×2.0 mm, datatype float32(code 16), magic `n+1`
- qform_code 1 / sform_code 1, srow = [[−2,0,0,90],[0,2,0,−126],[0,0,2,−72]]
- 라벨: 0 포함 고유값 101개 → **비영 라벨 100개, 1..100 연속** (실측)
- ROI order table `Schaefer2018_100Parcels_7Networks_order.txt` SHA256 `ca212790d0103949c8cfa0f7689f5935cad0d1fbfc06506f1fdf7986bee72786`, 100행, 첫 행 `1 7Networks_LH_Vis_1`, 끝 행 `100 7Networks_RH_Default_pCunPCC_2`
- 200/300 parcel 파일도 같은 방식으로 측정해 `atlas_spec.json` 에 기록

**그러나 이 캐시는 기존 `.npy` 를 만든 atlas가 아니다(미해결).** `scripts/stream_aomic_extract.py:230` 은 `fetch_atlas_schaefer_2018(n_rois=num_nodes)` 를 `resolution_mm`·`data_dir` 없이 호출하고, nilearn 0.13.1 의 기본값은 `resolution_mm=1`(`.venv/lib/python3.11/site-packages/nilearn/datasets/atlas.py:2226-2234`)이며 기본 저장 위치는 연결 폴더 밖의 `~/nilearn_data` 다. 저장소 전체에 `*Schaefer*1mm*` 파일은 **0건**이다. 따라서 기존 파생물의 `atlas_id`/`atlas_hash`/`roi_order_hash` 는 null 이다.

---

## 7. `[12,252)`초 구간이 실제 데이터에서 지원되는가 — 산술 판정

요건: 원본 acquisition clock에서 마지막 고정 window가 `[192,252)`초이므로 **최소 252초의 원본 coverage**가 필요하다. 2초 grid에서 window당 30 samples.

| run | volumes(실측) | TR=2초 가정 시 coverage | 252초 지원 | TR=0.75초(기존 적용값) 시 coverage | 252초 지원 |
|---|---:|---:|:--:|---:|:--:|
| PIOP1 emomatching | 135 | 270.0 s | ✅ (여유 18.0 s) | 101.25 s | ❌ |
| PIOP1 workingmemory | 162 | 324.0 s | ✅ (여유 72.0 s) | 121.5 s | ❌ |
| PIOP1 restingstate | 480 | 960.0 s | ✅ | 360.0 s | ✅ |
| PIOP2 restingstate | 240 | 480.0 s | ✅ | 180.0 s | ❌ |
| PIOP2 workingmemory | 160 | 320.0 s | ✅ (여유 68.0 s) | 120.0 s | ❌ |

판정:

1. **TR이 확정되지 않았으므로 `[12,252)` 지원 여부는 현재 확정 불가다.** 위는 두 후보 TR에 대한 조건부 산술이다.
2. 계획서가 인용한 TR=2초가 맞다면 다섯 run 유형 모두 `[12,252)` 를 지원한다. 단 **emomatching의 여유는 18.0초(=2초 기준 9 samples)뿐**이다. 앞쪽에서 제거된 volume이 9개를 넘으면 emomatching은 이 구간을 지원하지 못한다. 제거 volume 기록이 없으므로(§5) 이 여유가 실제로 남아 있는지 **검증 불가**다.
3. 기존 파생물에 실제로 적용된 TR=0.75초 가정 아래에서는 **두 target 모두 `[12,252)` 를 지원하지 못한다**(101.25 s, 121.5 s). 기존 `.npy` 를 그대로 쓰는 경로는 이 산술만으로도 배제된다.
4. PIOP1 restingstate 는 480 volumes 로 PIOP2 rest(240)와 **정확히 2배** 차이가 난다. 두 cohort의 rest 획득이 동일 TR인지 여부는 로컬 근거가 없어 판정하지 않는다.

---

## 8. PIOP2 확보 상태와 G4 영향

- 실측: `data/aomic/piop2/timeseries/100` 에 subject 디렉터리 **1개**(sub-0001), 파일은 `restingstate.npy`(240×100)와 `workingmemory.npy`(160×100). `emomatching` **0건**.
- 따라서 계획서 §2 의 "PIOP2 두 target pair 0" 은 **정확하다.**
- PIOP2 manifest(`extraction_manifest_20260415_144627.json`)는 `total_subjects: 1, processed: 1` 로, 애초에 1명만 시범 추출한 기록이다. 226행의 `participants.tsv` 는 있으나 시계열은 1명분뿐이다.

**G4 영향:** 계획서 §9 / WI-08 의 잠근 replication은 PIOP2 emo/WM paired cohort를 전제로 한다. 현 상태에서 paired subject 수는 0이므로 **G4 는 blocked** 이며, 지침서 WI-08의 규정대로 "미확보 사유를 기록하고 internal-only 결론으로 범위를 제한"하는 경로가 현재 유일하게 가능한 경로다. ds000030 의 다른 task로 대체하는 것은 계획서 §1이 명시적으로 금지한다.

---

## 9. 미해결 차단 항목

| ID | 무엇이 없어서 막혔는가 | 해소하려면 무엇이 필요한가 | 차단 gate |
|---|---|---|---|
| U1 | **task별 native TR 의 acquisition 근거가 0건.** sidecar `*_bold.json` 도 NIfTI 헤더도 로컬에 없음 | PIOP1/PIOP2 의 emomatching·workingmemory·restingstate `*_bold.json`(또는 NIfTI 헤더 pixdim[4]) 확보 후 JSON–헤더 일치 확인 | G0 |
| U2 | **제거 volume 기록 0건.** 추출 코드가 trimming을 하지 않고 manifest에도 필드가 없음 | fMRIPrep `*_desc-confounds_regressors.tsv` 의 `non_steady_state_outlier*` 열, 또는 원본 volume 수와 파생 volume 수를 함께 담은 derivative provenance | G0 |
| U3 | **원본 acquisition clock 기준 첫 sample 시간 미상** (U1·U2의 귀결). `derivative_start_sec` 를 어떤 run에서도 채울 수 없음 | U1+U2 해소 | G0 |
| U4 | **confounds TSV 0건.** 행 수·열 이름을 확인할 수 없어 24 motion / aCompCor 5(설명분산 순서) / FD 열 구성 가능성 **판정 불가**, design rank·residual DOF 계산 불가, window별 FD>0.5 비율 계산 불가 | 해당 run들의 `*_desc-confounds_regressors.tsv` 와 aCompCor metadata JSON 확보 | G0, G1 |
| U5 | **events TSV 0건 → onset 원점 미확인** | 해당 run들의 `*_events.tsv` 확보 | G0 |
| U6 | **원본/파생 BOLD NIfTI 0건.** 올바른 TR로 재추출(WI-02)할 입력 자체가 없음. 기존 스크립트가 streaming 후 삭제(`:455`) | PIOP1/PIOP2 fMRIPrep derivative BOLD 재확보(대량 다운로드 계획 별도 승인 필요) | G0, G1 |
| U7 | **문헌값의 추적 불가.** 문헌 검토 D1 행에 TR·volume 숫자가 없고, 계획서 §2 본문에만 존재 | D1 원문(Snoek 2021)의 해당 표·본문 구절을 문헌 검토 문서에 수치와 함께 인용해 고정 | G0 |
| U8 | **계획서 §2 의 "로컬 WM 160" 서술이 로컬 사실과 불일치** (로컬 PIOP1 WM 전수 162, 160은 PIOP2 1건) | 계획서 §2 문장을 "PIOP2 WM 160 대 PIOP1/문헌 162" 로 정정하고 U1·U2로 원인 규명 | G0 |
| U9 | **기존 파생물의 atlas 신원 미확인.** nilearn 기본 `resolution_mm=1` 파일이 저장소에 없음 | 추출 시 사용한 `~/nilearn_data` 의 Schaefer 1mm 파일 확보 및 해시, 또는 명시적 atlas 경로로 재추출 | G0 |
| U10 | **group_id 를 만들 metadata 0건.** participants.tsv 에 가족/중복 식별 열 없음; PIOP1–PIOP2 subject overlap 확인 불가 | AOMIC 공식 문서의 subject 관계·cohort overlap 정의 확인, 확인 불가 범위 명시 | G1, G4 |
| U11 | **PIOP2 target pair 0건** | PIOP2 emomatching+workingmemory 를 가진 subject cohort 확보 | G4 |
| U12 | **후보 집합 내 전처리 이력 불균질.** sub-0167 emomatching 은 confounds 없이(nuisance 회귀 0) 추출되었고, 이 subject 는 196 후보에 포함 | U4 해소 후 전 run 재추출(WI-02); 재추출 전에는 이 run을 정상으로 취급하지 않음 | G0, G1 |
| U13 | **실행 환경 불일치.** 지침서가 지정한 `.venv/bin/python` 이 이 셸에서 실행 불가(심볼릭 링크 대상 부재) | WI-00 workspace snapshot 에 실제 사용 가능한 인터프리터와 버전을 기록하고 재현 환경을 고정 | G1 |

---

## 10. G0 판정

**G0 = blocked.**

계획서 §10 표의 G0 통과 조건은 "미해결 TR·offset·원본 대응 0" 이다. 현재 미해결 항목은 TR(U1), offset(U2·U3), 원본 대응(U4·U5·U6) 모두에서 0이 아니다. 지침서 WI-01 의 중단 조건 "TR/offset 불명, confound alignment 미확인" 에 정확히 해당한다.

동시에, G0를 blocked 로 두더라도 이번 감사에서 **확정된 사실**은 다음과 같다:

1. 계획서 §2 표의 7개 수치는 **7/7 재현**된다.
2. 기존 추출의 TR 0.75초 전역 적용은 **코드(6개 지점)와 저장된 manifest(2,452건 전부)로 입증**된다. 반증되지 않았다.
3. PIOP2 rest 의 저장된 `scan_duration_sec = 180.0` 초는 계획서가 인용한 480초의 0.375배로, **TR 오적용이 artifact에 기록으로 남아 있다.**
4. 기존 `.npy` 를 주분석에 재사용하는 경로는 §7의 산술(TR 0.75 하에서 두 target 모두 252초 미달)만으로도 배제된다.
5. `[12,252)` 구간은 TR=2초가 확정될 경우에만 지원되며, emomatching 의 여유는 18초(9 samples)로 매우 작다.
6. G4 는 PIOP2 paired cohort 0건으로 별도 blocked 다.

다음 단계는 U1·U2·U4·U5·U6 를 해소할 **파일 확보 계획**(무엇을, 몇 건, 어디서)을 먼저 승인받는 것이며, 그 전에는 WI-02 재추출을 시작할 수 없다.

---

## 11. 산출물

| 파일 | 내용 |
|---|---|
| `provenance/source_runs.jsonl` | 헤더 1행 + run 1,228행. 모든 `native_tr`·`source_*`·`confounds_*`·`events_*`·`discarded_volumes`·`derivative_start_sec`·`atlas_*`·`group_id` 는 null 이며 각 행 `unresolved` 배열에 사유 기록 |
| `provenance/_gen_source_runs.py` | 위 파일 생성 스크립트(재실행 가능, 3.3초) |
| `provenance/missing_sources.json` | 미확보 파일 종류 8항목(M01–M08) |
| `provenance/atlas_spec.json` | 로컬 Schaefer 캐시 3종의 실측 명세 + 기존 파생물 atlas 미확인 사유 |
| `reports/timing_audit.md` | 본 문서 |

`source_runs.jsonl` 키 규약: `run_key = dataset/subject/session/task/run/acquisition`, 없는 entity의 빈값은 **`na`** 로 일관 직렬화(구분자 `/` 와 충돌하지 않도록 `n/a` 대신 `na` 사용, 사유는 헤더 레코드 `key_convention.empty_entity_value_rationale` 에 기재). run_key 1,228개 전부 유일함을 python 으로 검증했다.
