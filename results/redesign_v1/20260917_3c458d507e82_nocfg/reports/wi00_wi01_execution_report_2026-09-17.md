# WI-00 / WI-01 실행 보고서 — 재설계 G0 감사

**release_id** `20260917_3c458d507e82_nocfg` · **git HEAD** `7787ae0c9741c22c207032c8bd78fd462ce02b9f` · 2026-09-17

적용 문서: [재설계 프로토콜 v1.1](../../../../docs/experiments/mobse_redesign_protocol_2026-09-17.md), [작업 지침서 v1.0](../../../../docs/experiments/mobse_redesign_work_instructions_2026-09-17.md)

## 0. 이 문서의 지위

WI-00(현재 상태 보존)과 WI-01(원본·TR·시간축 감사)의 실행 결과를 하나로 묶은 **통합 보고서**다. 세부 감사 기록은 `timing_audit.md`와 `implementation_map.md`에 있고, 이 문서는 (a) 그 두 문서를 독립 재계산으로 검토한 결과, (b) 그 과정에서 확정된 **정정 사항**, (c) 후속 gate를 막는 **남은 항목 전체**를 담는다.

`timing_audit.md`와 이 문서가 충돌하면 **이 문서를 적용**한다. 정정 사유는 §4에 남긴다.

측정은 전부 이 세션의 원격 실행 셸(격리 Linux VM, system `python3` 3.10.12, numpy 2.2.6)에서 수행했다. `.venv/bin/python`은 이 환경에서 broken symlink다(§8).

## 1. 결론

| Gate | 판정 | 핵심 사유 |
|---|---|---|
| G0 Provenance | **blocked** | 두 primary target(emomatching, workingmemory)의 원본 BOLD·sidecar·confounds·events가 모두 0건. native TR 미확정. |
| G1 Measurement lock | planned | G0 종속. 추가로 `group_id` 구성 불가(U10)와 subject ID 네임스페이스 충돌(U17). |
| G2 Implementation lock | planned | G0 종속. v2 scaffolding 전부 미존재. |
| G3 Internal release | planned | G0 종속. §7 예산 산술은 검산 통과(총 768 fits). |
| G4 External release | **blocked** | PIOP2 emomatching 0건 → paired target 구성 불가. |
| G5 Interpretation | planned | G0 종속. |

**핵심 변화(1차 보고 대비):** 저장소 안에 AOMIC 원본 restingstate BOLD 9개가 있었고, 그 NIfTI 헤더가 두 cohort rest의 native TR을 직접 준다. 따라서 "native TR 근거 0건"은 **restingstate에 한해 거짓**이다. G0 blocked라는 최종 판정은 유지되지만, **차단 사유의 범위는 두 target으로 좁혀진다**.

## 2. 산출물

| 파일 | SHA256 |
|---|---|
| `provenance/workspace_snapshot.json` | `43dac7b5195059f9…` (정정 후, §4-E4) |
| `provenance/source_runs.jsonl` | `81645ac323376afc…` (헤더 1 + run 1,228) |
| `provenance/missing_sources.json` | `9c6199d65661d43f…` |
| `provenance/atlas_spec.json` | `ec0034be9462f014…` |
| `provenance/_gen_source_runs.py` | `e2f83f5c5ac76888…` |
| `reports/implementation_map.md` | `01e65ed89f9a28f2…` |
| `reports/timing_audit.md` | `fe1e88f81986a371…` |
| `gate_evidence.json` | revision 2 |
| `docs/experiments/figures_redesign_2026-09-17/` | RD1–RD4 (PNG+PDF, manifest·caption·README) |

전체 해시는 `gate_evidence.json`의 `artifact_hashes` / `protocol_figures`에 있다.

## 3. 검증된 사실

모든 값은 실제 명령 출력에서만 가져왔다. 추론값은 없다.

### 3.1 로컬 AOMIC 인벤토리

| 항목 | 수 | 비고 |
|---|---:|---|
| 파생 ROI 시계열 `.npy` | 2,456 | `data/aomic/**/timeseries/{100,200}` · 371 MB |
| 원본 BOLD `.nii.gz` (restingstate만) | 9 | `data/legacy_phase2/` 아래. PIOP1 2 + PIOP2 5 + 중복 2 |
| 두 target task의 BOLD | **0** | — |
| sidecar `*_bold.json` | **0** | 저장소 전체 |
| confounds `.tsv` (AOMIC 범위) | **0** | 저장소 전체로는 2,149건(ds000030 1,969 / ds000243 180) |
| events `.tsv` | **0** | 저장소 전체 |
| extraction manifest `.json` | 4 | — |
| `participants.tsv` | 3 | piop1 216행/13열, piop2 226행/12열, id1000 928행/31열 |

### 3.2 native TR — 확정된 것과 미확정인 것

원본 NIfTI-1 헤더 `pixdim[4]`를 gzip+struct로 직접 파싱했다(`xyzt_units` 시간 단위 = 초, 9개 파일 전부 일관).

| 데이터셋 | task | acq | volumes | **native TR** | 실제 지속시간 |
|---|---|---|---:|---:|---:|
| PIOP1 (ds002785) | restingstate | mb3 | 480 | **0.75 s** | **360.0 s** |
| PIOP2 (ds002790) | restingstate | seq | 240 | **2.00 s** | **480.0 s** |
| PIOP1 | emomatching | — | 135 | **미확정** | — |
| PIOP1 | workingmemory | — | 162 | **미확정** | — |
| PIOP2 | workingmemory | — | 160 | **미확정** | — |

여기서 나오는 세 가지 결론:

1. **기존 추출의 TR 오적용은 PIOP2에 한정 확정된다.** 추출 코드는 모든 run에 `--tr 0.75`를 적용했고(`scripts/stream_aomic_extract.py:485`, ok run 2,458건 전부 `tr=0.75`), PIOP1 rest는 native가 실제로 0.75초라 **우연히 옳다**. PIOP2 rest는 native 2.00초인데 0.75초로 처리되어 manifest에 480초를 **180초**로 기록했고(0.375배), band-pass 0.008–0.1 Hz의 실효 통과대역도 그 배수만큼 왜곡되었다.
2. **두 primary target은 어느 분기에서도 기존 파생물을 재사용할 수 없다.** TR=2.0초라면 추출이 잘못된 TR로 필터링한 것이고, TR=0.75초라면 emomatching 101.25초 / workingmemory 121.5초로 **주분석 요구 252초에 미달**한다. 후자의 경우 파생물뿐 아니라 **프로토콜의 `[12,252)` window 설계 자체가 emomatching에 대해 성립하지 않는다** — 이는 설계 개정을 요구하는 조건이다.
3. 252초 요구는 TR 2.0초에서 **126 volumes**, TR 0.75초에서 **336 volumes**를 뜻한다. 두 target은 전자에서만 충족된다.

`RepetitionTime` 문자열은 `scripts/`·`mobse/`·`tests/`·`configs/` 전체에 **0건**이다. JSON/헤더를 읽는 경로가 코드에 존재하지 않는다.

### 3.3 파생 시계열 길이 (전수, task 내 분산 0)

| dataset | task | length | n(subject) |
|---|---|---:|---:|
| PIOP1 | emomatching | 135 | 207 |
| PIOP1 | workingmemory | 162 | 204 |
| PIOP1 | restingstate | 480 | 210 |
| PIOP1 | anticipation | 200 | 197 |
| PIOP1 | faces | 330 | 203 |
| PIOP1 | gstroop | 245 | 205 |
| PIOP2 | workingmemory | 160 | 1 |
| PIOP2 | restingstate | 240 | 1 |

100-node와 200-node 트리는 완전히 동일하다(1 run = 두 파일, 1,228 × 2 = 2,456).

### 3.4 계획서 §2 표 7수치 — 7/7 재현

216 / 207 / 204 / 210 / 202 / 196 / 0 모두 일치. 명령은 `ls -1 .../timeseries/100/*/<task>.npy | wc -l` 및 `comm -12` 조합.

### 3.5 manifest 집계

- 4개 manifest 합산: `ok` 2,458 / `excluded_motion` 11 / `no_bold` 1 (총 2,470 레코드).
- ok 2,458건 **전부 `tr=0.75`**, task별 분기 없음.
- `scan_duration_sec = n_timepoints × tr` 는 ok 전건에서 정확히 성립(부동소수 오차 0).
- `status=ok` 인데 `mean_fd=null` 인 레코드는 **8건** = `sub-0167` × {anticipation, emomatching, faces, gstroop} × {100, 200 nodes}. 같은 subject의 rest(0.2042)·WM(0.1919)에는 FD가 있다.
- manifest의 run 단위 `mean_fd` 는 **스칼라 하나뿐**이다. frame-wise FD 시계열이 없으므로 계획서 §3.3의 window별 FD>0.5 비율, design rank, residual DOF는 **계산 불가**다.

### 3.6 Atlas

`data/cache/_atlas_probe/schaefer_2018` 의 2 mm 파일 3종(100/200/300 Parcels, 7Networks, FSLMNI152)과 order.txt 3종의 SHA256·헤더·라벨을 재확인했다: 91×109×91, 2.0 mm iso, 비영 라벨 1..100 연속. **그러나 이것은 기존 `.npy` 를 만든 atlas가 아니다** — 추출 코드는 `fetch_atlas_schaefer_2018(n_rois=N)` 을 해상도 인자 없이 호출하고(`:230`), nilearn 0.13.1 기본값은 `resolution_mm=1` 이며 기본 저장 경로는 연결 폴더 밖 `~/nilearn_data` 다. 저장소에 Schaefer 1 mm 파일은 0건이다.

## 4. 정정 사항 (Errata)

이 세션이 앞서 산출한 문서·보고의 오류를 확정하고 정정한다. 각 항목은 재현 명령으로 확인했다.

**E1 — "AOMIC 원본 BOLD 0건"은 거짓.**
`timing_audit.md` §4 표, U1, U6, `missing_sources.json` M02, `gate_evidence.json` rev1이 모두 0건이라고 적었으나, 실제로는 9개가 존재한다:
`data/legacy_phase2/os_phase2_openneuro/openneuro/ds002785/2.0.0/uncompressed/sub-000{1,2}/func/*_task-restingstate_acq-mb3_bold.nii.gz` (PIOP1),
`.../ds002790/2.0.0/uncompressed/sub-000{1..5}/func/*_task-restingstate_acq-seq_bold.nii.gz` (PIOP2),
`data/legacy_phase2/os_ds002790_smoke/.../sub-000{1,2}/...` (중복본).
원인: 감사가 `data/aomic/` 범위와 일부 `find` 패턴에만 의존해 `data/legacy_phase2/` 아래 AOMIC 트리를 놓쳤다. **예방:** 부재 주장은 accession(ds002785/ds002790) 기준 저장소 전수 검색으로만 확정한다.

**E2 — "native TR의 acquisition 근거 0건"(U1)은 restingstate에 대해 거짓.**
§3.2 표가 정정값이다. U1은 **두 target task로 범위를 좁혀** 다시 쓴다. 계획서가 D1에서 인용한 "PIOP2 rest 240 volumes = 480초"는 이제 **로컬 원자료로 직접 확인**되었다.

**E3 — sub-0167의 confounds 결측 범위가 축소 서술되었다.**
`timing_audit.md` §3.1이 같은 문단에서 "4개 run"과 "emomatching만 없었다"를 동시에 적었다. 실제로는 **anticipation·emomatching·faces·gstroop 4개 run 전부**가 nuisance 회귀 없이 저장되었다(rest·WM만 confounds 보유). `source_runs.jsonl`은 `confounds_were_absent_at_extraction`을 정확히 4행에 붙여 올바르다.

**E4 — `workspace_snapshot.json`의 README 레코드가 손상되어 있었다.**
`{"path": "EADME.md", "current_sha256": "", "head_sha256": "e3b0c442…"}` — 경로 첫 글자 절단, 현재 해시 공백, HEAD 해시가 **빈 입력의 SHA256**이었다. 이는 `implementation_map.md` §4의 완료 판정 근거(1)을 무효화한다. 정정값: `current=71b96bec6b9115eb45b3d108b3c1077c75ee6e85fcce816f28d5392d7c9ef325`, `head=b9db81ac45e7255f32d921e2070bb6c9729142907a144de8470bb4aa46dabcb9`. 정정 이력은 해당 파일의 `corrections` 필드에 보존했다. 나머지 6개 파일의 해시는 전부 정확했다.

**E5 — `missing_sources.json`의 근거 문구가 사실과 다르다.**
M03의 `"no '*confounds*' file under data/"` → 실제로는 data/ 아래 2,149건이 있다(AOMIC 범위만 0건). M02의 `.nii.gz` 열거도 부정확하다(저장소 전체 `.nii(.gz)` 2,866개). **실질 주장(AOMIC 범위 0건)은 유지되나 근거 문구는 범위를 명시해야 한다.**

**E6 — PIOP2 보유 범위가 과소 기록되었다.**
`data/aomic/piop2` 기준으로는 sub-0001 1명이 맞으나, 저장소 전체로는 원본 rest NIfTI가 sub-0001~0005 **5명분**, 파생 timeseries가 sub-0001·0002 **2명분** 더 있다. G4 blocked 결론(emomatching 0건)은 그대로다.

**E7 — 같은 subject에 대해 충돌하는 세 번째 파생물이 존재한다.**
`data/legacy_phase2/os_ds002790_smoke/timeseries/100/ds002790_sub-000{1,2}/` 에 rest·wm·attention·language·motor 5개가 있고 **전부 (240, 100)** 이다. `data/aomic/piop2`의 workingmemory는 160이다. 즉 동일 cohort·동일 subject의 WM 길이가 240과 160으로 공존하며, 5개 task가 전부 정확히 240이라는 점에서 **이 트리의 task 라벨 매핑 자체를 신뢰할 수 없다**. "WM 160 vs 162" 논의는 이 세 번째 값을 고려해야 한다.

**E8 — acquisition entity "복원 불가" 주장이 과도하다.**
`source_runs.jsonl` 헤더가 "session/run/acquisition entities cannot be recovered"라고 적었으나, restingstate에 한해 원본 파일명이 `acq-mb3`(PIOP1) / `acq-seq`(PIOP2)를 직접 보존한다.

**E9 — release_id의 code-hash가 이미 stale이다.**
현재 작업 트리의 code-hash는 `8ad9c1e7dfa2`이며, `3c458d507e82`는 `scripts/make_redesign_protocol_figures.py` 생성 전 시점의 값이다. snapshot 자체는 그 시점 기준으로 정확하다. **release_id는 동결된 시점 식별자로만 쓰고, 현재 트리 지칭에 쓰지 않는다.**

## 5. 계획서·지침서 개정 필요 목록

main 성능 접근 전이므로 아래는 기술적 정정이며, 적용 시 버전과 사유를 남겨 재잠금한다.

| ID | 위치 | 현재 서술 | 개정 내용 |
|---|---|---|---|
| P1 | 프로토콜 §2 | "로컬 WM 160 대 문헌 162" | 로컬 PIOP1 WM은 204명 전원 162. 160은 PIOP2 값 → **cohort 간 차이**로 정정. 추가로 smoke 트리의 240(E7)을 명시. |
| P2 | 프로토콜 §2 / 문헌 검토 D1 | "D1에서 두 target TR은 2초이며 PIOP2 rest 240 volumes는 480초다" | D1 행에 TR·volume 숫자가 없다. PIOP2 rest 2초/480초는 **로컬 헤더로 확인**되었으므로 근거를 D1이 아니라 헤더 측정으로 바꾸고, 두 target의 2초는 **아직 근거 없음**으로 표기. |
| P3 | 프로토콜 §3.1 | 12초 guard + `[12,252)` | TR 0.75초 분기에서 emomatching(135 vol = 101.25초)은 이 구간을 지원하지 못한다. **target TR 확정 후에만 이 구간을 동결**한다는 조건을 명시. |
| P4 | 프로토콜 §4-1 / §8 | `group_id`, group 단위 재표집 | 로컬 metadata에 가족·중복 식별 열이 없다(U10). "모든 subject = 1인 group"으로 퇴화시킬 수밖에 없으며 그 가정의 검증 불가 범위를 명시. |
| P5 | 지침서 §2 `source_runs.jsonl` | `canonical_subject` | PIOP1/PIOP2가 동일 `sub-0001…` 네임스페이스를 쓴다(U17). **dataset prefix 필수화**. 없으면 WI-08의 subject independence 검사가 216건 위양성을 낸다. |
| P6 | 프로토콜 §3.2 / §3.3 | band-pass 0.008–0.1 Hz, residual DOF = `n_volumes − rank(design)` | 60초 window의 주파수 분해능은 1/60 ≈ 0.0167 Hz로 0.008 Hz 성분이 window 내에서 분해되지 않는다. residual DOF 정의에 filter로 잃는 DOF를 포함할지 결정하고 동결. |

## 6. 차단 항목 통합 목록

U1–U13은 `timing_audit.md` §9에서, U14 이후는 이번 점검에서 추가되었다. "확인 주체"가 *이 보고서*인 항목은 내가 직접 명령으로 재현했다.

| ID | 내용 | 해소 조건 | 차단 |
|---|---|---|---|
| U1′ | **두 target task**의 native TR 근거 0건 (rest는 §3.2로 해소) | target의 `*_bold.json` 또는 NIfTI `pixdim[4]` 확보 | G0 |
| U2 | 제거(non-steady-state) volume 기록 0건 | confounds의 `non_steady_state_outlier*` 열 또는 원본/파생 volume 수 동시 기록 | G0 |
| U3 | `derivative_start_sec` 미상 | U1′ + U2 | G0 |
| U4 | confounds 0건 → 24 motion·aCompCor 5·FD 구성, design rank, residual DOF, window별 FD 비율 **판정 불가** | 해당 run의 confounds TSV + aCompCor metadata JSON | G0·G1 |
| U5 | events 0건 → onset 원점 미확인 | events.tsv | G0 |
| U6′ | **두 target**의 BOLD 0건 → 재추출 입력 없음 (rest는 9개 존재) | fMRIPrep derivative BOLD 확보 | G0·G1 |
| U7 | 문헌 검토 D1에 TR·volume 숫자 없음 | Snoek 2021 해당 구절을 수치와 함께 D1에 고정 | G0 |
| U8 | 계획서 §2 "로컬 WM 160" 서술 오류 | P1 적용 | G0 |
| U9 | 기존 파생물의 atlas 신원 미확인(1 mm 파일 0건) | `~/nilearn_data` Schaefer 1 mm 해시 확보 또는 명시적 atlas 경로 재추출 | G0 |
| U10 | 가족/중복 metadata 0건 → `group_id` 구성 불가 | AOMIC 공식 문서의 subject 관계 정의 | G1·G4 |
| U11 | PIOP2 emomatching 0건 → paired target 불가 | PIOP2 emo+WM cohort 확보 | G4 |
| U12 | sub-0167의 **4개 run**이 nuisance 회귀 없이 저장, 196 후보에 포함 | U4 해소 후 전 run 재추출 | G0·G1 |
| U13 | `.venv/bin/python` broken symlink | 실행 호스트 확정 후 snapshot 고정 | G1 |
| **U14** | 이 실행 셸에 torch·scipy·sklearn·nilearn·nibabel·pytest **전부 부재**. 대체 인터프리터도 없음 | 실행 호스트 확정(§8) | G1·G2·G3 |
| **U15** | openneuro.org 및 S3 egress 차단(`000`). pypi·github은 도달 | egress 허용 또는 대체 반입 경로 | G0 확보 경로·G4 |
| **U16** | 이 셸 자원 4 core / 3 GB RAM / GPU 없음 vs §7의 768 fits | `resource_budget.md`를 실제 실행 호스트에서 pilot 측정으로 작성 | G1·G3 |
| **U17** | PIOP1/PIOP2가 동일 `sub-0001…` 네임스페이스. 문자 교집합 216, 전 열 일치 0/216, sex+age 동시 일치 6 | `canonical_subject` dataset prefix 필수화(P5). 실제 overlap은 공식 문서로만 판정 | G1·G4 |
| **U18** | `mobse/data/nuisance.py:21-48` 이 파일 부재 시 `None` 을 **조용히** 반환, `:51-66` 이 길이 불일치를 warning 후 trim/**zero-pad**. U12의 기계적 원인 | v2 `preprocess.py` 재사용 금지 또는 "누락=실패" adapter. T02가 이 동작을 직접 겨냥 | G0 재발방지·G2 |
| **U19** | `mobse/evaluate.py:107,132,140` 이 ETTh1을 **무조건** 평가·profiling | v2 `evaluate.py` classification-only 신규 작성 | G2 (T16) |
| **U20** | `mobse/evaluate.py:94` 가 checkpoint를 `glob` 최후 항목으로, `mobse/io.py:10-14` 가 **mtime 최신** 파일을 template/window로 채택 | v2 CLI에서 경로 필수 인자화 | G2·G3 (T15) |
| **U21** | `mobse/models/mobse.py:93-98` 이 PyG 설치 여부로 `DenseGCNConv` / 자체 `DenseGraphLayer` 를 선택 | v2 `models.py` 는 dense backend 1개 하드코딩, PyG import 제거 | G2 (T10) |
| **U22** | `mobse/profiling.py:28-31` 이 thop 부재 시 예외를 삼키고 `params × batch` 를 `flops` 로 반환 | FLOPs 미지원 시 `None`/`NA` | G5 (WI-09) |
| **U23** | `pyproject.toml:39-41` 의 `testpaths = ["tests"]`, `conftest.py` 부재 → `tests/v2/` 를 만들면 깨진 legacy 2건이 함께 수집되어 gate evidence 오염 | `tests/v2` 전용 testpath/마커 분리 또는 legacy 명시적 `--ignore` | G2 |
| **U24** | `mobse/data/__init__.py` 가 `etth1` 경유로 torch를 강제 import → 순수 numpy 모듈도 torch 없이 import 불가 | v2 패키지는 `__init__.py` 에서 lazy import | G1·G2 |
| **U25** | 60초 window 분해능 1/60 ≈ 0.0167 Hz vs highpass 0.008 Hz 부정합. residual DOF 정의가 filter DOF 미반영 | P6 적용, main 전 동결 | G1·G3 |
| **U26** | AOMIC derivative 다운로드 용량 미산정(U15로 조회 불가). 가용 1,022 GB / `data/` 이미 187 GB | U15 해소 후 실측 산정 또는 streaming 추출 설계 | G0·G1 |
| **U27** | smoke 트리의 PIOP2 파생물이 5개 task 전부 240 length → **task 라벨 매핑 신뢰 불가**(E7) | 해당 트리를 주분석 후보에서 명시적 제외하거나 라벨 근거 확보 | G0 |

## 7. 후속 단계 산술 (조건부)

### 7.1 mean FD 기준 상한 추정 — **QC 통과 N이 아니다**

manifest에 이미 저장된 run 단위 `mean_fd` 에 계획서 §3.3의 ≤0.2 mm 기준만 적용한 값이다. window별 FD>0.5 비율, residual DOF, nonfinite/constant ROI 검사는 **전혀 반영되지 않았다**. 또 이 `mean_fd` 는 TR 0.75초 전역 적용 하의 추출 산물이다. **실제 QC 통과 N은 반드시 이보다 작거나 같다.**

| task | manifest 레코드(100-node) | 중앙값 mean FD | ≤0.2 통과 subject |
|---|---:|---:|---:|
| emomatching | 207 (FD 보유 206) | 0.1076 | **191** |
| workingmemory | 204 | 0.1088 | **180** |
| restingstate | 211 | 0.1010 | **206** |

restingstate 레코드가 211인 것은 `sub-0001` 이 pilot manifest(`…20260415_145920.json`)와 본 manifest에 **중복 기록**되었기 때문이다. 고유 subject는 210이다.

- 두 target 모두 통과: **172** (상한 추정)
- 두 target + rest 모두 통과: **166** (상한 추정) ← 계획서가 요구하는 complete-case 기준

### 7.2 분할 산술 (N = 166 조건부)

pilot = min(32, ⌊0.2 × 166⌋) = min(32, 33) = **32** → main pool **134**.
outer 5-fold test = 27/27/27/27/26, outer train 107, inner 3-fold val 36/36/35, inner train 71.
WI-07 완료기준 검산: window prediction rows = 134 × 2 × 4 × 3 × 4 = **12,864**, run prediction rows = 134 × 2 × 4 cells = **1,072**, primary checkpoint = 60.

정밀도 주의: subject당 `b_i ∈ {0, 0.5, 1}` 이므로 N=134에서 1단위 차이는 0.5/134 ≈ 0.0037 BA다. δ=0.02는 약 **5.4명분의 discordance**에 해당한다. 정식 평가는 WI-03 `precision_scenarios.md`의 몫이며 여기서는 fold 산술만 확인했다.

### 7.3 계산 예산 검산 — 5/5 칸 정확

480 = 8×3×4×5, 60 = 4×5×3, 120 = 4×2×5×3, 96 = 8×3×4, 12 = 4×3. **총 768 fits** (표에 합계 미기재).

## 8. 실행 환경 제약 — **이 세션 한정**

아래는 이 세션의 원격 실행 셸(격리 Linux VM)에 대한 사실이며, **사용자의 macOS 호스트에는 적용되지 않을 수 있다**. `.venv/lib/python3.11/site-packages` 에는 torch 2.10.0, torch_geometric 2.7.0, scikit-learn 1.8.0, nilearn 0.13.1, nibabel 5.4.2, pytest 9.0.2의 dist-info가 있으나 **이 셸에서는 실행 검증이 불가능하다**(해당 인터프리터가 가리키는 `/opt/homebrew` 경로가 이 VM에 없음).

| 항목 | 값 |
|---|---|
| Python | system `python3` 3.10.12 |
| 사용 가능 | numpy 2.2.6, pandas 2.3.3, matplotlib 3.10.9, seaborn 0.13.2 |
| 부재 | torch, scipy, scikit-learn, nilearn, nibabel, pytest |
| egress | openneuro.org `000`, s3.amazonaws.com/openneuro.org `000`, pypi.org `200`, github.com `200` |
| 자원 | 4 core, RAM 3 GB, GPU 없음, 디스크 여유 1,022 GB / 1.9 TB |

따라서 이 셸에서 NIfTI는 `gzip`+`struct` 직접 파싱으로 처리했고, figure는 system matplotlib으로 렌더링했다(한글 글리프 부재로 figure 내부 텍스트는 영문). **WI-04 이후의 실제 구현·학습은 이 셸에서 수행할 수 없다.**

## 9. G0가 막혀 있어도 병렬 진행 가능한 작업

**P0 — 전제 확정**
1. 실행 호스트를 확정하고(로컬 macOS vs 별도 서버) 그곳에서 `python -VV`, 주요 패키지 버전, CPU/GPU/RAM을 기록해 `workspace_snapshot.json` 에 고정. 이 device 셸이 실행 호스트가 아님을 명시(U13·U14·U16).
2. OpenNeuro/S3 반입 경로 확정(U15). 이것 없이는 U6′·U11의 "파일 확보 계획"을 승인해도 실행할 수 없다.

**P1 — 원자료 0건으로도 100% 가능**
3. `mobse/v2/manifests.py` 스키마 + `configs/redesign_v1/` config schema 확정. `canonical_subject` dataset prefix 강제(P5), `na` 빈값 규약을 기존 `source_runs.jsonl` 과 일치시킴.
4. `mobse/v2/splits.py` 전체 구현 + 결정론 테스트(T03·T14). 계획서 §4-4 알고리즘은 subject ID 리스트만 있으면 numpy로 완성 가능.
5. `mobse/v2/statistics.py` (paired bootstrap, seed 9001, 10,000회, 1.25–98.75 percentile) + T13·T14.
6. `mobse/v2/evaluate.py` 의 집계 로직(window→run→subject→BA→contrast). **classification-only 신규 작성**(U19).

**P2 — 라이브러리 확보 후**
7. `features.py` + `templates.py` + T04·T05·T07 (sklearn 필요, 합성 fixture로 충분).
8. `models.py` (A–D) + T06·T08·T09·T10 (torch 필요, PyG import 제거 — U21).
9. `train.py` + `cli.py` (glob fallback 금지 — U20).

**P3 — 문서 작업 (도구 무관)**
10. §5의 P1–P6을 계획서·지침서에 반영하고 버전·사유 기록.
11. U18–U22를 지침서 §5 "재사용 지도"에 **줄 번호와 함께** 반영 — 재사용 금지 근거를 서술이 아니라 코드 위치로 고정.
12. U23 해소: `tests/v2` 수집 경계 설계.

**주의:** P1–P2 산출물은 pilot 실데이터 없이는 "구현 완료"이지 **G2 통과가 아니다**. WI-06 완료기준은 T01–T16 **및** pilot end-to-end이며 후자는 G0 해소를 요구한다.

## 10. 검증하지 못한 경계

| 항목 | 이유 |
|---|---|
| 두 target task의 native TR | 해당 task의 원본·sidecar가 로컬에 없다. 로컬 원본은 **restingstate만** 존재. |
| `TaskName` / `SliceTiming` / `NumberOfVolumes` | `*_bold.json` 저장소 전체 0건. 원본 9개의 NIfTI `slice_duration` 도 전부 0.0이라 slice timing 복원 불가. |
| 제거 volume 수 | 기록 매체 자체가 없다(추출 코드에 trimming 없음, manifest에 필드 없음, confounds 없음). |
| confounds 열 구성 / design rank / residual DOF / window별 FD 비율 | AOMIC confounds 0건. |
| 기존 `.npy` 를 만든 atlas 신원 | Schaefer 1 mm 파일 0건, `~/nilearn_data` 는 마운트 밖. |
| PIOP1–PIOP2 실제 subject overlap | 로컬 metadata에 연결 키 없음. ID가 겹치지만 동일인이 아님만 확인(U17). |
| 가족/쌍둥이 관계 유무 | participants.tsv 전 열에 해당 정보 없음. "관계가 없다"가 아니라 **"확인할 수단이 없다"**. |
| 저장된 `mean_fd` 값의 타당성 | 어떤 confounds 열에서 어떻게 산출됐는지 검증할 원자료가 없다. §7.1은 상한 추정이다. |
| macOS 호스트의 패키지·자원 | 이 셸에서 조회 불가(§8). dist-info는 기록일 뿐 실행 검증이 아니다. |
| AOMIC derivative 다운로드 용량 | U15로 openneuro/S3 조회 불가. |
| 문헌 원문 대비 D1 인용(U7) | 원문 미보유. literature_review의 D1 행에 수치가 없다는 점만 확인. |

## 11. 변경 기록

| version | changed_rule | reason | data/outcome_access_scope | affected_artifacts | supersedes |
|---|---|---|---|---|---|
| gate_evidence rev2 | G0 검사 항목의 BOLD·native TR 판정 | E1·E2 확정 | metadata·provenance only (모델 결과 미접근) | `gate_evidence.json` | rev1 (`cee5718ffbc2…`) |
| workspace_snapshot corrections[0] | `git.modified_tracked_files[0]` | E4 레코드 손상 | 동일 | `provenance/workspace_snapshot.json` | 손상 레코드 |
| figures RD3 | panel b 를 "TR 두 가정" → "측정값 / 미확정 분기" | E2 반영 | 동일 | `fig_rd3_timing_model.*`, manifest, caption | 이전 렌더 |
| figures RD4 | panel a 에 raw BOLD 9건 행 추가, blocker 목록 갱신 | E1·E6·U10·U17 반영 | 동일 | `fig_rd4_g0_audit_status.*`, manifest, caption | 이전 렌더 |

모델 성능 결과는 이 시점까지 존재하지 않으며 접근한 바 없다. 따라서 위 변경은 전부 **main outcome 접근 전 기술적 수정**이며 exploratory 분리 대상이 아니다.

## 12. 다음 단계

G0 해소의 선행 조건은 순서대로 **(1) 실행 호스트 확정, (2) OpenNeuro/S3 반입 경로 확보(U15), (3) 두 target의 BOLD·sidecar·confounds·events 확보 계획 승인 — 무엇을·몇 건·어디서**다. 그 전에는 WI-02 재추출을 시작하지 않는다. 그동안 §9의 P1·P3 작업은 병렬로 진행 가능하다.

---

# 부록 A — Wave 1 결과 (h197, 2026-09-17)

실행 호스트 h197(`bmcws`)에서 메타데이터 6,055 파일(1.1 GiB, 실패 0)을 확보하고 감사했다. 이 부록은 본문 §1–§12를 갱신하며, 충돌 시 부록을 적용한다.

## A.1 native TR — 전부 확정

raw sidecar의 `RepetitionTime`을 run 단위로 읽었다. 각 dataset×task 조합 내 **TR·volume 분산 0**.

| dataset / task | runs | volumes | **native TR** | 지속시간 | `[12,252)` |
|---|---:|---:|---:|---:|:--:|
| PIOP1 emomatching | 208 | 135 | **2.00 s** | 270 s | ✓ |
| PIOP1 workingmemory | 207 | 162 | **2.00 s** | 324 s | ✓ |
| PIOP1 restingstate | 210 | 480 | **0.75 s** | 360 s | ✓ |
| PIOP2 emomatching | 222 | 135 | **2.00 s** | 270 s | ✓ |
| PIOP2 workingmemory | 224 | 160 | **2.00 s** | 320 s | ✓ |
| PIOP2 restingstate | 224 | 240 | **2.00 s** | 480 s | ✓ |

세 가지가 확정된다.

1. **계획서 §2의 "두 target TR은 2초"가 원자료로 확인되었다.** 본문 §3.2가 두 분기로 남겨 두었던 항목이 해소된다. P2(D1 근거 교체)는 여전히 필요하지만, 이제 근거는 문헌이 아니라 sidecar 실측이다.
2. **`[12,252)` window 설계는 개정 없이 유지된다.** 여섯 조합 모두 252초를 충족하므로 본문 §5의 P3는 철회한다. emomatching의 여유는 18초로 가장 빠듯하다.
3. **기존 추출의 TR 오적용 범위가 확정되었다.** 모든 run에 0.75초를 적용했고, PIOP1 restingstate에서만 우연히 옳다. 두 primary target은 **2.67배 잘못된 rate**로 필터링되었다 — 기존 파생물의 주분석 재사용 불가가 조건부가 아니라 확정이다.

## A.2 PIOP2 외부 코호트 존재 — U11 해소

PIOP2가 emomatching 222 / workingmemory 224 / restingstate 224 run을 보유한다. 로컬 0건은 **데이터셋에 없어서가 아니라 받은 적이 없어서**였다. 본문 §1의 G4 blocked 사유와 §6의 U11이 해소된다. 외부 검증 범위 축소(internal-only)는 더 이상 필요하지 않다.

## A.3 nuisance·events — 구조적으로 성립

- **24 motion / aCompCor 5 / FD**: 1,295 run 중 motion 미달 0, FD 열 부재 0. aCompCor 5개 미만이 **4 run**이며, 이는 gate 차단이 아니라 `exclusions.jsonl`로 넘길 run 단위 제외 사유다(계획서 §3.2가 대체를 금지한다).
- **events**: task run 861건 전부 보유. `events_absent` 434건은 restingstate run 총수(210+224)와 **정확히 일치**하므로 결함이 아니다.
- **non_steady_state**: fMRIPrep은 해당 volume을 outlier regressor로 **표시만 하고 제거하지 않는다**. 따라서 confounds 행 수 = 보관본 전체 길이이고, derivative 시작점 offset 문제는 발생하지 않는다. 다만 **보관 전에 dummy가 제거되었는지는 이 파일들로 판정할 수 없다**(U3 잔존).

## A.4 실행 환경 확정 — 본문 §8 대체

h197에 전용 venv(`venv-mobse-v2`, Python 3.11)를 구축하고 lock을 남겼다.

| 항목 | 값 |
|---|---|
| torch | 2.10.0+cu128, `cuda_available=True`, device 1개, CUDA 12.8 |
| 핀 8종 | numpy 2.4.3 / scipy 1.17.1 / scikit-learn 1.8.0 / pandas 3.0.1 / nibabel 5.4.2 / nilearn 0.13.1 / matplotlib 3.10.9 / pytest 9.0.2 |
| lock | `environment_lock_h197.txt` (56 packages) |
| guard | `torch_geometric` 부재 확인 — U21 |
| egress | OpenNeuro·S3 도달 |

본문 §8의 제약(torch 부재, egress 차단, 4 core/3 GB/GPU 없음)은 **이 세션의 원격 셸에만 해당**하며 프로젝트 제약이 아니었다. U13·U14·U15·U16이 h197 작업으로 해소된다. GPU 1장 확보로 §7.3의 768 fits가 실행 가능 범위에 들어온다.

## A.5 정정 — E10: 감사 스크립트의 판정 로직 오류

`02_wave1_audit.py`의 `U5_events_origin`이 **restingstate를 포함한 모든 run**에 events를 요구했다. rest에는 events가 없는 것이 정상이므로 434건이 결함으로 집계되고 U5가 영구히 `still_blocked`로 남았다. `U4_nuisance_constructible`도 전체 `all()`이라 4 run 때문에 전체가 차단으로 표시되었다.

**수정:** events는 `task != "restingstate"`인 run에만 요구하고, run 단위 결함은 `run_level_exclusion_candidates`로 분리해 gate 판정과 구분했다. 정상·결함 fixture 양쪽으로 회귀 확인했다 — rest의 events 부재는 더 이상 결함으로 세지 않고, task run의 events 부재는 여전히 `still_blocked`를 유발한다.

**근본 원인:** 판정 기준을 "모든 run"으로 일괄 설정하고 task 종류별 적용 범위를 구분하지 않았다. **예방:** 판정 함수마다 적용 모집단을 명시적 변수(`event_bearing`, `targets`)로 분리하고, 그 수를 `wave1_summary.json`의 `events_scope_note`에 기록해 판정 근거가 출력에 남게 했다.

## A.6 갱신된 차단 항목

| 상태 | 항목 |
|---|---|
| **해소** | U1′(target TR), U2(제거 volume 기록), U4(구조적 구성 가능), U5(events), U11(PIOP2 코호트), U13·U14·U15·U16(실행 호스트) |
| **재추출로 소멸** | U9(atlas 신원 — 고정 atlas로 재추출), U12(sub-0167 — 재추출) |
| **완화** | U17(ID 네임스페이스 — `canonical_subject`에 dataset prefix 적용, `wave1_runs.jsonl`에 반영) |
| **잔존** | U3(보관 전 dummy 제거 여부 판정 불가), U6′(target BOLD — Wave 2), U10(가족/중복 metadata 부재), U26(Wave 2 용량 미산정), U18–U23·U25(코드 결함과 설계 결정 — 구현 단계) |
| **신규** | 4 run이 aCompCor 5개 미만 → run 단위 제외 후보 |

## A.7 본문 대비 철회·변경

| 본문 위치 | 변경 |
|---|---|
| §1 G4 blocked | **철회.** PIOP2 코호트 존재(A.2) |
| §3.2 결론 2 (두 분기) | **확정으로 대체.** target TR = 2.0초 |
| §5 P3 (`[12,252)` 동결 조건) | **철회.** 여섯 조합 모두 성립 |
| §5 P2 | 유지하되 근거를 D1 인용 → sidecar 실측으로 교체 |
| §6 U11 | 해소 |
| §8 실행 환경 제약 | A.4로 대체 |
| §9 P0 1·2 (호스트 확정, egress) | 완료 |
| §10 "두 target의 native TR" | 해소. "보관 전 dummy 제거 여부"는 잔존 |

## A.8 다음

1. h197의 `wave1_audit/` 3종과 `h197_environment.json`·`environment_lock_h197.txt`를 `provenance/h197_wave1/`로 반입 → `source_runs.jsonl` 갱신.
2. `03b_wave2_size_probe.py`로 BOLD 용량 실측(U26) 후 Wave 2 착수 여부 결정.
3. Wave 2와 병행 가능: `mobse/v2/manifests.py` 스키마(dataset prefix 강제), `splits.py`+T03·T14, `statistics.py`+T13·T14 — 모두 원자료 없이 완성 가능.

---

# 부록 B — h197 직접 실행 결과 (2026-09-17)

Mac의 Desktop Commander를 통해 h197에 SSH로 직접 접속해 실행했다. 이전까지는 사용자가 터미널에서 수동 실행했으나, 이후 작업은 이 경로로 수행한다.

## B.1 감사 재실행 — 5/5 resolved

`02_wave1_audit.py`의 판정 로직 수정(부록 A.5, E10) 후 재실행 결과다.

| 항목 | 판정 |
|---|---|
| `U1_native_tr_targets` | resolved |
| `U2_discarded_volumes` | resolved |
| `U4_nuisance_constructible` | resolved |
| `U5_events_origin` | resolved |
| `window_12_252_supported_for_targets` | resolved |

`clean 1291 / 1295`. 남은 4건은 aCompCor 5개 미만으로, **run 단위 제외 후보**다:

```
ds002785/sub-0029/na/workingmemory/na/seq
ds002785/sub-0134/na/workingmemory/na/seq
ds002790/sub-0101/na/workingmemory/na/seq
ds002790/sub-0226/na/emomatching/na/seq
```

task run 861건 전부 events 보유, FD 열 부재 0, motion 24열 미달 0, residual DOF 상한 최솟값 98(PIOP1 emomatching)로 전 run이 `>30`을 충족한다.

## B.2 run 단위 mean FD — 실제 confounds 기반

`05_run_level_fd.py`로 1,295 run의 `framewise_displacement`를 직접 계산했다(오류 0). 첫 행의 구조적 결측은 전 run에서 정확히 1개이며 분모에서 제외했다.

| dataset / task | runs | 중앙값 mean FD | ≤0.2 통과 |
|---|---:|---:|---:|
| PIOP1 emomatching | 208 | 0.1079 | 192 |
| PIOP1 workingmemory | 207 | 0.1090 | 180 |
| PIOP1 restingstate | 210 | 0.1009 | 206 |
| PIOP2 emomatching | 222 | 0.1145 | 207 |
| PIOP2 workingmemory | 224 | 0.1004 | 218 |
| PIOP2 restingstate | 224 | 0.1188 | 209 |

**complete-case 상한** (run 단위 mean FD ≤0.2 + aCompCor ≥5만 적용):

| | emo∩WM | emo∩WM∩rest |
|---|---:|---:|
| PIOP1 (primary) | 171 | **164** |
| PIOP2 (external) | 202 | **196** |

**이것은 QC 통과 N이 아니다.** 고정 window별 FD>0.5 비율 ≤10%, nonfinite/constant ROI, design rank 실측이 아직 적용되지 않았다(WI-02). 최종 N은 이보다 작거나 같다.

본문 §7.1의 상한 추정 166은 잘못된 TR로 추출된 manifest의 `mean_fd`에 기반했으나, **FD는 frame 간 변위라 TR에 의존하지 않으므로 그 값 자체는 유효했다** — PIOP1 emomatching 중앙값이 0.1076(구) 대 0.1079(신)로 일치한다. 차이 166 → 164는 aCompCor 제외 2건과 cohort 정의 차이에서 온다.

### 갱신된 분할 산술 (N = 164)

pilot = min(32, ⌊0.2 × 164⌋) = **32** → main pool **132**.
outer 5-fold test = 27/27/26/26/26, outer train ≈ 105–106, inner 3-fold val ≈ 35.
WI-07 완료기준: window prediction rows = 132 × 2 × 4 × 3 × 4 = **12,672**, run prediction rows = 132 × 2 × 4 cells = **1,056**, primary checkpoint = 60.

δ=0.02는 N=132에서 1단위 차이 0.5/132 ≈ 0.0038이므로 약 **5.3명분의 discordance**에 해당한다.

## B.3 Wave 2 용량 — U26 해소

목록만으로 산정했다(다운로드 없음). `space-MNI152NLin2009cAsym` preproc BOLD 기준.

| dataset | restingstate | emomatching | workingmemory | 합계 |
|---|---:|---:|---:|---:|
| PIOP1 | 74.3 GiB | 21.3 GiB | 25.4 GiB | **121.0 GiB** |
| PIOP2 | 39.9 GiB | 22.2 GiB | 26.6 GiB | **88.7 GiB** |
| | | | | **209.7 GiB** |

h197 `/mnt/data` 여유 **3.0 TiB / 5.5 TiB**. **streaming 추출은 불필요**하며 전량 다운로드가 여유 있게 들어간다. 기존 `stream_aomic_extract.py`의 streaming 구조를 답습할 이유가 없어졌고, 이는 §5의 코드 결함 목록을 우회할 근거가 된다 — 새 추출기는 원본을 보존한 채 검증 가능한 형태로 작성한다.

## B.4 실행 호스트 사양

| 항목 | 값 |
|---|---|
| host | bmcws (Ubuntu 20.04) |
| GPU | **NVIDIA GeForce RTX 3090 Ti, 24,564 MiB** |
| torch | 2.10.0+cu128, CUDA 12.8, device 1 |
| 디스크 | `/mnt/data` 5.5 TiB (여유 3.0 TiB) |

GPU 1장 기준으로 §7.3의 768 fits 자원 계획을 WI-03에서 pilot 실측으로 작성한다.

## B.5 반입된 산출물

`provenance/h197_wave1/` — `wave1_runs.jsonl`(1,295행), `wave1_summary.json`, `wave1_files.sha256`(6,058행), `run_level_fd.json`, `wave1_fetch_report.json`, `wave2_size_probe.json`, `h197_environment.json`, `environment_lock_h197.txt`. 전체 SHA256은 `gate_evidence.json` rev5의 `h197_imported_artifacts`에 있다. **BOLD 본체는 h197에 두고 반입하지 않는다.**

## B.6 남은 것

| ID | 내용 | 비고 |
|---|---|---|
| U3 | 보관 전 dummy 제거 여부 | 이 파일들로 **판정 불가** — 제한으로 명시하고 진행 |
| U6′ | target BOLD | Wave 2 (209.7 GiB, 실행 가능) |
| U10 | 가족/중복 metadata 부재 | `group_id`를 subject 단위로 퇴화시키고 그 가정의 검증 불가 범위를 명시 |
| — | U18–U23·U25 | 코드 결함·설계 결정. 구현 단계에서 처리 |

---

# 부록 C — v2 모듈 착수 (splits, statistics)

Wave 2 다운로드와 병행해, **원자료 없이 완성 가능한** 두 모듈을 구현하고 검증했다. 지침서 §9의 P1 항목 4·5에 해당한다.

## C.1 `mobse/v2/__init__.py`

무거운 의존성을 import 하지 않는다. 기존 `mobse/data/__init__.py`가 `etth1` 경유로 torch를 강제 import 해 numpy만 필요한 모듈까지 torch 없이는 쓸 수 없게 만든 문제(U24)를 되풀이하지 않기 위함이다. 두 모듈 모두 **numpy만** 필요하다.

## C.2 `mobse/v2/splits.py` — 프로토콜 §4

| 규칙 | 구현 |
|---|---|
| `group_id` | `make_groups()`가 subject→group 매핑 또는 퇴화형(subject 1명 = group 1개)을 모두 받는다. U10 상황에서도 동작하며 어떤 가정을 썼는지 manifest의 `grouping_assumption`에 남는다 |
| subject key | dataset prefix를 전제로 한다 (U17) |
| pilot | `min(32, ⌊0.2N⌋)`, seed 20260917, **목표를 넘기지 않는 전체 group만** 배정. 미달 시 사유를 기록 |
| fold 배정 | PCG64 tie-break 순서 → 인원수 내림차순(동률은 그 순서) → 현재 subject 수가 최소인 fold, 동률은 작은 index |
| seeds | outer 20260918, inner `20261000+fold`, external 20262000 |
| 자동 축소 금지 | group 수 < fold 수이면 `SplitError`. 프로토콜 §4-3 |
| 경계 검증 | `verify_disjoint()`가 pilot/outer test/outer train/inner val/inner train의 모든 쌍을 확인 |
| fit scope | `assert_fit_scope()`가 허용 집합 밖 subject를 거부 (T03) |
| manifest | `folds.json` payload + 내용의 SHA256(`split_hash`) |

## C.3 `mobse/v2/statistics.py` — 프로토콜 §8

| 규칙 | 구현 |
|---|---|
| run probability | **seed 평균 → window 평균** 순서 고정. 모양이 (4,3)이 아니거나 비유한·범위 밖이면 실패 |
| threshold | 0.5, **동일값은 class 1** |
| `b_i` | `(I[emo] + I[WM]) / 2`, `BA = mean_i(b_i)` |
| 주 contrast | 같은 subject의 b 차이. subject 집합이 다르면 실패 |
| bootstrap | seed 9001, 10,000회, **group 단위 복원추출**. 반복 추출된 subject는 각 인스턴스가 동일 가중 |
| 동일 재표집 | `bootstrap_indices()`가 index를 먼저 만들고 모든 cell이 공유 — 이래야 paired 구조가 유지된다 |
| CI | 주 contrast 97.5%(1.25–98.75)로 family-wise 95% 보수 제어, 보조 95%(2.5–97.5) |
| 통계 단위 | 결과 객체에 `n_subjects`·`n_groups`·`statistical_unit`을 싣는다. **window·seed·fold 수를 N으로 세지 않는다** |
| 판정 | `interpret()`가 §8의 네 규칙을 문자열로. 비유의를 효과 없음·동등성으로 바꾸지 않는다는 문구를 포함 |

## C.4 검증 — 35 tests passed

h197의 `venv-mobse-v2`(pytest 9.0.2)에서 실행했다.

```
PYTHONPATH=. pytest tests/v2 -q
35 passed in 0.32s
```

`tests/v2/test_splits.py` — T03과 분할 결정성:
- group이 fold를 가로지르지 않음, 가족 fixture로 outer test 경계 확인
- 모든 main subject가 정확히 하나의 outer test fold에 속함
- pilot·outer test·inner val·inner train의 모든 쌍이 서로소
- 금지된 subject를 fit에 넣으면 `SplitError` (T03 핵심)
- 같은 seed 재현성, 다른 seed는 동률 순서만 변경
- group 수 부족 시 자동 축소 대신 실패
- `split_hash`가 내용에 묶임 (N 164 vs 163이면 달라짐)

`tests/v2/test_statistics.py` — T13과 T14:
- run probability 손계산(window 평균 0.2/0.5/0.8/0.9 → 0.6), 불완전 입력 거부
- threshold 동일값 → class 1
- 2 subject × 2 task × 4 window × 3 seed 전 과정 손계산 → BA 0.75
- **group의 두 subject가 항상 같은 횟수로 뽑힘** (200회 draw 전수 확인, T14 핵심)
- 같은 index를 모든 cell에 적용하면 상수 차이가 상수로 유지됨
- `n_subjects`/`n_groups`가 window·seed 수와 무관
- family-wise CI가 nominal보다 넓음
- group 매핑 누락·빈 입력은 조용히 넘어가지 않고 실패

## C.5 실제 N으로 확인한 분할

`build_folds()`에 N=164(부록 B.2의 complete-case 상한)를 넣은 결과가 보고서 예측과 정확히 일치한다.

```
N 164  pilot 32  main 132
outer test  [27, 27, 26, 26, 26]
outer train [105, 105, 106, 106, 106]
inner val (fold 0) [35, 35, 35]
expected window rows 12,672   run rows 1,056   checkpoints 60
```

## C.6 테스트 수집 경계 (U23)

`pyproject.toml`의 `testpaths = ["tests"]` 때문에 인자 없이 `pytest`를 돌리면 `mobse.data.hcp` 부재로 깨지는 legacy 2건이 함께 수집된다. **경로를 명시해 `pytest tests/v2`로 돌리면** `testpaths`가 무시되어 legacy는 수집되지 않는다. `tests/v2/README.md`에 근거와 함께 기록했고, `pyproject.toml`은 수정하지 않았다(tracked 파일 보존).

## C.7 남은 v2 모듈

`manifests.py`(스키마, dataset prefix 강제), `features.py`+`templates.py`(sklearn 필요, 합성 fixture로 검증 가능), `models.py`(torch 필요, PyG import 제거 — U21), `preprocess.py`·`train.py`·`cli.py`(glob fallback 금지 — U20). `evaluate.py`의 집계 로직은 `statistics.py`에 이미 들어갔고, 나머지는 classification-only로 신규 작성한다(U19).

---

# 부록 D — v2 구현 전체와 수용 시험 T01–T16 (2026-09-17, Wave 2 진행 중)

부록 C 는 `splits.py`·`statistics.py` 두 모듈 시점의 기록이다. 그 뒤 나머지
9개 모듈을 모두 작성했고, 지침서 §6 의 수용 시험 T01–T16 을 전부 붙였다.
이 부록의 모든 수치는 `provenance/_gen_v2_inventory.py` 가 생성한
`provenance/v2_inventory.json` 에서 인용한다 — 손으로 옮겨 적지 않는다.

## D.1 모듈 목록 (11개, 2,439 줄)

| 모듈 | 줄 | sha256(앞 12) | 역할 |
|---|---:|---|---|
| `mobse/v2/__init__.py` | 13 | `c884876e4717` | 패키지 진입점 — 무거운 import 없음 (U24 회피) |
| `mobse/v2/preprocess.py` | 259 | `57a99f253fb1` | 원 acquisition clock·[12,252) 고정 창·FD QC |
| `mobse/v2/manifests.py` | 343 | `8f6701764f58` | run key·산출물 스키마·해시 — U17/U20 |
| `mobse/v2/splits.py` | 332 | `8291021bcad5` | grouped nested CV 분할 — 프로토콜 §4 |
| `mobse/v2/features.py` | 191 | `c11a9f2797c2` | Ledoit–Wolf FC → Fisher-z → frozen scaler/PCA |
| `mobse/v2/templates.py` | 254 | `56fe80d22ad1` | K-means bank·희소화·정규화·joint ROI permutation |
| `mobse/v2/models.py` | 272 | `8220f8c762a2` | ROI encoder·gate·dense graph layer — PyG 미사용 (U21) |
| `mobse/v2/train.py` | 247 | `2eb6f801b0ab` | grid·config 선택·epoch 예산·test 누출 차단 |
| `mobse/v2/evaluate.py` | 215 | `a11a324f8516` | classification-only 평가·release 완결성 검증 |
| `mobse/v2/statistics.py` | 193 | `99028ff3042b` | 종점 집계·paired group bootstrap — 프로토콜 §8 |
| `mobse/v2/cli.py` | 120 | `ffd022bebdec` | 경로 명시 필수 CLI (glob fallback 없음) |

`mobse/v2/__init__.py` 는 여전히 무거운 의존성을 import 하지 않는다. 기존
`mobse/data/__init__.py` 가 `etth1` 경유로 torch 를 강제 import 해 numpy 만
필요한 모듈까지 막던 문제(U24)를 되풀이하지 않기 위해서다.

## D.2 시험 파일 (11개, 176개 함수)

| 파일 | 함수 | 담당 T-ID | sha256(앞 12) |
|---|---:|---|---|
| `test_acceptance_coverage.py` | 3 | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16 | `5068bef17cc4` |
| `test_evaluate_cli.py` | 19 | T15, T16 | `cb8a6fe55a51` |
| `test_features.py` | 15 | T04, T07 | `64f2c436fae1` |
| `test_import_closure.py` | 5 | — | `a6c9ff480644` |
| `test_manifests.py` | 22 | T02, T11, T15 | `0db9087c335a` |
| `test_models.py` | 21 | T06, T08, T09, T10, T16 | `7b3456a4a8a9` |
| `test_preprocess.py` | 19 | T01 | `36877eaa10a9` |
| `test_splits.py` | 19 | T03 | `4c6e87633a2b` |
| `test_statistics.py` | 16 | T13, T14 | `ce543dce6063` |
| `test_templates.py` | 20 | T05 | `0a77612932c7` |
| `test_train.py` | 17 | T12 | `bef85a980fa8` |

h197 venv 실행 결과: **178 passed, 2 warnings in 7.78s**
(`PYTHONPATH=. python -m pytest tests/v2 -q -p no:cacheprovider`).
함수 수 176 과 수집 수 178 의 차이는 parametrize 확장분이다.

## D.3 수용 시험 커버리지 T01–T16

| 수용 시험 | 담당 파일 | 상태 |
|---|---|---|
| T01 Timing | `test_preprocess.py` | 통과 |
| T02 Provenance | `test_manifests.py` | 통과 |
| T03 Subject isolation | `test_splits.py` | 통과 |
| T04 Frozen transform | `test_features.py` | 통과 |
| T05 Graph/null | `test_templates.py` | 통과 |
| T06 ROI alignment | `test_models.py` | 통과 |
| T07 FC information | `test_features.py` | 통과 |
| T08 Routing | `test_models.py` | 통과 |
| T09 Mixture | `test_models.py` | 통과 |
| T10 Backend/checkpoint | `test_models.py` | 통과 |
| T11 Target | `test_manifests.py` | 통과 |
| T12 Selection boundary | `test_train.py` | 통과 |
| T13 Endpoint | `test_statistics.py` | 통과 |
| T14 Statistical unit | `test_statistics.py` | 통과 |
| T15 Integrity | `test_evaluate_cli.py`, `test_manifests.py` | 통과 |
| T16 Scope | `test_evaluate_cli.py`, `test_models.py` | 통과 |

커버리지는 문서 주장이 아니라 시험으로 강제한다.
`tests/v2/test_acceptance_coverage.py` 가 (1) 16개 T-ID 가 모두 `tests/v2` 안에서
참조되는지, (2) 지정한 담당 파일이 실제로 그 ID 를 참조하는지, (3) 지침서 §6 표가
정의하는 T-ID 집합이 여전히 16개인지를 검사한다. 시험을 지우거나 이름만 바꿔 놓고
"통과"로 보고하는 경로를 막는 것이 목적이다. 이 검사기 자신은 모든 T-ID 를
나열하므로 귀속 계산에서 제외했다.

## D.4 기존 suite 와 신규 suite — 측정된 실패 표

지침서 §4 는 기존 failure 와 신규 failure 를 **별도 표**로 둘 것을 요구한다.
추론이 아니라 실제 실행 결과다.

### D.4.1 기존(legacy) suite — `pytest tests --ignore=tests/v2`

| 항목 | 결과 | 원인 | 분류 |
|---|---|---|---|
| `tests/test_hcp_templates.py` | collection ERROR | `from mobse.data.hcp import …` — 해당 모듈 없음 | **기존 결함** |
| `tests/test_subject_split.py` | collection ERROR | 동일 | **기존 결함** |
| 나머지 22건 | 22 passed | — | — |

두 collection error 의 근거는 커밋 `52c0f7e`(2026-04-01,
"refactor(data): migrate hcp->os pipeline and align configs")다. 이 커밋이
`mobse/data/hcp.py` 를 삭제했고, 같은 커밋에서 `tests/` 는 **한 파일도 건드리지
않았다**(`git show --stat 52c0f7e -- tests/` 가 공집합). 즉 2026-04-01 이후
약 5.5개월 동안 잠복해 있던 결함이며, 이번 작업과 인과가 없다. 확인 명령:

```
git log --oneline --diff-filter=D -- mobse/data/hcp.py
git show --stat 52c0f7e -- tests/
```

### D.4.2 신규(v2) suite — `pytest tests/v2`

| 항목 | 결과 |
|---|---|
| 실패 | **0** |
| 통과 | 178 |

**이번 작업이 만든 신규 failure 는 0건이다.**

### D.4.3 이번 세션에 실제로 고친 legacy failure 1건

`tests/test_pipeline_integration.py::test_full_pipeline_synthetic` 는 seaborn 부재로
실패하고 있었다(`mobse/report.py:15`). D.5 의 핀 보강으로 해소되어 22 passed 가 됐다.

## D.5 근본 원인과 재발 방지 — 의존성 핀 누락 (E11)

**증상.** 두 번에 걸쳐 핀 누락으로 실행이 죽었다.
1. `PyYAML` 부재 → legacy suite 가 `mobse/config.py:8` 에서 collection 단계에 사망.
2. `seaborn` 부재 → `mobse/viz.py:8` 부재로 figure 생성 경로와
   `test_full_pipeline_synthetic` 이 사망.

**근본 원인.** 핀 목록을 *계획서가 서술한 알고리즘*(Ledoit–Wolf, K-means, PCA…)에서
역산했다. 올바른 기준은 *release 가 실제로 import 하는 것*이다. 두 기준이 갈리는
지점(설정 파서, 시각화 래퍼)에서 정확히 빠졌다.

**방지 장치.** `scripts/h197/07_verify_import_closure.py` — 표준 라이브러리만 쓰는
AST 워커다. 문서가 아니라 소스를 읽어 최상위 third-party import 를 모으고,
stdlib·first-party·의도적 제외(torch, torch_geometric)를 뺀 나머지가 핀 파일에
모두 있는지 확인한다. import 이름과 배포판 이름이 다른 경우(`yaml`→PyYAML,
`sklearn`→scikit-learn 등)는 매핑 표로 처리한다.

첫 실행이 즉시 5건을 잡았다 — seaborn 외에 networkx·requests·thop·tqdm.
scope 를 둘로 나눠 처리했다.

| scope | 대상 | 핀 파일 | 판정 |
|---|---|---|---|
| release | `mobse/v2`, `tests/v2`, `scripts/h197`, figure 생성기, `mobse/viz.py` | `requirements-v2.txt` | **PASS** |
| repo | `mobse`, `tests`, `scripts` 전체 | 위 + `requirements-legacy-extra.txt` | **PASS** |

`networkx`·`requests`·`thop`·`tqdm` 는 legacy 전용이므로 release 핀에 섞지 않고
`scripts/h197/requirements-legacy-extra.txt` 로 분리했다 — 섞으면 release 환경이
계획서에 없는 패키지를 끌고 들어간다. 네 개의 버전은 h197 venv 에서
`pip index versions` 로 확인한 값이다(초안에서 기억으로 적었던 세 개가 실제와
달라 정정했다: networkx 3.5→3.6.1, requests 2.32.5→2.34.2, tqdm 4.67.1→4.70.1).

가드는 스크립트로만 두지 않고 suite 안에 넣었다 —
`tests/v2/test_import_closure.py` 5건이 release scope·repo scope·PyYAML/seaborn
회귀·`torch-geometric` 계열 금지(U21)를 각각 검사한다. 산출물은
`provenance/import_closure_release.json`·`import_closure_repo.json`.

**부수 확인.** repo scope 스캔이 legacy figure 스크립트 2건의
`DeprecationWarning: invalid escape sequence '\D'` 를 드러냈다
(`scripts/make_etth1_story_figures.py:574`, `scripts/make_unified_empirical_figure2.py:143`).
tracked 파일이고 이번 release 경로 밖이라 수정하지 않고 기록만 한다.

## D.6 환경 lock 갱신

`venv-mobse-v2/environment_lock_h197.txt` = **58 패키지**(seaborn 추가 전 57, PyYAML
추가 전 56). torch 는 `2.10.0+cu128`, CUDA 12.8, GPU 1기로 이전 기록과 동일하며,
`torch_geometric` 은 여전히 미설치다(U21 guard 유지 — `04_setup_venv.sh` 가 설치를
감지하면 lock 을 쓰지 않고 종료한다).

## D.7 아직 구현하지 않은 것 (정직한 경계)

| 항목 | 상태 | 막고 있는 것 |
|---|---|---|
| `configs/redesign_v1/` runtime config schema | 미작성 | — (바로 가능) |
| CLI 하위 명령의 실제 학습 루프 본문 | 골격만 | WI-02 재추출 산출물 |
| WI-02 재추출 | 미착수 | Wave 2 (진행 중, 15 GiB/209.7 GiB) |
| WI-08 외부 재현·WI-09 민감도·WI-10 독립 재계산·WI-11 최종 패키지 | 미착수 | 위 전부 |

D.1–D.3 의 모듈은 **합성 fixture 로 검증된 상태**다. 실제 BOLD 로 돌린 적은 없고,
그것은 Wave 2 완료 뒤 WI-02 에서 처음 일어난다. 이 구분을 흐리지 않는다.


---

# 부록 E — runtime config 스키마, `validate` 본체, 계획서 개정 P1–P6

부록 D 이후에 한 일이다. 세 가지가 서로 맞물린다 — config 가 상수를 잠그고,
`validate` 가 그 config 로 manifest 를 검사하고, 개정 기록이 둘의 근거를 남긴다.

## E.1 runtime config 스키마 (WI-05 잔여 산출물)

`mobse/v2/config.py` 와 `configs/redesign_v1/` 3종. 설계 원칙 셋:

1. **조용한 default 금지 (T02).** 미지의 키는 오타로 보고 거부하고, 빠진 필수 키도
   거부한다. 위반은 한 번에 모아 보고한다 — 하나씩 고치며 재실행하지 않도록.
2. **코드 상수가 단일 출처.** seed·창 경계·grid·grid 축 값은 각 모듈의 상수가
   정본이고 config 는 그것을 *다시 적어 잠근다*. 둘이 어긋나면 실패시킨다. 즉
   **config 로 알고리즘을 바꿀 수 없다** — 바꾸려면 상수와 config 를 함께 고치고
   계획서 §11 에 개정을 남겨야 한다.
3. **결정적 해시.** `canonical_json()` 이 키 정렬·list/tuple 통일·구분자 고정을
   해서 같은 내용이 같은 해시를 준다. 이 해시가 `release_id` 의 마지막 성분이다.

| config | 필드 수 | config_hash | release_id 예시 |
|---|---:|---|---|
| `configs/redesign_v1/external.yaml` | 53 | `7daa536b` | `20260917_3c458d507e82_7daa536b` |
| `configs/redesign_v1/main.yaml` | 53 | `85556f56` | `20260917_3c458d507e82_85556f56` |
| `configs/redesign_v1/pilot.yaml` | 53 | `fd6c8a27` | `20260917_3c458d507e82_fd6c8a27` |

세 config 의 해시가 서로 다르다 — 즉 pilot/main/external 이 같은 release 경로를
덮어쓸 수 없다. 현재 release 디렉터리 이름의 `nocfg` 자리가 앞으로 이 해시로 채워진다.

검증은 `tests/v2/test_config.py` 36건이 담당한다. 특히
`test_constant_override_is_rejected` 가 6개 축(분석 구간 끝, FD 상한, outer seed,
null seed, epoch 상한, bootstrap 반복)에 대해 config 가 상수를 이기지 못함을 확인한다.

## E.2 `mobse-v2 validate` 본체 구현

CLI 하위 명령 중 **원자료 없이 완결되는 유일한 명령**이라 먼저 구현했다.
나머지(`prepare`/`split`/`fit`/`evaluate`/`report`)는 WI-02 재추출 산출물을
입력으로 받으므로 골격만 있고, 호출하면 `NotImplementedError` 로 그 사실을 말한다.

구현하면서 **artifact 이름 충돌**을 발견했다. WI-01 이 만든 감사본
`provenance/source_runs.jsonl`(schema `wi01-source-runs-0.1`)과 계획서 §2 표가
정의하는 release 산출본 `source_runs`는 **이름이 같고 스키마가 다르다**. 감사본을
release 스키마로 검사하면 "아직 내려받지 않은 파일"이 전부 스키마 위반으로 나와
쓸모가 없다. 그래서 `validate` 는 헤더의 `schema_version` 으로 분기한다.

감사본 경로의 검사 내용이 더 중요하다 — 감사본은 null 이 정상이므로,
**모든 null 에 이유가 붙어 있는지**를 본다. 이유 없는 null 이 바로 조용한 default 가
들어설 자리다. 실제 산출물에 돌린 결과:

```
manifest_schema_version : wi01-source-runs-0.1
records                 : 1,228
unique_run_keys         : 1,228
datasets                : piop1 1,226 / piop2 2
usable_for_primary      : 0
record_errors           : 0
verdict                 : pass
```

즉 1,228 run 전부에서 null 필드마다 `unresolved` 사유가 붙어 있고, run_key 중복
0건, task 내 TR 충돌 0건이다. **이 점검은 이번이 처음이다** — 지금까지는 감사
스크립트가 자기 산출물을 검사하지 않았다. 산출물은
`provenance/validate_report.json`.

`usable_for_primary_analysis` 가 0 인 것은 정상이다. Wave 2 와 WI-02 재추출 전에는
어떤 run 도 주분석에 쓸 수 없다.

## E.3 계획서 개정 P1–P6 적용, §11 개정 기록 신설

계획서는 사전 등록 문서이므로 본문을 조용히 고치지 않는다. 본문 해당 위치에
`[개정 Pn]` 표시를 붙이고, 신설한 **§11 개정 기록**에 원문·개정문·근거·날짜를 남겼다.
**모든 개정은 main 성능을 보기 전에 이루어졌다.**

| ID | 처리 | 요지 |
|---|---|---|
| P1 | 적용 | "로컬 WM 160 대 문헌 162" → **cohort 간 차이**로 정정 (PIOP1 WM 은 204명 전원 162, 160 은 PIOP2 값) |
| P2 | 적용 | TR 근거를 문헌 D1 → **sidecar 직접 측정**으로 교체. 6개 조합 전부 확정 |
| P3 | **철회** | run 길이 270–480초로 `[12,252)` 가 무조건 성립. 계획서 §3.1 수정 없음 |
| P4 | 적용 | 관계 metadata 부재(U10) → `group_id` **1 subject = 1 group 퇴화** + 미검증 범위 2항 명시 |
| P5 | 적용 | `canonical_subject` **dataset prefix 필수화** (계획서·지침서 양쪽) |
| P6-a | 적용 | band-pass **적용 단위를 전체 run 으로 명시**. 0.008 Hz 가 60초 창에서 0.48 cycle 인 성질을 기록하되 detrend 추가 없음. 고역 대안은 WI-09 로 이관 |
| P6-b | 적용 | residual DOF 에 **filter 로 잃는 자유도를 포함**해 동결 |

### E.3.1 P6-b — 동결한 정의와 실제 값

```
residual_dof = min( n_volumes - rank(design),
                    floor( 2 * (f_high - f_low) * T_run_sec ) )
```

둘째 항은 통과대역 [0.008, 0.1] Hz 가 길이 `T_run_sec` 의 run 에서 남기는 실수
자유도다(유지 주파수당 sin/cos 2개). 확정된 6개 조합:

| dataset / task | TR (s) | volumes | T_run (s) | filter DOF |
|---|---:|---:|---:|---:|
| PIOP1 / emomatching | 2.00 | 135 | 270.0 | 49 |
| PIOP1 / workingmemory | 2.00 | 162 | 324.0 | 59 |
| PIOP1 / restingstate | 0.75 | 480 | 360.0 | 66 |
| PIOP2 / emomatching | 2.00 | 135 | 270.0 | 49 |
| PIOP2 / workingmemory | 2.00 | 160 | 320.0 | 58 |
| PIOP2 / restingstate | 2.00 | 240 | 480.0 | 88 |

전부 30을 넘는다. 즉 실제로는 이 항이 하한을 준다는 사실만 기록되고 기준은
완화되지 않는다. **이 개정은 기준을 더 엄격하게 만든다** — 종전 정의는 filter 로
잃는 자유도를 세지 않아 residual DOF 를 과대 보고했다.

### E.3.2 개정 중 발견한 문서·코드 불일치

P5 개정문에 처음에 `piop1/sub-0001` 이라고 적었는데, 실제 검증기
`manifests.validate_canonical_subject()` 는 `ds002785:sub-0001` 형식만 통과한다
(`^[A-Za-z0-9]+:sub-[A-Za-z0-9]+$`). **코드가 옳다** — run_key 가 `/` 로 나뉘므로
prefix 를 `/` 로 붙이면 키 분해가 모호해지고, prefix 는 별칭(piop1)이 아니라
OpenNeuro accession 이어야 오래간다. 문서를 코드에 맞춰 고쳤다.

재발 방지로 `tests/v2/test_protocol_documents.py` 9건을 붙였다. 본문 `[개정 Pn]`
표시와 §11 표의 1:1 대응(양방향), P3 철회 선언 유지, P6-b 수식 존재, 고정 window
4개 유지, 그리고 **계획서에 적힌 `ds…:sub-…` 예시를 실제 검증기에 통과시키는**
시험이다. 마지막 것이 이번에 잡은 종류의 불일치를 자동으로 막는다.

### E.3.3 P5 미반영 산출물 1건 (정직한 경계)

WI-01 감사본 `provenance/source_runs.jsonl` 은 개정 이전에 생성되어
`canonical_subject` 가 `sub-0001` 형식이고 run_key prefix 도 별칭(`piop1/…`)이다.
**소급 수정하지 않는다** — 원자료 미확보 상태의 기록이기 때문이다. WI-02 재추출이
만드는 release 산출본부터 P5 형식을 적용하며, 그 시점에
`manifests.validate_record()` 가 강제한다. 이 경계를 계획서 §11 에도 적어 두었다.

## E.4 갱신된 규모

| 항목 | 부록 D 시점 | 현재 |
|---|---:|---:|
| v2 모듈 | 11개 / 2,439 줄 | **12개 / 2,921 줄** |
| 시험 파일 | 11개 | **13개** |
| 시험 함수 | 176 | **223** |
| h197 수집·통과 | 178 | **236** |
| runtime config | 없음 | **3종 (pilot/main/external)** |
| 구현된 CLI 하위 명령 | 0 | **1 (`validate`)** |


---

# 부록 F — U3 해소와 atlas 공간 불일치(U28), Wave 2 착수 중 발견

Wave 2 가 도는 동안 이미 받아 둔 Wave 1 raw sidecar 와, 내려오기 시작한 Wave 2
BOLD 헤더를 읽어 두 건을 처리했다. 둘 다 **WI-02 재추출을 시작하기 전에 정해져야
하는 값**이라 지금 확정해 둔다.

## F.1 U3 해소 — 폐기 volume 수가 raw sidecar 에 있었다

WI-01 은 "dummy volume 제거 여부를 로컬에서 판정 불가"로 남겼다. Wave 1 로 raw
sidecar 를 확보한 뒤 전수 조사했다(`scripts/h197/09_survey_discarded_volumes.py`,
raw sidecar **1,295개**, 조합 내 분산 **0**):

| dataset / task | n | DiscardedByScanner | DiscardedByUser | RepetitionTime |
|---|---:|---:|---|---:|
| ds002785/emomatching | 208 | 2 | (없음) | 2 |
| ds002785/restingstate | 210 | 2 | (없음) | 0.75 |
| ds002785/workingmemory | 207 | 2 | (없음) | 2 |
| ds002790/emomatching | 222 | 2 | (없음) | 2 |
| ds002790/restingstate | 224 | 2 | (없음) | 2 |
| ds002790/workingmemory | 224 | 2 | (없음) | 2 |

**결론: 모든 run 에서 스캐너가 앞 2 volumes 를 버렸고, 변환 단계 추가 폐기는 없다.**
`derivative_start_sec = 2 × TR` 이다 (TR 2초 → 4.0초, TR 0.75초 → 1.5초).

계획서 §3.1 이 이미 이 경우를 지시해 두었다 — "앞 2 volumes가 이미 제거되었다면
남은 sample의 원래 시간을 복원해 선택한다". 그대로 적용한 결과:

| 조합 | TR | vol | 첫 표본 원시각 | 마지막 원시각 | `[12,252)` | 2초 격자와 정확 일치 |
|---|---:|---:|---:|---:|:---:|---:|
| piop1/emomatching | 2.00 | 135 | 4.00 | 272.00 | 성립 | **120/120** |
| piop1/workingmemory | 2.00 | 162 | 4.00 | 326.00 | 성립 | **120/120** |
| piop1/restingstate | 0.75 | 480 | 1.50 | 360.75 | 성립 | 40/120 |
| piop2/emomatching | 2.00 | 135 | 4.00 | 272.00 | 성립 | **120/120** |
| piop2/workingmemory | 2.00 | 160 | 4.00 | 322.00 | 성립 | **120/120** |
| piop2/restingstate | 2.00 | 240 | 4.00 | 482.00 | 성립 | **120/120** |

**두 target task 의 시계열은 보간되지 않는다.** dummy 2개를 되살린 원 시각이
4, 6, 8, … 초이므로 목표 격자 12, 14, …, 250 초가 전부 실제 획득 시점과 겹친다.
보간이 필요한 것은 bank source 인 PIOP1 restingstate(TR 0.75초) 하나뿐이다.
주장의 강도가 달라지는 지점이라 별도로 적는다 — 주분석 입력에는 재표본화 오차가
들어가지 않는다.

고정 창의 원본 frame 범위(TR 2초, start 4.0초): `(4,34) (34,64) (64,94) (94,124)`.
즉 124번째 frame 까지만 쓰므로 135·160·162·240 vol 모두 여유가 있다.

이 값들은 `tests/v2/test_acquisition_facts.py` 가 고정한다 — 코드가 조용히
달라지면 그 시험이 깨진다.

## F.2 U28 (신규) — atlas 템플릿 공간 불일치

Wave 2 로 내려온 fMRIPrep derivative 를 열어 보고 발견했다.

| | 공간 | 격자 | 크기 |
|---|---|---|---|
| Wave 2 BOLD (실제) | **MNI152NLin2009cAsym** | 3.0 × 3.0 × 3.3 mm | 65 × 77 × 60 |
| 기존 캐시 atlas | **FSLMNI152** (= MNI152NLin6Asym) | 2 × 2 × 2 mm | 91 × 109 × 91 |

**템플릿이 다르다.** 두 MNI 변형은 같은 이름을 공유할 뿐 정렬이 다르며, 이 계획의
H1 자체가 "해부학적으로 정렬된 graph bank 가 값을 더하는가"이므로 정렬 provenance 가
결과를 지탱하는 축이다. 여기서 엇갈리면 H1 의 해석이 무너진다.

**처리:** TemplateFlow 에서 같은 템플릿의 Schaefer-100 을 받았다.

```
tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz
sha256 7221cee56943599833dc2b98aac56626…
shape [97, 115, 97]  zooms [2.0, 2.0, 2.0]  labels 1–100 (결손 0개)
lookup table sha256 a81a63f67fdaffd7b2b4b6c7df05f75b…  (100 rows)
roi_order_hash f7684b0e05e11a42c7abdfeccc54a835…
```

**BOLD 격자로 재표본화해도 100 parcel 이 전부 살아남는지** 직접 확인했다
(nearest-neighbour, 같은 템플릿 내 격자 변환):

| | parcel 존재 | 최소 voxel | 중앙값 voxel | 5 voxel 미만 |
|---|---:|---:|---:|---:|
| 재표본화 직후 | **100 / 100** | 102 | 344 | 0개 |
| brain mask 적용 후 | **100 / 100** | 102 | 335 | 0개 |

ROI 손실이 없으므로 계획서 §3.2 의 "100 ROI 순서와 checksum 고정"을 그대로 만족한다.
사양은 `provenance/atlas_spec_2009c.json` 에 기록했다. 기존
`provenance/atlas_spec.json`(FSLMNI152 2mm)은 **WI-01 감사 기록으로 남기고 재추출에
쓰지 않는다** — 지우지 않고 용도를 분리한다.

### F.2.1 이 발견이 기존 결과에 갖는 의미

기존 `.npy` 추출기 `scripts/stream_aomic_extract.py` 는
`nilearn.fetch_atlas_schaefer_2018()` 기본값을 썼고, 그것은 FSLMNI152 계열이다.
즉 기존 파생물은 **TR 오적용(2.67배)** 에 더해 **템플릿 불일치**까지 안고 있다.
재사용하지 않기로 한 판단이 한 겹 더 보강된다 — 다만 이 두 번째 결함은 이번에야
확인했으므로, 앞선 판단의 근거였던 것은 TR 쪽이다.

## F.3 갱신된 차단 항목

| ID | 상태 | 근거 |
|---|---|---|
| U3 폐기 volume 미상 | **해소** | raw sidecar 1,295건 전수, 전부 scanner=2 / user=없음 |
| U28 atlas 템플릿 불일치 | **해소** | TemplateFlow 2009cAsym Schaefer-100 확보, BOLD 격자 재표본화 후 100/100 parcel 생존 |
| U6′ target BOLD 부재 | 진행 중 | Wave 2 (209.7 GiB) |
| U10 관계 metadata 부재 | **미해소** | participants.tsv·sidecar 어디에도 가족·중복 식별 열 없음 → 개정 P4 로 명시 |


---

# 부록 G — WI-02 재추출 파이프라인 구현과 실자료 검증 (Wave 2 진행 중)

Wave 2 가 끝난 뒤에 착수하면 그때부터 디버깅이 시작된다. 이미 내려온 일부
subject 로 **파이프라인을 먼저 완성하고 실자료로 통과시켜** 두었다.

## G.1 구성

| 파일 | 역할 |
|---|---|
| `mobse/v2/extract.py` | nuisance 설계·자유도·잔차·z-score — **순수 함수**. 합성 fixture 로 검증 가능 |
| `scripts/h197/10_wi02_extract.py` | 경로 조립·입출력·manifest — 계산은 하지 않는다 |
| `tests/v2/test_extract.py` (37건) | 위 순수 함수의 계약 |
| `tests/v2/test_wi02_driver.py` (10건) | 드라이버를 합성 run 으로 통째로 돌린다 |

경로는 BIDS entity 로 **직접 조립**한다(`run_paths()`). glob 최신 파일 탐색을 쓰지
않는다(U20). `ACQ` 표에 dataset×task 의 acquisition entity 를 고정했다 — PIOP1
restingstate 만 `mb3` 이고 나머지는 `seq` 다.

## G.2 nuisance 설계 (계획서 §3.2 그대로)

| 블록 | 열 수 | 근거 |
|---|---:|---|
| motion | 24 | `{trans,rot}_{x,y,z}` × (원값, `_derivative1`, `_power2`, `_derivative1_power2`) |
| aCompCor | 5 | mask `combined`(WM+CSF), `Retained=True`, `VarianceExplained` 내림차순. 동률은 열 이름으로 깬다 |
| spike | 가변 | 원본 frame 의 FD > 0.5 mm 마다 one-hot. frame 삭제·이어붙이기 없음 |
| 상수·추세 | 2 | intercept + linear drift **1개만** — filter 와 중복해 rank 를 올리지 않는다 |

미분 열의 **첫 행 결측만** 0 으로 정의하고, 그 외 결측은 실패다. aCompCor 가 5개
미만이면 다른 열로 대체하지 않고 실패시킨다 — 계획서가 못박은 지점이다.

## G.3 실자료 통과 (PIOP1 emomatching, 이미 내려온 8명)

`--dry-run`, 8명, 13초.

| subject | 판정 | design rank | spike | residual DOF | mean FD | spike ratio | 제외 사유 |
|---|---|---:|---:|---:|---:|---:|---|
| `ds002785:sub-0001` | **제외** | 40 | 9 | 49 | 0.167 | 0.067 | window3_spike_ratio>0.1, window3_spikes>3 |
| `ds002785:sub-0002` | ok | 31 | 0 | 49 | 0.069 | 0.000 | — |
| `ds002785:sub-0003` | ok | 32 | 1 | 49 | 0.122 | 0.007 | — |
| `ds002785:sub-0004` | ok | 31 | 0 | 49 | 0.127 | 0.000 | — |
| `ds002785:sub-0005` | ok | 31 | 0 | 49 | 0.080 | 0.000 | — |
| `ds002785:sub-0006` | ok | 38 | 7 | 49 | 0.167 | 0.052 | — |
| `ds002785:sub-0007` | ok | 39 | 8 | 49 | 0.185 | 0.060 | — |
| `ds002785:sub-0008` | ok | 31 | 0 | 49 | 0.075 | 0.000 | — |

**결과: ok 7, 제외 1, 오류 0.** 확인된 것:

* design 이 **full rank** 다 (rank = 열 수). spike 수에 따라 31–39 로 변한다 —
  collinearity 없이 spike 가 그대로 자유도를 먹는다.
* residual DOF 가 전부 **49** — 개정 P6-b 대로 `n-rank`(≈96–104)가 아니라
  **filter 항이 하한을 준다**. 예측한 그대로다.
* 제외된 `sub-0001` 은 사유를 **둘 다** 보고했다
  (`window3_spike_ratio>0.1`, `window3_spikes>3`). §3.3 의 "중복 사유와 우선 사유를
  모두 저장" 요구를 만족한다.
* ROI 시계열 (135, 100) 전부 유한, 격자 변환 후 (120, 100), 창 4개 각 (30, 100),
  FC (100, 100) → Fisher-z 4,950 edge 전부 유한.

처리 속도 약 1.6초/run → 1,295 run 전량 약 **35분**. Wave 2 완료 뒤 병목이 아니다.

## G.4 근본 원인 E12 — 남의 함수 시그니처를 기억으로 적었다

드라이버 첫 판이 두 번 깨졌다.

1. `qc_decision(run_qc, window_qc, task=...)` → 그 함수는 `task` 인자를 받지 않는다.
2. `decision["keep"]`, `decision["reasons"]` → 실제 반환 키는
   `passed` / `all_reasons` / `primary_reason` 이다.

둘 다 **내가 쓴 모듈**인데도 호출부를 시그니처를 읽지 않고 적었다. 앞서 의존성
핀에서 버전을 기억으로 적었던 것(E11)과 같은 종류다.

방지 장치를 코드 쪽에 뒀다. 실자료 smoke 는 Wave 2 가 끝나야 전량 돌릴 수 있고
지금은 8명뿐이므로, **합성 fixture 로 드라이버를 통째로 돌리는**
`tests/v2/test_wi02_driver.py` 를 붙였다. 특히
`test_qc_decision_contract_is_what_driver_expects` 가 인자 이름과 반환 키 집합을
직접 고정한다 — 둘 중 하나라도 바뀌면 실자료 없이 즉시 깨진다. 나머지 9건은
정상 경로, 창 4개 기록, 다중 QC 사유 수집, 파일 누락 시 skip, 결손 parcel 거부,
경로 조립(glob 아님), atlas 캐시 재사용을 각각 확인한다.

## G.5 아직 하지 않은 것

* **band-pass 를 아직 적용하지 않는다.** 현재 경로는 nuisance 회귀 → z-score →
  재표본화다. 0.008–0.1 Hz 필터의 종류·차수·padding·회귀 순서는 계획서 §3.2 가
  "pilot 기술 검증에서 기록하고 main 전에 동결"하라고 정했으므로, pilot 이
  분리된 뒤에 확정해 붙인다. residual DOF 는 이미 필터를 전제로 계산하고 있다
  (개정 P6-b) — 즉 **자유도 회계는 필터를 반영하고 실제 필터는 아직 없다**는
  불일치가 지금 존재하며, WI-03 에서 닫는다. 흐리지 않고 적어 둔다.
* events 기반 label 부착은 WI-03 이후다. 현재 manifest 에 `observed_label` 이 없다.
* 전량 실행은 Wave 2 완료 뒤다. 현재 8 run 만 돌렸다.

## G.6 현재 규모 (부록 D·E 대비)

| 항목 | 부록 D | 부록 E | 현재 |
|---|---:|---:|---:|
| v2 모듈 | 11 / 2,439 줄 | 12 / 2,921 줄 | **13 / 3,309 줄** |
| 시험 파일 | 11 | 13 | **16** |
| 시험 함수 | 176 | 223 | **274** |
| h197 수집·통과 | 178 passed | 236 passed | **310 passed** |
| 신규 failure | 0 | 0 | **0** |
| 미커버 수용시험 T-ID | 0 | 0 | **0** |

전량 `PYTHONPATH=. python -m pytest tests/v2 -q -p no:cacheprovider` 로 h197 venv
에서 확인했다. 기존 legacy suite 는 여전히 22 passed / collection error 2 (부록 D.4,
2026-04-01 커밋이 남긴 기존 결함)이며 이번 작업이 만든 신규 failure 는 없다.

---

# 부록 H — band-pass 순서 문제: 준비했고, 답은 못 냈다

부록 G.5 에서 "band-pass 를 아직 적용하지 않았다"고 적은 항목이다. Wave 2 대기
시간에 먼저 정리해 보려 했고, **결론적으로 이 단계에서는 정할 수 없다**는 것을
확인했다. 확인한 근거를 남긴다.

## H.1 무엇이 문제인가

계획서 §3.2 는 "nuisance와 filter를 **일관되게** 처리하는 하나의 검증된
구현·버전을 고정"하라고 요구한다. 이 "일관되게"가 가리키는 것은 처리 **순서**다.
세 가지가 가능하다.

| | 처리 |
|---|---|
| A | nuisance 를 원신호에서 회귀 → 잔차를 필터링 |
| B | 신호와 nuisance 를 **같은 필터로** 거른 뒤 회귀 |
| X | 신호만 필터링 → **거르지 않은** nuisance 로 회귀 |

X 가 문헌이 경고하는 순서다(Hallquist et al., 2013, *NeuroImage*). regressor 가
가진 통과대역 밖 성분이 필터링된 신호에는 없어 적합이 틀어지고, 제거했어야 할
nuisance 가 통과대역 안으로 되돌아온다.

**현재 WI-02 구현은 A 의 앞부분만 해 둔 상태다** — nuisance 회귀까지 하고 필터를
붙이지 않았다. 즉 순서를 아직 고르지 않았다.

## H.2 시도와 그 실패 (E13)

`scripts/h197/11_filter_order_probe.py` 로 합성 신호 비교를 만들었다.
**첫 판은 잘못 설계됐다.**

1. 문헌이 경고하는 순서(X)를 **아예 넣지 않았다**. A 와 B 만 비교했으니 검사하려던
   대상이 빠졌다.
2. filtfilt 의 edge transient 를 **run 전체에서** 채점했다. 통과대역 하한이
   0.008 Hz 인데 run 이 270초면 전이 구간이 run 길이와 맞먹는다. 어차피 버릴
   구간의 왜곡이 점수를 지배했다.

둘 다 고쳤다 — X 를 추가하고, 채점을 **원 시각 `[12,252)` 안으로** 한정했다
(계획서가 이미 버리는 구간을 점수에서도 뺀 것이다).

**그런데 고친 뒤에도 답이 나오지 않는다.** A 의 잔차가 1–5%, B·X 가 6–22% 로
A 가 압도적으로 보이는데, 이건 우열이 아니라 **합성의 구조가 A 에게 유리하게
짜였다**는 사실이다. 합성에서 nuisance 를 설계행렬과 **정확히 같게** 만들었으므로
"먼저 회귀"는 구성상 최적이 된다 — 남길 것이 없다.

실제로 순서가 문제되는 국면은 정반대다. **nuisance 모형이 불완전해서** 설계로
잡지 못한 성분을 필터가 잡아야 하는 경우이고, 그 국면은 실제 confounds 와 실제
BOLD 가 있어야 만들어진다. 즉 계획서가 이 명세를 "pilot 기술 검증에서 기록하고
main 전에 동결"하라고 정한 판단이 옳았음이 확인된 셈이다.

## H.3 그래도 얻은 것 하나

세 처리의 결과가 단위 진폭 신호에서 **최대 0.65 만큼** 갈린다
(`A_vs_B_max_abs_diff_in_window`, `A_vs_X_max_abs_diff_in_window`). 순서 선택은
장식이 아니다. 아무거나 골라 두고 넘어갈 수 없으며, pilot 에서 실자료로 골라
동결해야 한다.

`11_filter_order_probe.py` 는 그 pilot 실행의 뼈대로 남긴다 — `synth()` 를 실제
run 로더로 바꾸면 그대로 쓸 수 있다.

## H.4 정직한 상태

| 항목 | 상태 |
|---|---|
| band-pass 순서 (A / B / X) | **미정.** pilot 기술 검증에서 실자료로 결정 |
| filter 종류·차수·padding | **미정.** 같은 시점에 함께 동결 |
| WI-02 현재 구현 | nuisance 회귀까지. 필터 없음 |
| residual DOF 계산 | **이미 필터를 전제** (개정 P6-b) |

마지막 두 줄이 어긋나 있다는 점을 다시 적어 둔다 — 자유도 회계는 필터를
반영하는데 실제 필터는 없다. WI-03 에서 닫는다. 이 probe 는 gate evidence 의
**해소된 항목이 아니라 열린 항목**으로 기록한다.

---

# 부록 I — WI-02 사전 점검과 WI-03 코호트 구성 (Wave 2 진행 중, 2회차)

## I.1 6개 조합 사전 점검 — 경로 조립 검증

Wave 2 가 끝난 뒤에 경로 오류를 발견하면 그때부터 다시 돌려야 한다. 이미 내려온
subject 로 6개 조합 전부를 `--dry-run --limit 4` 로 미리 통과시켰다.

| dataset / task | TR | 결과 |
|---|---:|---|
| ds002785 / emomatching | 2.00 | ok 3, 제외 1, 오류 0 |
| ds002785 / workingmemory | 2.00 | ok 3, 제외 1, 오류 0 |
| ds002785 / restingstate | 0.75 | ok 3, 제외 1, 오류 0 |
| ds002790 / emomatching | 2.00 | subject 미도착 (내려받기 진행 중) |
| ds002790 / workingmemory | 2.00 | 〃 |
| ds002790 / restingstate | 2.00 | 〃 |

PIOP2 는 아직 내려오지 않아 직접 통과시킬 수 없다. 대신 **경로 조립의 핵심인
acquisition entity 를 Wave 1 실파일로 대조**했다 — confounds 파일명 전수:

| dataset | emomatching | workingmemory | restingstate |
|---|---|---|---|
| ds002785 | `acq-seq` 208 | `acq-seq` 207 | **`acq-mb3`** 210 |
| ds002790 | `acq-seq` 222 | `acq-seq` 224 | **`acq-seq`** 224 |

합 1,295 로 Wave 1 감사 수와 일치한다. 드라이버의 `ACQ` 표와 정확히 같다 —
PIOP1 rest 만 `mb3` 다. PIOP2 경로는 **코드 대조로만 검증**했고 실행 검증은
내려받기 완료 후로 남는다. 이 구분을 흐리지 않는다.

restingstate(TR 0.75, 480 volume)는 run 당 약 5초로 target task(1.6초)보다 느리다.
6개 조합 전량은 약 1시간 40분으로 추정한다.

## I.2 `mobse/v2/cohort.py` — WI-03 코호트 구성

WI-02 의 6개 manifest 를 subject 단위로 접는다. 기준은 계획서 §3.3 한 줄이다 —
"두 task와 rest의 각 4개 window가 모두 유효한 subject만 primary complete-case에
포함한다". 즉 emomatching·workingmemory·restingstate **셋 모두** QC 통과가 조건이다.

| 함수 | 역할 |
|---|---|
| `read_extract_manifest` | WI-02 JSONL 읽기. 헤더 없으면 실패 |
| `build_subjects` | subject 단위로 접고 **사유를 모두 보존** |
| `subjects_to_records` | `manifests.SCHEMAS["subjects"]` 적합 레코드 |
| `exclusion_records` | `SCHEMAS["exclusions"]` 적합. 중복 사유 + 우선 사유 |
| `summarize` | 코호트·사유별 집계 |

설계상 지킨 것:

* **사유를 합치지 않는다.** 한 subject 가 emo 에서 `mean_fd>0.2`, rest 에서
  `residual_dof<=30` 이면 둘 다 `all_reasons` 에 `task:reason` 형태로 남는다.
* `group_id` 는 `canonical_subject` 와 같다 — 관계 metadata 부재(U10), 개정 P4.
* dataset prefix 없는 subject 는 **자동 보정하지 않고 실패**시킨다(개정 P5).
  같은 `sub-0001` 이라도 dataset 이 다르면 다른 사람이므로 분리 유지된다(U17).
* 같은 (subject, task) 가 두 번 오면 조용히 합치지 않고 실패한다.

이 모듈은 **분할을 하지 않는다.** seed·알고리즘은 `splits.py` 가 단일 출처이고,
여기서는 그것이 먹을 수 있는 subject 목록만 만든다. 접합은 시험으로 확인했다 —
적격 50명을 `build_folds()` 에 넣어 pilot 10명(= `min(32, ⌊0.2·50⌋)`)을 얻는다.

시험 25건 (`tests/v2/test_cohort.py`).

## I.3 E12 재발 — 같은 부류가 한 번 더 나왔다

`build_folds()` 의 반환 구조를 또 **기억으로 적었다**: `folds["pilot"]["n_subjects"]`
로 썼는데 실제 키는 `n` 이고, 상위에는 `n_subjects_total` 이 따로 있다.

부록 G.4 에서 `qc_decision` 건으로 같은 진단을 내리고 가드를 붙였는데, 그 가드는
**그 함수 하나만** 덮는다. 부류 전체가 재발했다.

이번에는 접합부 자체를 고정했다 — `test_build_folds_return_shape_is_what_callers_expect`
가 상위 키 집합과 `pilot` 키 집합을 직접 검사한다. 모듈 경계를 넘는 호출마다
이렇게 반환 구조를 시험으로 박아 두는 것이 이 부류의 실질적 대책이다.

정직하게 적자면: 이 실수는 **호출 전에 시그니처를 읽으면 애초에 나지 않는다.**
가드는 사후 안전망이지 대책이 아니다.

## I.4 갱신된 규모

| 항목 | 부록 G | 현재 |
|---|---:|---:|
| v2 모듈 | 13 / 3,309 줄 | **14 / 3,552 줄** |
| 시험 파일 | 16 | **17** |
| h197 수집·통과 | 310 | **335** |
| 신규 failure | 0 | **0** |

---

# 부록 J — label 부착과 창 manifest, 그리고 전 구간 실자료 통과 (3회차)

## J.1 label 은 task entity 에서만 온다 (`mobse/v2/labels.py`)

계획서 §1 이 target 을 못박았다 — "주 target은 AOMIC PIOP1의 `emomatching=0`,
`workingmemory=1` **run identity**다". 즉 label 은 run 의 task entity 이고,
events.tsv 내용이나 군집 결과가 아니다. 이 구분이 T11 의 전부다.

구현에서 지킨 것:

* `label_source` 는 `task_metadata` 하나뿐이다. 스키마 쪽
  `ALLOWED_LABEL_SOURCES` 가 cluster ID 계열을 이미 거부하지만, 이 모듈은
  **그런 경로를 애초에 만들지 않는다.**
* **restingstate 는 label 을 받지 않는다.** rest manifest 를 넘기면 즉시 실패한다.
  붙여 두면 3-class 문제로 조용히 번진다 — 계획서는 2-class 다.
* 알 수 없는 task(`faces`, `gstroop`, `anticipation`, 대소문자 다른 것)는 기본값으로
  넘기지 않고 거부한다.
* `window_key` 는 `<run_key>#win-<n>` 이다. run_key 가 `/` 로 나뉘므로 창 구분자를
  `/` 로 쓰면 키 분해가 모호해진다 — P5 에서 `canonical_subject` 에 적용한 논리와 같다.

부분 창(4개 미만), 표본 수·ROI 수 불일치, 창 시작 시각 불일치는 전부 실패다.
**제외된 run 의 창은 만들지 않는다** — 만들어 두고 나중에 거르면 "몇 개는 남아
있더라"가 생긴다. 시험 24건 (`tests/v2/test_labels.py`).

## J.2 `scripts/h197/12_build_windows_manifest.py`

재추출과 분리했다. 창 레코드 스키마나 label 규칙이 바뀌어도 **209 GiB 를 다시 읽지
않아야** 하기 때문이다. 드라이버는 창 배열과 해시를 만들고, 이 단계가 그것을
스키마 레코드로 옮긴다. `manifests.write_jsonl` 이 스키마 검증·키 중복·덮어쓰기
거부를 담당한다(지침서 §2 — 같은 release 결과를 덮어쓰지 않는다).

## J.3 전 구간 실자료 통과

PIOP1 12 run(emo 6 + WM 6)을 **실제로 추출**해서(`--dry-run` 아님) 끝까지 흘렸다.

```
WI-02 추출   emomatching    ok 5 / 제외 1 / 오류 0
             workingmemory  ok 4 / 제외 2 / 오류 0
창 manifest  run 9 → 창 레코드 36
cohort       subject 6, 적격 0 (rest manifest 미포함이므로 정상)
```

검증한 것:

| 확인 | 결과 |
|---|---|
| 창 레코드 수 | 36 = ok run 9 × 4 창 |
| label 분포 | emomatching 20 / workingmemory 16 — ok run 수와 일치 |
| `label_source` | `{task_metadata}` 단일 |
| 창 시작 분포 | 12.0 / 72.0 / 132.0 / 192.0 각 9건 — 고르다 |
| `window_key` 고유성 | 36/36 |
| 실제 `.npy` | (30, 100) float32, 전부 유한 |
| cohort 사유 보존 | `restingstate_missing` 6, WM 제외 사유 4종이 subject 별로 모두 남음 |

창 평균이 0 이 아닌 것(예: −0.076)은 정상이다. z-score 는 **run 전체**에서 하고
창은 그 뒤에 잘라내므로, 창 단위 평균이 0 일 이유가 없다. 계획서 §3.2 의 "run 내
ROI별 z-score" 그대로다.

## J.4 부수 수정 — `features.py` 의 sklearn 지연 import

`labels.py` 가 ROI 수 상수 하나 때문에 `features` 를 import 하는데, 그 모듈이
최상위에서 sklearn 을 끌어와 **상수만 필요한 모듈에까지 무거운 의존성이 전파**됐다.
`templates.py` 에서 이미 같은 처리를 했던 것과 같은 문제다(U24 회피). LedoitWolf·
PCA·StandardScaler 를 각 사용처로 내렸다. 계산 경로는 그대로이고 시험 364건이 통과한다.

## J.5 갱신된 규모

| 항목 | 부록 I | 현재 |
|---|---:|---:|
| v2 모듈 | 14 | **15** |
| 시험 파일 | 17 | **18** |
| h197 수집·통과 | 335 | **364** |
| 신규 failure | 0 | **0** |
| 미커버 수용시험 T-ID | 0 | **0** |

---

# 부록 K — WI-04 graph bank 를 실제 rest 로 적합 (4회차)

H1 의 핵심은 "해부학적으로 정렬된 graph bank 가 값을 더하는가"다. 그 bank 는
지금까지 **합성 fixture 로만** 검증돼 있었다. PIOP1 rest 가 127건 내려와 있어
실자료로 끝까지 돌려 봤다.

**이것은 주분석이 아니다.** pilot 분리 전이고 fold 도 없으므로 여기서 나온 bank 는
어떤 결과에도 쓰이지 않는다. 확인 대상은 두 가지 — 파이프라인이 실제 BOLD 에서
도는가, 그리고 bank 가 만족해야 할 성질이 실자료에서도 성립하는가.

## K.1 실행

rest 30명 재추출(ok 27 / 제외 2 / skip 1 / 오류 0, 170초) 후
`scripts/h197/13_bank_demo.py`:

```
창 108개, subject 27명
correlations (108, 100, 100)   Fisher-z (108, 4950)
PCA (108, 10)                  transform fingerprint 58da1ba0dc9df563…
bank seed 30009  K=3           bank fingerprint a31fa7cd75e33a7a…
```

`4950 = 100·99/2` 로 edge 수가 맞고, bank seed `30009 = 30000 + 100·0 + 9` 로
계획서 §5 의 규약(outer fit 은 inner_fold=9)과 일치한다.

## K.2 bank 성질 — 전부 성립

| 성질 | 요구 | 실측 |
|---|---|---|
| 대칭 | `S = Sᵀ` | 최대 비대칭 **0.00e+00** (정확히 대칭) |
| 유한 | 모든 원소 유한 | 성립 |
| 비음 | `S ≥ 0` | 최소값 **0.0000**, 성립 |
| 희소화 밀도 | off-diagonal 상위 20% 양수 edge | 세 template 전부 **0.200** (990/4,950) |
| self-loop 정규화 | `S = D^(−1/2)(A+I)D^(−1/2)` | spectral radius **1.0 / 1.0 / 1.0** |

spectral radius 가 정확히 1.0 인 것은 self-loop 를 더한 뒤 대칭 정규화한
행렬의 최대 고유값이 1 이라는 성질 그대로다. 즉 정규화가 명세대로 적용됐다.
행합은 0.534–1.436 범위이고 대각 최소 0.025 로, 정규화 후에도 자기 연결이 살아 있다.

## K.3 T05 — joint ROI permutation 이 spectrum 을 보존한다

null bank(seed 1729)의 spectral radius 도 1.0 / 1.0 / 1.0 이고, 실제 bank 와의
**최대 차이가 1.55e-15** 다. 배정밀도 기계 오차 수준이다.

이것이 matched null 의 요점이다 — null 은 "약한 그래프"가 아니라 **같은 스펙트럼
구조를 가지되 ROI 대응만 뒤섞인** 그래프여야 한다. 그래야 A−C 차이가 그래프의
세기가 아니라 **해부학적 정렬** 때문이라고 말할 수 있다. 실자료에서 이 성질이
기계 오차 수준으로 성립함을 처음 확인했다.

## K.4 관찰 — 군집 크기 불균형

K=3 군집 크기가 **[59, 6, 43]** 로 나왔다. 두 번째 군집이 108창 중 6창뿐이다.

이 시연의 N 이 27명으로 작으므로 그대로 주분석의 예측은 아니다. 다만 **본 적합에서
감시해야 할 지표**이긴 하다. 한 군집이 지나치게 작으면 그 template 은 소수 창의
평균이 되어 routing 이 사실상 2-way 로 퇴화할 수 있다. 계획서는 K=3 을 고정했고
K 민감도는 WI-09 로 이관돼 있으므로 **여기서 K 를 바꾸지 않는다.** 본 적합의
fold 별 군집 크기를 기록해 두고, 퇴화가 실제로 일어나는지는 결과로 판단한다.

## K.5 세 번째 시그니처 실수 (E12 부류, 4회째)

`bank.k()` 로 호출했는데 `k` 는 `@property` 다. AST 목록에서 method 로 보였지만
데코레이터를 확인하지 않았다.

부록 I.3 에서 "가드는 사후 안전망이지 대책이 아니다"라고 적었는데 그대로 반복했다.
이번 실수는 **시연 스크립트에서만** 났고 모듈·시험에는 없다 — 시험이 있는 코드는
이 부류가 통과하지 못한다. 시연/드라이버 스크립트에도 같은 수준의 접합 시험이
필요하다는 것이 이번 교훈이다(`test_wi02_driver.py` 가 그 선례다).

## K.6 남은 것

이 시연은 **fold 없이 전체 rest 로 적합**했다. 실제로는 fit scope 별로
(outer/inner fold, allowed_subjects 제한) 적합해야 하고, 그 경계 검증이 T03·T04 다.
합성으로는 이미 통과했고, 실자료 fold 적합은 WI-03 분할 확정 후다.

---

# 부록 L — 스크립트 접합 시험 설치, E12 부류 종결 (5회차)

## L.1 무엇이 네 번 반복됐나

이번 작업에서 **모듈 함수의 시그니처나 반환 구조를 기억으로 적어** 네 번 깨졌다.

| # | 어디서 | 무엇을 | 실제 |
|---|---|---|---|
| 1 | `10_wi02_extract.py` | `qc_decision(..., task=...)` | 그 인자는 없다 (`residual_dof`) |
| 2 | `10_wi02_extract.py` | `decision["keep"]`, `["reasons"]` | `passed` / `all_reasons` / `primary_reason` |
| 3 | `tests/v2/test_cohort.py` | `folds["pilot"]["n_subjects"]` | `n`, 상위에 `n_subjects_total` |
| 4 | `13_bank_demo.py` | `bank.k()` | `k` 는 `@property` |

**네 건 모두 시험이 없는 스크립트(또는 새로 쓴 시험)에서 났다.** 시험이 붙어 있는
모듈 코드에서는 한 번도 나지 않았다. 부록 G.4 에서 `qc_decision` 하나에만 가드를
붙였고, 부록 I.3 에서 "가드는 사후 안전망이지 대책이 아니다"라고 적었는데도 두 번 더
반복됐다. 스크립트가 시험 밖에 있다는 것이 구조적 원인이다.

## L.2 설치한 것 — `tests/v2/test_h197_scripts.py` (44건)

**전 스크립트 일괄 검사** (`scripts/h197/*.py` 전부에 parametrize):

* 적재만으로 깨지지 않는가 — import 시점 오류를 전부 잡는다
* 모듈 docstring 이 있는가
* `if __name__ == "__main__"` 가드가 있는가 (없으면 적재가 부작용을 낸다)

**접합부 계약 고정** — 위 네 건을 각각 직접 검사한다:

* `GraphBank.k` 가 `property` 인지 `inspect.getattr_static` 으로 확인
* `qc_decision` 에 `residual_dof` 가 있고 `task` 가 **없는지**, 반환 키 집합이 정확히
  `{passed, all_reasons, primary_reason}` 인지
* `build_folds` 에 `n_subjects_total` 이 있고 `pilot` 에 `n` 이 있으며
  `n_subjects` 가 **없는지**
* `build_bank`·`fit_transform_on_training_rest`·`make_null_bank`·`write_jsonl` 의
  인자 이름, `bank_seed(0, 9) == 30009`

**`13_bank_demo.py` 를 합성 자료로 통째 실행** — 12명 × 4창 = 48창 fixture 를
만들어 `main()` 을 argv 로 호출하고, 실자료에서 확인했던 성질을 그대로 검사한다:
FC (48,100,100) → Fisher-z (48,4950) → PCA (48,10), bank seed 30009,
대칭 오차 < 1e-12, off-diagonal 밀도 0.20 ± 0.01, spectral radius 1.0 ± 1e-9,
**joint permutation 의 spectrum 차이 < 1e-9**. 빈 manifest 는 종료 코드 1.

이제 이 부류는 **실자료 없이 suite 에서 잡힌다.** `13_bank_demo.py` 를 처음 돌릴 때
났던 `bank.k()` 오류는 지금 코드에 다시 넣으면 시험 두 건이 즉시 깨진다.

## L.3 Wave 2 — ds002790 이 아직 시작되지 않은 이유 (확인함)

4회차까지 PIOP2 subject 가 0 이라 "받는 순서겠거니" 하고 넘겼는데, 이번에
**근거를 확인했다.** 로그 첫 줄과 프로세스 명령줄을 읽었다:

```
=== ds002785 ===
  selected: 1250 files, 121.0 GiB
  downloading 1202 files (119.0 GiB), skipping 48 already complete
ds002790 언급 횟수: 0
명령줄: python -u 06_wave2_fetch_bold.py --dest … --listing-cache … --jobs 24
```

`--datasets` 를 주지 않았고, 스크립트의 기본값은
`w1.DATASETS = ["ds002785", "ds002790"]` 이며 `for ds in args.datasets:` 로 두
dataset 을 차례로 돈다(`06_wave2_fetch_bold.py:96, 111`). 즉 **ds002785 가 끝나면
ds002790 이 자동으로 이어진다.** 개입할 것이 없다.

현재 ds002785 는 980/1220 파일(102 GiB / 121.0 GiB)로 약 84% 다. 남은 ds002790
88.7 GiB 를 더하면 완료까지 약 5시간 반으로 추정한다(실측 약 20 GiB/h 기준).

## L.4 갱신된 규모

| 항목 | 부록 J | 현재 |
|---|---:|---:|
| 시험 파일 | 18 | **19** |
| 시험 함수 | 322 | **336** |
| h197 수집·통과 | 364 | **408** |
| 신규 failure | 0 | **0** |
| 미커버 수용시험 T-ID | 0 | **0** |

수집 408 과 함수 336 의 차이 72 는 스크립트 parametrize 확장분이다
(파이썬 스크립트 수 × 3종 검사).

---

# 부록 M — `split` CLI 본체와 PIOP1 자동 착수 watcher (6회차)

## M.1 대기 시간을 없앤다 — `14_watch_and_extract_piop1.sh`

Wave 2 는 두 dataset 을 **차례로** 받는다. 6회차 시점에 ds002785 는 1220/1250 파일
(122 GiB / 121.0 GiB 목표)로 사실상 끝났고, ds002790 의 88.7 GiB 가 남아 있었다.
PIOP1 재추출은 PIOP2 를 기다릴 이유가 없으므로 **겹쳐 돌리면 그만큼 총 시간이 준다**
(PIOP1 3개 조합 약 50분 vs ds002790 약 4.5시간).

문제는 착수 시점이 내 점검 주기(60분)에 묶인다는 것이었다. 그래서 감시 스크립트를
h197 에 걸었다.

* 완료 판정을 **로그에 `=== ds002790 ===` 가 나타나는 것**으로 한다. fetcher 가 다음
  dataset 으로 넘어갔다는 뜻이라 파일 수를 세는 것보다 모호하지 않다. 안전장치로
  남은 `.part` 가 0인지도 함께 본다.
* 그 즉시 ds002785 의 3개 조합(emo 2.0 / WM 2.0 / rest 0.75)을 순차 추출하고,
  이어서 창 manifest(target 2종만)를 만든다.
* 2시간 안에 조건이 성립하지 않으면 추출을 **시작하지 않고** 실패로 기록한다 —
  조건이 어긋난 채로 돌리는 것보다 낫다.
* `setsid` + PID 파일. 로그는 `watch_piop1.log`, 조합별 로그는 `derivatives_v2/`.

## M.2 `mobse-v2 split` 본체 (두 번째로 구현된 하위 명령)

`cohort.py` 의 `subjects.jsonl` 을 받아 `folds.json` 을 쓴다. 설계에서 지킨 것:

* **적격 판정을 다시 하지 않는다.** `cohort.py` 가 계획서 §3.3 기준으로 매긴
  `eligible` 을 그대로 쓴다. 두 곳에서 판정하면 언젠가 어긋난다.
* **분할 알고리즘·seed 는 `splits.py` 가 단일 출처다.** CLI 는 config 에서 읽은
  값을 넘길 뿐이고, config 는 이미 코드 상수와 대조돼 있다(부록 E.1).
* `group_id` 는 cohort 가 정한 것을 그대로 쓴다 — 관계 metadata 부재로 subject 와
  같다(개정 P4 / U10).
* **disjoint 를 문서로만 두지 않는다.** pilot↔main_pool, outer test↔train,
  inner val↔train↔outer test 를 `verify_disjoint()` 로 실제로 확인한 뒤에만 쓴다.
* 이미 있는 `folds.json` 은 덮어쓰지 않는다(지침서 §2).
* 적격 0명이면 실패시킨다 — "임의 증원 대신 제한을 보고한다"(지침서 WI-03).

### M.2.1 독립 경로가 같은 수를 냈다

합성 subjects 164명으로 돌린 결과:

```
pilot 32 (target 32)   main_pool 132
outer test [27, 27, 26, 26, 26]   합 132
config_hash 85556f56   split_hash 9897e07b79c47a8c…
```

이 수치는 **부록 B.2 에서 코호트 상한을 산정할 때 독립적으로 계산했던 값과 같다**
(PIOP1 복합 상한 164 → pilot 32, main 132, outer test 27/27/26/26/26). 두 경로가
일치한다는 뜻이고, 한쪽을 고쳐도 다른 쪽이 어긋나면 시험이 잡는다.

시험 18건(`tests/v2/test_cli_split.py`)이 위 성질을 각각 고정한다. 특히
`test_every_main_subject_is_in_exactly_one_outer_test` 는 각 main subject 가 정확히
한 outer test fold 에만 있는지를 세어 확인한다 — 지침서 WI-07 의 완료 기준이다.

## M.3 갱신된 규모

| 항목 | 부록 L | 현재 |
|---|---:|---:|
| 시험 파일 | 19 | **20** |
| 시험 함수 | 336 | **353** |
| h197 수집·통과 | 408 | **425** |
| 구현된 CLI 하위 명령 | 1 (`validate`) | **2 (`validate`, `split`)** |
| 신규 failure | 0 | **0** |

남은 CLI 하위 명령 `prepare`·`fit`·`evaluate`·`report` 는 WI-02 재추출 산출물과
학습 루프가 있어야 본체가 생긴다.

---

# 부록 N — watcher 동작, PIOP2 사전 점검 통과, PIOP1 실추출 착수 (7회차)

## N.1 watcher 의 안전장치가 실제로 일했다

`14_watch_and_extract_piop1.sh` 는 두 조건을 함께 봤다 — 로그에
`=== ds002790 ===` 출현 **그리고** 남은 `.part` 0. 실제 로그:

```
16:21:34  ds002790 구간 진입 감지. ds002785 파일 1250, 남은 .part 24
16:21:34    .part 가 남아 있어 더 기다린다
   … 27분간 24 → 17 → 12 → 7 → 3 → 1 → 0
16:48:36  ds002785 완료 확인: 1250 파일. WI-02 추출을 시작한다
```

**두 번째 조건이 없었으면 24개 파일이 아직 내려오는 중에 추출을 시작했을 것이다.**
fetcher 는 다음 dataset 의 목록을 먼저 찍고 이전 dataset 의 in-flight 전송을
마무리한다 — 로그 한 줄만 믿으면 안 되는 구조였다. 27분을 더 기다렸고, 그 결과
추출은 1250 파일이 모두 확정된 상태에서 시작했다.

## N.2 PIOP1 emomatching 실추출 — 첫 전량 결과

```
ok 183 / 제외 25 / skip 8 / 오류 0   (5분 54초, 216 subject 디렉터리)
```

`183 + 25 + 8 = 216` 으로 subject 디렉터리 수와 맞는다. skip 8 은 emomatching run
자체가 없는 subject 다(PIOP1 emo 보유 208 = 216 − 8, 부록 A 의 Wave 1 감사와 일치).
**오류 0** — 216 run 전부가 경로 조립·nuisance 설계·QC·창 절단을 통과했거나 QC
사유와 함께 정상적으로 제외됐다.

제외율 25/208 ≈ 12.0% 는 run 단위 FD 기준 적용 결과이며, 부록 B.2 의 복합 상한
추정(PIOP1 164/216 ≈ 24% 제외, **세 run 모두** 통과 기준)과 모순되지 않는다 —
그쪽은 세 task 교집합이고 이쪽은 한 task다.

workingmemory·restingstate 는 이어서 진행 중이다.

## N.3 PIOP2 사전 점검 통과 — 6회차 동안 막혔던 항목

ds002790 이 내려오기 시작해(40 subject) 드디어 실행 검증을 했다.

| dataset / task | TR | 결과 |
|---|---:|---|
| ds002790 / emomatching | 2.00 | ok 2 / 제외 2 / skip 1 / **오류 0** |
| ds002790 / workingmemory | 2.00 | ok 5 / 제외 0 / skip 0 / **오류 0** |
| ds002790 / restingstate | 2.00 | ok 3 / 제외 2 / skip 0 / **오류 0** |

**PIOP2 restingstate 가 `acq-seq`** 인 것(PIOP1 은 `acq-mb3`)이 실제 실행에서
확인됐다. 부록 I.1 에서 파일명 전수 대조로만 검증했던 항목이 이제 실행으로
검증됐다. 6개 조합 전부 실행 검증 완료다.

## N.4 `15_build_subjects.py` — WI-03 코호트 산출

`cohort.py` 가 계산하고 이 스크립트는 읽고 쓴다. 설계에서 막은 것:

* **세 task manifest 를 모두 요구한다.** rest 를 빼고 돌리면 계획서 §3.3 기준상
  전원이 `restingstate_missing` 으로 부적격이 되는데, 그걸 조용히 내지 않고
  실패시킨다. 부록 J.3 의 실자료 시연에서 실제로 그 상태가 나왔던 적이 있다.
* dataset 이 섞이면 거부한다 — cohort 는 dataset 단위다.
* 기존 `subjects.jsonl` 은 덮어쓰지 않는다(지침서 §2).
* 부적격 subject 는 `exclusions.jsonl` 에 **모든 사유**와 우선 사유를 함께 쓴다.

계약 시험 5건을 `tests/v2/test_h197_scripts.py` 에 추가했다(부록 L 의 방침 적용
— 새 스크립트에는 반드시 접합 시험을 붙인다).

## N.5 갱신된 규모

| 항목 | 부록 M | 현재 |
|---|---:|---:|
| h197 수집·통과 | 425 | **433** |
| 신규 failure | 0 | **0** |
| 6개 조합 실행 검증 | 3/6 (PIOP1만) | **6/6** |
| CLI 구현 | 2/6 | 2/6 |

---

# 부록 O — PIOP1 전량 추출과 그 과정에서 드러난 두 문제 (8회차)

## O.1 PIOP1 3개 조합 전량 추출 완료

watcher 가 16:48:36 에 착수해 17:21:09 에 끝났다. **32분 33초.**

| 조합 | ok | 제외 | skip | 오류 | 소요 |
|---|---:|---:|---:|---:|---:|
| ds002785 / emomatching | 183 | 25 | 8 | 0 | 5분 54초 |
| ds002785 / workingmemory | 175 | 29 | 9 | **3** | 8분 21초 |
| ds002785 / restingstate | 187 | 23 | 6 | 0 | 18분 17초 |

창 manifest: **1,432 레코드** (emo 732 + WM 700 = 183×4 + 175×4), sha256 `ed92adce978796c8…`.

각 조합의 세 수의 합이 216(subject 디렉터리 수)과 맞고, skip 수(8/9/6)는 해당
task run 이 없는 subject 수로 Wave 1 감사의 보유 수(208/207/210)와 일치한다.
restingstate 가 오래 걸리는 것은 TR 0.75초·480 volume 때문이다(약 5초/run).

## O.2 문제 1 — 'error 3건'의 정체가 서로 달랐다 (E14)

workingmemory 의 오류 3건을 열어 보니 **세 건이 다른 종류**였다.

| subject | 내용 | 실제 성격 |
|---|---|---|
| sub-0029 | `a_comp_cor_00: VarianceExplained 가 없다` | 계획서가 예상한 **자료 조건** |
| sub-0134 | `Retained aCompCor 가 1개뿐이다 (필요 5)` | 계획서가 예상한 **자료 조건** |
| sub-0171 | `OSError: [Errno 5] Input/output error` | **진짜 고장** |

앞의 두 건은 계획서 §3.2 가 "선택 정의에 맞는 5개가 없으면 임의 다른 열로
대체하지 않는다"고 **미리 정해 둔 상황**이다. 결함이 아니라 예상된 제외 사유다.
그런데 내 드라이버는 모든 예외를 `status: "error"` 로 묶어 버렸다.

**이게 왜 문제인가.** 셋을 같은 error 로 세면 **진짜 고장이 정상적인 제외 건수에
묻힌다.** 실제로 이번에 "error 3"만 보고 넘어갔다면 디스크 문제(O.3)를 못 봤을
것이다. 지침서가 "실행 실패는 실패로 기록하고 결과가 나쁜 fit 을 실패로
재분류하지 않는다"고 한 것의 반대 방향 요구 — 고장과 예상된 제외를 섞지 않는 것 —
도 같이 지켜야 한다.

**고친 방법.** `ExtractDataError(ExtractError)` 를 두어 계획서가 예상한 자료
조건(aCompCor 부족·VarianceExplained 부재·constant ROI·비구조적 FD 결측)에 쓰고,
구조적 실패(형상 불일치·parcel 결손·파일 손상)는 `ExtractError` 로 남겼다.
드라이버는 `ExtractDataError` 를 `status: "excluded"` + `data_condition:` 접두
사유로 기록한다. 시험 6건을 추가해 두 부류가 섞이지 않게 고정했다.

즉 이제 **`error` 는 "고쳐야 할 것이 있다"만 의미한다.**

## O.3 문제 2 — h197 의 RAID1 이 degraded 이고 남은 디스크가 배드섹터를 만든다

sub-0171 의 I/O 오류를 파고든 결과다. **이 항목은 자료 분석이 아니라 하드웨어
문제이며, 이 프로젝트의 자료 209 GiB 가 그 위에 있다.**

```
md0 : active raid1 sda1[0]
      5860389440 blocks super 1.2 [2/1] [U_]
```

`[2/1] [U_]` — RAID1 이 **2개 중 1개만** 살아 있다. 이중화가 없다. 그리고 남은
sda1 이 읽기 오류를 낸다:

```
sd 0:0:0:0: [sda] Sense Key : Medium Error
sd 0:0:0:0: [sda] Add. Sense: Unrecovered read error - auto reallocate failed
blk_update_request: I/O error, dev sda, sector 65206280
```

부팅 이후 I/O 오류 **236건**이고 최근까지 계속 난다 — 부팅 후 380–383시간에
134건, 503시간 20건, 522시간 79건, 562시간 3건(현재 563시간, 약 1시간 전).

`smartctl`·`mdadm --detail` 은 sudo 가 필요해 확인하지 못했다. **확인하지 못한
것으로 명시한다.**

**현재 자료 상태.** PIOP1 전량 추출이 216 subject × 3 task = **648 run 을 전부
읽었고** 그 중 I/O 오류는 sub-0171 workingmemory **1건**, 재시도하니 정상적으로
읽혔다(파일 재검증: mask·BOLD 모두 정상 적재, shape (65,77,60,162)). 사실상
전수 읽기 검증이 된 셈이다. 다만 이것은 **"지금은 읽힌다"이지 "안전하다"가
아니다.** 이중화가 없는 상태에서 배드섹터가 늘고 있다.

정기 점검마다 I/O 오류 누적 수를 함께 기록한다.

## O.4 sub-0171 재추출

`ExtractDataError` 분리를 반영한 코드로 workingmemory 전량을 다시 돌렸다.
이렇게 하면 (a) sub-0171 이 재시도되고 (b) 앞의 두 자료 조건이 `excluded` 로
올바르게 기록된다.

---

# 부록 P — 실자료 코호트와 분할: **적격 153명** (9회차)

> **이 부록의 수치는 개정 P7 적용 전 값이며 부록 U 로 대체되었다.**
> 적격 153 → **157**, pilot 30 → **31**, main 123 → **126**,
> outer test [25,25,25,24,24] → **[26,25,25,25,25]**,
> split_hash `586f1c50…` → **`ace5f4a4…`**, WI-07 기준 11,808/984 → **12,096/1,008**.
> 절차와 검산 논리는 그대로 유효하므로 삭제하지 않고 보존한다.

## P.1 sub-0171 복구 확인

S3 재다운로드(sha256 일치) 뒤 workingmemory 를 다시 돌렸다.

| | ok | 제외 | skip | error |
|---|---:|---:|---:|---:|
| 1차 (구버전 코드) | 175 | 29 | 9 | **3** |
| 2차 (ExtractDataError 분리 + 파일 복구) | **176** | **31** | 9 | **0** |

차이가 정확히 설명된다: ok +1 은 sub-0171 복구, 제외 +2 는 sub-0029·sub-0134 가
`error` → `excluded`(data_condition)로 재분류된 것. `176+31+9 = 216` ✓.

정본을 교체하고 창 manifest 를 다시 만들었다 — **1,436 레코드**
(emo 732 + WM 704), sha256 `3c8bb84321965c12…`.

emomatching·restingstate 정본은 구버전 코드로 만들어졌으나 둘 다 error 0 이었으므로
`ExtractDataError` 분리의 영향이 없다(이 변경은 error→excluded 재분류일 뿐 ok 판정을
바꾸지 않는다). 최종 release 의 WI-02 정식 실행은 Wave 2 완료 후 6개 조합 전량이므로
그때 전부 같은 코드로 다시 돈다.

## P.2 코호트 — 216명 중 **적격 153명**

```
[cohort] subject 216, 적격 153   (ds002785 153/216)
task 별 ok: emomatching 183, workingmemory 176, restingstate 187
```

제외 사유를 규칙별로 묶으면(subject 당 중복 가능):

| 규칙 | 건수 |
|---|---:|
| `window_spikes>3` | **118** |
| `window_spike_ratio>0.1` | **91** |
| `mean_fd>0.2` | 47 |
| `run_spike_ratio>0.1` | 26 |
| 파일 없음 (해당 task run 미보유) | 23 |
| `data_condition` (aCompCor 관련) | 2 |

## P.3 예측 164 vs 실측 153 — 왜 다른가

부록 B.2 의 **복합 상한 164** 는 `run 단위 mean FD ≤ 0.2` + `aCompCor ≥ 5` 두
기준만으로 산정한 값이다. 당시에는 TR 이 확정되지 않아 고정 창 경계를 정할 수
없었고, 따라서 **창 단위 FD 기준을 계산에 넣지 못했다.**

실측에서 그 창 단위 기준이 압도적이다 — `window_spikes>3` 118건 +
`window_spike_ratio>0.1` 91건 = **209건**으로, run 단위 기준(47+26 = 73건)의
약 2.9배다. run 전체 평균 FD 는 통과하지만 특정 창에 spike 가 몰린 subject 가
많다는 뜻이다.

즉 **예측이 틀린 것이 아니라 상한이었다.** 부록 B.2 는 이 값을 "복합 상한
(upper bound)"으로 명시했고 `153 ≤ 164` 로 일관된다. 계획서 §3.3 의 "196명은
상한 후보이고 최종 N이 아니다"도 그대로 성립한다.

### P.3.1 부수 관찰 — 세 task 의 QC 실패는 독립이 아니다

세 task 의 개별 통과율이 독립이라면 교집합은
`216 × (183/216) × (176/216) × (187/216) ≈ 129.1명` 이어야 한다. 실제는 **153명**으로
**24명 많다.**

머리를 많이 움직이는 subject 가 세 task 에서 함께 실패하는 양의 상관이 있다는
뜻이며, 생리적으로 예상되는 결과다. 교집합이 독립 가정보다 크므로 코호트 측면에서는
유리한 방향이다. 이 값은 **관찰이지 가정이 아니다** — 독립성을 어디에도 쓰지 않는다.

## P.4 분할 — CLI `split` 실자료 첫 실행

```
subjects_total  216      subjects_eligible  153      n_groups  153
pilot_n         30       pilot_target  30
main_pool_n     123
outer_test      [25, 25, 25, 24, 24]   합 123
config_hash     85556f56
split_hash      586f1c50895a98e1…
```

`pilot = min(32, ⌊0.2 × 153⌋) = min(32, 30) = 30` 으로 계획서 §4-2 의 공식과 맞고,
outer test 합이 main pool 과 정확히 일치한다. `verify_disjoint()` 가
pilot↔main_pool, outer test↔train, inner val↔train↔outer test 를 모두 통과했다.

### P.4.1 확정된 WI-07 완료 기준 수치

main N = 123 에서:

| 항목 | 기대 수 |
|---|---:|
| window prediction rows | **11,808** (123 × 2 task × 4 창 × 3 seed × 4 cell) |
| run prediction rows | **984** |
| primary checkpoints | **60** (4 cell × 5 outer × 3 seed) |

이 수치가 WI-07 의 완료 판정 기준이 된다.

## P.5 아직 정본이 아니다

이 분할은 **PIOP1 선행 실행**이다. Wave 2 의 ds002790 이 완료되면 6개 조합을 같은
코드로 전량 다시 돌리고, 그 결과로 만든 분할이 release 정본이 된다. 지금 값은
파이프라인이 실자료에서 끝까지 도는 것과 규모를 확인한 것이다.

---

# 부록 Q — 디스크 포화와 작업 억제 결정 (10회차)

## Q.1 측정값

```
load average: 57.10, 49.87, 44.08
iowait: 62%   (vmstat, blocked 프로세스 11개)
Wave 2: 800/1340, 51.2 GiB / 88.7 GiB, 4.7 MiB/s (초기 6.3 → 현재 4.7)
md0: [2/1] [U_]  변화 없음, FAIL 0
```

D 상태(무중단 I/O 대기)에 커널 스레드 `md0_raid1` 과 `jbd2/md0-8`(ext4 저널)이
들어가 있다. **배열 스레드와 저널이 함께 막혀 있다는 것은 병목이 상위 계층이
아니라 디스크 자체라는 뜻이다.** 불량 섹터 재시도가 대기열을 잡고 있는 양상과
일치한다.

`dmesg` I/O 오류 누적은 236 → 230 으로 **줄었는데, 이것은 개선이 아니라 링 버퍼
회전이다.** 절대 누적치를 지표로 쓸 수 없다는 뜻이므로, 앞으로는
`Current_Pending_Sector`(SMART) 를 지표로 삼는다 — 단 sudo 가 필요해 자동 점검에
넣을 수 없다. **이 한계를 명시한다.**

## Q.2 내가 남긴 부하 정리

9회차에서 돌린 `du -sh ds002790` 이 **72분간 D 상태로 묶여 있었다.** 결과도
못 받고 디스크만 두드리고 있었다. 종료시켰다.

교훈: 약해진 디스크에서 `du`·`find` 같은 **전 트리 순회는 비용이 비대칭적으로
크다.** 상태 점검은 `df`(수퍼블록만 읽음)와 로그 tail 로 충분하며, 앞으로 정기
점검에서 `du -sh` 를 쓰지 않는다.

## Q.3 작업 억제 결정

디스크가 포화 상태이고 pending 1,942 섹터가 있는 상황에서, **내가 만드는 추가
부하를 줄이는 쪽으로 판단했다.**

| 작업 | 결정 | 근거 |
|---|---|---|
| Wave 2 다운로드 | **계속** | 60% 진행, 재개 가능, 중단해도 디스크가 나아지지 않음 |
| PIOP1 emo·rest 재추출(정본 통일) | **보류** | 24분간 무거운 읽기. 얻는 것은 코드 일관성뿐이고 결과는 동일함이 논리적으로 보장됨(둘 다 error 0) |
| Wave 2 전량 해시 검증 | **보류** | 209 GiB 재독. 해시 기록이 없어 가치도 제한적 |
| `du`·`find` 전 트리 순회 | **중단** | Q.2 |
| PIOP2 추출 | Wave 2 완료 후 진행 | 필수 경로 |

즉 **필수 경로만 돌리고 편의성·일관성 목적의 재실행은 하드웨어 조치 이후로
미룬다.** 이 결정은 결과의 정확성을 낮추지 않는다 — 보류한 항목 중 수치를 바꾸는
것은 없다.

## Q.4 함께 돌고 있는 다른 작업

부하 상위는 `sglang::schedul`(97.3% CPU, 메모리 10%, 1시간 17분 경과)로 이
프로젝트와 무관한 LLM 서버다. 디스크 대기열에도 이 프로젝트 밖의 작업이 섞여
있다. **h197 은 공용 호스트이므로 관측된 부하 전부를 이 프로젝트에 귀속시키지
않는다.**

---

# 부록 R — 부록 Q 정정: 병목은 디스크가 아니었다 (11회차)

## R.1 정정 대상

부록 Q.1 에 이렇게 적었다.

> 배열 스레드와 저널이 함께 막혀 있다는 것은 병목이 상위 계층이 아니라 **디스크
> 자체**라는 뜻이다.

**이 일반화는 틀렸다.** 한 시간 뒤 재측정:

| | 10회차 | 11회차 |
|---|---:|---:|
| load average | 57.10 | **1.89** |
| iowait | **62%** | **0%** |
| D 상태 프로세스 | 11 | **0** |
| Wave 2 처리율 | 4.7 MiB/s | **4.5 MiB/s** |
| sglang LLM 서버 | 실행 중 | **여전히 실행 중** |

## R.2 무엇이 실제로 일어났나

`load 57 → 1.89`, `iowait 62% → 0%` 로 극적으로 떨어졌는데 **Wave 2 처리율은
사실상 그대로다(4.7 → 4.5 MiB/s).** sglang 도 여전히 돌고 있다.

따라서:

1. **다운로드는 애초에 디스크 제약이 아니었다.** iowait 이 62%에서 0%로 바뀌는
   동안 처리율이 변하지 않았다면, 병목은 상류(네트워크·S3)다.
2. **D 상태 무리는 전 트리 메타데이터 순회가 만든 것이었다.** 72분간 묶여 있던
   내 `du -sh`(Q.2)와 동시에 돌던 `dumpe2fs` 가 대기열을 잡았고, 그 뒤로 다른
   프로세스들이 줄줄이 막혔다. `du` 를 종료시키자 대기열이 풀렸다.
3. 즉 **"디스크가 느리다"가 참인 범위는 전 트리 메타데이터 순회이고, 순차 대용량
   읽기·쓰기에는 해당하지 않았다.** 나는 전자에서 관측한 것을 후자까지 일반화했다.

## R.3 Q.3 의 결정은 유지하되 근거를 바꾼다

부록 Q.3 에서 PIOP1 재추출과 Wave 2 해시 검증을 보류했다. **결정 자체는 유지하나
근거가 달라진다.**

| | 부록 Q 의 근거 (틀림) | 정정된 근거 |
|---|---|---|
| PIOP1 emo·rest 재추출 보류 | 디스크가 포화 상태라 | **pending 1,942 섹터 위에서 약 100 GiB 를 추가로 읽을 이유가 없다.** 결과는 동일함이 논리적으로 보장되므로 위험만 늘린다 |
| Wave 2 해시 검증 보류 | 디스크 부하 | **비교할 기준 해시가 없어 손상을 탐지할 수도 없다.** 209 GiB 를 읽고 얻는 것이 없다 |
| `du`·`find` 순회 중단 | 디스크 부하 | **유지 — 이것만은 원래 근거가 옳았다.** 실측으로 72분 블로킹을 확인했다 |

부하가 아니라 **불필요한 읽기를 줄인다**가 옳은 표현이다. 부하는 이미 정상으로
돌아왔고, 위험은 부하가 아니라 복구 불가 섹터 1,932개다.

## R.4 교훈

한 시점의 `iowait`·`load` 스냅샷으로 원인을 단정했다. 두 수치는 **누가 무엇을
하고 있었는지**에 따라 크게 흔들리는데, 공용 호스트에서는 특히 그렇다. 부록 Q.4 에
"관측 부하 전부를 이 프로젝트에 귀속시키지 않는다"고 적어 놓고도, 바로 위
Q.1 에서는 원인을 디스크로 단정했다 — **같은 문서 안에서 앞뒤가 맞지 않았다.**

부하 판단은 **변화량**으로 해야 한다. 이번에 결정적이었던 것은 "iowait 이 62%에서
0%로 떨어지는 동안 처리율이 안 변했다"는 대조였지, 어느 한 시점의 절대값이
아니었다.

## R.5 현재 상태

```
Wave 2: 1060/1340, 68.4 GiB / 88.7 GiB, 4.5 MiB/s, ETA 76분, FAIL 0
md0: [2/1] [U_] 변화 없음   load 1.89   iowait 0%   D 상태 0
```

17.2 GiB/h 로 안정적이며, 다음 점검 창 안에 완료될 전망이다.

---

# 부록 S — PIOP2 처리 watcher와, 하마터면 만들 뻔한 프로토콜 밖 산출물 (12회차)

## S.1 잡은 오류 — PIOP2 에 `split` 을 돌리려 했다

12회차 점검 계획에 이렇게 적어 두었다.

```
PYTHONPATH=. python -m mobse.v2.cli split --config configs/redesign_v1/external.yaml \
    --subjects .../cohort_piop2/subjects.jsonl --output-dir .../splits_piop2
```

**실행 직전에 계획서 §9 를 다시 읽고 멈췄다.**

> PIOP1 main pool(pilot 제외)에서 같은 3-fold selection 규칙으로 config/E를 정하고
> bank·변환·모델을 최종 fit한다. **PIOP2 rest·labels·성능으로 fit/선택/calibration
> 하지 않는다.** PIOP2는 같은 QC·window 규칙과 task pairing을 적용하고 cohort
> 차이·제외 수를 보고한다.

PIOP2 는 **fold 로 나누는 대상이 아니다.** config 와 E 는 PIOP1 main pool 에서
정해지고, PIOP2 는 그 잠긴 모델을 한 번 평가받는 held-out 코호트다. 여기에
5-fold outer CV 를 만들면 **프로토콜에 없는 산출물**이 release 안에 남고, 나중에
누군가(나 자신 포함) 그것을 의미 있는 분할로 오인할 수 있다.

`external.yaml` 이라는 파일 이름이 "external 용 분할을 만들라"처럼 읽혔던 것이
착각의 출발점이다. 그 config 의 용도는 **외부 평가 실행의 설정**이지 분할 생성이
아니다. `splits.EXTERNAL_SEED` 도 "외부 최종 선택 seed"이지 PIOP2 를 쪼개는
seed 가 아니다.

## S.2 방지 장치

`tests/v2/test_h197_scripts.py` 에 4건을 추가했다.

* `test_piop2_watcher_does_not_split` — PIOP2 watcher 소스에 `cli split` 과
  `splits_piop2` 가 **없어야** 하고, 왜 분할하지 않는지 근거가 적혀 있어야 한다.
* `test_watchers_require_zero_part_files` — 두 watcher 모두 완료 판정에 `.part`
  검사와 무한 대기 방지(`MAX_WAIT_SEC`)가 있어야 한다.
* `test_watchers_build_windows_from_target_tasks_only` — 창 manifest 호출부에
  `restingstate` 가 들어가면 안 된다.

시험이 "이 코드가 무엇을 하는가"가 아니라 **"이 코드가 무엇을 하면 안 되는가"**를
고정하는 형태다. 프로토콜 위반은 대개 기능 추가로 나타나므로 이 방향이 맞다.

## S.3 `16_watch_and_process_piop2.sh`

ds002790 완료 즉시 **추출 3종 → 창 manifest(target 2종) → 코호트**까지 하고
**멈춘다.**

완료 판정은 **fetch 프로세스 종료 AND 남은 `.part` 0** 두 조건을 모두 본다.
7회차에서 로그의 구간 진입만 믿었다면 24개가 전송 중인 상태로 시작했을 것이므로
(부록 N.1), 이번에는 프로세스 생존 여부까지 함께 본다 — ds002790 이 마지막
dataset 이라 "다음 구간 진입" 신호가 아예 없기 때문이다.

## S.4 현재

```
Wave 2: 1320/1340, 85.8 GiB / 88.7 GiB, 4.6 MiB/s, ETA 11분, FAIL 0
watcher: 대기 중 (fetch alive=1, .part=47)
load 2.45   suite 444 passed / 0 failed
```

---

# 부록 T — PIOP2 완료와, 그 과정에서 드러난 QC 과엄격 (13회차)

## T.1 Wave 2 완료, PIOP2 전량 처리

watcher 가 자동 착수해 21분 만에 3개 조합을 끝냈다.

| 조합 | ok | 제외 | skip | error |
|---|---:|---:|---:|---:|
| ds002790 / emomatching | 204 | 18 | 4 | 0 |
| ds002790 / workingmemory | 214 | 10 | 2 | 0 |
| ds002790 / restingstate | 203 | 19 | 2 | **2** |

창 manifest **1,672 레코드**, 코호트 **226명 중 적격 189**.

`Wave 2 전체: ds002785 1,250 파일 130.0 GB + ds002790 1,340 파일 = FAIL 0.`

## T.2 error 2건 — 또 분류가 틀렸다 (E15)

```
ds002790:sub-0141  parcel 27 가 brain mask 안에서 비었다
ds002790:sub-0180  parcel 10 가 brain mask 안에서 비었다
```

이 subject 들의 fMRIPrep brain mask 가 Schaefer parcel 하나를 덮지 못한다. 그런데
계획서 §3.3 은 이것을 **제외 사유로 명시**한다 — "BOLD/FC nonfinite, constant ROI,
**100 ROI 불일치**, confound 정렬 오류, 잔차 자유도 부족, 필요한 구간 누락은 run
제외다."

즉 결함이 아니라 예상된 자료 조건인데 `ExtractError` 로 올라가 `status: error` 가
됐다. 부록 O.2 에서 같은 부류를 고쳐 놓고 **이 경로는 빠뜨렸다.** `ExtractDataError`
로 바꿨다.

다만 구분은 유지한다 — **atlas 재표본화 단계의 parcel 결손은 여전히
`ExtractError`** 다. 그쪽은 특정 subject 가 아니라 atlas·격자 자체의 문제이므로
전 subject 에 영향을 주는 구조적 결함이다.

## T.3 더 큰 것 — spike 허용치를 계획서보다 엄격하게 적용하고 있었다 (개정 P7)

PIOP2 적격률(189/226 = 83.6%)이 PIOP1(153/216 = 70.8%)보다 눈에 띄게 높아 원인을
보다가 발견했다.

계획서 §3.3:

> 각 run 전체 mean FD≤0.2 mm, 전체 및 각 고정 window에서 FD>0.5 mm **비율≤10%** 를
> 주 기준으로 한다. … task의 30 원본 frames 구간에서는 **최대 3개**까지 허용한다.
> **rest는 native frame 수로 계산한다.**

**3/30 = 0.10 으로 비율 상한과 정확히 같다.** 즉 "최대 3개"는 별도의 규칙이 아니라
**30 frame 창에서 10% 비율 규칙을 개수로 표현한 것**이다. 그리고 "rest는 native
frame 수로 계산한다"는 창 길이가 다르면 그 길이로 계산하라는 지시다.

그런데 내 `qc_decision` 은 **창 길이와 무관하게 절대 3개**를 적용했다. 실제 창 길이:

| | TR | 60초 창의 원본 frame | 비율 규칙 허용 | 내 구현 허용 | 실효 비율 |
|---|---:|---:|---:|---:|---:|
| task (양 코호트) | 2.00 | 30 | 3.0 | 3 | 10.0% |
| PIOP2 rest | 2.00 | 30 | 3.0 | 3 | 10.0% |
| **PIOP1 rest** | **0.75** | **80** | **8.0** | **3** | **3.75%** |

**PIOP1 restingstate 에만 2.7배 엄격한 기준이 적용되고 있었다.** PIOP2 rest 는 TR
2초라 영향이 없다 — 이것이 두 코호트 적격률 차이의 한 원인이다.

### T.3.1 개정 P7

허용 개수를 창의 관측 frame 수에 비례 조정한다.

```
허용 = 3 × (관측 frame 수 / 30)
```

30 frame 창에서 3 으로 **종전과 완전히 동일**하고, 80 frame 창에서 8 이 되어 비율
상한과 일치한다. 계획서 §3.3 본문과 §11 표에 P7 로 기록했다.

**이것은 기준 완화가 아니다.** 계획서가 정한 10% 비율 기준을 정확히 적용하는
것이고, 종전 구현이 그 기준보다 엄격했다. TR 2초 창의 판정은 한 건도 바뀌지 않는다.
시험 `test_scaled_allowance_matches_ratio_rule_at_any_length` 가 20·30·40·80·120
frame 전부에서 두 규칙이 같은 경계를 주는지 확인한다.

### T.3.2 왜 놓쳤나

`WINDOW_SPIKE_ALLOWANCE = 3` 을 상수로 박으면서 **그 3이 어떤 창 길이를 전제한
값인지 적지 않았다.** 계획서 문장에는 "30 원본 frames 구간에서"가 분명히 있었는데
상수로 옮기는 과정에서 조건이 탈락했다. 지금은 `SPIKE_ALLOWANCE_REFERENCE_FRAMES
= 30` 을 함께 두고 3/30 = 비율 상한임을 시험으로 고정했다.

**두 코호트를 비교하지 않았다면 발견하지 못했을 것이다.** 단일 코호트만 봤다면
"PIOP1 적격 153" 을 그대로 받아들였을 것이다. 계획서 §9 가 "cohort 차이·제외 수를
보고한다"고 요구한 것이 이런 검출력을 준다.

## T.4 재추출

P7 과 E15 를 반영해 **rest 두 조합만** 다시 돌린다(P7 은 창 길이가 30이 아닌
PIOP1 rest 에만, E15 는 PIOP2 rest 의 2건에 영향). task 4개 조합은 판정이 바뀌지
않으므로 다시 돌리지 않는다 — 부록 Q·R 의 "불필요한 읽기를 늘리지 않는다" 원칙과
일치한다.

재추출 후 두 코호트를 다시 만들고 PIOP1 분할을 갱신한다. **부록 P 의 적격 153,
pilot 30, main 123 은 P7 적용 전 값이므로 갱신될 것이다.**

---

# 부록 U — P7·E15 정본 반영: 적격 **157 / 189**, 분할 갱신 (14회차)

## U.1 무엇을 했나

부록 T 에서 예고한 대로 rest 두 조합 재추출 결과를 정본으로 올리고, 두 코호트와
PIOP1 분할을 다시 만들었다. **예고한 수치가 한 건도 어긋나지 않았다.**

| 항목 | P7·E15 전 | 후 | 비고 |
|---|---:|---:|---|
| PIOP1 rest `ok` | 187 | **202** | `excluded → ok` 15건, 그 외 전이 없음 |
| PIOP1 rest `excluded` | 23 | 8 | |
| PIOP2 rest `ok` | 203 | **203** | 불변 |
| PIOP2 rest `error` | 2 | **0** | `error → excluded` 2건 (E15) |
| PIOP1 적격 subject | 153 | **157** | 신규 4명, 이탈 0명 |
| PIOP2 적격 subject | 189 | **189** | 변화 없음 |

신규 적격: `ds002785:sub-0058`, `sub-0071`, `sub-0111`, `sub-0215`.
**이탈은 양쪽 코호트 모두 0건이다** — 완화 방향 개정이면 반드시 단조 증가해야
하고, 실제로 그랬다.

rest `ok` 가 15건 늘었는데 적격 subject 는 4명만 늘었다. 나머지 11명은 emomatching
이나 workingmemory 에서 이미 탈락해 있었기 때문이다.

## U.2 덮어쓰지 않고 승격하는 절차

재추출은 `/tmp/p7_piop*_rest` 로 냈으므로 manifest 의 `path` 가 `/tmp` 를 가리켰다.
그대로 정본에 넣으면 **재부팅 한 번에 전 창이 사라지는 manifest** 가 된다.
승격 스크립트(`/tmp/p7_install.py`)를 따로 만들어 다음 순서로 처리했다.

1. manifest 의 모든 창에 대해 정본 경로의 기존 파일 sha256 을 **읽어서** 비교
2. 하나라도 불일치하면 **즉시 중단**(덮어쓰기 금지)
3. 불일치가 없을 때만 정본에 없는 파일을 복사하고, 복사 직후 해시 재확인
4. manifest 의 `path` 를 정본 경로로 재작성

```
PIOP1  동일=748  신규=60  충돌=0     (748 = 187 ok × 4 창, 60 = 15 × 4)
PIOP2  동일=812  신규=0   충돌=0     (812 = 203 ok × 4 창)
```

**기존 1,560개 창이 전부 바이트 동일**했다. 즉 P7·E15 는 판정만 바꿨고 이미
통과한 창의 수치는 한 비트도 건드리지 않았다. 재작성된 manifest 를 다시 전수
검증했다: `windows=808 missing=0 hash_mismatch=0` / `windows=812 missing=0
hash_mismatch=0`.

교체 전 원본은 `derivatives_v2*/.backup/` 에 타임스탬프로 보존했다(manifest,
cohort, splits).

## U.3 갱신된 분할

```
subjects_total  216      subjects_eligible  157      n_groups  157
pilot_n         31       pilot_target  31
main_pool_n     126
outer_test      [26, 25, 25, 25, 25]   합 126
config_hash     85556f56               (변화 없음)
split_hash      ace5f4a41446a585…      (구: 586f1c50895a98e1…)
folds_sha256    a73875f2a98164f4…
```

`pilot = min(32, ⌊0.2 × 157⌋) = min(32, 31) = 31`. 같은 명령을 다른 출력 경로로
다시 돌려 `folds.json` 이 **바이트 동일**함을 확인했다(재현성).

라이브러리의 `verify_disjoint()` 와 **별개로** 독립 검증 스크립트를 써서
pilot∩main_pool=0, pilot∪main_pool=적격집합, 각 outer 의 test∩train=0,
test∪train=main_pool, outer test 쌍별 교집합=0, outer test 합집합=main_pool,
inner train∩val=0, inner 합집합=outer train, inner val∩outer test=0 을 전부
확인했다. 라이브러리가 자기 산출물을 자기 함수로 검사하는 것만으로는 부족하다.

### U.3.1 분할은 코호트 변화에 안정적이지 않다

| 비교 | 값 |
|---|---:|
| pilot 유지 | 7 / 31 |
| pilot 신규 | 24 |
| pilot 이탈 | 23 |
| 공통 main_pool subject 중 outer fold 동일 | 35 / 100 (35.0%) |

적격자가 4명 늘었을 뿐인데 **배정은 거의 전부 바뀐다.** seed 고정 배정은 그룹
목록 전체에 의존하므로 당연한 결과지만, 함의는 분명하다.

> **코호트가 확정되기 전에는 분할을 소비하는 어떤 단계도 시작하면 안 된다.**

이번에는 안전했다. 폐기된 `splits_piop1` 로 **적합된 모델이 하나도 없기 때문**이다
(WI-05 이후 미착수). 구 분할은 지우지 않고 `splits_piop1/SUPERSEDED.md` 로 사유·
대체본·구신 해시를 남겼다. 이것은 WI-03 미결 산출물인 `locks/measurement_lock.json`
의 필요성을 실증한다 — 코호트·분할을 잠그는 절차가 없으면 이런 교체가 조용히
일어날 수 있다.

## U.4 갱신된 WI-07 완료 기준

main N = **126** 에서:

| 항목 | 기대 수 | 구 값 (N=123) |
|---|---:|---:|
| window prediction rows | **12,096** (126 × 2 task × 4 창 × 3 seed × 4 cell) | 11,808 |
| run prediction rows | **1,008** (126 × 2 task × 4 cell) | 984 |
| primary checkpoints | **60** (4 cell × 5 outer × 3 seed) | 60 |

PIOP2 외부 평가(§9, held-out)는 적격 189명 기준 window **1,512** / run **1,512**.

> **주의**: N=126 에서 `main_pool 창 수`(126×2×4=1,008)와 `run prediction rows`
> (126×2×4=1,008)가 우연히 같다. 서로 다른 양이다. N=123 에서도 984/984 로 같았다.

창 manifest 는 target task 만 쓰므로 재생성하지 않았고, 값만 검증했다.

```
windows_piop1.jsonl  1,436 행  (183 emo ok + 176 wm ok = 359 run × 4 창)
  main_pool 126명 → 1,008 창 (기대 1,008)   pilot 31명 → 248 창 (기대 248)
  적격 subject 중 창이 8개가 아닌 경우: 0건
windows_piop2.jsonl  1,672 행  (204 + 214 = 418 run × 4 창)
  적격 189명 → 1,512 창 (기대 1,512)        창이 8개가 아닌 적격: 0건
```

## U.5 제외 사유 상위 (갱신)

PIOP1 (적격 157/216)

```
 27  workingmemory:mean_fd>0.2
 20  workingmemory:run_spike_ratio>0.1
 20  workingmemory:window2_spike_ratio>0.1
 20  workingmemory:window2_spikes>3
 16  emomatching:mean_fd>0.2
 13  workingmemory:window3_spike_ratio>0.1
```

PIOP2 (적격 189/226)

```
 15  emomatching:mean_fd>0.2
 15  restingstate:mean_fd>0.2
 10  emomatching:window3_spike_ratio>0.1
 10  emomatching:window3_spikes>3
  6  emomatching:window2_spike_ratio>0.1
  6  workingmemory:mean_fd>0.2
```

두 코호트 모두 **workingmemory/emomatching 의 head motion 이 주 탈락 요인**이고,
P7 이후 rest 는 PIOP1 에서 사실상 탈락 요인이 아니다. PIOP2 rest 의
`mean_fd>0.2` 15건은 P7 과 무관하다(TR 2초, 창 30 frame — 판정 불변).

## U.6 P7 이 드러낸 것: 두 창 기준은 이제 **같은 기준**이다

갱신된 제외 사유에 `window0_spike_ratio>0.1` 과 `window0_spikes>8` 이 **항상 함께**
나온다. 계획서 §3.3 의 두 창 기준이 P7 하에서 수학적으로 동일해지기 때문이다.

```
비율 기준:  n_spikes / n_observed > 0.1
개수 기준:  n_spikes > 3 × (n_observed / 30)  =  0.1 × n_observed
```

부동소수점에서도 정말 같은지 **추론하지 않고 전수 확인**했다: 창 길이 1–1000,
각 길이에서 가능한 모든 spike 개수 0–n 에 대해 두 조건의 참거짓이 갈리는 경우가
**0건**이었다(`3*(80/30)` 은 IEEE754 에서 정확히 `8.0` 이다).

이 중복은 P7 이 틀렸다는 증거가 아니라 **맞다는 증거다.** §3.3 은 이미
"전체 및 각 고정 window에서 FD>0.5 mm 비율≤10%"를 주 기준으로 세워 두고, 그
다음 문장에서 "task의 30 원본 frames 구간에서는 최대 3개까지 허용한다.
rest는 native frame 수로 계산한다"고 적는다. 뒷문장은 **앞 기준의 재진술**이지
독립된 제2 기준이 아니다. 절대 3개로 읽으면 "rest는 native frame 수로 계산한다"가
가리킬 대상이 없어진다.

남는 것은 표기 중복(같은 조건이 사유 문자열 2개로 기록됨)뿐이다. 계획서가 두
기준을 모두 적고 있으므로 **코드에서 한쪽을 지우지 않았다.** 사유가 중복되는 것은
집계에서 과대계상될 수 있으니 판독 시 주의한다.

## U.7 부수 발견: h197 에 낡은 패키지 사본

`MoBSE_dataset/v2check/mobse` 가 9-17 중간 시점 사본이고 **P7 이 없다**
(`SPIKE_ALLOWANCE_REFERENCE_FRAMES` 부재, `preprocess.py` md5 불일치). 정본은
`legacycheck` 이다. `scripts_h197/` 과 `legacycheck/` 전체를 grep 해 **이 경로를
참조하는 곳이 한 군데도 없음**을 확인했고, 삭제하지 않고
`v2check/STALE_DO_NOT_USE.md` 를 넣어 표시했다.

E12(기억으로 API 호출) 와 같은 부류의 위험이다. 같은 이름의 사본이 두 벌 있으면
어느 쪽이 돌았는지가 산출물에 남지 않는다.

## U.8 회귀 확인

```
453 passed, 2 warnings in 21.52s      (tests/v2, legacycheck)
```

P7 시험 `test_scaled_allowance_matches_ratio_rule_at_any_length` 포함 전부 통과.

## U.9 확인하지 못한 것

- **PIOP1 emo/wm, PIOP2 3조합의 Wave 2 파일 해시 재검증**은 여전히 미실시다.
  비교할 기준 해시가 없고(Wave 1 과 달리 사전 기록이 없다), 불량 섹터 1,932개인
  디스크에서 ~100 GiB 를 더 읽을 이유가 없다. 부록 R 의 판단을 유지한다.
- **band-pass 순서**는 여전히 미결(부록 H). 계획서 §3.2 에 따라 WI-03 pilot
  기술 검증으로 미룬다.
- **WI-08 subject 독립성**(PIOP1↔PIOP2 동일인 참여 여부)은 공식 문서 없이는
  판정 불가다. dataset prefix 로 ID 충돌은 막았지만 **동일인 여부는 확인되지
  않았다.**

## U.10 E16 — 증거 파일이 "키가 0개"라고 말하고 있었다

갱신된 `cohort_summary.json` 을 읽다가 걸렸다.

```
"exclusions_artifact": { "n_records": 59, "unique_keys": 0 }
```

59개 레코드에 유일 키가 0개일 수는 없다. `manifests.write_jsonl()` 이
`_primary_key_field(artifact)` 로 키 필드를 찾는데, 그 매핑에
**`exclusions` 항목이 없었다**. 없으면 `None` 이 돌아오고, 그러면

- `unique_keys` 가 0 으로 보고되고 (**증거 파일이 거짓을 말한다**)
- **중복 검사 자체가 조용히 꺼진다** (더 나쁜 쪽)

같은 매핑을 전수 확인하니 `window_predictions` 와 `run_predictions` 도
빠져 있었다. **WI-07 의 주 산출물 12,096행·1,008행이 중복 검사 없이
쓰이게 되어 있었다.** 한 창이 두 번 들어가면 집계가 조용히 틀어진다.
아직 그 코드가 돌지 않았을 뿐이다.

### U.10.1 키 정의

```python
"exclusions":         ("stage", "key_level", "key")
"window_predictions": ("cell", "model_seed", "window_key")
"run_predictions":    ("cell", "run_key")
```

`exclusions` 는 한 파일에 run/window/subject 단계가 섞일 수 있어 복합키다.
예측 두 종은 완료기준 행 수 공식에서 역산했다 —
`window = N × task × 창 × seed × cell` 이므로 `window_key` 당 `seed × cell` 행,
`run = N × task × cell` 이므로 `run_key` 당 `cell` 행이다. `scope` 는 파일 단위로
고정이라 키에 넣지 않았다(넣으면 키가 넓어져 중복을 놓친다).

### U.10.2 근본 원인과 가드

근본 원인은 **"매핑에 없으면 검사를 건너뛴다"는 기본값**이다. 새 artifact 를
추가하면서 키 정책을 적지 않으면 검사가 꺼지는데 아무 소리도 나지 않는다.

가드로 `test_every_schema_artifact_has_an_explicit_key_policy` 를 넣었다.
`SCHEMAS` 의 모든 artifact 는 키 정책이 있거나, **키가 필요 없다고 명시적으로
선언된 집합(`keyless_by_design`)에 들어가야** 한다. 지금 그 집합에는
`fit_manifest` 하나뿐이다(`fit_id` 가 내용 해시라 중복이 곧 동일 레코드다).

이 시험은 **작성하자마자 두 건을 잡았다.** 가드를 사후 안전망이라고 적었던
부록 L 의 표현을 여기서는 조금 고쳐야겠다 — 이번 것은 안전망이 아니라 탐지기였다.

### U.10.3 영향 범위

```
461 passed (종전 453 + manifests 5 + 신규 스크립트 parametrize 3)
subjects.jsonl  해시 불변   5ab19339…  /  a19570288…
exclusions.jsonl 해시 불변  74a04e31…  /  8642ba849…
cohort_summary.json 만 변경 (unique_keys 0 → 59 / 0 → 37)
folds.json 불변 — subjects.jsonl 을 읽으므로 영향 없음
```

**분석 결과는 하나도 바뀌지 않았다.** 바뀐 것은 증거 파일의 정확성과, 아직
돌지 않은 코드의 안전성이다.

## U.11 E17 — 증거 파일의 해시가 트리와 어긋나 있었다

rev22 를 쓰기 전에 `gate_evidence.json` 이 기록한 모든 해시를 실제 파일과
대조하는 검증기를 다시 돌렸다. **8건이 어긋나 있었다.**

```
v2_module_hashes/extract.py                  c5384e2f… -> b725f6ae…
v2_module_hashes/preprocess.py               57a99f25… -> 689ed2d8…
v2_test_hashes/test_extract.py               d9e35f12… -> 68a9b00c…
v2_test_hashes/test_h197_scripts.py          645cc5c8… -> bca80a94…
v2_test_hashes/test_preprocess.py            36877eaa… -> 648887ce…
h197_scripts/requirements-v2.txt             7a35c84d… -> 8b60c832…
script_contract_guard.guard_sha256           c831cdba… -> bca80a94…
G0/reports/wi00_wi01_execution_report…md     df80f2b5… -> 19d0f3e2…
```

전부 **P7·E15 수정으로 바뀐 파일들**이다. rev21 의 서술은 "둘 다 고치고 재추출
중"이라고 적었으면서 그 수정이 닿은 파일의 해시는 갱신하지 않았다. 즉
**rev21 의 증거 블록은 자기가 서술한 코드가 아닌 이전 코드를 가리키고 있었다.**

### U.11.1 왜 놓쳤나

해시 재검증을 **증거를 쓴 직후가 아니라 증거를 쓰기 전에** 돌렸기 때문이다.
코드를 고치고 → 시험을 돌리고 → 증거에 서술을 적고 → (검증 없이) 마감하는 순서였다.
검증은 마지막이어야 한다.

### U.11.2 함께 드러난 누락

`h197_scripts` 블록에 스크립트 **11개만** 들어 있었다. 07·09·10·11·12·13·14·15·16
과 `requirements-legacy-extra.txt` **10개가 미등록**이었다. 그중 `10_wi02_extract.py`
와 `15_build_subjects.py` 는 **이번 코호트를 만든 바로 그 스크립트들**이다.
전부 등록했다(총 21개).

`script_contract_guard.guard_test_count` 도 실제 시험 수와 맞춰 갱신했다.

### U.11.3 가드

검증기를 `verify_gate_hashes.py` 로 고정하고, **증거 파일을 쓴 다음 반드시
마지막에** 돌린다. 이번 rev22 마감 검증 결과를 §U.12 에 남긴다.

한계를 분명히 적는다: 이 검증기는 **`gate_evidence.json` 이 이미 기록한 경로만**
검사한다. `h197_scripts` 누락처럼 **아예 기록되지 않은 파일은 잡지 못한다.**
이번에는 디렉터리 전수와 대조해서 찾았고, 그 대조를 검증기에 넣어 두었다.

## U.12 rev22 마감 검증

`scripts/h197/17_verify_gate_hashes.py` 로 `gate_evidence.json` rev22 를 전수
대조했다. 이 검증기는 두 가지를 본다 — (1) 기록된 해시가 실제 파일과 같은가,
(2) 해시를 모으는 디렉터리에 **기록되지 않은 파일이 있는가**.

```
검사 102건: 일치 102, 불일치 0, 파일없음 0, 미기록 0
```

`h197_scripts` 는 11 → 21 개로, `v2_test_hashes` 는 README 를 포함해 21 개로
완전해졌다. `script_contract_guard.guard_test_count` 는 44 → 60 으로 맞췄다
(이 시험은 `scripts/h197/*.py` 에 parametrize 되므로 스크립트를 추가하면
자동으로 늘어난다 — 44 는 그 이후 추가분을 반영하지 않은 값이었다).

시험: **461 passed** (`tests/v2`, h197 `legacycheck`).

마지막 3건은 `17_verify_gate_hashes.py` 를 추가하면서 `test_h197_scripts.py` 의
parametrize 가 자동으로 늘어난 것이다(57 → 60). 가드가 새 스크립트를 스스로
받아들였다는 뜻이고, 이번에도 통과했다.

## U.13 이번 회차의 요약

| | |
|---|---|
| 정본 반영 | PIOP1/PIOP2 rest manifest, 덮어쓰기 0건, 신규 창 60개 |
| 코호트 | PIOP1 **157**/216, PIOP2 **189**/226 (이탈 0) |
| 분할 | pilot 31 / main 126 / outer [26,25,25,25,25], `ace5f4a4…`, 재현 확인 |
| WI-07 기준 | window **12,096** / run **1,008** / checkpoint 60 |
| 새로 잡은 결함 | E16(키 정책 누락 → 중복 검사 비활성), E17(증거 해시 stale + 스크립트 10개 미등록) |
| 시험 | 453 → **461** |
| 증거 | rev21 → **rev22**, 마감 검증 102건 전부 일치 |

E16 과 E17 은 둘 다 **분석 결과를 바꾸지 않았다.** 바뀐 것은 아직 돌지 않은
코드의 안전성과, 증거 파일이 사실을 말하는지 여부다. 그러나 두 결함 모두
**"빠뜨려도 아무 소리가 나지 않는" 구조**에서 나왔다는 점은 같다 — 키 정책이
없으면 검사가 꺼지고, 기록되지 않은 파일은 해시 대조에 걸리지 않는다. 두 곳
모두 "명시하지 않으면 실패한다"로 뒤집었다.

---

# 부록 V — WI-03 미결 산출물 3종과, 가드가 막지 못한 다섯 번째 E12 (15회차)

부록 U.3.1 에서 "코호트가 확정되기 전에는 분할을 소비하는 어떤 단계도 시작하면
안 된다"고 적고, 그것을 강제할 장치가 없다는 점을 지적했다. 이번 회차는 그
장치를 만들고, WI-03 의 나머지 두 산출물을 붙였다.

## V.1 `locks/measurement_lock.json`

지침서 WI-03 의 완료 기준은 "실제 N과 분할 hashes가 고정되며 **pilot은 모든
main/final fit에서 제외된다**"이다. 잠금 파일은 그 두 가지를 담는다.

### V.1.1 담은 것

| 절 | 내용 | root |
|---|---|---|
| `cohorts.piop1` | 세 task manifest, subjects, exclusions, cohort_summary, 창 manifest, atlas, folds | h197 자료 |
| `cohorts.piop2` | 같음, **folds 는 null** (§9 held-out) | h197 자료 |
| `environment` | 계획서, 지침서, config 3종(+config_hash), `mobse/v2` 전 모듈 해시와 집계 code_hash | 저장소 |
| `endpoint` | N_primary 126, N_external 189, δ 0.02, bootstrap seed/n/percentile | — |
| `change_policy` | 무효화 조건과 그 뒤 절차 | — |

```
lock_hash  1c1fba957b355f08…      (본문 정규화 후 sha256, 자기 자신은 제외)
split_hash ace5f4a41446a585…
code_hash  be04d7ecfd3f9e70…
```

잠금은 서로 다른 두 기계에 걸쳐 있다. `cohorts` 경로는 h197 자료 디렉터리
기준, `environment` 경로는 저장소 기준이다. 그래서 검증기는 root 를 **절별로**
받는다. root 가 없는 절은 조용히 넘어가지 않고 `skipped` 로 남기며,
`lock_is_clean()` 은 `skipped` 가 있으면 **깨끗하지 않다고 판정한다.**
검사하지 못한 것을 통과로 세지 않는다.

### V.1.2 기록된 참은 참이 아니다

잠금 파일에 "불변식 통과"라고 적어 두는 것만으로는 아무것도 보장하지 않는다.
`verify_lock()` 은 `folds.json` 을 **다시 읽어 불변식을 다시 계산한다.**

```
pilot ∩ main_pool = ∅
pilot ∪ main_pool = 적격집합
outer test ∩ train = ∅ ,  test ∪ train = main_pool
outer test 쌍별 교집합 = ∅ ,  합집합 = main_pool
inner train ∩ val = ∅ ,  inner 합집합 = outer train ,  inner val ∩ outer test = ∅
pilot 이 어떤 fold 의 train·test·inner 에도 없다        ← WI-03 완료 기준 그 문장
```

기록된 값과 재계산이 다르면 그것도 `mismatch` 로 보고한다.

### V.1.3 실물 변조 시험

단위시험(18건)만으로 끝내지 않고 **실제 잠금 파일로** 확인했다. 잠긴 파일 17개를
사본 트리에 복사하고 거기서 `folds.json` 의 outer fold 0 train 에 pilot 1명을
끼워 넣었다.

```
사본 그대로        검사 24건: 일치 24, 불일치 0, 파일없음 0, 불변식실패 0, 미검사 0   rc=0
pilot 1명 주입 후  [MISMATCH] folds.json 기대 a73875f2a981 실제 cba8a7b32c55
                   [MISMATCH] 기록된 불변식과 재계산이 다르다
                              ['inner_structure_valid', 'outer_test_union_train_is_main_pool',
                               'pilot_absent_from_every_fit']
                   [INVARIANT] 같은 3건                                                 rc=1
data_root 없이     [SKIPPED] 17건 미검사                                                rc=1
```

해시와 불변식이 **각각 독립으로** 잡았다. 둘 중 하나만 있었어도 잡혔겠지만,
해시는 "무언가 바뀌었다"만 말하고 불변식은 **무엇이 깨졌는지**를 말한다.

### V.1.4 변경 정책

```
· 잠긴 항목이 하나라도 바뀌면 이 잠금은 무효다. 새 잠금을 만들고
  supersedes 에 구 lock_hash 와 사유를 남긴다. 구 파일은 지우지 않는다.
· 무효가 되면 그 잠금에 의존해 적합된 산출물은 다시 만든다. 부분 갱신하지 않는다.
· main OOF 를 한 번이라도 수행한 뒤에는 δ 와 분석 N 을 바꾸지 않는다 (§8).
· pilot 은 모든 main/final fit 에서 제외된다. verify 가 매번 재확인한다.
· PIOP2 는 fold 를 만들지 않는다. 외부 평가 전에 fit·선택·calibration 에 쓰지 않는다 (§9).
```

## V.2 `reports/resource_budget.md`

계획서 §7 은 "pilot 에서 peak memory·시간을 측정해 자원 계획을 만든다"고 정한다.
`fit` CLI 가 아직 없으므로 **pilot 측정을 대신하지 않는다**고 문서 첫머리에
적고, 줄마다 [측정]/[추정]/[미측정] 을 구분했다.

측정 요약 (RTX 3090 Ti, batch 32, float32, 반복 25회):

| 항목 | 값 |
|---|---|
| 1 epoch — inner train 536창 | 0.085 – 0.144 s |
| 1 epoch — outer train 808창 | 0.155 – 0.245 s |
| peak GPU | 92.8 – 96.5 MiB |
| trainable params | A/C 6,469, B/D 6,021 (bank 는 전 cell 에서 buffer) |
| fold 내부 변환 1회 (FC+PCA+bank) | 0.86 s |
| FLOPs | **NA** (§9 — thop 이 dense graph einsum 을 세지 못함) |

**cell 사이의 차이는 이 측정으로 해소되지 않는다.** 네 cell 의 최솟–최댓값
구간이 크게 겹친다. outer 가 inner 보다 일관되게 느린 것(창 1.5배)만 신호로 읽고
cell 간 비교는 하지 않았다. 이 규모에서는 커널 실행 오버헤드가 지배적이다 —
창 808개면 26 batch 이고 모델이 6천 parameter 다.

추정: fit 768개가 전부 max 50 epoch 을 써도 **1.87 h**, early stopping 이
inner 를 절반에서 멈추면 1.27 h. checkpoint 192개 총 **27 MiB**.

**그래서 제약은 계산이 아니다.** 파생 창 전체가 54.7 MiB 인 반면 원본 BOLD 는
209.7 GiB 이고, 그 209.7 GiB 가 이중화 없는(`[2/1] [U_]`) 디스크 한 장 위에
있으며 그 디스크는 1,932 섹터를 읽지 못한다. 유리한 쪽으로 읽으면 —
**파생물이 55 MiB 뿐이므로 WI-02 재추출 말고는 원본 없이 다른 기계에서
돌릴 수 있다.**

## V.3 `reports/precision_scenarios.md`

계획서 §8 이 요구한 "QC 후 N 과 사전 paired-error discordance/상관 시나리오
simulation" 이다. 공식이 아니라 자료를 생성해 **계획서가 정한 bootstrap 절차를
그대로** 돌렸다 — n_boot 10,000, percentile 1.25–98.75, group=subject.

### V.3.1 결과

**현재 설계는 δ=0.02 를 검출할 정밀도가 없다.**

참 효과가 정확히 δ=0.02 일 때 97.5% CI 하한이 0 을 넘을 확률:

| discordance π | N=126 (주분석) | N=189 (외부) |
|---:|---:|---:|
| 0.05 | 0.191 | 0.303 |
| 0.10 | 0.110 | 0.130 |
| 0.20 | 0.061 | 0.075 |
| 0.30 | 0.048 | 0.062 |

(ρ=0 기준. ρ=0.5 면 더 낮다.) 계획서가 "실질적 우월성"으로 정의한
**하한 > δ 는 이 16개 칸에서 0.008–0.015** 로, 귀무(δ=0)에서의 오탐률
0.0125 와 사실상 구분되지 않는다.

이유는 단순하다. **CI 반폭이 δ 보다 훨씬 크다.** N=126, π=0.10 에서 반폭
0.044 인데 δ 는 0.02 다. 효과가 목표치만큼 있어도 CI 가 0 을 두 배 넘게 감싼다.

### V.3.2 절차가 보정되어 있다는 확인

δ=0 인 칸에서 P(하한>0) 가 **0.006–0.017** 로 나왔다. 97.5% CI 의 이론값
`(1−0.975)/2 = 0.0125` 와 일치한다. 위 숫자가 낮은 것은 **절차 결함이 아니라
설계의 정밀도 문제**라는 뜻이다.

### V.3.3 pilot 으로는 확정할 수 없다

계획서는 pilot 추정을 "불확실성과 함께" 쓰라고 했다. pilot 31명에서 π 의
Wilson 95% 구간은 참 π=0.10 일 때 **[0.035, 0.253]** 이다. 그 구간은 위 표에서
P(하한>0) 를 0.05 에서 0.19 까지 가른다. **pilot 은 정밀도 주장의 근거가 될 수
없다.** 구현 가능성·비용·기준선 동작을 보는 용도로만 쓴다.

### V.3.3.1 그렇다면 무엇을 검출할 수 있나

"80% power 를 확보했다"고 적지 않기 위해 반대로 물었다 — **80% 를 주려면 효과가
얼마여야 하는가.** `P(하한>0) = 0.80` 이 되는 δ 를 이분법으로 찾았다.

| π | N=126 δ₈₀ | δ=0.02 대비 |
|---:|---:|---:|
| 0.05 | 0.041 | 2.0× |
| 0.10 | 0.061 | 3.0× |
| 0.20 | 0.088 | 4.4× |
| 0.30 | 0.105 | 5.3× |

(ρ=0 기준. ρ=0.5 면 5–20% 더 크다.) **가장 유리한 가정에서도 사전 등록한 δ 의
두 배**가 필요하고, 그럴듯한 가정에서는 3–5배다. 표본을 189 로 키워도 δ₈₀ 은
15–20% 줄 뿐이다(√N). δ=0.02 에 닿으려면 N 이 수천 명 규모여야 한다.

grid 48칸을 서로 다른 시각에 두 번 돌려 **48칸 전부 동일**함을 확인했다.

### V.3.4 simulation 이 계획서 구현과 같은 절차인가

속도를 위해 multinomial 경로를 썼다(`d` 가 다섯 값만 취하므로 재표집 평균의
분포가 다섯 칸 multinomial 과 같다). 그 대체가 정당한지를 시험으로 고정했다.

* group=subject 에서 `statistics.bootstrap_indices` 의 group bootstrap 이 평범한
  subject bootstrap 과 **재표집 배열까지 완전히 동일**함 (500회 전건 비교).
* `paired_bootstrap` 의 CI 가 벡터화 index 경로와 **완전 일치**함.
* multinomial 경로와 index 경로의 CI 차이가 격자 한 칸(`0.5/N`) 규모를 넘지
  않고 계통 편차가 없음 (6회 반복, N=126·189).

### V.3.5 그래서 무엇을 하나

계획서 §8 이 이미 답을 정해 두었다 — "유의성은 실행 gate 가 아니다. 내부
결과가 음성이어도 데이터와 설계가 잠겨 있으면 외부 검증을 수행하고 같은 가설을
보고한다." 계획대로 실행하되 **결과를 '불확실'로 보고할 준비를 하고 시작한다.**

δ 는 바꾸지 않는다. 정밀도가 부족하다는 사실이 δ 를 키울 근거가 되지 않는다.
표본 증원도 하지 않는다 — 지침서 WI-03 이 "단지 작은 N 이면 임의 증원 대신
**제한을 보고한다**"고 정했고, 이 문서가 그 보고다.

**사전에 이 문서가 있다는 것이 핵심이다.** 결과가 나온 뒤에 정밀도 부족을
사후 변명으로 꺼내는 일은 없다.

## V.4 E12 다섯 번째 — 가드가 있었는데 또 났다

`21_resource_benchmark.py` 를 돌리자 실행 중에 터졌다.

```
TypeError: fit_transform_on_training_rest() missing 1 required positional argument: 'fit_subjects'
```

**이미 가드가 있었다.** `test_build_bank_and_transform_signatures` 가

```python
p = inspect.signature(fit_transform_on_training_rest).parameters
assert {"rest_features", "fit_subjects", "n_components", "allowed_subjects"} <= set(p)
```

로 `fit_subjects` 가 필수 인자임을 정확히 고정하고 있었고, suite 는 통과했다.

### V.4.1 왜 통과했나

그 가드는 **라이브러리 쪽 계약**만 본다. 계약이 존재하는지는 확인해도,
**새로 쓴 스크립트가 그 계약대로 부르는지는 보지 않는다.** 스크립트에 대한
검사는 "임포트가 되는가"뿐이었고, 잘못된 호출은 함수 **안**에 있어서 임포트
시점에 실행되지 않는다.

부록 L 에서 "네 건 모두 시험 밖의 스크립트에서 났다"고 진단하고
`test_h197_scripts.py` 를 붙였는데, 그 진단이 절반만 맞았다. 스크립트를
적재하는 것과 스크립트의 **호출부를 검사하는 것**은 다르다.

### V.4.2 호출부를 정적으로 검사한다

`test_script_call_sites_match_library_signatures` 를 넣었다.

1. 각 `scripts/h197/*.py` 를 AST 로 파싱한다.
2. `from mobse.v2 import ... as ...` / `from mobse.v2.x import f` 두 형태 모두에서
   임포트된 라이브러리 callable 을 해석한다.
3. 그 callable 을 부르는 `ast.Call` 마다 인자 개수·키워드 이름을 모아
   **실제 `inspect.Signature` 에 `bind` 해 본다.**
4. `*args`/`**kwargs` 가 섞인 호출은 판정 불가이므로 **건너뛴다** — 추측하지 않는다.

가드가 실제로 동작하는지를 확인하는 **자기시험**도 붙였다.
`test_call_site_checker_catches_the_actual_mistake_that_happened` 가 이번에
저지른 그 호출(`F.fit_transform_on_training_rest(feats)`)을 검사기에 넣어
정확히 1건을 잡는지 본다. 잡지 못하면 가드가 아니다.

### V.4.3 남는 한계

정적 검사라 **런타임에 결정되는 호출**(변수에 담긴 함수, getattr)은 못 잡는다.
그리고 인자 **개수·이름**만 보지 **타입·의미**는 보지 않는다. `fit_subjects` 에
엉뚱한 리스트를 넘기는 실수는 여전히 통과한다. 그건 이 가드의 범위 밖이고,
그렇게 적어 둔다.

## V.5 회귀·검증

```
시험          521 passed, 11 skipped     (종전 461)
              test_locks 18, test_precision_simulation 12,
              test_h197_scripts 57 → 101 (스크립트 5개 추가 × parametrize
              + 호출부 검사 + 대조기 자기시험 5건)
잠금          검사 24건 전부 일치, rc=0
해시          검사 119건 전부 일치
인용 수치     대조 실패 0건
증거          gate_evidence rev23
```

`11 skipped` 는 호출부 검사가 `mobse.v2` 를 임포트하지 않는 스크립트에서
건너뛴 것이다 — 검사 대상이 없다는 뜻이지 실패가 아니다.

## V.6 이번 회차에 확인하지 못한 것

- **pilot 31명에서의 실제 peak memory·시간.** 계획서 §7 이 요구하는 측정이고,
  `fit` CLI 구현 후로 미룬다. V.2 의 숫자는 **합성 자료** 측정이며 크기만 실제
  분할에서 가져왔다.
- **두 주 contrast 의 결합 확률.** V.3 은 contrast 하나를 모형화했다. A−B 와
  A−C 는 A 를 공유해 양의 상관이 있고, 결합 확률은 단순 곱보다 높지만
  **계산하지 않았다.** 상관 구조를 모르면서 숫자를 만들지 않는다.
- **π 와 ρ 의 실측값.** 가정이다. 실제 값은 pilot fit 이후에야 관측된다.
- **early stopping 이 실제로 몇 epoch 에서 멈추는지.** V.2 는 상한만 계산했다.

## V.7 재검수에서 잡힌 내 문장 두 개

문서를 다 쓴 뒤 인용한 수치를 **원자료 JSON 과 기계적으로 대조**하는 스크립트를
돌렸다. 두 건이 걸렸다.

**1. 과잉 일반화.** V.3.1 과 `precision_scenarios.md` §0 에 이렇게 썼다.

> 하한 > δ 는 **48개 칸 어디서도 0.02 를 넘지 않는다.**

틀렸다. 48칸 전체의 최댓값은 **0.335** 다 (N=189, π=0.05, δ_true=0.04).
내가 본 것은 **δ_true=0.02 인 16칸**이었고 거기서는 0.008–0.015 가 맞다.
δ_true 를 0.04 로 놓은 칸까지 싸잡아 "어디서도"라고 쓴 것이 오류다.

정정한 문장은 범위를 명시한다 — "그 16개 칸에서 0.008–0.015 로, 귀무(δ=0)에서의
오탐률 0.0125 와 사실상 구분되지 않는다." **주장은 오히려 더 강해졌다.** δ 만큼의
효과가 실제로 있어도 "실질적 우월성" 판정이 귀무 오탐과 구별되지 않는다는 뜻이다.

**2. 반올림으로 범위를 벗어남.** peak GPU 를 "93–97 MiB" 로 적었는데 실측
최솟값은 **92.8** MiB 다. 93 으로 반올림한 값을 범위의 **하한**으로 쓰면 실제
값이 범위 밖으로 나간다. 92.8–96.5 로 고쳤다.

### V.7.1 왜 이런 대조가 필요한가

두 건 다 **해시 검증으로는 절대 잡히지 않는다.** 파일은 멀쩡하고 해시도 맞다.
틀린 것은 문장이 원자료를 요약한 방식이다. `17_verify_gate_hashes.py` 는
"파일이 바뀌지 않았다"를 보증하지 그 파일을 옳게 읽었는지는 보증하지 않는다.

그래서 이번부터 마감 절차가 셋이다.

```
1. 시험 전량 통과
2. 해시 전건 일치        — 파일이 기록과 같은가
3. 인용 수치 원자료 대조 — 문장이 파일을 옳게 읽었는가   ← 새로 추가
```

3번은 문서에서 숫자를 뽑아 JSON 과 맞춰 보는 방식이라 자동화 범위가 제한적이다
(표의 모든 칸을 파싱하지는 않는다). 이번에는 핵심 주장 — δ=0.02 에서의
P(하한>0) 8개, MDE 16개, epoch 범위, peak GPU, fit 합계, 잠금의 N 과 해시 인용 —
을 대조했고 그중 둘이 틀렸다. **비율로 보면 적지 않다.**

---

# 부록 W — `fit` 본체와, pilot 이 잡아낸 학습 예산 문제 (16회차)

계획서 §4-2 는 "pilot 에서만 구현·학습 가능성, 장비 비용, **기준선의 기술적
동작**을 확인한다"고 정한다. 그 확인을 했고, 통과하지 못했다.

## W.1 `fit` 본체

`mobse/v2/fitting.py` (536줄) 와 `cli.run_fit()` 을 붙였다. 한 번의 호출이
**(role, cell, outer, inner, config, seed) 하나**이며, 계획서 §7 의 비용표
768 칸 중 한 칸이다.

### W.1.1 경계를 자료로 강제한다

```
fit_fold_transform(rest_refs, train_subjects, ...)
    → fit_transform_on_training_rest(z, fit_subjects, allowed_subjects=train_subjects)
```

`allowed_subjects` 를 넘기므로 허용 밖 subject 가 하나라도 섞이면
`FeatureError` 로 **실패**한다 (T03). 시험
`test_allowed_subjects_is_actually_passed_through` 가 그 인자가 실제로
넘어가는지를 확인한다 — 경계의 방어선은 인자이고, 넘기지 않으면 경계가 사라진다.

`resolve_fold_subjects()` 는 fold 를 꺼내면서 pilot 이 섞였는지, train 과 평가
집합이 겹치는지를 매번 확인한다. `inner_fold = 9`(= `templates.OUTER_FIT_INNER_FOLD`)
는 outer 최종 적합이고, 그 경우 **early stopping 을 켤 수 없다** — 평가 집합이
outer test 이므로 그것으로 멈추면 leakage 다. 코드가 거부한다.

### W.1.2 경로를 추측하지 않는다

창 `.npy` 경로는 WI-02 추출 manifest 가 기록한 값만 쓰고, 읽은 뒤 sha256 을
대조한다. label 은 창 manifest 에서 오고, 두 파일이 **같은 창 집합·같은 해시·
같은 label** 을 가리키는지 `crosscheck_with_windows_manifest()` 가 대조한다.
한 파일만 믿으면 label 과 자료가 어긋나도 알 수 없다.

### W.1.3 run 예측은 여기서 쓰지 않는다

계획서 §8 은 **세 seed 의 창 확률을 먼저 평균**하라고 정한다. fit 하나는 seed
하나이므로 여기서 run 예측을 내면 `n_seeds=1` 짜리가 최종 산출물과 혼동된다.
`fit` 은 `window_predictions.jsonl` 만 쓰고 run 집계는 `evaluate` 의 몫이다.

산출물은 넷이다 — `fit_manifest.json`, `checkpoint.pt`,
`window_predictions.jsonl`, `fit_report.json`.

## W.2 pilot 기술 검증: 실행은 됐다

pilot 31명 안에서 계획서의 알고리즘 그대로 기술용 분할을 만들고(pilot-of-pilot
6 / pool 25 / outer test 5×5), 그 안에서 실제 fit 을 돌렸다. **main pool 은
건드리지 않았다.**

```
cell A, outer 0, inner 0, config 0, seed 42, 최대 50 epoch, cuda
학습 창 104 (13명)   평가 창 56 (7명)
best epoch 21 / 26 epoch 에서 early stopping
end-to-end 12.66 s,  순수 학습 1.63 s,  peak GPU 89.6 MiB,  peak RSS 1.65 GiB
```

cell A 와 B 의 `encoder_init_hash` 가 `ace71bf9320887a3` 로 **동일**하다 —
계획서 §7 의 "같은 seed 의 공통 encoder 초기화를 맞춘다"가 실자료에서 성립한다.

## W.3 그런데 balanced accuracy 가 정확히 0.5 였다

```
eval_balanced_accuracy 0.5   eval_loss 0.6975 (≈ ln 2)
p_class1 범위 [0.368, 0.501], 평균 0.426, sd 0.025
56 창 중 55 창을 class 0 으로 예측
truth 0 평균 p1 = 0.4225,  truth 1 평균 p1 = 0.4293
```

정확히 0.5 가 나오는 이유는 단순하다. 모형이 거의 전부를 class 0 으로 찍으면
subject 마다 emomatching 은 맞고 workingmemory 는 틀리므로 `b_i = 0.5` 가 되고,
평균도 0.5 가 된다. **표본이 적어서가 아니라 모형이 상수를 내고 있었다.**

## W.4 표본 부족인가 배선 결함인가 — 가른다

두 가지를 구분하지 않으면 아무것도 결론낼 수 없다. 세 가지를 쟀다.

### W.4.1 같은 자질의 선형 기준선 (계획서 §6 의 S 후보 3)

같은 창의 FC Fisher-z 4,950 차원으로 logistic regression:

```
train window accuracy 1.000,  BA 1.000
val   window accuracy 0.929,  BA 1.000
```

**신호는 자료에 분명히 있다.** 그것도 아주 쉽게 갈린다.

### W.4.2 신경망은 학습 집합조차 못 맞혔다

```
train window accuracy 0.500,  train BA 0.500
```

표본 부족은 이것을 설명하지 못한다. **자기 학습 자료를 못 맞히는 모형은 표본이
적은 것이 아니다.**

### W.4.3 표현은 멀쩡했다

ROI mean pooling 직후 32차원에 선형 probe 를 걸었다.

| 자질 | train BA | val BA |
|---|---:|---:|
| graph 이후 pooled 32차원 | 0.885 | 0.857 |
| graph 이전 encoder 출력 32차원 | 0.808 | 0.786 |
| raw ROI mean/variance 200차원 (S 후보 1) | 1.000 | 0.714 |

**표현은 신호를 담고 있다.** 그런데 그 위의 `Linear(32→2)` 가 쓰지 못했다.

pooled feature 의 통계가 이유를 말해 준다 — **표본 간 표준편차 평균 0.054,
최대 0.108 인데 절댓값 평균은 0.802** 다. 큰 공통 offset 위에 작은 변동이
얹혀 있다. 선형 probe 는 StandardScaler 로 offset 을 없애고 변동을 키우니 바로
갈리지만, 모형의 head 는 그 작은 변동을 그대로 받는다. graph layer 의
LayerNorm 은 ROI 마다 32차원 **안에서** 정규화하므로 표본 간 offset 을 없애
주지 않는다.

## W.5 진짜 원인: 학습 예산이 평탄면 안에서 끝난다

배선이 아니라면 최적화다. epoch 을 늘려 봤다 (batch 32, config 0, seed 42).

| epoch | update 수 | train BA | val BA | val loss |
|---:|---:|---:|---:|---:|
| 50 | 200 | 0.500 | 0.500 | 0.686 |
| 200 | 800 | **1.000** | 0.714 | 0.499 |
| 600 | 2,400 | 1.000 | 0.643 | 0.768 |

**모형은 배울 수 있다. 50 epoch 에서 멈췄을 뿐이다.** 600 epoch 에서 val 이
다시 나빠지는 것은 정상적인 과적합이다.

### W.5.1 epoch 이 아니라 update 수다

batch 크기만 바꿔 50 epoch 을 고정했다 (같은 자료, 같은 seed).

| batch | 50 epoch 의 update | train BA | val BA | val loss |
|---:|---:|---:|---:|---:|
| 32 | 200 | 0.500 | 0.500 | 0.686 |
| 16 | 350 | 0.808 | 0.714 | 0.650 |
| 8 | 650 | 0.769 | 0.643 | 0.601 |
| 4 | 1,300 | **1.000** | 0.929 | 0.416 |

단조롭다. **평탄면 탈출을 정하는 것은 epoch 이 아니라 optimizer update 수다.**

### W.5.2 학습 집합이 커지면 나아지는가 — 아니다

"main 은 창이 더 많으니 epoch 당 update 도 많아서 괜찮을 것"이라는 낙관적
읽기를 그대로 두지 않고 쟀다. pilot outer train 에서 subject 수를 바꿔가며
(batch 32 고정) 학습 집합 window accuracy 를 봤다.

| 학습 subject | 창 | batch/epoch | 50 ep = update | train win acc @50ep | @800–1,000 update |
|---:|---:|---:|---:|---:|---:|
| 8 | 64 | 2 | 100 | 0.656 | 0.922 (800) |
| 13 | 104 | 4 | 200 | 0.625 | 0.933 (800) |
| 20 | 160 | 5 | 250 | 0.569 | 0.719 (1,000) |

**학습 집합이 커질수록 같은 update 수에서 더 나쁘다.** 낙관적 읽기는 지지되지
않는다. 탈출에는 대략 **800 update 이상**이 필요하고, 자료가 많아지면 더 든다.

### W.5.3 main 규모에서는 어떻게 되나 — 계산은 되지만 측정은 안 됐다

| 규모 | 창 | batch/epoch | 50 epoch 의 update |
|---|---:|---:|---:|
| pilot inner (13명) | 104 | 4 | 200 |
| **main inner (67명)** | **536** | **17** | **850** |
| **main outer (101명)** | **808** | **26** | **1,300** |

main 은 pilot 의 4–6.5배이고 탈출 구간(≈800)에 **겨우 닿거나 살짝 넘는다.**
그런데 W.5.2 가 "자료가 많으면 더 든다"고 말하므로, 850 update 가 536창에서
충분한지는 **알 수 없다.**

여기에 early stopping 이 겹친다. patience 5, min_delta 0.0005 인데 평탄면에서는
epoch 당 loss 변동이 1e-3 규모로 요동친다. pilot 에서는 그 요동 덕에 우연히
26 epoch 까지 살아남았다. **평탄면을 수렴으로 오인하고 멈출 수 있다.**

> 최악의 경우: 768개 fit 전부가 평탄면 안에서 끝나 balanced accuracy 0.5 를
> 내고, 주 대조가 "불확실"로 결론난다. **가설과 아무 상관 없는 이유로.**

## W.6 그래서 무엇을 했나 — 아무것도 바꾸지 않았다

계획서 §7 은 "max 50 epochs", "patience=5", "batch 32" 를 **명시적으로** 정한다.
개정 P7 때와 다르다 — P7 은 계획서 문장을 정확히 읽으면 답이 하나뿐이었지만,
여기에는 해석의 여지가 없다. 숫자가 그냥 그렇게 적혀 있다.

**그러므로 이것은 정정이 아니라 변경이고, 내가 단독으로 하지 않는다.**
부록 H 의 band-pass 순서와 같은 취급으로 **열린 항목**에 올린다.

### W.6.1 결정이 필요한 사항 (제안 P8, **미적용**)

선택지는 셋이다.

1. **그대로 둔다.** 근거: main 규모의 update 수가 pilot 의 4–6.5배이고 탈출
   구간에 닿는다. 위험: W.5.2 가 그 낙관을 지지하지 않는다.
2. **epoch 상한을 올린다** (예: 50 → 200). 자원 비용은 학습 1.87 h → 7.5 h 로,
   고정비를 더해도 하루 안이다(`resource_budget.md` §8.1). early stopping 은
   그대로 두되 patience 를 키운다.
3. **예산을 update 수로 다시 쓴다** (예: 최소 1,500 update 보장). 규모에
   무관하게 같은 최적화 예산을 준다는 점에서 가장 정합적이지만, 계획서 문구를
   더 크게 바꾼다.

**어느 쪽이든 main OOF 전에 정해야 한다.** 지금이 그 시점이다.

### W.6.2 결정을 줄일 측정 하나

main 규모에서 평탄면을 실제로 벗어나는지는 **한 번의 측정으로 확인된다.**

> main inner fold 하나(outer 0 / inner 0, cell A, config 0, seed 42)를 epoch
> 상한 없이 돌리고 **학습 손실 곡선만** 본다. inner validation 도 outer test 도
> 보지 않는다. 선택에 쓰지 않으므로 leakage 가 아니다.

이 측정은 아직 하지 않았다. **잠금이 걸린 분할을 소비하는 첫 행위**이므로
결정 전에 단독으로 시작하지 않는다.

## W.7 pilot 결과를 결과로 읽지 않는다

W.3–W.5 의 어떤 숫자도 가설에 대한 증거가 아니다. 계획서 §4-2 가 pilot 을
기술 검증용으로 한정했고, pilot 은 주 분석에서 **전부 제외**된다. 특히

- 선형 기준선이 val BA 1.00 을 냈다고 해서 "FC 기준선이 이긴다"고 쓰지 않는다.
  7명의 validation 이고, 계획서 §6 의 S 후보 선택 절차를 따른 것도 아니다.
- 신경망이 0.5 를 냈다고 해서 "제안 구조가 작동하지 않는다"고 쓰지 않는다.
  학습 예산 안에서 평탄면을 못 벗어난 것이고, 예산을 늘리면 학습 집합을
  완전히 맞힌다.

## W.8 회귀·검증

```
시험          563 passed, 11 skipped     (종전 521)
              +26 test_fitting, +8 test_cli_fit, 그 외 parametrize 증가
해시          검사 136건 전부 일치
인용 수치     대조 실패 0건
잠금          검사 24건 전부 일치, rc=0
```

`mobse/v2` 가 바뀌었으므로 rev23 잠금은 **무효**다. 변경 정책대로 새 잠금을
만들었다.

```
현재  5a735929b525…  2026-09-18T02:57:01Z
       ← 2eb2783e3dcc…  (재생성, 사유 미기재)
       ← 1c1fba957b35…  (rev23)
```

가운데 항목은 `--reason` 없이 재생성한 것이다. 그것을 보고 builder 에
**`--overwrite` 에 `--reason` 필수** 검사를 넣고 다시 만들었다 — 변경 정책이
"새 잠금에 supersedes 와 사유를 남긴다"고 정하는데 도구가 그것을 강제하지
않고 있었다. 사슬은 지우지 않고 `locks/superseded/` 에 그대로 남긴다.

### W.8.1 마감 절차가 또 한 건 잡았다

인용 수치 대조기(`22_crosscheck_reported_numbers.py`)가 **보고서의 lock_hash
인용 불일치**를 잡았다. 잠금을 새로 만들었는데 보고서는 옛 해시만 인용하고
있었다. 해시 검증은 파일이 바뀌지 않았는지만 보므로 이런 것을 잡지 못한다.
rev23 에서 3단계를 넣어 두지 않았다면 그대로 나갔을 것이다.

## W.9 이번 회차에 확인하지 못한 것

- **main 규모의 평탄면 탈출** — W.6.2. 결정 전 단독 실행하지 않는다.
- **`prepare`·`evaluate`·`report` CLI** — 여전히 미구현.
- **band-pass 순서·사양** — 부록 H 이후 그대로 열려 있다.
- **pilot 에서의 S 후보 전체 비교** — 계획서 §6 의 S 후보 4종과 구조 비교
  2종은 이번에 돌리지 않았다. W.4 의 선형 probe 는 진단용이지 S 선택 절차가
  아니다.

---

# 부록 X — h197 디스크 교체 뒤 재개: E18·E19·E20, 선생님 결정, 통과대역 자유도 (2026-09-23)

## X.1 복원 확인

h197 은 새 배열 `md1`(RAID1, WD40EFPX ×2, `[2/2] [UU]`)로 옮겨졌고 `/etc/fstab` 은 UUID,
`mdadm.conf` 는 md1 로 갱신됐다. `/mnt/data/mp2026/MoBSE_dataset` 는 같은 경로로 복원됐다.
h197 의 손실 원장(`~/loss_ledger_20260923.md`)에 MoBSE 항목은 없다.

- **Wave 1**: `provenance/h197_wave1/wave1_files.sha256` 6,058 파일을 `sha256sum -c` 로 대조 — **전부 일치** (rc=0).
- **Wave 2**: 파일 수 nii.gz 2,590 + 로그 4 로 기록과 같다. 해시 기준선이 없어 내용 대조는 못 했다 (열린 항목 그대로).
- 기존 4단계 마감(HEAD `5d6677a` 스냅샷)은 전부 기대값이었다.

## X.2 E18 — 네 검사가 모두 통과했는데 창 파일이 빠져 있었다

PIOP1 workingmemory 추출 manifest 의 704창 `windows[].path` 가 전부 `/tmp/wm_rerun2/` 를
가리켰다. 재부팅이 `/tmp` 를 비워 원본이 사라졌다. `derivatives_v2/` 의 WM `.npy` 는 1차
추출(sub-0171 I/O error)본이라 **sub-0171(main pool) 4창이 없었다.** fit 은 manifest 의
path 를 그대로 읽으므로(`mobse/v2/fitting.py`) 이대로면 PIOP1 WM 전량을 불러올 수 없었다.

근본 원인은 셋이다. (1) 2차 재추출을 `/tmp` 에 받고 manifest 만 정본 위치로 옮겼다 — 추출기는
`--output-dir` 절대경로를 manifest 에 박는다. (2) 잠금은 manifest **파일**의 해시만 보고
그 안의 창 경로를 열어 보지 않는다. (3) 직전 인수인계가 "`/tmp` 는 교체 후에도 남는다"고
적었으나, 디스크와 무관하게 **재부팅이 `/tmp` 를 지운다.**

복구: 현행 코드로 WM 전량을 재추출(`MoBSE_dataset/recovery_20260923/wm_rerun3/`)해 ok 176 /
excluded 31 / skipped 9 (기록과 동일), 잠긴 manifest 의 **704창 sha256 전부 일치**를
확인했다. sub-0171 4창을 `derivatives_v2/sub-0171/` 에 추가(덮어쓰기 없음)하고 manifest 의
경로 문자열만 `derivatives_v2/` 로 바꿨다(704건, 경로 외 변화 없음을 문자열 대조로 확인).
원본 manifest 는 `recovery_20260923/backup/` 에 있다 (D1, 선생님 사후 승인 "D1 - 추천대로").

장치: `scripts/h197/25_verify_window_files.py` — 잠금이 가리키는 6개 manifest 의 ok 창 전부를
역참조해 data-root 밖 경로·누락·해시 불일치·빈 ok run 이면 rc=1. 자기시험 7건. 수정 전 실자료에서
704 `outside_root` 를 잡았고, 수정 후 4,728창 전부 일치.

## X.3 E19 — `code_hash` 가 저장소 위치에 의존

`manifests.code_hash` 가 절대경로 문자열을 해시에 넣어, 모듈 17개의 sha 가 전부 같은데도
저장소 위치만 바뀌면 값이 바뀌었다. 잠금과 `fit_manifest.json` 둘 다 이 값을 쓴다. 파일명만
해시하도록 고치고 위치 불변·이름 변경·중복 이름 시험 3건을 넣었다. 수정 후 값 `e96eff358ce3…` 는
Mac 경로와 h197 `/mnt/data/code/MoBSE` 에서 같았다.

## X.4 E20 — 잠금이 코드를 기록만 하고 검사하지 않았다

E19 수정으로 `mobse/v2` 가 바뀌었는데 19번이 여전히 24/24 를 냈다. `verify_lock` 의 레코드
탐색이 `{"path","sha256"}` 모양만 찾는데 `environment.code` 는 `{"code_hash","modules"}`
모양이라 아무도 다시 계산하지 않았다. `locks.verify_code_record()` 를 추가해 모듈별 sha 와
`code_hash` 를 재계산한다. 시험 7건, 검사를 끈 변이 사본에서 6건이 실패함을 확인했다.
19번 검사 수는 24 → 42 로 늘었다.

## X.5 잠금 사슬

```
1c1fba957b35 → 2eb2783e3dcc → 5a735929b525 → 44b07ea14fd5 (E18 경로 정정)
             → 6e68eb939beb (E19/E20 코드) → 02e7434f228c (P8·P9 개정 기록, 현행)
```

모든 재생성에서 split_hash `ace5f4a4…`, N 126/189, 코호트·창 내용은 불변이다.

## X.6 선생님 결정 (원문)

| 항목 | 원문 | 적용 |
|---|---|---|
| D1 | "D1 - 추천대로" | X.2 대로 시행 완료 |
| band-pass | "band-pass - 동시 회귀 ok" | 계획서 개정 P9 — 순서만 결정. 통과대역은 X.7 로 보류 |
| P8 | "P8 - 최소 1,500 update 보장, 상한 200 epoch, early stopping은 최소치 이후에만 ok (필요하다면 epoch 수를 더 늘려도 됨. 최소 수치 조정도 가능)" | 계획서 개정 P8 기록. 구현 전 |
| CLI | "CLI - 추천안 대로" | evaluate → report → prepare 순 |
| §6 | "§6 S 후보 4 + 구조 비교 2 - 추천안 대로" | 구현·합성 시험은 지금, 실자료 실행은 통과대역 확정 후 main OOF 와 같은 release |
| lock_hash 인용 | "rev24 낡은 lock_hash 인용 - 추천대로" | rev25 에서 현행화 + 22번이 gate evidence 인용도 대조 |
| 커밋 | "커밋방식 - ok. 커밋 규약만 잘 지켜주면 ok" | 로컬 커밋, 푸시 없음 |
| 저장소 사본 | "\"/Users/hwon/projects/Git/Manuscript/MoBSE\" 를 그대로 rsync 클론해서 h197의 /mnt/data/code/MoBSE에 만들자" | 코드·문서·결과·`.git` 먼저, `data/`·`artifacts/`·`nilearn_cache/` 는 백그라운드 전송 |

## X.7 통과대역 상한 — 동시 회귀로 정확히 세면 0.1 Hz 에서 target run 이 전부 탈락한다

동시 회귀의 residual DOF 는 `n − rank([nuisance, 차단대역 기저])` 다. P6-b 의
`min(n − rank(nuisance), floor(2·Δf·T))` 는 nuisance 와 필터가 같은 자유도를 이중으로 쓰지
않는다고 가정하므로 **과대 보고한다.** 2026-09-23 추천안의 "DOF = n − p_nuis − p_freq 로
P6-b 회계와 정확히 일치" 는 틀린 서술이었다.

confounds 만으로 전 ok run 을 실측했다 (DCT-II 기저, 하한 0.008 Hz, `MIN_RESIDUAL_DOF = 30`,
판정은 `≤ 30` 이면 탈락):

| 상한 | PIOP1 emo | PIOP1 WM | PIOP1 rest | PIOP2 emo | PIOP2 WM | PIOP2 rest |
|---|---|---|---|---|---|---|
| 0.10 Hz | 최대 20, **183/183 탈락** | 최대 29, **176/176 탈락** | 29/202 탈락 | 최대 20, **204/204 탈락** | 최대 29, **214/214 탈락** | 0/203 |
| 0.15 Hz | 최소 39, 0 탈락 | 최소 50 | 최소 44 | 최소 40 | 최소 55 | 최소 97 |
| 0.20 Hz | 최소 66, 0 탈락 | 최소 82 | 최소 80 | 최소 67 | 최소 87 | 최소 145 |
| 0.25 Hz | 최소 92, 0 탈락 | 최소 114 | 최소 116 | 최소 93 | 최소 118 | 최소 192 |

산출물: `MoBSE_dataset/recovery_20260923/checks/dof_simultaneous_probe.json`, `dof_probe_hi{0.15,0.2,0.25}.json`.
기존 창에는 필터가 없으므로 이 표는 현재 코호트를 바꾸지 않는다. 통과대역 상한은 **선생님 결정 대기**이며,
P6-b 는 P9 구현 때 정확식으로 대체한다.

적격 판정 경로도 확인했다 — QC 는 FD·창별 FD·`residual_dof` 만 쓰고 신호 값은 쓰지 않는다
(`scripts/h197/10_wi02_extract.py::process_run`). 따라서 필터가 적격에 영향을 주는 경로는
`residual_dof` 하나이며, 위 표가 그 영향의 전부다.

## X.8 회귀·검증 (rev25)

h197 저장소 사본 `/mnt/data/code/MoBSE` 에서, 2026-09-23T04:35Z–04:37Z.

```
시험          586 passed, 12 skipped      (rev24 563/11; guard 7 + E19 3 + E20 7 + 22번 gate 인용 3 + 25번 파라미터)
해시          검사 141건 전부 일치         (rev24 136)
인용 수치     대조 실패 0건                 (gate evidence 의 lock_hash 인용 대조 추가)
잠금          검사 42건 전부 일치, rc=0     (E20 으로 코드 18건 추가)
창 파일       6개 manifest 4,728창 전부 일치, rc=0
```

## X.9 이번 회차에 확인하지 못한 것

- **통과대역 상한** — 선생님 결정 대기 (X.7). 그 전에는 P9 구현·전 창 재추출을 하지 않는다.
- **P8 구현** — 계획서에 기록만 했다. 코드·config 상수는 아직 50 epoch / patience 5 다.
- **Wave 2 내용 무결성** — 해시 기준선이 없다. 파일 수만 대조했다.
- **h197 사본의 `data/`** — 186 GB 중 일부만 전송됐다 (백그라운드 진행 중). `data/` 는 주분석에 쓰지 않는 legacy 자료다.
- **G1 의 "resource plan from pilot measurement" fail 판정** — rev24 의 pilot 측정(부록 W) 이후 갱신됐는지 이번에 재검토하지 않았다.

---

# 부록 Y — WI-06 evaluate 배선 (rev26, 2026-09-23 예약 슬롯)

## Y.1 무엇을 했나

인수인계 남은 작업 1번. 선생님 결정 "CLI - 추천안 대로"(evaluate → report → prepare)의 첫 단계다.
`mobse/v2/cli.py` 의 `evaluate` 가 `NotImplementedError` 를 내던 자리에 `run_evaluate` 를 붙였다.

- 입력: `--config --splits --predictions … --fit-manifest … --output-dir --tasks emomatching workingmemory`.
  release 는 cell × outer fold × seed 개의 fit 이므로 예측·manifest 경로를 fit 마다 **전부 명시**한다 (`nargs=+`).
- 출력: `run_predictions.jsonl`(schema `wi06-run-predictions-0.1`), `evaluation.json`(cell 별 BA, H1·H2·interaction 의 subject 차이와 평균, 입력 sha256).
- 범위: 분류만(T16), outer 최종 적합(`role=outer`, `eval_role=outer_test`)만, 두 task 모두 필수. **paired bootstrap 구간과 gate 판정은 report 몫**으로 남겼다.

## Y.2 무결성 검사 (T15)

checkpoint 는 manifest 옆 고정 이름 `checkpoint.pt` 에서 해시를 다시 계산해 예측 행의 `checkpoint_sha256` 과 대조한다(glob 없음, U20).
fit 격자 완전성(seed 3, 칸마다 같은 seed 집합), fit 사이 `code_hash`·`env_hash`·`source_hash` 동일, split·config 해시 일치,
행의 scope·cell·seed 일치, 학습 subject 누설, `window_key`↔`run_key` 접두 일치, subject·task 당 run 하나, 행 수·window×seed 격자를 검사한다.
불완전 평균은 하지 않고 실패한다.

## Y.3 시험

`tests/v2/test_cli_evaluate.py` 18건 — 합성 release(outer fold 2 × cell 4 × seed 3 = 24 fit, main pool 10명)로 끝까지 돌리고
BA·H1 을 손계산과 대조한다. 누설·scope·code_hash 동일성 검사를 끈 사본에서 해당 3건이 실패함을 확인했다.
실자료 fit 은 돌리지 않았다 — main pool 을 소비하지 않았다.

## Y.4 잠금

`mobse/v2` 변경으로 잠금을 재생성했다. split·창 불변, code_hash 만 `e96eff358ce3` → `729b28bba30e`.

```
… → 6e68eb939beb (E19/E20 코드) → 02e7434f228c (P8·P9 개정 기록) → c34ae1f60948 (WI-06 evaluate 배선, 현행)
```

## Y.5 마감

이 보고서의 sha256 이 gate evidence 에 묶여 있어, 이 파일 안에 자기 마감 결과를 적으면 순환한다.
rev26 마감 5단계 결과는 커밋 메시지와 인수인계 문서에 적는다. 1·2차 마감에서 17번이 해시 갱신
누락 3건(잠금 파일 기록 2곳, 이 보고서 1곳)을, 22번이 보고서의 lock_hash 인용 누락 1건을 잡아 고친 뒤 다시 돌렸다.

## Y.6 이번 회차에 확인하지 못한 것

- evaluate 를 **실자료**로 돌리지 않았다 — outer fit 이 없다(통과대역·P8 전 fit 금지).
- `report`·`prepare` 본체는 아직 없다.
- 통과대역 상한은 여전히 선생님 결정 대기 (X.7).

---

# 부록 Z — P9 band-pass 구현 · P10 정확 DOF (rev27, 2026-09-23 예약 슬롯)

## Z.1 결정과 범위

선생님 결정 원문: 결정 2 **"band-pass - 동시 회귀 ok"**, 결정 9 **"통과대역 0.2 Hz로"** (14:21 KST).
이 두 결정이 정한 것은 regression 순서(동시 회귀)와 통과대역 상한(0.1 → 0.2 Hz) 뿐이다. 하한 0.008 Hz,
`MIN_RESIDUAL_DOF = 30`, nuisance 구성(24P + aCompCor 5 + spike + intercept + linear drift), FD 기준, 창 `[12,252)` 는 바꾸지 않았다.

## Z.2 구현 선택 (결정이 아니라 측정과 맞춘 것)

- 차단대역 기저는 결정 전 DOF 실측에 쓴 **DCT-II** `cos(π·k·(t+0.5)/n)`, `f_k = k/(2·n·TR)` 이다. `f_k` 가 [0.008, 0.2] 밖인 성분을 nuisance 설계행렬 뒤에 붙여 한 번에 최소제곱 회귀한다 (`mobse/v2/extract.py::add_stopband`).
- **k=0 은 넣지 않는다** — 상수열이라 intercept 와 같다. 넣어도 rank 는 같으므로 실측 스크립트(k=0 포함)와 DOF 가 동일하다. linear drift 는 차단대역 기저와 선형독립이라 그대로 두었다(계획서 §3.2 상수/추세 구성 불변).
- residual DOF 는 **정확식 `n − rank([nuisance, 차단대역 기저])`** (개정 P10). P6-b `min(…)` 식은 계획서에 기록으로 남기고 코드에서는 제거했다.
- `summarize_design` 은 차단대역 기저가 없는 설계를 거부한다 — filter 없이 DOF 를 세면 조용히 과대 보고되던 P6-b 경로를 막는다.
- manifest: schema `wi02-extract-0.2`, run 레코드 `design` 에 `nuisance_rank`, `design_rank`(결합), `residual_dof_definition`, `filter_spec`(method·basis·n_stopband·n_passband) 추가, `filter_dof` 제거. `nuisance_columns` 에는 nuisance 열만 적는다.

## Z.3 검증

- 시험: `test_extract.py` 에 6개 조합의 통과대역 성분 수(104/124/139/104/123/185)와 spike 없는 run 의 정확 DOF(74/94/109/74/93/155)를 `dof_probe_hi0.2.json` 의 `n_pass_dct`·`new_dof` 중앙값과 대조, 통과대역 보존·차단대역 제거(DCT 성분 정확, 격자 밖 0.35 Hz 사인 제거·0.07 Hz 보존), 겹친 자유도를 한 번만 세는지, 기저 없는 설계 거부. `test_wi02_driver.py` 는 드라이버가 **결합 설계로 회귀하는지**를 spy 로 직접 확인한다(DOF 수치만으로는 nuisance 만 회귀하는 결함을 못 잡는다).
- 변이 검사 4건(h197 사본): 드라이버가 nuisance 만 회귀, 상한 0.1 복귀, DOF 1 차이, k=0 포함 — 결과는 Z.6.
- 실자료 dry-run (h197, `--dry-run --limit 6`, 비정본 scratch `$HOME/slot/p9_dry/`): PIOP1 emo·PIOP1 rest·PIOP2 rest 18 run 의 ok/excluded 판정과 사유가 `derivatives_v2` 와 **전부 같고**, DOF 는 spike 없는 run 에서 74 / 109 / 155, spike 있는 run 에서 그보다 spike 수 이하로 작다.

## Z.4 잠금

`mobse/v2/extract.py` 변경으로 잠금을 재생성했다. split·코호트 불변(19번 42/42), code_hash `729b28bba30e` → `87c119c14e21`.

```
… → 02e7434f228c (P8·P9 개정 기록) → c34ae1f60948 (WI-06 evaluate 배선) → cf66f91e12fb (P9/P10 구현, 현행)
```

**주의 — 이 잠금의 창 파일은 아직 P9 이전 추출본(`derivatives_v2`, 통과대역 미적용)이다.** 잠금은 코드와 창을 함께 기록하지만
이번 잠금에서 두 쪽은 같은 추출을 가리키지 않는다. 전 창 재추출(`derivatives_v3*`) 뒤 다시 잠근다. 그 전에는 main pool 을 소비하는 fit 을 하지 않는다.

## Z.5 발견 — `derivatives_v2` 에는 band-pass 가 적용되지 않았다

코드를 읽어 확인했다: 종전 `10_wi02_extract.py::process_run` 은 nuisance 회귀 → z-score → 2초 격자 재표집만 했고, `BANDPASS_*` 는
manifest 에 **기록만** 되었다(필터 적용 코드 없음). 계획서 P6-a("전체 run 을 native grid 에서 필터링")는 구현되지 않은 상태였다.
P9 결정 전에는 regression 순서가 미정이었으므로 적용을 미룬 것이지만, manifest 의 `bandpass_hz` 가 적용된 것처럼 읽힌다는 점은
"기록만 하고 검사하지 않는" E20 과 같은 부류다. 이번 구현으로 `filter_spec.method` 가 실제 적용 경로를 가리키고, 기저 없는 설계는 거부된다.
PIOP1 rest(TR 0.75초)는 그동안 0.25 Hz 초과 성분이 남은 채 2초 격자로 재표집되었다 — 재추출로 해소된다.

## Z.6 변이 검사와 마감

변이 검사 (h197 scratch 사본, `test_extract.py`+`test_wi02_driver.py` 66건): M1 드라이버가 nuisance 만 회귀 → 1건 실패(spy 시험),
M2 상한 0.1 복귀 → 20건, M3 DOF +1 → 10건, M4 k=0 포함 → 9건. 네 변이 모두 검출.
PIOP1 rest 의 2초 격자 재표집은 `preprocess.resample_to_grid` 의 선형 보간(`np.interp`)이며 별도 anti-alias 필터가 없음을 코드로 확인했다(Z.5 근거).
rev27 마감 5단계 결과는 순환을 피해 커밋 메시지와 인수인계 문서에 적는다(Y.5 규칙).

## Z.7 이번 회차에 확인하지 못한 것

- 전 창 재추출을 하지 않았다 — 적격 157/189·split_hash 불변은 dry-run 18 run 에서만 확인.
- 1,295 run 전체에서 동시 회귀의 수치 안정성(결합 설계 조건수)을 재지 않았다. PIOP1 rest 는 결합 설계 열이 약 370개(n=480)다.
- P8 은 구현 전.

---

# 부록 AA — P9 전 창 재추출 · 대조 · 재잠금 (rev28, 2026-09-23 예약 슬롯)

## AA.1 재추출

h197, HEAD `4316ef1`, 2026-09-23T06:20:51Z–06:56:25Z. 출력은 새 디렉터리 `derivatives_v3/`(PIOP1)·`derivatives_v3_piop2/`(PIOP2) — `derivatives_v2*` 는 건드리지 않았다.
6개 조합 모두 rc=0, error 0. 여섯 manifest header 가 전부 schema `wi02-extract-0.2`, `bandpass_hz [0.008, 0.2]`, `dry_run false` 이고, ok run 의 `filter_spec.method` 는 전부 `simultaneous_regression` 이다.
ok run 의 residual DOF 최솟값은 조합별 66 / 82 / 80 (PIOP1 emo·wm·rest), 67 / 87 / 145 (PIOP2) — 모두 `MIN_RESIDUAL_DOF = 30` 초과.

## AA.2 run 단위 대조 (v3 ↔ v2)

`run_key` 로 맞춰 status 와 사유 집합을 비교했다 (PIOP1 WM 은 E18 로 v2 1차본에 빠진 sub-0171 창이 있는 `recovery_20260923/wm_rerun3` 과 합쳐 기준으로 삼음).

| 조합 | run | ok / excluded / skipped (v2 = v3) | status 차이 | 사유 차이 |
|---|---|---|---|---|
| PIOP1 emomatching | 216 | 183 / 25 / 8 | 0 | 0 |
| PIOP1 workingmemory | 216 | 176 / 31 / 9 | 0 | 0 |
| PIOP1 restingstate | 216 | 202 / 8 / 6 | 0 | 1 |
| PIOP2 emomatching | 226 | 204 / 18 / 4 | 0 | 1 |
| PIOP2 workingmemory | 226 | 214 / 10 / 2 | 0 | 0 |
| PIOP2 restingstate | 226 | 203 / 21 / 2 | 0 | 0 |

사유 차이 2건은 **이미 제외된 run** 에 `residual_dof<=30` 이 추가로 붙은 것이다 (`ds002785/sub-0200` rest, `ds002790/sub-0057` emo — 둘 다 mean_fd·spike 사유로 v2 에서도 제외). 차단대역 기저가 자유도를 쓰는 P10 정확식의 예상된 결과이고, 판정은 바뀌지 않았다.

## AA.3 창·코호트·분할

- `12_build_windows_manifest.py`: PIOP1 창 1,436, PIOP2 창 1,672 — v2 와 `window_key` 집합이 같고 해시 외 필드 차이 0, `data_sha256` 은 전부 달라졌다(필터가 바뀌었으므로 기대한 결과).
- `15_build_subjects.py`: 적격 **157/216**, **189/226**. `subjects.jsonl` 은 v2 와 **바이트 단위로 같다** (sha256 `5ab1933922027dee…`, `a19570288677369a…`).
- `mobse.v2.cli split --config configs/redesign_v1/main.yaml` → `derivatives_v3/splits_piop1_p7/folds.json`: split_hash **`ace5f4a41446…` 재현**, config_hash `85556f56`, pilot 31 / main 126, outer test [26,25,25,25,25]. v2 folds 와 다른 키는 `subjects_manifest` 경로 하나.

코호트·분할 불변이 확인되어 재잠금으로 진행했다 (달랐다면 멈추고 보고하기로 한 지점).

## AA.4 재잠금

`scripts/h197/18_build_measurement_lock.py` 의 `COHORTS` 경로를 `derivatives_v3*` 로 바꾸었다 (다른 코드 변경 없음 — `mobse/v2` 불변, code_hash `87c119c14e21` 유지).
잠금 `cf66f91e12fb` → **`e8b648a7c4dc`** (2026-09-23T07:18:44Z). 19번 42/42, 25번 창 4,728 전부 `derivatives_v3*` 안에서 역참조·해시 일치.
rev27 의 caveat("코드와 창이 같은 추출을 가리키지 않는다")는 이 잠금으로 해소된다. 잠금 파일에 남은 `derivatives_v2` 문자열은 `--reason` 본문 한 곳뿐이다.

```
… → c34ae1f60948 (WI-06 evaluate 배선) → cf66f91e12fb (P9/P10 구현) → e8b648a7c4dc (P9 재추출 창, 현행)
```

## AA.5 이번 회차에 확인하지 못한 것

- 결합 설계 조건수(수치 안정성)는 여전히 1,295 run 전체에서 재지 않았다 (Z.7).
- 재추출 창의 신호 수준 점검(통과대역 밖 잔여 전력)은 하지 않았다 — 합성 시험(Z.3)에만 근거.
- P8 은 구현 전. main pool 을 소비하는 fit 은 하지 않았다.
- `derivatives_v2*` 는 대체되었으나 삭제하지 않았다 (정리는 선생님 확인 뒤).


# 부록 AB — P8 구현 (rev29, 2026-09-23 예약 슬롯)

선생님 결정 원문(2026-09-23): "P8 - 최소 1,500 update 보장, 상한 200 epoch, early stopping은 최소치 이후에만 ok (필요하다면 epoch 수를 더 늘려도 됨. 최소 수치 조정도 가능)". 이번 회차는 값(1,500 / 200)을 그대로 구현했고 조정하지 않았다. patience 5·min_delta 0.0005 는 결정 범위 밖이라 그대로다.

## AB.1 구현

- `mobse/v2/train.py`: `MAX_EPOCHS` 50 → 200, `MIN_UPDATES = 1500`, `updates_per_epoch(n) = ceil(n/32)`, `min_epochs_for(n) = ceil(1500 / updates_per_epoch(n))`. `early_stop_epoch(..., min_epoch)` 는 최소 epoch 이전 epoch 를 best 후보·인내 계산에서 제외한다.
- `mobse/v2/fitting.py::train_fold(min_updates=MIN_UPDATES)`: inner fit 은 최소 epoch 전에 멈추지 않는다. 최소 epoch 이 epoch 상한을 넘거나, outer 공통 E 가 최소 update 를 채우지 못하거나, epoch 이 200 을 넘으면 `FitError`. `FitResult` 에 `min_epoch`·`updates_per_epoch`·`updates_run` 기록.
- config: `train.max_epochs: 200`, 새 잠긴 키 `train.min_updates: 1500` (main·pilot·external). CLI `fit` 은 config 값을 넘기고 `fit_report.json` 에 기록한다. `scripts/h197/23_pilot_learnability_probe.py` 기본값도 200 / 1,500.

## AB.2 구현 선택 (결정이 아니라 결정을 지키기 위한 것)

- **best epoch 도 최소 epoch 이후에서 고른다.** 멈춤만 늦추고 best 를 전 구간에서 고르면 공통 E(= inner best 12개 중앙값 올림)가 최소치 아래로 내려가 outer fit 이 1,500 update 를 못 채울 수 있다.
- 기본값 `min_updates` 를 1,500 으로 두었다 — 인자를 빠뜨리면 조용히 최소치가 꺼지는 기본값을 피했다 (E21 과 같은 유형). 0 은 합성 시험만 쓴다.

## AB.3 main 분할에서의 귀결 (subject 수만 센 것 — 창·라벨·예측을 읽지 않음)

적격 subject 당 창 8개(2 task × 4)를 가정해 `folds.json`(split_hash `ace5f4a41446`)의 subject 수로 계산했다. inner 학습 창 528–544 → update/epoch 17 → **최소 epoch 89**. outer 학습 창 800–808 → update/epoch 25–26 → 최소 epoch 58–60. inner best ≥ 89 이므로 공통 E ≥ 89 이고 outer fit 은 최소 89 × 25 = 2,225 update 로 최소치를 넘는다.

## AB.4 검증·재잠금

- 시험 (h197): **631 passed / 12 skipped** (신규 12건: 상수, 최소 epoch 계산, 최소치 전 멈춤·선택 금지, 상한 초과·최소치 미달 거부, 기본값 고정, CLI 가 1,500 을 넘기는지 spy, config 덮어쓰기 거부).
- `mobse/v2` 가 바뀌어 잠금 재생성: `e8b648a7c4dc` → **`9ae4e4ee1a91`** (2026-09-23T08:20:30Z), code_hash `87c119c14e21` → `4382c5bd78ae`. 19번 42/42, 25번 창 4,728. 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → cf66f91e12fb (P9/P10 구현) → e8b648a7c4dc (P9 재추출 창) → 9ae4e4ee1a91 (P8 구현, 현행)
```

## AB.5 이번 회차에 확인하지 못한 것

- pilot update probe 재측정(재추출 창, P8 규칙)은 하지 않았다. pilot 분할에서 최소 epoch 이 200 을 넘는지 아직 모른다 — 넘으면 fit 이 거부되고, 상한·최소치 조정은 결정문대로 pilot 측정 근거로만 한다.
- 창 8개/subject 가정은 적격 정의(두 task run 모두 ok)에서 온 것이고 fold 별로 창 수를 직접 세지는 않았다.
- 1,500 update·200 epoch 에서의 실측 학습 시간은 재지 않았다 (인수인계 문서의 약 10 h 는 추정).
- main pool 을 소비하는 fit 은 하지 않았다.


# 부록 AC — E22 결정성 적용 (rev30, 2026-09-23 예약 슬롯)

잠긴 config 키 `runtime.deterministic: True`(choices=(True,))는 기록만 되고 torch 에 적용되지 않았다. rev29 뒤 pilot P8 probe 에서 같은 인자(v3 창, inner 0, seed 42, 1,500 update, cuda)를 두 번 돌려 train BA 0.808 / 0.500 이 나왔다 — E21(band-pass 기록만) 과 같은 유형이다. 이 조치는 프로토콜이 이미 True 로 잠근 것을 적용하는 것이라 결정을 요하지 않는다.

## AC.1 구현

- `mobse/v2/fitting.py::apply_determinism()`: `torch.use_deterministic_algorithms(True)` (비결정 연산은 RuntimeError), `cudnn.deterministic = True`, `cudnn.benchmark = False`, `CUBLAS_WORKSPACE_CONFIG` 미설정이면 `:4096:8`, 이미 `:4096:8`·`:16:8` 이면 유지, 다른 값이면 `FitError`. 적용 뒤 실제 상태를 되읽어 하나라도 꺼져 있으면 `FitError`.
- `train_fold` 가 seed 설정 전에 호출한다. CLI `fit` 과 probe 23·24 가 모두 이 진입점을 쓴다. 상태는 `FitResult.determinism` 에 남는다.
- CLI `fit`: `runtime.deterministic` 이 True 가 아니면 `CLIError`, `fit_report.json` 에 `determinism` 기록.

## AC.2 검증

- 시험 (h197): **637 passed / 12 skipped** (신규 6: 설정 적용, 동등 cuBLAS 값 유지, 비결정 값 거부, train_fold spy, CUDA 에서 같은 seed 두 번 예측 동일, CLI 기록). 전체 시간 168.9 s (rev29 판 약 119 s).
- 실자료 반복 (pilot-of-pilot, 측정 전용): 위 인자 두 번 → 모든 스칼라 출력 동일 (train BA 0.808 / 0.808, val BA 0.571 / 0.571). 한 쌍만 확인했다.
- `mobse/v2` 가 바뀌어 잠금 재생성: `9ae4e4ee1a91` → **`a8537ffba0bd`** (2026-09-23T09:20Z), code_hash `4382c5bd78ae` → `c2b943c04b93`. 19번 42/42, 25번 창 4,728. 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → e8b648a7c4dc (P9 재추출 창) → 9ae4e4ee1a91 (P8 구현) → a8537ffba0bd (E22 결정성 적용, 현행)
```

## AC.3 pilot P8 probe 재측정 (결정적 실행, 측정 전용 — 가설 검정 아님)

분할은 `derivatives_v2/pilot_tech/splits/folds.json`(pilot-of-pilot, subject 목록만). cell A, config 0, outer 0, inner 0–2 × seed 42–44, 1,500 update (학습 창 104–112, update/epoch 4 → 375 epoch; P8 상한 200 을 이 probe 프로세스에서만 풀었다 — 프로토콜 상수 불변). main pool 을 쓰지 않았다.

| 창 | fit | train BA 중앙값 [범위] | train BA = 1.0 | val BA 중앙값 [범위] | 선형 기준선 val BA |
|---|---|---|---|---|---|
| v2 (대체된 창) | 9 | 1.000 [0.654, 1.000] | 7/9 | 0.714 [0.429, 0.833] | 1.000 / 0.917 |
| v3 (0.008–0.2 Hz) | 9 | 0.962 [0.643, 1.000] | 1/9 | 0.571 [0.500, 0.750] | 1.000 / 0.917 |

- rev29 인수인계에 적힌 비결정 실행 수치(v3 train BA 중앙값 0.750, 1.0 도달 0/9)는 이것으로 대체한다. 결정적 실행에서 v3 의 학습 적합 저하는 그보다 작다 (중앙값 0.962). val BA 중앙값은 v2 0.714, v3 0.571.
- 1 cell·1 config·pilot 규모이고 fit 9개씩이다. 차이의 원인은 진단하지 않았다.

## AC.4 이번 회차에 확인하지 못한 것

- 결정성의 실자료 확인은 한 쌍(v3, inner 0, seed 42)뿐이다. 다른 cell·config 의 비결정 연산 여부는 CUDA 합성 시험(cell B)과 이 한 쌍으로만 확인했다 — 비결정 연산이 있으면 조용히 넘어가지 않고 RuntimeError 로 멈춘다.
- 결정성 설정의 학습 시간 영향은 재지 않았다 (probe fit 한 개 약 35–45 s, 이전 약 30 s — 같은 조건 비교 아님).
- main pool 을 소비하는 fit 은 하지 않았다.


# 부록 AD — WI-06 report CLI 배선 (rev31, 2026-09-23 예약 슬롯)

인수인계 남은 작업 2번. 선생님 결정 "CLI - 추천안 대로"(evaluate → report → prepare)의 둘째 단계다. 결정을 요하는 값은 새로 정하지 않았다 — seed·반복 수·percentile·δ·임계는 모두 잠긴 config 에서 읽는다.

## AD.1 계약

- 입력: `--config --evaluation(evaluation.json) --predictions(run_predictions.jsonl) --subjects(subjects.jsonl) --output-dir`. 출력 `statistics.json` (schema `wi06-statistics-0.1`), 덮어쓰기 거부.
- 경로 계약 변경(구현 선택, 결정 아님): report 필수 경로에 `evaluation`·`subjects` 를 추가했다. `run_predictions` 에 `group_id` 가 없어 group 재표집의 출처가 필요하다.

## AD.2 통계

- config 값: seed 9001, 10,000회, 주 contrast [1.25, 98.75], 보조 [2.5, 97.5], δ 0.02, 임계 0.5.
- group 재표집 index 를 **한 번** 만들어 H1(A−B)·H2(A−C)·interaction·cell BA 에 공유한다 (계획서 §8 "모든 cell 에 같은 재표집").
- H1·H2 는 97.5% family-wise CI, interaction·cell BA 는 95% 기술적 CI. `statistics.interpret` 문자열과 `lower_gt_0`·`lower_gt_delta`, `both_primary_lower_gt_0` 를 기록한다. **유의성은 gate 가 아니다** — G3 판정은 완전성·정합성뿐이다.

## AD.3 무결성

evaluation.json 의 config_hash, run_predictions sha256 기록과 대조한다. run 행마다 threshold, `prediction = classify(ensemble_p)`(동일값 class 1), window×seed 4×3, 분류 task, 중복을 검사한다. run 행만으로 subject `b_i` 를 재계산해 evaluation.json 의 subject_scores·subject_differences·cell BA 와 대조한다. complete-case, cell 간 subject 동일, subjects.jsonl 의 group 존재·eligible, subject 수를 확인한다.

## AD.4 시험

`tests/v2/test_cli_report.py` 11건 — evaluate 시험의 합성 release(outer fold 2 × cell 4 × seed 3, main pool 10명)를 evaluate → report 로 끝까지 돌린다. H1 점추정 0.25 와 97.5%·95% 구간을 `statistics.py` 없이 PCG64 로 독립 재계산해 대조하고, H2 는 0 구간, 가족 group 을 넣으면 n_groups 9 로 통째 재표집됨을 확인한다.

- 돌연변이 (Mac 사본): sha 대조·group 매핑·부적격 검사를 하나씩 끄면 해당 시험이 실패한다. subject_scores 대조와 subject_differences 대조는 하나만 끄면 다른 하나(와 cell BA 대조)가 잡는다 — 중복 장치다.
- 첫 판은 시험이 `test_cli_evaluate` 를 import 문으로 불러 import closure 가드(`test_import_closure` 2건)가 핀 없는 third-party 로 잡았다. 파일 경로 로드로 바꿨다.
- h197 전체: **648 passed / 12 skipped** (137 s).

## AD.5 잠금

`mobse/v2/cli.py` 변경으로 잠금을 재생성했다: `a8537ffba0bd` → **`bdf27e45a1ad`** (2026-09-23T10:23:35Z), code_hash `c2b943c04b93` → `2f0c2d426a97`. 19번 42/42, 25번 창 4,728. 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → 9ae4e4ee1a91 (P8 구현) → a8537ffba0bd (E22 결정성 적용) → bdf27e45a1ad (WI-06 report CLI, 현행)
```

## AD.6 이번 회차에 확인하지 못한 것

- report 를 **실자료**로 돌리지 않았다 — outer fit 이 없다 (main pool 미소비).
- 합성 release 는 subject 하나 = group 하나이고 가족 group 은 시험 1건뿐이다. 실제 코호트는 관계 metadata 부재로 group = subject 다 (P4).
- `prepare` 본체는 아직 없다.


# 부록 AE — WI-06 prepare CLI 배선 (rev32, 2026-09-23 예약 슬롯)

인수인계 남은 작업 2번. 선생님 결정 "CLI - 추천안 대로"(evaluate → report → prepare)의 마지막 단계다. 결정을 요하는 값은 새로 정하지 않았다 — 분석 구간은 잠긴 config, 통과대역은 코드 상수(결정 9)에서 읽어 **대조만** 한다.

## AE.1 추출 스크립트와의 관계 (먼저 확인한 것)

- 실제 release 산출물은 세 단계로 만들어졌다: `scripts/h197/10_wi02_extract.py`(fMRIPrep → ROI 창·QC, run manifest) → `12_build_windows_manifest.py`(target task manifest → `windows.jsonl`) → `15_build_subjects.py`(세 task manifest → `subjects.jsonl`·`exclusions.jsonl`).
- 기존 prepare 골격의 계약 `--config --source-runs --output-dir` 은 쓸 입력이 없었다. release 스키마 `source_runs` 는 만들어진 적이 없고, WI-01 감사본은 스키마가 다르다 (부록 E.2).
- 10번은 원자료 경로·atlas 를 받고 209 GiB 를 읽는다. CLI 에 넣으면 경로 계약이 원자료 배치에 묶인다.

## AE.2 계약 (구현 선택, 결정 아님)

- **prepare = 12 + 15 를 한 명령으로.** 입력 `--config --extract-manifests(한 dataset 의 emomatching·workingmemory·restingstate 셋) --output-dir`. 출력 `windows.jsonl`·`subjects.jsonl`·`exclusions.jsonl`·`cohort_summary.json`·`prepare_report.json`(schema `wi06-prepare-0.1`), 덮어쓰기 거부. 추출(10번)은 CLI 밖에 둔다.
- 새 계산은 없다 — 12·15 가 부르던 `labels.build_window_records`·`cohort.build_subjects` 등을 그대로 부른다. 창은 `TARGET_TASKS` 순서로 만든다 (인자 순서 무관).

## AE.3 무결성

- 헤더 대조 (기록만 되고 대조되지 않는 값을 남기지 않는다, E21·E22 류): `schema_version = wi02-extract-0.2`, `analysis_interval_sec = [timing.analysis_start_s, analysis_end_s]`, `bandpass_hz = [extract.BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ]`, `dry_run is False`, `atlas_sha256` 형식.
- 세 task 정확히 하나씩, dataset·atlas_sha256 단일. rest 가 빠지면 거부 (조용히 전원 부적격을 내지 않는다).
- 적격 subject 마다 창 2 task × 4 = 8개.

## AE.4 실자료 대조 (h197, 측정 전용 — fit 없음, main pool 미소비)

`derivatives_v3`·`derivatives_v3_piop2` 의 잠긴 manifest 를 **섞은 순서**(rest, wm, emo)로 넣어 `$HOME/slot/prep_eq_20260923_201836/` 에 썼다. 잠긴 산출물과 **바이트 동일**:

| cohort | windows.jsonl | subjects.jsonl | exclusions.jsonl |
|---|---|---|---|
| PIOP1 (main.yaml) | `0750c81c0670` 동일 | `5ab1933922027` 동일 | `2e51f25bf1df` 동일 |
| PIOP2 (external.yaml) | `640d36b58c52` 동일 | `a19570288677` 동일 | `a8546588bf2e` 동일 |

## AE.5 시험

`tests/v2/test_cli_prepare.py` 19건 — 합성 manifest(5명, 부적격 2명)로 12·15 스크립트를 subprocess 로 돌린 결과와 바이트 동일, 인자 순서 무관, 덮어쓰기·rest 누락·task 중복·dataset 혼합·미지 task·헤더 7종·atlas 불일치·창 누락(spy) 거부, 옛 `--source-runs` 계약 거부, 모든 하위 명령에 본체 있음. `test_evaluate_cli.py` 의 "prepare 미구현" 시험은 "옛 계약 거부" 로 바꿨다.

- 돌연변이 (Mac 사본): 헤더 대조를 끄면 6건, dataset·atlas·task 중복·창 수 검사를 하나씩 끄면 각 1건 실패. 헤더의 atlas 형식 위반(`xyz`)은 헤더 대조를 꺼도 task 간 atlas 불일치 검사가 잡는다 — 중복 장치로 기록.
- h197 전체: **667 passed / 12 skipped** (156 s).

## AE.6 잠금

`mobse/v2/cli.py` 변경으로 잠금을 재생성했다: `bdf27e45a1ad` → **`bcb08fc40f09`** (2026-09-23T11:23:37Z), code_hash `2f0c2d426a97` → `117f7340f186`. 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → a8537ffba0bd (E22 결정성 적용) → bdf27e45a1ad (WI-06 report CLI) → bcb08fc40f09 (WI-06 prepare CLI, 현행)
```

## AE.7 이번 회차에 확인하지 못한 것

- 10번(추출)과 prepare 사이의 계약(manifest 헤더 필드)은 헤더 대조로만 묶였다. 10번 자체를 CLI 로 옮기지 않았다.
- `cohort_summary.json` 은 입력 경로를 담아 잠긴 파일과 바이트 비교하지 않았다.
- `prepare_report.json` 의 `code_hash`·`env_hash` 는 기록하지 않는다 (잠금이 code_hash 를 가진다).


# 부록 AF — S 후보 1·3 (logistic) 과 S 선택 규칙 (rev33, 2026-09-23 예약 슬롯)

인수인계 남은 작업 2번의 첫 단위. 선생님 결정 5 원문: "§6 S 후보 4 + 구조 비교 2 - 추천안 대로" — 구현·합성 시험은 지금, 실자료 실행은 main OOF 와 같은 release. 이번 단위는 **S 후보 1·3 과 네 후보 공통 선택 규칙**만 다룬다. S 후보 2·4 (32-hidden MLP) 와 구조 비교 2종은 아직이다. 실자료 실행 없음, main pool 미소비.

## AF.1 계획서가 정한 것 (그대로 옮김)

- S 후보 1: raw ROI mean/variance 200 + logistic regression. S 후보 3: signed Fisher-z FC 4,950 + logistic regression. FC 는 `features.window_features` 와 같은 함수 (시험이 배열 동일을 확인).
- StandardScaler 는 해당 training task 창에만 fit. C ∈ {0.001, …, 10000} 8개 (계획서 문장을 시험이 직접 파싱해 대조), L2·intercept.
- S 는 outer fold 마다 inner subject-equal log loss 최소 후보/설정. loss 는 A–D 와 같은 함수 (`train.subject_equal_loss`, inner 3 fold OOF run 확률).

## AF.2 구현 선택 (계획서가 정하지 않은 값 — 결정 아님)

- variance `ddof=0`, feature 순서 = ROI mean 100 뒤 variance 100.
- solver `lbfgs`, tol `1e-4`, max_iter `10000`, class_weight 없음. sklearn 1.8 에서 `penalty` 인자가 폐기 예정이라 `l1_ratio=0.0` 으로 L2 를 명시한다.
- 수렴 여부·반복 수를 fit 기록에 남기고 **미수렴 fit 이 섞이면 선택이 거부한다**.
- 선택 동률(차이 ≤ 1e-6)은 후보 순서 S1<S2<S3<S4, 그 다음 설정 순서(C 오름차순). A–D 의 동률 규칙(공동 BA)과 별개. 선생님이 달리 정하면 바꾼다.
- 비교하는 모든 후보/설정의 OOF run 집합이 같아야 한다 (같은 inner 모집단).

## AF.3 시험

`tests/v2/test_baselines.py` 17건 (합성 자료): 계획서 문장 대조 2, feature 순서·ddof·FC 동일·거부 3, sklearn Pipeline(StandardScaler + L2 logistic)과 예측 확률 일치·scaler 가 training 창 평균·C 크기 순서, 미수렴 기록, 합성 신호 복원 2 (mean 신호→S1, 상관 신호→S3), 설정 순서, loss 손계산, OOF 병합 중복 거부, 선택·동률·거부 5종, inner 3 fold × 16 설정 끝까지.

- 돌연변이 (Mac 사본, `.backup/baselines_mutation.sh`): ddof, 미수렴 거부, 동률 허용오차, 수렴 판정, OOF 집합 대조, fold 중복, C grid, 동률 순서, scaler 적용 — **9/9 검출**.
- 합성 상관 신호 시험은 초판(공통 성분 10 ROI, 45 edge)에서 4,950차원·80창으로 BA 0.625 에 그쳐 실패했다. 신호를 40 ROI 로 넓혀 통과시켰다 — 시험 자료 설계 문제이고 구현 변경은 없다.

## AF.4 잠금

`mobse/v2/baselines.py` 추가로 잠금을 재생성했다: `bcb08fc40f09` → **`4ea208ed77f7`** (2026-09-23T12:21:01Z), code_hash `117f7340f186` → `dc8ce8b741ae`. 검사 43건 (모듈 1개 증가), 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → bdf27e45a1ad (WI-06 report CLI) → bcb08fc40f09 (WI-06 prepare CLI) → 4ea208ed77f7 (S 후보 1·3, 현행)
```

## AF.5 이번 회차에 확인하지 못한 것

- S 후보 2·4 (MLP), 구조 비교 2종 — 미구현.
- 실제 규모(inner 학습 창 528–544, FC 4,950차원)에서 C=10000 의 lbfgs 수렴 여부 — 합성 소규모에서만 수렴 확인. 실자료에서 미수렴이 나오면 선택이 거부하므로 조용히 지나가지는 않는다.
- S 후보를 fit·evaluate CLI 에 배선하지 않았다 (라이브러리 함수만).

# 부록 AG — 결정 10 (logistic 미수렴, 개정 P11) · 결정 11 항목 2 (pilot 1,500 대 3,000 update) (rev34, 2026-09-23 예약 슬롯)

선생님 결정 원문 (2026-09-23 21:5x KST):

- 결정 10 — 권고 "main pool을 쓰지 않는 pilot 창으로 수렴 여부부터 재고, 그 결과를 보고 (a)를 사전 등록하는 것입니다. …" 에 **"ok"**. (a) 원문: "미수렴 설정은 빼고 나머지 grid에서 고르되, 뺀 설정 수를 보고합니다. 사실상 grid가 줄어드는 것이므로 계획서 개정 행이 필요합니다."
- 결정 11 — "main OOF 전에 정할 것 두 가지 — 1. logistic 미수렴 처리 규칙 — pilot 수렴 측정 뒤 사전 등록 / 2. v3 창에서의 최소 update 수 — pilot에서 1,500 대 3,000 비교 뒤 조정 여부 판단 …" 에 **"ok"**.

승인 범위 밖 (바꾸지 않음): logistic solver·tol·max_iter·C grid, 최소 update 값·patience·min_delta·batch·grid·상한 200 epoch.

## AG.0 문구 정정

부록 AF.2·AF.5 와 rev33 보고의 "미수렴 fit 이 섞이면 선택이 거부한다" 는 실제 동작 "**미수렴 설정이 하나라도 있으면 그 outer fold 의 선택 전체가 오류로 멈춘다**" 를 "해당 설정만 빼고 계속" 으로 읽히게 했다. rev34 부터 동작은 아래 AG.1 (개정 P11) 이다.

## AG.1 pilot logistic 수렴 측정 (측정 전용, main pool 미소비)

- 자료: `derivatives_v3` (0.2 Hz) pilot 창, pilot 기술 분할(`derivatives_v2/pilot_tech/splits/folds.json`, 31명) 5 outer × 3 inner = 15 fold. 창 해시 대조(verify=True).
- 대상: S1(ROI mean/var 200)·S3(FC 4,950) × C 8개, **현행 `fit_logistic` 그대로** (lbfgs, tol 1e-4, max_iter 10000).
- 산출물: h197 `MoBSE_dataset/derivatives_v3/pilot_tech_p8/logistic_convergence/` (`fits.jsonl` 240행, `summary.json`, `meta.json`, 측정 스크립트 사본, `git_head.txt` = 87d9804). 벽시계 200 s.

| 후보 | C | 미수렴 / 15 | 반복 수 중앙값 (최대) | fit 시간 중앙값 (최대) s |
|---|---|---|---|---|
| S1 | 0.001 | 0 | 4 (5) | 0.01 (0.06) |
| S1 | 0.01 | 0 | 9 (11) | 0.05 (0.11) |
| S1 | 0.1 | 0 | 24 (25) | 0.01 (0.50) |
| S1 | 1 | 0 | 51 (55) | 0.01 (1.44) |
| S1 | 10 | 0 | 67 (73) | 0.01 (1.37) |
| S1 | 100 | 0 | 59 (72) | 0.01 (1.68) |
| S1 | 1000 | 0 | 36 (43) | 0.01 (0.98) |
| S1 | 10000 | 0 | 18 (20) | 0.00 (0.43) |
| S3 | 0.001 | 0 | 18 (19) | 1.30 (1.81) |
| S3 | 0.01 | 0 | 22 (24) | 1.65 (2.12) |
| S3 | 0.1 | 0 | 23 (35) | 1.80 (3.16) |
| S3 | 1 | 0 | 18 (20) | 1.06 (2.07) |
| S3 | 10 | 0 | 12 (12) | 0.83 (1.15) |
| S3 | 100 | 0 | 12 (13) | 0.76 (1.25) |
| S3 | 1000 | 0 | 12 (13) | 0.70 (1.28) |
| S3 | 10000 | 0 | 12 (13) | 0.77 (1.26) |

**240 fit, 미수렴 0.** 학습 창 104–112. val loss·BA 는 `fits.jsonl` 에 저장만 했고 성능으로 해석하지 않는다.

한계 (확인하지 못한 경계):

- 수렴 판정은 sklearn lbfgs 의 tol 기준이다. S3 은 특징(4,950)이 표본보다 훨씬 많아 사실상 분리 가능하므로, 큰 C 에서 반복 수가 12 로 오히려 적은 것은 "유한한 최적해에 도달" 이 아니라 "기울기가 tol 아래로 떨어짐" 으로 읽어야 한다. 이 측정은 **경고 없이 끝나는지**만 보였다.
- main 학습 창(528–544)으로 외삽하지 않는다. main 에서 미수렴이 나오면 아래 P11 규칙이 처리한다.

## AG.2 사전 등록 — 개정 P11

- 멈춤 조건(21:56 기록 시 덧붙인 보호 장치, 선생님 원문 아님): "C ≤ 100 에서도 미수렴" 또는 "한 후보에서 8개 중 4개 이상 미수렴" → **해당 없음** (미수렴 0). 따라서 등록했다.
- 계획서 §11 P11 행 (개정 전: C grid·L2·intercept·solver/tol 고정, 미수렴 규칙 없음 → 개정 후: (a) 원문), 본문 §6 에 `[개정 P11]`.
- 코드 `mobse/v2/baselines.select_s`: 미수렴 설정(`converged=False`)을 후보에서 빼고 나머지에서 고른다. 뺀 설정은 `SSelection.excluded`(`"<candidate>/<setting_id>"`)·`n_excluded` 에 남고, `table` 행에 `converged` 가 붙는다. 동률 기준(best)도 수렴 설정 안에서만 잡는다. **모든 설정이 미수렴이면 멈춘다** (구현 선택 — P11 이 정하지 않은 경우).
- 시험 `tests/v2/test_baselines.py` 19건 (+2: 제외·보고, 미수렴 0 보고; 기존 거부 시험은 "전부 미수렴" 으로 바꿈). 돌연변이 (`.backup/baselines_mutation_p11.sh`, Mac 사본): 제외 목록·수·table 표기·동률 기준·후보 제외 5종 + 기존 9종 = **14/14 검출**.
- 잠금: `4ea208ed77f7` → **`3f3c751b35c7`** (2026-09-23T13:26:24Z), code_hash `dc8ce8b741ae` → `e259cb1048a8`. 검사 43건, 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → bcb08fc40f09 (WI-06 prepare CLI) → 4ea208ed77f7 (S 후보 1·3) → 3f3c751b35c7 (개정 P11, 현행)
```

## AG.3 결정 11 항목 2 — pilot 1,500 대 3,000 update (측정 전용, main pool 미소비 — 가설 검정 아님)

- 조건: `grid1500_det` (부록 AC.3) 과 같다 — cell A, config 0, outer 0, inner 0–2 × seed 42–44, 결정적 실행(E22). 3,000 update = pilot 750 epoch 이므로 `p8_probe_uncapped` 와 같은 방식으로 **이 프로세스 안에서만** `fitting.MAX_EPOCHS` 를 덮었다 (main 경로 가드·상수 불변). `min_updates 3000`, `max_epochs 750` → 정확히 750 epoch.
- 한 실행 안에서 25 epoch(= 100 update)마다 train/val loss·BA 기록. 기록용 train forward 는 torch CPU·CUDA RNG 상태를 저장·복원했다.
- 산출물: h197 `MoBSE_dataset/derivatives_v3/pilot_tech_p8/grid3000_det/` (18 실행 JSON, `summary.json`, 스크립트 사본, `git_head.txt`).

**결정성 대조**: 18 실행 모두 첫 375 epoch 의 val loss 열이 `grid1500_det` 과 **완전히 같고**, 1,500 지점의 train BA·val BA 도 18/18 일치했다.

| 창 | train BA 중앙값 1,500 → 3,000 | train BA 1.0 도달 1,500 → 3,000 | val BA 중앙값 1,500 → 3,000 | val BA 범위 1,500 → 3,000 |
|---|---|---|---|---|
| v3 (0.2 Hz) | 0.962 → 1.000 | 1/9 → 6/9 | 0.571 → 0.714 | [0.500, 0.750] → [0.571, 0.786] |
| v2 (0.1 Hz, 참고) | 1.000 → 1.000 | 7/9 → 9/9 | 0.714 → 0.643 | [0.429, 0.833] → [0.500, 0.857] |

곡선 (평탄해지는 지점):

- **곡선은 평탄해지지 않는다.** 한 실행 안에서 train loss 가 직전 기록의 1.5배를 넘게 뛰는 일이 v3 5–11회, v2 4–8회 있었다. 1,500–3,000 구간 기록 16개 중 train BA 1.0 인 기록 수는 v3 1–6개, v2 5–15개다.
- train BA 가 처음 1.0 에 닿는 update: v3 중앙값 2,100 [1,100, 2,700], v2 중앙값 600 [500, 1,900]. 끝까지 1.0 을 유지하기 시작하는 지점은 v3 6/9 에서 2,900–3,000, 나머지 3/9 는 3,000 에서도 1.0 이 아니다.
- 따라서 3,000 지점의 "1.0 도달 6/9" 은 끝점이 진동의 어디에 걸렸는지에 크게 좌우된다 — 끝점 한 개 값으로 예산 충분성을 판단하기 어렵다.

해석 한계: pilot 규모(학습 창 104–112, update/epoch 4)·1 cell·1 config (lr 0.001, dropout 0.1, weight decay 0.0001). val 은 7명 안팎 — val BA 차이를 성능 차이로 읽지 않는다.

권고 (결정 아님 — 최소치는 바꾸지 않았다):

1. v3 창은 v2 보다 학습 자료를 맞히는 데 update 가 약 3.5배 걸린다 (처음 1.0 도달 중앙값 2,100 대 600). 1,500 은 v3 에서 학습 자료 적합 전에 끊는 쪽이다.
2. 3,000 으로 올리면 main 최소 epoch 은 inner(학습 창 528–544, update/epoch 17) **177**, outer(800–808, 25–26) **116–120** — 상한 200 안이지만 inner 여유는 23 epoch 이다. 1,500 이면 inner 89, outer 58–60.
3. 다만 곡선의 진동은 update 수만의 문제가 아닐 수 있다 (학습률·안정성). grid·학습률 변경은 승인 범위 밖이라 측정하지 않았다.

선생님 판단이 필요한 것: 최소 update 를 (i) 1,500 유지, (ii) 3,000 으로 조정(계획서 P8 추가 행 + `train.MIN_UPDATES`·config 잠금 재생성), (iii) 다른 값 — 중 어느 쪽인지.

## AG.4 이번 회차에 확인하지 못한 것

- main 규모에서의 logistic 수렴 (pilot 결과를 외삽하지 않음).
- 곡선 진동의 원인 (학습률·batch·gradient clip 등) — 측정 범위 밖.
- 다른 cell(B–D)·config 1–7 에서 1,500 대 3,000 차이.
- S 후보 2·4·구조 비교 2 — 미구현 (남은 작업 3).

# 부록 AH — 결정 12 (가): `train_fold` best checkpoint 정정 · pilot config 4·0 6,000 update 곡선 (rev35, 2026-09-23 예약 슬롯)

선생님 결정 원문 (2026-09-23 23:1x KST): 23:00 대화 권고 "(가) 먼저 할 것: pilot 추가 측정 1회 + `train_fold` 정정 — config 4(학습률 0.0003)를 같은 조건으로 약 6,000 update까지 곡선 측정 … `train_fold` 가 best checkpoint의 확률을 내도록 고칩니다. 두 결과를 보고 최소치를 정하고, 필요하면 상한도 함께 조정합니다." 에 **"ok (가)로.. 만약 더 update가 필요하면 권고해 주길.."**.

승인 범위 밖 (바꾸지 않음): 최소 update·상한 값의 변경 자체(권고만), 학습률·patience·min_delta·batch·grid·gradient clip, 곡선 진동 원인 진단.

## AH.1 `train_fold` 정정 — 계획서 §7 정합 (새 결정 아님)

- rev34 까지 inner fit 은 best epoch 을 **기록만** 하고 평가 확률(`eval_run_probs`·`eval_window_probs`·`eval_loss`)과 반환 모델은 **마지막 epoch**(= best + patience 까지) 것이었다. 계획서 §7 은 config 를 inner OOF run loss 로 고르고 "selected best checkpoint의 epoch를 기록한다" — best checkpoint 기준이 맞는 해석이다. "기록만 하고 적용 안 하는" 구조의 또 한 사례 (E21·E22 와 같은 꼴).
- 코드 `mobse/v2/fitting.train_fold`: 최소 epoch 이후 매 epoch `early_stop_epoch` 로 현재 best 를 구하고, best 가 그 epoch 으로 갱신되면 `state_dict` 를 깊은 복사로 보관한다 (RNG 소비 없음). 끝나면 보관 epoch 이 최종 best epoch 과 같은지 확인(다르면 `FitError`)하고, best 가 마지막 epoch 이 아니면 복원한 뒤 평가 확률을 계산한다. best epoch 정의(최소 epoch 이후, min_delta 0.0005, patience 5)는 그대로다.
- outer/external fit(early stopping 없음, 정확히 E epoch)은 바뀌지 않는다.
- 기록: `FitResult.eval_epoch` (평가 가중치의 epoch), `fit_report.json` 의 `eval_epoch`.
- 시험 `tests/v2/test_fitting.py` +4 (36 → 40): (a) 반환 확률 = best epoch 시점 평가 forward 의 확률이고 마지막 epoch 확률과 다름, 반환 모델도 best checkpoint; (b) best 가 마지막 epoch 이면 결과 불변; (c) outer 경로 불변 (학습 중 평가 forward 없음, eval_epoch = E); (d) 같은 입력 두 번 → 확률·val loss 완전 동일. 돌연변이 (`.backup/slot_2315/mut_best_ckpt.sh`, Mac 사본): 복원 생략, 복원 안 함 조건, 매 epoch 보관, 복사 대신 참조 보관, eval_epoch 을 마지막으로, outer eval_epoch 오기 = **6/6 검출**.
- 이미 끝난 pilot 측정(`grid1500_det`·`grid3000_det`·아래 `grid6000_det`)은 min_updates = 전체 epoch 이라 early stopping 이 발동하지 않고 곡선을 기록하는 방식이므로 이 정정의 영향이 없다 — 재측정하지 않았다.
- 잠금: `3f3c751b35c7` → **`f93f1c504ba2`** (2026-09-23T14:21Z), code_hash `e259cb1048a8` → `39863e0e81fa`. 검사 43/43, 창 4,728, 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → 4ea208ed77f7 (S 후보 1·3) → 3f3c751b35c7 (개정 P11) → f93f1c504ba2 (결정 12 best checkpoint 평가, 현행)
```

## AH.2 pilot config 4·config 0 6,000 update 곡선 (측정 전용, main pool 미소비 — 가설 검정 아님)

- 조건: `grid3000_det` (부록 AG.3) 과 같다 — v3 창(0.2 Hz), cell A, outer 0, inner 0–2 × seed 42–44, 결정적 실행(E22), 100 update(25 epoch)마다 기록, 기록 forward 는 RNG 저장·복원. 6,000 update = pilot 1,500 epoch (update/epoch 4) — 이 프로세스 안에서만 `fitting.MAX_EPOCHS` 를 2000 으로 덮었다 (main 경로 가드·상수 불변). `min_updates 6000`, `max_epochs 1500` → 정확히 1,500 epoch.
- config (코드 `train.build_grid` 순서로 확인): **config 4** = lr 0.0003·dropout 0.1·wd 0.0001, **config 0** = lr 0.001·dropout 0.1·wd 0.0001. 두 설정을 GPU 0 에서 나란히 돌렸다 (다른 사용자 sglang 약 19 GB 동거).
- 측정은 시작 시점(HEAD 53211b8) 코드 사본(`grid6000_det/code/`)으로 돌렸다 — 같은 회차의 AH.1 편집이 도중에 섞이지 않게. 각 실행 JSON 에 `fit_module` 경로 기록.
- 산출물: h197 `MoBSE_dataset/derivatives_v3/pilot_tech_p8/grid6000_det/` (18 실행 JSON, `summary.json`, 스크립트·코드 사본, `git_head.txt`, `git_status.txt`). 벽시계 14:16:48Z–14:33:35Z (16 분 47 초), 실행당 학습 46–93 s.

**결정성 대조**: config 0 의 9 실행 모두 첫 3,000 update 곡선(30 기록)과 val loss 750개가 `grid3000_det` 과 **완전히 같다** (9/9).

| config | 지점 (update) | train BA 중앙값 | train BA 1.0 수 / 9 | val BA 중앙값 [범위] |
|---|---|---|---|---|
| 4 (lr 0.0003) | 1,500 | 0.808 | 0 | 0.583 [0.500, 0.929] |
| | 3,000 | 0.654 | 0 | 0.571 [0.500, 0.750] |
| | 4,500 | 0.692 | 1 | 0.571 [0.500, 0.750] |
| | 6,000 | 0.769 | 1 | 0.643 [0.500, 0.750] |
| 0 (lr 0.001) | 1,500 | 0.962 | 1 | 0.571 [0.500, 0.750] |
| | 3,000 | 1.000 | 6 | 0.714 [0.571, 0.786] |
| | 4,500 | 1.000 | 5 | 0.667 [0.500, 0.786] |
| | 6,000 | 1.000 | 7 | 0.750 [0.571, 0.786] |

| config | 처음 train BA 1.0 도달 update 중앙값 [범위] | 6,000 까지 1.0 에 못 닿음 | 끝까지 1.0 유지 시작 update | 진동 횟수 (train loss > 직전 × 1.5) |
|---|---|---|---|---|
| 4 | 3,600 [2,400, 4,600] (6/9) | **3/9** | 1/9 만 (6,000 = 마지막 기록 한 점) | 8–18 |
| 0 | 2,100 [1,100, 2,700] (9/9) | 0/9 | 7/9 가 5,400–6,000, 2/9 는 6,000 에서 1.0 아님 | 13–23 |

읽는 법:

- **두 설정 모두 6,000 update 안에서 train BA 1.0 이 안정되지 않는다.** config 0 의 "유지 시작" 5,400–6,000 은 끝점 직전에 걸린 것이라 안정 상태로 읽을 수 없다 (진동 13–23회).
- **config 4 는 update 를 늘려도 train 적합이 단조롭게 좋아지지 않는다** — 중앙값 0.808(1,500) → 0.654(3,000) → 0.769(6,000). 1,500 에서 1.0 은 0/9, 6,000 에서 1/9. 3/9 는 6,000 까지 한 번도 1.0 에 닿지 않았다 (i0 s43 은 3,000 이후 0.500–0.538 에 머묾).
- 해석 한계: pilot 규모(학습 창 104–112)·1 cell·2 config. val 은 7명 안팎. 이전 측정(부록 AC·AG)에서 같은 update 수에서 자료가 많을수록 덜 학습됐으므로 main(528–544)에서는 이 수치보다 update 가 더 필요할 수 있다 (미측정). 진동의 원인은 진단하지 않았다 (승인 범위 밖).

## AH.3 권고 (결정 아님 — 최소치·상한은 바꾸지 않았다)

선생님 원문 "만약 더 update가 필요하면 권고해 주길" 에 따른 권고다.

1. **update 수만으로는 해결되지 않을 가능성이 크다.** config 4 는 6,000 에서도 9개 중 1개만 train BA 1.0 이고 3개는 한 번도 닿지 않았으며, config 0 도 6,000 까지 안정되지 않았다. 최소 update 를 올리는 것은 "학습 자료에 닿을 기회" 를 늘릴 뿐 안정적 적합을 보장하지 않는다. 학습률·안정성(예: gradient clip, 학습률 schedule) 쪽은 승인 범위 밖이라 측정·진단하지 않았고 **선생님 판단에 넘긴다**.
2. update 를 올린다면, 두 학습률에 같은 기회를 주는 값으로 **U = 5,000** 을 권고한다 — config 4 의 처음 1.0 도달 최댓값 4,600 을 덮고 약간 여유를 둔 값이다 (pilot 기준, main 외삽 불확실성 때문에 하한으로 읽어야 한다). 이때 main 귀결:
   - inner 최소 epoch = ceil(5,000 / 17) = **295** (학습 창 528–544 → 17 update/epoch) → **상한 200 으로는 불가**. 상한은 최소 epoch + early stopping 여유가 필요하므로 **400** 을 함께 권고 (여유 105 epoch ≫ patience 5).
   - outer 공통 E ≥ ceil(5,000 / 25–26) = **193–200** epoch (학습 창 800–808).
   - 시간: 합성 벤치마크(결정성 적용 전, bmcws, 부록 참조 `wi03_resource_budget`) 의 학습 상한 1.87 h(50 epoch)를 epoch 비례로 늘리면 상한 200 → 약 7.5 h, 상한 400 → 약 15 h. main 실측이 아니며 결정성 적용 후 main 의 epoch 당 시간은 재지 않았다.
3. update 를 올리지 않는 선택(1,500 유지)이나 3,000 (상한 200 안, inner 여유 23 epoch) 도 가능하다. 3,000 은 config 0 에는 처음 1.0 도달을 9/9 덮지만(최댓값 2,700) config 4 에는 3,000 에서 1.0 이 0/9 다 — grid 가 lr 0.001 쪽으로 기운다.
4. AH.1 정정으로 config 선택은 이제 best checkpoint 의 inner loss 로 이뤄진다 — 곡선 진동 때문에 끝점 운에 좌우되던 부분은 줄었다. 이 점은 어느 값을 고르든 적용된다.

선생님 판단이 필요한 것: (i) 최소 update·상한 — 1,500/200 유지, 3,000/200, 5,000/400, 다른 값 중 하나. (ii) config 4(lr 0.0003)가 6,000 에서도 적합이 안정되지 않는 점을 update 밖의 수단(학습률·안정성)으로 다룰지 — 다룬다면 무엇을 pilot 에서 잴지. 값이 정해지면 계획서 P8 추가 행·`train.MIN_UPDATES`·`MAX_EPOCHS`·config 잠금 재생성·gate evidence 새 revision 을 한다.

## AH.4 이번 회차에 확인하지 못한 것

- main 규모(학습 창 528–544) 에서의 곡선·epoch 당 시간 (결정성 적용 후) — 미측정.
- config 1–3·5–7, cell B–D 의 곡선.
- 곡선 진동·config 4 적합 저하의 원인 — 승인 범위 밖, 진단하지 않음.
- 정정된 `train_fold` 의 실자료 실행 — 합성 시험만 (측정 곡선은 early stopping 이 발동하지 않는 방식이라 영향 없음).

# 부록 AI — S 후보 2·4 (32-hidden MLP) 구현·합성 시험 (rev36, 2026-09-24 예약 슬롯)

근거: 선생님 결정 5 "§6 S 후보 4 + 구조 비교 2 - 추천안 대로" (구현·합성 시험은 지금, 실자료 실행은 main OOF 와 같은 release). 인수인계 남은 작업 2번 — 결정 12 확인을 기다리는 동안 진행하는 가역 항목. **새 결정 없음. 실자료 fit 없음, main pool 미소비.**

## AI.1 프로토콜이 정한 것 (그대로 옮김)

- §6 표: S 후보 2 "동일 200 features + 32-hidden MLP", S 후보 4 "위 FC + 32-hidden MLP". feature 함수는 S 후보 1·3 과 같은 `roi_mean_var`·`fc_fisher_z`.
- §6 "S 후보의 StandardScaler는 해당 training task에만 fit한다", "MLP는 아래 8개 grid와 같은 예산이다" → §7 공통 grid config_id 0–7, AdamW·batch 32·cross-entropy·gradient clip 1.0, [개정 P8] 최소 update·상한 epoch·최소치 이후 early stopping, subject-equal validation log loss·patience 5·min_delta 0.0005, selected best checkpoint (결정 12 정정과 같은 규칙), outer 는 "해당 선택 모델의 3개 inner best epochs 중앙값 올림" (`train.baseline_epochs`) 만큼 정확히.
- 선택은 S 후보 1–4 공통 `select_s` (동률 S1<S2<S3<S4 → 설정 순서). MLP 의 setting_rank = config_id.

## AI.2 구현 (`mobse/v2/baselines.py`)

- `MLP_CANDIDATES = (S2, S4)`, `MLP_HIDDEN = 32`, `mlp_settings()` → 16 설정 (`config=<id>`), `build_mlp`, `fit_mlp`, `MLPFit` (`record()` 에 `converged: True`·`init_hash`), `mlp_param_hash`.
- `fit_mlp` 는 `fitting.train_fold` 의 학습 규칙을 feature 벡터 입력에 옮긴 것이다 — 결정성 적용(`fitting.apply_determinism`), `torch.manual_seed(model_seed)` 초기화, `model_seed` CPU generator shuffle, inner 는 최소 epoch 이후 best 갱신마다 가중치 보관 → best 복원 → 평가(보관/best 불일치면 실패), outer/external 은 `epochs_exact` 필수·early stopping 없음, 상한 초과·최소 update 미달 거부.
- **값은 모두 호출 시점의 `train` 상수를 읽는다** (`min_updates`·`max_epochs` 인자 기본값은 None, batch·patience·min_delta·grad clip 은 인자로 받지 않음). 결정 12 로 `train.MIN_UPDATES`·`MAX_EPOCHS` 가 바뀌면 MLP 쪽은 고칠 곳이 없다.

구현 선택 (프로토콜이 정하지 않음 — 결정 아님):

| 항목 | 선택 | 이유 |
|---|---|---|
| 층 구성 | 은닉층 1개 `Linear(d→32) → GELU → Dropout(p) → Linear(32→2)` | "32-hidden" 의 최소 해석 |
| 활성화 | GELU | §6 ROI encoder·gate 와 같은 활성화 |
| dropout 위치 | 은닉 활성화 뒤, p = grid 값 | grid 의 dropout 을 쓰는 유일한 자리 |
| 입력 표준화 | sklearn StandardScaler, training 창만 | S 후보 1·3 과 같음 |
| 초기화 | PyTorch 기본 (seed 뒤) | `train_fold` 와 같음 |
| 수렴 | 개념 없음 → `SEntry.converged` 항상 True | P11 은 logistic 규칙 |

## AI.3 시험 (`tests/v2/test_baselines.py`, 19 → 30, 합성 자료만)

계획서 문장 대조 (32-hidden, 8개 grid 예산), 설정 16개·순서, 구조 (층 종류·차원·dropout p), P8 기본값이 호출 시점 `train` 상수에서 오는지 (monkeypatch), 가드 9종, inner 가 최소 epoch 전에 멈추지 않음, **inner 평가 확률 = 같은 seed 로 best_epoch 만큼만 학습한 outer fit 의 확률·가중치와 완전 동일** (best checkpoint 복원 확인), 결정성·seed 별 초기화 해시·scaler 가 training 창만, S2(mean 신호)·S4(FC 신호) 합성 신호 회복 (창 정확도 ≥ 0.9), `select_s` 에서 S1<S2<S3<S4·config 순 동률 처리.

돌연변이 (`.backup/slot_0915/mut_mlp.py`, Mac 사본): best 복원 제거, 최소 epoch 전 멈춤 허용, scaler 를 평가 창에 fit, hidden 16, GELU→ReLU, dropout 고정, MIN_UPDATES 리터럴 고정, outer epoch 요구 제거, 상한 검사 제거, seed 무시, 후보 순서 뒤집기 = **11/11 검출** (seed 무시는 첫 판에서 살아남아 `init_hash` 기록·시험을 추가한 뒤 검출).

## AI.4 잠금

`mobse/v2` 변경으로 재잠금 `f93f1c504ba2` → **`4acf47a8c79a`** (2026-09-24T00:22:06Z), code_hash `39863e0e81fa` → `0f30e7b29312`. 검사 43/43, 창 4,728, 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → 3f3c751b35c7 (개정 P11) → f93f1c504ba2 (결정 12 best checkpoint 평가) → 4acf47a8c79a (S 후보 2·4 MLP, 현행)
```

## AI.5 이번 회차에 확인하지 못한 것

- MLP 의 실자료 fit·GPU 실행·main 규모 시간 — 하지 않음 (실자료 실행은 main OOF 와 같은 release).
- `fit_mlp` 의 학습 루프는 `train_fold` 와 같은 규칙을 **따로 구현**한 것이다 (공통 함수로 묶지 않음 — 주 경로 `train_fold` 를 건드리지 않으려는 선택). 두 루프가 앞으로 어긋나지 않게 하는 장치는 아직 없다 — 남은 작업 3 (잠긴 키 ↔ 소비 지점 대응표) 에서 함께 다룬다.
- gradient clip 을 빼는 돌연변이는 시험에 넣지 않았다 (합성 자료에서 효과가 드러나지 않을 수 있어 검출을 보장하지 못함).
- 구조 비교 2종, S 후보의 fit·evaluate CLI 배선 — 미구현.


# 부록 AJ — §6 구조 비교 2종 모델 구조·합성 시험 (rev37, 2026-09-24 예약 슬롯)

근거: 선생님 결정 5 "§6 S 후보 4 + 구조 비교 2 - 추천안 대로" (구현·합성 시험은 지금, 실자료 실행은 main OOF 와 같은 release). 인수인계 남은 작업 2번. **새 결정 없음. 실자료 fit 없음, main pool 미소비. 학습·선택 규칙은 배선하지 않았다 (AJ.5 질문).**

## AJ.1 프로토콜이 정한 것 (그대로 옮김)

- §6 표: 구조 비교 "ROI encoder pooled feature + PCA FC10 fusion MLP" — "같은 종류의 정보에 접근하는 no-graph comparator; 완벽한 구조 ablation은 아님". 구조 비교 "training-rest single average graph + 동일 encoder/head" — "여러 template의 필요성".
- §6 "no-graph FC comparator와 실제 parameter/비용을 함께 보고한다". §7 "baseline·pilot·mechanism·다른 민감도 비용은 별도다".
- 계획서는 두 구조의 **학습·선택 규칙**(자기 grid 선택인지, A–D 공동 선택 config·E 재사용인지, seed 수)을 정하지 않았다 (§6·§7 grep: 두 행 외 언급 없음).

## AJ.2 구현

`mobse/v2/models.py`: `COMPARATOR_SPEC = {"NG", "SG"}` (구현 편의 이름), `FUSION_HIDDEN = 32`, `FusionMLPComparator`, `SingleGraphComparator`, `build_comparator`. 두 모델 모두 `forward(x, pca)` → `{"logits", …}` 로 A–D 와 같은 호출 모양이다 (학습 루프 배선은 하지 않음).
`mobse/v2/templates.py`: `SingleGraph`, `build_single_graph(correlations, fit_subjects)`.

구현 선택 (프로토콜이 정하지 않음 — 결정 아님):

| 항목 | 선택 | 이유 |
|---|---|---|
| NG fusion | A–D `ROIEncoder` → ROI mean pooling(32, graph layer 없음) ‖ PCA FC10 → `Linear(42→32) → GELU → Dropout(p) → Linear(32→2)` | "pooled feature + PCA FC10 fusion MLP" 의 최소 해석, 은닉 32 는 S 후보 MLP·gate 와 같음 |
| SG 모델 | A–D 와 같은 `ROIEncoder`·`DenseGraphLayer`×2·ROI mean pooling·`Linear(32→2)`, graph 하나는 buffer, gate 없음, PCA 는 예측에 안 씀 | "동일 encoder/head"; B/D 와 같은 규칙 |
| SG graph | training-rest window **전부의 원래 correlation 평균** (= clustering 없는 K=1 raw centroid) → §5 와 같은 대각 0·양수 상위 20%·동률 ROI index 순·`D^(−1/2)(A+I)D^(−1/2)` | "single average graph"; bank 와 같은 sparsify 규칙이라 template 수만 다르다 |
| SG null | 만들지 않음 | §6 표에 없음 |
| 생성 순서 | encoder 를 먼저 만든다 | 같은 seed 에서 encoder 초기값이 A–D 와 같다 (시험). graph layer·head 이후 초기값은 gate 유무로 A–D 와 다르다 |

## AJ.3 시험 (합성 자료만)

- `tests/v2/test_models.py` 21 → 31: 계획서 표 두 행 문장 대조, NG 구조·차원·parameter 수 공식·dropout p, NG 가 PCA 를 실제로 씀·없으면 거부, **NG 는 ROI 순서 치환에 불변** (graph 전 ROI 혼합·ROI ID 없음), SG graph buffer·PCA 비사용, **SG = bank `[S,S,S]` 인 A–D 모델(fixed·dynamic)과 가중치를 맞추면 출력 동일**, 같은 seed 에서 encoder 초기값이 cell A 와 동일, 인자·모양·NaN 거부.
- `tests/v2/test_templates.py` 20 → 24: 평균→§5 규칙 대조, **`build_bank(k=1)` 의 template·raw centroid 와 동일**, 결정성·입력 민감성, 모양·빈 입력·NaN·빈 subject 거부.
- 돌연변이 (`.backup/slot_1015/mut_comparators.py`, Mac 사본, python 치환·count==1 확인·복원): PCA concat 제거, fusion hidden 16, GELU→ReLU, dropout 고정, ROI pooling 을 첫 ROI 로, SG graph 재정규화, SG graph layer 1개, SG graph 를 parameter 로, encoder 생성 순서 뒤로, NaN graph 허용, NG 에 graph 허용, 평균 대신 중앙값, sparsify 생략, self-loop 정규화 생략, 빈 fit subject 허용 = **15/15 검출**.

## AJ.4 잠금

`mobse/v2` 변경으로 재잠금 `4acf47a8c79a` → **`ff4f766ce090`** (2026-09-24T01:18:07Z), code_hash `0f30e7b29312` → `537ff921250e`. 검사 43/43, 창 4,728, 창·코호트·분할 불변 (split_hash `ace5f4a41446`).

```
… → f93f1c504ba2 (결정 12 best checkpoint 평가) → 4acf47a8c79a (S 후보 2·4 MLP) → ff4f766ce090 (구조 비교 2종 모델, 현행)
```

## AJ.5 선생님께 여쭐 것 (결과 해석에 영향 — 배선 전에 필요)

두 구조 비교의 학습·선택 규칙:

- (가) **독립 선택**: 각 구조가 §7 8개 grid 에서 자기 inner OOF subject-equal loss 로 config 를 고르고, outer epoch 은 baseline 규칙(선택 config 3 inner best epochs 중앙값 올림), seed 42–44 확률 평균(§8). fit 수 구조당 inner 120 + outer 15 = 135, 두 구조 270.
- (나) **A–D 공동 선택 config·E 재사용**: 재튜닝 없음 (추가 null 민감도와 같은 방식). fit 수 두 구조 outer 30 (+ inner 선택 없음). A–D 에 맞춰 고른 recipe 라 비교가 A 쪽에 유리할 수 있다.
- 권고: (가). no-graph comparator 는 "같은 정보로 graph 없이 얼마나 되는가" 를 묻는 대조군이라 자기 recipe 로 맞춰야 A 와의 차이를 graph 경로 탓으로 읽을 수 있다. SG 도 같은 이유. 비용은 S 후보와 같이 "별도" 로 보고한다.

## AJ.6 이번 회차에 확인하지 못한 것

- 실자료 fit·GPU·main 규모 시간 — 하지 않음. fit·evaluate CLI 배선 없음 (AJ.5 결정 뒤).
- `SingleGraph` 를 fold 변환(`fitting.fit_fold_transform`)에 붙이는 배선 없음 — 지금은 호출자가 training-rest correlation 을 넘기는 라이브러리 함수다. training subject 경계는 호출 측 책임.
- A–D 와 graph layer·head 초기값이 다르다 (gate 유무). 비교에 영향이 있는지는 재지 않았다.


# 부록 AK — 잠긴 config 키 ↔ 소비 지점 대응표 시험, `train.model_seeds` 미소비 발견·적용 (rev38, 2026-09-24 예약 슬롯)

근거: 인수인계 남은 작업 3 ("config 잠긴 키 ↔ 소비 지점 대응표 시험", 결정 불요·가역). **새 결정 없음. 실자료 fit 없음, main pool 미소비.**

## AK.1 측정 — 잠긴 키 39개의 소비 지점

`config.SCHEMA` 의 `locked_to` 키 39개마다 `mobse/v2` 함수 AST 에서 그 상수 이름(`X`, `mod.X`) 또는 config 키 문자열(`cfg["a.b"]`) 참조를 찾았다 (`.backup/slot_1115/scan.py`, 측정 전용).

- 36개: 값이 계산·분기에 들어가는 함수가 있다.
- **`train.model_seeds` (42, 43, 44)**: 어디서도 소비되지 않았다. `fit --model-seed` 는 아무 정수나 받았고, `evaluate` 의 `_check_fit_grid` 는 seed **개수**(3)와 칸마다 같은 집합인지만 봤다 — seed {1, 2, 3} 격자도 통과했다. 계획서 §5 "A–D 및 모델 seed 42–44" 와 어긋날 수 있는 경로 (E21·E22 와 같은 "잠겨 있지만 적용 안 됨" 유형).
- `stats.nominal_pct`: 상수는 안 쓰이지만 `cli.run_report` 가 `cfg["stats.nominal_pct"]` 로 읽는다 (잠금 검사로 상수와 같음) — 소비됨.
- `bank.null_seeds_sensitivity`: 소비 없음. 민감도 null 실행 경로가 아직 없으므로 **대기 목록**으로 둔다.

## AK.2 적용 — `train.model_seeds`

`mobse/v2/cli.py`:
- `run_fit`: config 를 읽은 직후, `--model-seed` 가 `cfg["train.model_seeds"]` 밖이면 데이터를 읽기 전에 `CLIError`.
- `_check_fit_grid`: 격자가 꽉 차고 칸마다 같은 집합이어도, 그 집합이 `train.MODEL_SEEDS` 와 다르면 `CLIError`.

계획서가 정한 값의 적용일 뿐 값·규칙을 바꾸지 않았다. pilot 측정 스크립트(CLI 를 거치지 않음)와 S 후보·구조 비교 라이브러리(`fit_mlp` 등 seed 인자)는 건드리지 않았다 — 그 경로의 seed 제약은 CLI 배선 때 넣는다.

## AK.3 시험

- 새 `tests/v2/test_config_consumption.py` (43 시험): 잠긴 키 수 39 고정; 모든 잠긴 키가 `CONSUMERS` 또는 `PENDING` 중 정확히 하나에 있음; `CONSUMERS` 의 키마다 적힌 함수가 존재하고 그 값을 참조함 (38 키); `PENDING` 키는 아직 어디서도 참조되지 않음 (소비가 생기면 실패해 표 이동을 강제); **`fitting.train_fold` 와 `baselines.fit_mlp` 가 읽는 학습 상수 집합이 {BATCH_SIZE, MAX_EPOCHS, MIN_UPDATES, PATIENCE, MIN_DELTA, GRAD_CLIP} 로 같음** (부록 AI.5 의 "두 루프 어긋남 장치 없음" 에 대한 정적 장치); 잠긴 상수 이름이 여러 모듈에 정의되면 알려진 것(`CELLS`: `evaluate`·`train`)뿐이고 값이 같음.
- `test_cli_fit.py` +3: seed 0·41·45 거부, 출력 디렉터리 비어 있음.
- `test_cli_evaluate.py` +1: seed 44 → 45 로 바꾼 꽉 찬 격자 거부.
- 돌연변이 (`.backup/slot_1115/mut_consumption.py`, Mac 사본, python 치환·count==1 확인·복원): fit seed 검사 끔, fit seed 검사 블록 삭제, evaluate seed 집합 검사 끔, report 가 nominal 대신 familywise 백분위 사용, `fit_mlp` clip 리터럴화, `train_fold` clip 기본값 리터럴화, FD 상한 리터럴화, 표 없는 잠긴 키 추가 = **8/8 검출**.

한계: 대응표는 **정적 참조** 검사다. 참조는 적용의 필요조건일 뿐이며, 값이 동작을 실제로 바꾸는지는 개별 spy·결과 시험(E21·E22·P8·결정 12·AK.3 seed 시험)이 맡는다. 리터럴화 돌연변이는 값이 같아 동작 시험으로는 잡히지 않고 이 표로만 잡힌다 — 결정 12 로 값이 바뀔 때 한쪽만 바뀌는 일을 막는 용도다.

## AK.4 잠금

`mobse/v2/cli.py` 변경으로 재잠금 `ff4f766ce090` → **`d15dd718225e`** (2026-09-24T02:21:50Z), code_hash `537ff921250e` → `bb5d96e77ef1`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번), 창·코호트·분할 불변.

## AK.5 이번 회차에 확인하지 못한 것

- `bank.null_seeds_sensitivity` 의 소비 경로 — 민감도 null 실행이 미구현이라 대기 목록에 있다.
- 잠기지 않은 `choices` 키(`splits.n_outer_folds`, `bank.pca_components`, `stats.delta`, `runtime.*` 등)는 표 대상이 아니다. `cfg[...]` 참조는 있으나 대응표로 고정하지 않았다.
- `fit_mlp`·구조 비교의 seed 제약 — CLI 배선 전이라 없음.
- 정적 표는 이름으로 찾으므로 같은 이름의 다른 상수를 구분하지 않는다. 모듈 최상위 정의 중 겹치는 이름은 `CELLS` 하나이고 값이 같음을 시험으로 고정했다. 함수 안 지역 변수·인자 이름이 상수 이름과 같은 경우는 구분하지 못한다.
- `evaluate.CELLS` 는 `train.CELLS` 와 별도 리터럴이다 (값 같음 시험만 추가, 하나로 합치지 않음).

# 부록 AL — 결정 13: pilot head 직전 특징 정규화(BN·LN) 6,000 update 곡선 (측정 전용, rev39, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 13 (선생님 원문 "(ㄷ) 결정 전에 pilot에서 (ㄴ)을 한 번 재 보기: config 0·4 곡선이 안정되는지만 확인하는 측정입니다." 선택, 09-24 11:1x KST; (ㄴ) = "마지막 층 직전에 특징 정규화 추가"). **측정 전용 — `mobse/v2` 모델·계획서·잠금·최소 update·상한·학습률 등 불변, main pool 미소비, val 은 저장만 하고 해석하지 않는다.** 모델 구조 변경 여부는 선생님 판단.

## AL.1 조건

- `grid6000_det` (부록 AH.2) 와 같다: v3 창(0.2 Hz), cell A, outer 0, inner 0–2 × seed 42–44, config 0 (lr 0.001) 과 config 4 (lr 0.0003), 결정적 실행(E22), 6,000 update (= pilot 1,500 epoch, 이 프로세스 안에서만 `fitting.MAX_EPOCHS` 덮기), 100 update 마다 기록, 기록 forward 는 RNG 저장·복원.
- 변형: 측정 시작 시점 코드 사본(HEAD 3d5440b, `headnorm6000_det/code/`)의 `models.build_cell` 을 프로세스 안에서만 감싸 `head = Sequential(norm, 원래 Linear(32→2))`. **BN** = `BatchNorm1d(32)`(주 변형), **LN** = `LayerNorm(32)`(참고), **ID** = `Identity`(대조). BN·LN 초기 affine 은 1/0 이라 RNG 를 쓰지 않아 encoder·graph·head 초기값은 무정규화와 같다. 기록 forward 는 eval 모드 (BN 은 running 통계 — 실제 평가·선택 경로와 같은 모드).
- 규모: BN·LN × 2 config × 9 = 36 실행 + ID 대조 6 (inner 0 × seed 42–44 × 2 config). GPU 0 (다른 사용자 sglang 동거)에서 5 개 나란히. 벽시계 03:16:12Z–03:41:56Z, 실행당 학습 62–91 s. 42/42 rc=0.
- 산출물: h197 `MoBSE_dataset/derivatives_v3/pilot_tech_p8/headnorm6000_det/` (실행 JSON 42, `summary.json` sha256 `e6aff2d0eb37…`, 스크립트 `d13_headnorm6000.py`, 코드 사본, `git_head.txt`).

**대조**: ID 6 실행 모두 곡선 60 기록(특징 통계 키 제외)과 val loss 1,500 개가 `grid6000_det` 과 **완전히 같다** (6/6) — 감싸기 자체는 학습 경로를 바꾸지 않는다.

## AL.2 곡선 (train BA 는 eval 모드, 9 실행)

| 변형 | config | train BA 중앙값 (1,500 / 3,000 / 4,500 / 6,000) | 1.0 수 / 9 (같은 지점) | train loss 중앙값 @6,000 |
|---|---|---|---|---|
| 무정규화 (AH.2) | 0 | 0.962 / 1.000 / 1.000 / 1.000 | 1 / 6 / 5 / 7 | 0.0025 |
| BN | 0 | 1.000 / 0.654 / 0.821 / 0.786 | 5 / 2 / 2 / 3 | 0.438 |
| LN | 0 | 0.846 / 1.000 / 1.000 / 1.000 | 1 / 5 / 8 / 5 | 0.0042 |
| 무정규화 (AH.2) | 4 | 0.808 / 0.654 / 0.692 / 0.769 | 0 / 0 / 1 / 1 | 0.473 |
| BN | 4 | 0.786 / 0.962 / 1.000 / 1.000 | 3 / 4 / 6 / 5 | 0.014 |
| LN | 4 | 0.577 / 0.643 / 0.769 / 0.731 | 0 / 0 / 3 / 2 | 0.381 |

| 변형 | config | 처음 1.0 도달 update 중앙값 [범위] (도달 수) | 6,000 까지 못 닿음 | 끝까지 1.0 유지 시작 (해당 수) | 진동 횟수 [범위] (중앙값) |
|---|---|---|---|---|---|
| 무정규화 | 0 | 2,100 [1,100, 2,700] (9) | 0 | 5,400–6,000 (7) | 13–23 (20) |
| BN | 0 | 400 [100, 1,700] (9) | 0 | 5,000, 5,900, 6,000 (3) | 24–30 (27) |
| LN | 0 | 1,600 [1,200, 2,600] (9) | 0 | 2,500–5,300 (5) | 15–21 (18) |
| 무정규화 | 4 | 3,600 [2,400, 4,600] (6) | 3 | 6,000 (1) | 8–18 (12) |
| BN | 4 | 850 [700, 1,700] (8) | 1 | 5,000–6,000 (5) | 17–27 (24) |
| LN | 4 | 4,100 [1,200, 5,600] (7) | 2 | 5,800, 6,000 (2) | 5–14 (11) |

진동 = 기록 간 train loss 가 직전의 1.5 배 초과 (AH.2 와 같은 정의). **상대비 기준이라 loss 가 작을수록 작은 절대 변동에도 걸린다** — BN 의 loss 가 훨씬 작은 구간이 많아 횟수가 부풀었을 수 있다 (이번 회차에 절대 기준으로 다시 세지 않았다).

## AL.3 head 입력 특징 (train 집합, eval 모드, 중앙값)

| 변형 | config | 입력 절댓값 평균 @1,500 / @6,000 | 입력 표본 간 SD @1,500 / @6,000 | 정규화 출력 표본 간 SD @1,500 / @6,000 |
|---|---|---|---|---|
| ID (inner 0, 3 실행) | 0 | 0.632 / 0.683 | 0.373 / 0.619 | = 입력 |
| ID (inner 0, 3 실행) | 4 | 0.623 / 0.763 | 0.366 / 0.354 | = 입력 |
| BN | 0 | 1.060 / 1.010 | 0.033 / 0.037 | 1.10 / 1.26 |
| BN | 4 | 0.962 / 1.073 | 0.025 / 0.033 | 0.94 / 1.16 |
| LN | 0 | 0.560 / 0.386 | 0.304 / 0.328 | 0.54 / 0.73 |
| LN | 4 | 0.501 / 0.436 | 0.338 / 0.319 | 0.54 / 0.66 |

표본 간 SD = 특징별 표본 SD(ddof 0)의 32 특징 평균. 부록 W(09-18 pilot, v2 창·다른 학습 조건)의 0.802 / 0.054 와 직접 비교할 수 없다 — 이번 무정규화(ID) 는 1,500 update 에서 이미 표본 간 SD 0.37 이다. BN 을 넣으면 **head 입력은 오히려 "큰 공통 값(≈1.0) 위의 작은 표본 간 변동(≈0.03)"** 으로 머물고 BN 이 이를 약 30–40 배 키워 head 에 준다.

## AL.4 읽는 법 (측정 사실만)

1. **BN**: 두 config 모두 1.0 첫 도달이 크게 앞당겨졌다 (config 0 2,100 → 400, config 4 3,600 → 850). config 4 는 6,000 에서 1.0 이 1/9 → 5/9, 못 닿음 3/9 → 1/9. 그러나 **config 0 은 1,500 이후 오히려 불안정** (6,000 에서 1.0 7/9 → 3/9, loss 중앙값 0.0025 → 0.44) 이고 진동 횟수는 두 config 모두 늘었다.
2. **LN**: config 0 은 무정규화와 비슷하거나 조금 앞선다 (첫 도달 1,600, 4,500 에서 8/9). config 4 는 무정규화와 비슷하게 적합이 안 된다 (6,000 에서 2/9, 못 닿음 2/9).
3. **"config 0·4 곡선이 모두 안정"** 된 변형은 없다. 결정 13 명세의 (i) 조건 "config 4 가 적합하고 진동이 줄면" 은 BN 에서 전반부(적합)만 충족, 후반부(진동 감소)는 충족하지 않는다 (진동 기준의 상대비 한계는 AL.2).
4. 확인하지 못한 원인 (진단은 승인 범위 밖): BN 의 후반 불안정이 학습(배치 통계)↔평가(running 통계) 차이에서 오는지 — head 입력 표본 간 SD 가 0.03 수준이라 running 평균·분산의 작은 오차가 크게 증폭될 수 있다는 가설이다. 이번 회차에 재지 않았다.

## AL.5 권고 (선생님 판단 대기 — 값·구조 변경 없음)

- **(ㄱ) 구조 변경 보류 + 결정 12 권고로 복귀** — 이번 측정만으로는 BN·LN 어느 쪽도 두 config 를 함께 안정시키지 못했다. 최소 update·상한은 AH.3 의 선택지(U = 5,000·상한 400 / 3,000·200 / 1,500·200) 중에서 정한다. **슬롯 권고안.**
- (ㄴ) BN 채택 쪽으로 가려면, 먼저 AL.4-4 가설을 가르는 pilot 측정 1회 (예: 같은 조건에서 기록 forward 를 train 모드 배치 통계로도 재어 두 모드 train BA 비교, 또는 BN momentum·eval 통계 재추정) 가 필요하다 — 새 승인 대상.
- 어느 쪽이든 A–D 구조를 바꾸면 계획서 개정 행 + NG·SG head 앞 동일 변경(결정 14) + 잠금 재생성이 따른다.

# 부록 AM — 결정 14 배선 1·2단계: 구조 비교(NG·SG)를 `train_fold` 한 경로로, SG graph 를 fold 변환에 (rev39, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다" 선택, 09-24 11:1x KST) 의 구현 순서 1·2. **선택 규칙(3단계)·CLI 배선(4단계)은 이번 회차에 하지 않았다. 실자료 fit 없음, main pool 미소비.**

## AM.1 학습 루프 — 두 번째 루프 없음

`mobse/v2/fitting.py`:
- 새 `_build_fit_model(cell, cfg, transform)`: `cell` 이 A–D 면 기존 `build_cell` (brain/null bank), `NG` 면 `build_comparator("NG", cfg)`, `SG` 면 fold 변환의 single graph 로 `build_comparator("SG", cfg, graph)`. 그 밖의 이름은 `FitError`. SG 인데 fold 변환에 single graph 가 없으면 `FitError` (다른 graph 로 대체하지 않는다).
- `train_fold` 는 모델 생성 한 줄만 이 함수로 바꿨다. 따라서 구조 비교도 결정성(`apply_determinism` → seed), P8 최소 update·상한 가드, inner 의 최소 epoch 이후 early stopping·best checkpoint 복원(결정 12), outer 의 early stopping 거부·정확히 E epoch 을 **같은 코드**로 받는다. `train` 상수 참조 집합은 변하지 않았다 (rev38 대응표 시험 통과).

## AM.2 fold 변환 — SG graph

- `fit_fold_transform(..., single_graph=False)`: `True` 이면 bank 를 만든 **같은** training-rest 창(training subject 경계, `allowed_subjects` 검사를 거친 목록)의 원래 correlation 으로 `templates.build_single_graph` 를 부른다. 기본값 False 라 A–D 경로의 변환·provenance 는 바뀌지 않는다.
- `FoldTransform.single` (기본 None). 있으면 provenance 에 `single_graph_id`·`single_graph_fingerprint`·`single_graph_n_windows` 를 **덧붙인다** (기존 키 불변 — 시험).
- 구현 선택 (결정 아님): SG graph 를 SG fit 에서만 만드는 opt-in. density 는 bank 와 같은 인자를 넘긴다.

## AM.3 시험·돌연변이

- `tests/v2/test_fitting.py` 40 → 56 (+16): single graph 는 요청할 때만 생김; training-rest 창과 정확히 같은 창으로 만든 graph 와 일치·평가 subject 없음; 평가 subject 하나를 넣으면 graph 가 달라짐(경계 시험의 구별력); single graph 가 bank provenance 를 바꾸지 않음; SG 에 graph 없으면 거부; 알 수 없는 cell 거부; NG·SG 각각 — 모델 종류·SG buffer = fold graph, encoder 초기값 해시가 A 와 같음(§6 "동일 encoder"), inner best checkpoint 평가(결정 12), P8 가드·outer early stopping 거부·정확히 E epoch, 같은 seed 재현·`apply_determinism` 1회 호출.
- 돌연변이 (`.backup/slot_1215/mut_d14.py`, Mac 사본, python 치환·count==1 확인·복원): single graph 안 만듦, SG 가 brain bank 첫 template 사용, NG 가 cell A 로 빌드, graph 없음 가드 제거, provenance 에서 single 누락, single density 변경, single graph 를 전체 rest(평가 subject 포함)로 만듦, 알 수 없는 cell 이 통과 = **8/8 검출**.

## AM.4 잠금

`mobse/v2/fitting.py` 변경으로 재잠금 `d15dd718225e` → **`d3f869dd5844` (2026-09-24T03:24:05Z)**, code_hash `bb5d96e77ef1` → `5471ff45f8c7`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). 창·코호트·분할 불변.

## AM.5 이번 회차에 확인하지 못한 것 · 남은 순서

- 3단계 선택: 구조별 8 config inner OOF 병합 → 선택(선택 손실·동률 세부는 구현 선택으로 표시), outer E = 선택 config 의 3 inner best epoch 중앙값 올림, seed 42–44 로 outer fit. **`fit_mlp`·구조 비교의 seed 42–44 제약은 아직 없다** (A–D CLI 만, rev38).
- 4단계: S 후보·구조 비교의 fit·evaluate CLI 배선 (`fit --cell` 선택지에 NG·SG 없음).
- 실자료 fit·GPU·시간 — 없음. SG graph 의 실자료 density·조건은 미측정.
- 결정 13 결과로 head 앞 정규화가 A–D 에 들어가면 NG·SG head 앞에도 같은 변경이 필요하다 (결정 14 절).


# 부록 AN — 결정 14 3단계: 구조 비교(NG·SG) 구조별 독립 선택·outer 계획·seed 42–44 제약 (rev40, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다" 선택, 09-24 11:1x KST) 의 구현 순서 3. **CLI 배선(4단계)은 이번 회차에 하지 않았다. 잠긴 값 변경 없음. 실자료 fit 없음, main pool 미소비.** 결정 12 값(최소 update·상한)·결정 13 구조 판단과 독립이다 — 선택 함수는 호출 시점 `train` 상수를 읽는다.

## AN.1 선택 — `baselines.select_comparator(results, structure=)`

- 입력: 한 outer fold·한 구조의 `ComparatorInner`(structure, config_id, inner_fold, model_seed, validation run 확률, best epoch) 24개 = 8 config × 3 inner fold. 결과 하나가 `train_fold` inner fit 하나다.
- 검사 (위반은 전부 `BaselineError`): 알 수 없는 구조 / 다른 구조가 섞임 (구조별 독립) / inner seed ≠ `train.INNER_SEED` (계획서 §7 "Inner seed=42") / (config, fold) 중복·누락·여분 (불완전 grid 를 정상 선택으로 처리하지 않음 — A–D 와 같은 원칙) / best epoch 가 1–`train.MAX_EPOCHS` 밖 / fold 간 run 겹침 (`merge_inner_oof`) / config 간 OOF run 집합 불일치.
- **구현 선택 (결정 14 가 세부를 정하지 않았다 — 계획서 §7 A–D 문장에 가장 가까운 형태):**
  - 선택 손실 = config 별 3 fold validation run 확률을 OOF 하나로 합친 뒤 subject 동일 가중 log loss (`inner_loss` — S 후보와 같은 함수, §7 "각 config의 inner OOF run loss를 subject별 동일 가중으로 합산"). fold 별 loss 평균이 아니다 (시험이 둘이 다른 경우를 고정). 구조가 하나라 cell 가중은 없다.
  - 동률 (차이 ≤ `train.TIE_TOLERANCE` = 1e-6) → OOF BA (§8 `b_i` 평균) 높은 것 → config_id 작은 것.
  - outer E = 선택 config 의 3 inner best epoch 에 `train.baseline_epochs` (중앙값 올림, §7 "Baseline의 epoch는 해당 선택 모델의 3개 inner best epochs 중앙값 올림"). 1–상한 밖이면 거부.
- `ComparatorSelection.outer_plan()`: 선택 config, 정확히 E epoch, seed = 호출 시점 `train.MODEL_SEEDS` (42–44) 세 개. outer fit 자체는 `train_fold(role=outer, epochs_exact=E)` 로 도는데, outer early stopping 거부·P8 가드는 rev39 부터 같은 코드다.
- fit 수: 구조당 inner 8×3×5 = 120 + outer 5×3 = 15, 두 구조 270 (결정 14 의 수와 같음 — 시험).

## AN.2 seed 제약

- `fit_mlp` (S 후보 2·4): `model_seed ∉ train.MODEL_SEEDS` 거부 (호출 시점 상수 — monkeypatch 시험).
- `train_fold`: **NG·SG 에만** `model_seed ∉ MODEL_SEEDS` 거부. A–D 라이브러리 경로는 바꾸지 않았다 — A–D 의 seed 검사는 rev38 부터 `cli.run_fit` 이 하고, pilot 측정 틀(`scripts/h197/23_…`, `24_…`)이 라이브러리 A–D 경로를 부른다. 이 비대칭은 구현 선택이며 시험(`test_a_to_d_library_path_keeps_accepting_other_seeds`)이 현재 동작을 고정한다.
- 대응표 (`test_config_consumption.py`): `train.model_seeds` 소비 지점 2 → 4 (`fitting.train_fold`, `baselines.fit_mlp` 추가). 두 학습 루프의 train 상수 참조 집합은 그대로 같다.

## AN.3 시험·돌연변이

- `tests/v2/test_baselines.py` 30 → 42 (+12): `fit_mlp` seed 0·41·45 거부, seed 집합 호출 시점 읽기; 구조 이름 = `models.COMPARATOR_SPEC`; 최저 OOF loss 선택·outer E = `baseline_epochs`; OOF 병합 loss ≠ fold 평균인 경우 병합 쪽으로 계산; 동률 → BA → config_id; 가드 11종; 구조별 독립; outer 계획 seed·E; fit 수 270.
- `tests/v2/test_fitting.py` 56 → 63 (+7): NG·SG × seed 0·41·45 거부, A–D 라이브러리 경로 seed 7 수용.
- Mac 전체 796 passed / 13 skipped.
- 돌연변이 (`.backup/slot_1315/mut_d14s3.py`, Mac 사본, count==1 확인·복원): fit_mlp seed 가드 제거·리터럴 굳힘, fold 평균 loss, BA 동률 제거, 큰 config_id, outer E = 최댓값, inner seed 가드 제거, 구조 섞임 가드 제거, 완비 검사 제거, run 집합 검사 제거, outer 계획 seed 리터럴, best epoch 범위 검사 제거, train_fold 구조 비교 seed 가드 제거, 가드를 A–D 에도 적용 = **14/14 검출**.

## AN.4 잠금

`mobse/v2/baselines.py`·`fitting.py` 변경으로 재잠금 `d3f869dd5844` → **`4fa15d0dd3c5` (2026-09-24T04:23:53Z)**, code_hash `5471ff45f8c7` → `63055a8a9381`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). 창·코호트·분할 불변.

## AN.5 이번 회차에 확인하지 못한 것 · 남은 순서

- 4단계: S 후보·구조 비교의 fit·evaluate CLI 배선 (`fit --cell` 선택지에 NG·SG 없음, 선택 결과를 파일로 남기는 경로 없음). 설계 선택 (`fit --cell` 확장 대 별도 하위 명령) 은 그때 표시.
- 선택 함수는 합성 입력으로만 시험했다. 실자료 inner 결과·GPU·시간 — 없음.
- 결정 13 결과로 head 앞 정규화가 A–D 에 들어가면 NG·SG head 앞에도 같은 변경이 필요하다 (결정 14 절). 선택 규칙은 그 변경과 무관하다.


# 부록 AO — 결정 14 4단계 (일부 4a): `fit --cell NG|SG` 배선 (rev41, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다" 선택, 09-24 11:1x KST) 의 구현 순서 4 중 **fit 배선만**. 선택 결과를 파일로 남기는 하위 명령(4b)·S 후보 CLI(4c)는 이번 회차에 하지 않았다. **잠긴 값 변경 없음. 실자료 fit 없음, main pool 미소비.**

## AO.1 설계 선택 (표시함)

- **`fit --cell` 확장** — 별도 하위 명령을 두지 않았다. 근거: 구조 비교 학습은 rev39 부터 A–D 와 같은 `train_fold` 한 경로이므로 입력(경로·fold·config·seed·epoch)과 산출물(`fit_manifest.json`·`checkpoint.pt`·`window_predictions.jsonl`·`fit_report.json`) 계약도 하나로 둔다. 선택지 `cli.FIT_CELL_CHOICES = ("A","B","C","D","NG","SG")` (= `train.CELLS` + `baselines.COMPARATOR_ORDER`, 시험 고정).
- SG 이면 `fit_fold_transform(..., single_graph=True)` — 이 fit 의 training-rest 로 graph 하나를 만든다. `fit_manifest.json` 에 `single_graph_id`·`single_graph_fingerprint` 를 덧붙인다 (기존 키 불변, `fit_report.json` `transform` 과 같은 값). A–D·NG 는 만들지 않는다. bank 는 여섯 이름 모두 같은 fold 변환에서 나온다.
- seed: 잠긴 `train.model_seeds` 검사는 `cli.run_fit` 이 cell 과 무관하게 먼저 한다 (NG·SG 는 `train_fold` 에서 한 번 더).

## AO.2 manifest 범위

- `manifests.COMPARATOR_CELLS = {"NG","SG"}` (= `models.COMPARATOR_SPEC` = `baselines.COMPARATOR_ORDER`, 시험 고정), `FIT_CELLS = ALLOWED_CELLS ∪ COMPARATOR_CELLS`.
- **구현 선택:** 구조 비교 이름은 fit 단위 산출물(`FIT_SCOPED_ARTIFACTS = {fit_manifest, window_predictions}`)과 `fit_id` 에서만 받는다. `run_predictions` 등 run·subject 집계는 A–D 만 받는다. `evaluate` 는 바꾸지 않았다 — NG·SG fit 을 섞으면 `_check_fit_grid` 가 "알 수 없는 칸" 으로 거부한다 (시험). 구조 비교의 outer 집계·보고 경로는 아직 없다.

## AO.3 시험·돌연변이

- `tests/v2/test_cli_fit.py` 13 → 22 (+9): 선택지 순서·알 수 없는 cell 거부; NG·SG inner fit 네 산출물·fit_id·예측 행 수·min_updates 1,500 전달; SG 만 graph 출처 기록 + A·NG 는 없음 + bank 동일; NG·SG outer 정확히 E epoch; NG seed 0·45 거부; evaluate 격자가 NG 칸 거부.
- `tests/v2/test_manifests.py` 30 → 33 (+3): NG·SG 가 window_predictions·fit_id 에서 받아지고 run_predictions 에서 거부; 이름 집합 일치 (torch 없으면 skip).
- Mac 전체 808 passed / 13 skipped.
- 돌연변이 (`.backup/slot_1415/mut_d14s4.py`, count==1 확인·복원): SG 에 graph 안 만듦, 모든 cell 에 graph 만듦, manifest graph 기록 제거, 선택지 A–D 로, 모든 artifact 에 NG·SG 허용, fit 범위 제거, fit_id A–D 로, run_predictions 를 fit 범위에 추가, 구조 이름 여분 = **9/9 검출**.

## AO.4 잠금

`mobse/v2/cli.py`·`manifests.py` 변경으로 재잠금 `4fa15d0dd3c5` → **`987de3635cb4` (2026-09-24T05:21:27Z)**, code_hash `63055a8a9381` → `c258f65edb56`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). 창·코호트·분할 불변.

## AO.5 이번 회차에 확인하지 못한 것 · 남은 순서

- 4b: 구조 비교 inner fit 산출물(`fit_report.json`·`window_predictions.jsonl`) → `ComparatorInner` → `select_comparator` → 선택 기록 파일 → outer fit 명령. 하위 명령 이름·입력 형식은 그때 표시.
- 4c: S 후보 1–4 fit·선택 CLI.
- 실자료 fit·GPU·시간 — 없음. 결정 13 판단으로 head 앞 정규화가 A–D 에 들어가면 NG·SG 에도 같은 변경 (결정 14 절).


# 부록 AP — 결정 14 4단계 (4b): `select-comparator` 선택 기록 하위 명령 + `fit_id` 에 config_id (rev42, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다" 선택, 09-24 11:1x KST) 의 구현 순서 4 중 **4b**. S 후보 CLI(4c)는 이번 회차에 하지 않았다. **잠긴 값 변경 없음. 실자료 fit 없음, main pool 미소비.**

## AP.1 사전 확인 — window → run 집계 함수

- `evaluate` 는 `evaluate.aggregate_runs` 를 쓴다. 이 함수는 cell A–D 에 **창 4 × seed 3 격자**를 요구하는 outer test 집계다 (`statistics.run_probability`, seed 평균 → 창 평균).
- inner fit 은 seed 42 하나다 (계획서 §7). `train_fold` 는 inner `eval_loss`·`eval_run_probs` 를 `fitting.run_probabilities` (run 당 창 4 개 평균) 로 계산한다.
- 그래서 선택 기록 하위 명령은 **`fitting.run_probabilities`** 를 쓴다 — inner fit 이 손실을 계산한 것과 같은 함수. `evaluate.aggregate_runs` 는 쓰지 않는다.

## AP.2 새 발견 — inner grid 의 `fit_id` 충돌 (정정함)

- `manifests.fit_id` payload 가 (role, cell, outer_fold, inner_fold, model_seed, split_hash, config_hash) 였고 **config_id 가 없었다.** inner grid 는 같은 (cell, fold, seed=42) 에서 config 0–7 여덟 개를 학습하므로, 서로 다른 여덟 fit 이 같은 `fit_id` 를 가졌다. A–D inner grid 도 같다. `fit_manifest.json` 에는 config_id 필드가 없고 `fit_report.json` 에만 있다.
- 정정 (규칙 변경 아님, 식별자 정정): `fit_id(..., config_id=)` 필수 인자, payload 에 추가. 접두(`inner-NG-o0i1s42-`)는 그대로. 빠뜨리면 `TypeError`, 음수·bool·float 는 `ManifestError`. `cli.run_fit` 이 `--config-id` 를 넘긴다. 실자료 fit 이 아직 없으므로 기존 산출물 영향 없음.
- 선택 기록 하위 명령은 fit_report 의 config_id 로 fit_id 를 다시 만들어 manifest 와 대조한다 — 보고서와 manifest 가 다른 fit 이면 거부.

## AP.3 `select-comparator` (설계 선택 — 표시함)

- **하위 명령 이름·입력 형식은 구현 선택이다.** `mobse-v2 select-comparator --config --splits --output-dir --structure NG|SG --outer-fold K --fit-manifest <24개>`. `fit_report.json`·`window_predictions.jsonl` 은 각 manifest 옆 고정 이름 (evaluate 의 `checkpoint.pt` 와 같은 방식 — 명시한 경로에서 결정, 탐색 아님, U20). 학습하지 않는다.
- 검사 (위반은 전부 `CLIError`): manifest 스키마 / fit_id 중복 / cell ≠ `--structure` (구조별 독립) / role ≠ inner 또는 eval_role ≠ inner_validation / outer fold ≠ `--outer-fold` / split_hash·config_hash 불일치 / 이웃 파일 없음 / fit_report fit_id ≠ manifest / config_id 로 다시 만든 fit_id ≠ manifest / fit_subjects ≠ folds.json inner train / 예측 행의 fit_id·cell·seed·scope·checkpoint hash 불일치 / truth ≠ run_key task / 예측 subject ≠ inner validation subject / 창으로 다시 계산한 inner 손실과 fit_report `eval_loss` 차이 > 1e-6 / fit 사이 code·env·source hash 불일치. 그 다음 `baselines.select_comparator` (rev40 가드 11종 — 불완전 grid·inner seed 등) 를 그대로 부른다.
- 산출물 `comparator_selection.json` (schema `d14-comparator-selection-0.1`, 있으면 거부): 선택 config·outer E·inner 손실·BA·동률 규칙·best epoch 3 개·config 별 표·outer 계획 (seed = 호출 시점 `train.MODEL_SEEDS`, `fit --cell <구조> --outer-fold K --inner-fold 9 --config-id <선택> --epochs <E> --model-seed <s>` 인자 목록)·규칙 문구 (구현 선택 표시)·입력 fit 24 개의 sha256·selector code_hash.
- 선택 규칙 자체는 rev40 그대로 (부록 AN.1, 구현 선택).

## AP.4 시험·돌연변이

- 새 `tests/v2/test_cli_select_comparator.py` (22 시험): 하위 명령 등록·필수 경로·구조 선택지 = `COMPARATOR_ORDER`; 합성 24 fit 에서 선택·outer E = `baseline_epochs`·입력 24 개 fit_id 서로 다름; outer 계획 인자가 `fit` parser 로 그대로 읽힘 (seed 42–44, inner 9, E); SG 독립 선택; 덮어쓰기 거부; 손실 재계산 = fit_report; 거부 15 종 (불완전 grid, 다른 구조, outer fit, outer fold, inner seed, config_id 바꿔치기, manifest 중복, 손실 불일치, validation subject 누락, outer_test scope, fit_subjects, code_hash 섞임, 이웃 파일 없음, checkpoint hash, truth).
- `tests/v2/test_cli_fit.py` 22 → 24: 실제 `run_fit` NG·SG inner 산출물(float32 forward → float 기록)의 창 예측으로 다시 계산한 손실이 fit_report `eval_loss` 와 1e-6 안에서 같고, config 0·1 fit_id 가 다름.
- `tests/v2/test_manifests.py` 33 → 34: 8 config fit_id 서로 다름, config_id 누락·잘못된 형 거부.
- Mac 전체 833 passed / 13 skipped.
- 돌연변이 (`.backup/slot_1515/mut_d14s4b.py`, count==1 확인·복원): fit_id payload config_id 제거, config_id 형 검사 제거, cell·role·outer fold·fit_id 재계산·손실 대조·subject·scope·fit_subjects·hash 일치·checkpoint·truth·덮어쓰기 가드 각각 제거, outer 계획 E+1, CLI 가 config_id=0 고정 = **16/16 검출**.

## AP.5 잠금

`mobse/v2/cli.py`·`manifests.py` 변경으로 재잠금 `987de3635cb4` → **`26adaed6f303` (2026-09-24T06:23:50Z)**, code_hash `c258f65edb56` → `07fd6cdb958e`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). 창·코호트·분할 불변.

## AP.6 이번 회차에 확인하지 못한 것 · 남은 순서

- 4c: S 후보 1–4 fit·선택 CLI.
- 구조 비교 outer 예측의 집계·보고 경로 (evaluate 는 A–D 만) — 결정 14 가 정하지 않은 범위라 아직 없음.
- A–D inner grid 의 선택(`train.select_config`)을 파일로 남기는 CLI 경로도 없다 — 이번에 확인만 함.
- 실자료 fit·GPU·시간 — 없음.


# 부록 AQ — 결정 14 4단계 (4c-i): S 후보 한 칸 fit 하위 명령 `fit-s` (rev43, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다" 선택, 09-24 11:1x KST) 의 구현 순서 4c ("S 후보 1–4 fit·선택 CLI") 를 둘로 나눈 앞 조각 **4c-i (fit)**. 선택 기록(4c-ii)은 이번 회차에 하지 않았다. S 후보의 규칙 자체는 결정 5 ("§6 S 후보 4 + 구조 비교 2 - 추천안 대로") 로 이미 구현된 rev33·rev36 그대로다. **잠긴 값 변경 없음. 실자료 fit 없음, main pool 미소비.**

## AQ.1 사전 확인

- S 후보는 raw ROI 창에서 feature 를 만든다 (`baselines.feature_matrix` — S1·S2 ROI mean/variance 200, S3·S4 signed Fisher-z FC 4,950). `fit` 은 fold 변환(bank·PCA)을 거친 `EncodedSet` 으로 학습하므로 **입력 계약이 다르다.** logistic(S1·S3)은 결정적 lbfgs 라 seed·epoch 개념이 없다.
- 지침서 WI-07 출력에 "selection" 이 있다 — A–D inner 선택(`train.select_config`)을 파일로 남기는 경로도 필요하다는 뜻으로 읽힌다. 경로는 아직 없다 (기록만, AQ.6).

## AQ.2 `fit-s` (설계 선택 — 표시함)

- **`fit` 과 나눈 별도 하위 명령은 구현 선택이다** (입력 계약이 달라서). `mobse-v2 fit-s --config --splits --subjects --windows --output-dir --task-manifests … --candidate S1…S4 --setting-id 'C=<값>'|'config=<0–7>' --outer-fold K --inner-fold F [--model-seed s] [--epochs E]`. rest manifest 를 받지 않는다 (bank·PCA 없음).
- 인자 규칙 (위반은 `CLIError`): logistic 에 `--model-seed`·`--epochs` 를 주면 거부 · MLP 는 `--model-seed` 필수, 잠긴 `train.model_seeds` 밖이면 거부 · MLP inner 에 `--epochs` 를 주면 거부 (early stopping, 상한은 호출 시점 `train.MAX_EPOCHS`) · MLP outer (`--inner-fold 9`) 는 `--epochs` 필수 (선택 설정 inner best epochs 중앙값 올림 — 계획서 §7) · 설정이 후보 grid 밖이면 거부 · 산출물이 있으면 거부 · 창 sha256 대조 (기본). MLP 에는 config 의 잠긴 `train.min_updates` 를 넘긴다.
- 라이브러리 본체 `baselines.fit_s` (새) 가 기존 `fit_logistic`·`fit_mlp` 를 그대로 부른다 — 학습 규칙 변경 없음. StandardScaler 는 이 fit 의 training 창에만 맞춘다. run 확률은 `fitting.run_probabilities`, 손실은 `inner_loss` (A–D·구조 비교와 같은 함수). `baselines.s_settings(candidate)` 는 `logistic_settings`·`mlp_settings` 와 같은 setting_id 문자열과 순위를 준다.
- 산출물 셋: `s_fit_report.json` (schema `d14-s-fit-report-0.1` — s_fit_id·후보·feature·설정·role·fold·seed·수렴·best epoch·평가 손실·BA·fit 기록·fit_subjects·모델/예측 sha256·code/env/config/source/split hash), `s_window_predictions.jsonl`, `s_model.npz` (scaler 와 parameter 배열 — torch 저장이 아니라 npz 인 것도 구현 선택). run 확률은 쓰지 않는다 — 선택은 inner 산출물을 모아 따로 한다 (4c-ii).
- **새 manifests artifact `s_window_predictions`** (구현 선택): cell 자리가 없고 후보·설정이 식별자, `model_sha256` 은 SHA256 형식 검사, 유일 키 (candidate, setting_id, window_key). `window_predictions` 와 이름부터 달라 2×2 `evaluate` 로 새어 들어가지 않는다 (시험 — S 행은 `window_predictions` 검증에서 거부).
- **새 `manifests.s_fit_id`**: payload 에 role·후보·설정·outer/inner fold·seed(logistic 은 None)·split/config hash — rev42 `fit_id` 정정과 같은 이유로 같은 fold 의 설정·seed 가 서로 다른 식별자를 갖는다. 접두 `s-<role>-S<n>-o<K>i<F>s<seed|na>-`.

## AQ.3 시험·돌연변이

- 새 `tests/v2/test_cli_fit_s.py` (17 시험, 합성 자료 ROI 12): 등록·필수 경로(rest manifest 없음); 후보 이름 3곳 일치 (`cli.S_CANDIDATE_CHOICES` = `baselines.CANDIDATE_ORDER` = `manifests.S_CANDIDATES`); setting 문자열·순위; logistic inner 산출물 셋 + 창 확률·손실이 같은 X 의 `fit_s` 와 일치; 분리 가능한 합성 신호에서 BA ≥ 0.75·확률 방향; 행으로 다시 계산한 손실 = 보고서 (1e-9)·S3 차원 = n_roi(n_roi−1)/2; scaler 평균 = training 창 평균 (평가 창 포함 평균과 다름); logistic seed·epochs 거부; grid 밖 설정 거부 4종; 덮어쓰기 거부; 변조 창 거부; MLP seed 누락·잠긴 seed 밖·inner epochs 거부; MLP inner 가 잠긴 최소 update 1,500 전달 (spy)·state 배열 저장; MLP outer epochs 필수·정확히 E epoch·행 scope = outer_test; `s_fit_id` 12 조합 구별·알 수 없는 후보 거부; S 행 `window_predictions` 거부; `s_window_predictions` 스키마 hash·키.
- Mac 전체 850 passed / 13 skipped (rev42 833 + 17).
- 돌연변이 (`.backup/slot_1615/mut_d14s4c.py`, count==1 확인·복원, rc 확인): logistic seed 가드·MLP 잠긴 seed·MLP inner epochs 가드 제거, min_updates 미전달, training 에 평가 subject 섞기, feature 종류 고정, 창 hash 대조 끄기, 행 scope 고정, logistic 확률 뒤집기, MLP state 미저장, `s_fit_id` payload 설정 제거, `model_sha256` hash 검사 제거, 유일 키 축소, `s_settings` 후보 거르기 제거 = **14/14 검출**.
- 등가로 남긴 것: CLI 의 grid 밖 설정 가드를 지워도 `fit_s` 가 같은 문구로 거부한다 (이중 가드 — 돌연변이 목록에서 뺌).

## AQ.4 잠금

`mobse/v2/baselines.py`·`cli.py`·`manifests.py` 변경으로 재잠금 `26adaed6f303` → **`64c4ef67f4d0` (2026-09-24T07:23:52Z)**, code_hash `07fd6cdb958e` → `a9a0fcea2bcb`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). 창·코호트·분할 불변.

## AQ.5 결정 12·13 과의 관계

`fit-s` 는 `fit_mlp` 를 부르고 `fit_mlp` 는 호출 시점 `train.MAX_EPOCHS`·`MIN_UPDATES` 를 읽는다. CLI 는 config `train.min_updates` 를 넘긴다 (spy 시험). 결정 12 값이 바뀌어도 여기서 따로 고칠 곳 없음. 결정 13 (head 앞 정규화) 은 S 후보와 무관하다 (S 는 §6 모델 구조를 쓰지 않는다).

## AQ.6 이번 회차에 확인하지 못한 것 · 남은 순서

- 4c-ii: S 선택 기록 하위 명령 (inner `s_fit_report`·`s_window_predictions` 32 설정 × 3 inner fold → `select_s` → 선택·outer 계획). outer 계획의 MLP seed·logistic 단일 fit 규칙, 외부 S ("외부 S도 PIOP1 main pool의 inner 결과로만 고른다") 의 입력 형식은 그때 확인.
- A–D inner 선택 기록 경로 (WI-07 출력 "selection") — 없음.
- 구조 비교·S outer 예측의 집계·보고 경로 — 없음.
- 실자료 fit·시간 (S3·S4 는 4,950 차원) — 없음.


# 부록 AR — 결정 15 반영: P8 값 5,000 update / 상한 400 epoch (계획서 P8-b, rev44, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 15. 결정 13 결과(부록 AL) 보고 뒤 대화에서 제시한 선택지 "(ㄱ-1) 구조 변경 보류 + 결정 12 값 3,000 update / 상한 200 (권고)", "(ㄱ-2) 구조 변경 보류 + 5,000 / 400 (슬롯 원 권고, 비용이 큼)", "(ㄱ-3) 구조 변경 보류 + 1,500 / 200 유지 (현행)", "(ㄴ) BN 쪽 검토 …" 가운데 선생님 선택 원문 **"(ㄱ-2) 구조 변경 보류 + 5,000 / 400 (슬롯 원 권고, 비용이 큼)"** (09-24 17:0x KST 기록). **실자료 fit 없음, main pool 미소비. main OOF 착수 승인 아님.**

## AR.1 바뀐 것

- 계획서 §11 에 **P8-b** 행 추가 (결정 원문 인용, 근거 부록 AH.2–AH.3·AL, 값 1,500/200 → 5,000/400, 모델 구조 불변). §7 본문 P8 표시 옆에 `[개정 P8-b]` 표시.
- `mobse/v2/train.py`: `MIN_UPDATES = 5000`, `MAX_EPOCHS = 400` (docstring 포함). `mobse/v2/config.py`: `train.max_epochs` 설명 문구만 (잠금 값은 `train` 상수 참조). `mobse/v2/fitting.py`: `train_fold` docstring 의 기본값 문구만.
- `configs/redesign_v1/{main,pilot,external}.yaml`: `train.max_epochs: 400`, `train.min_updates: 5000`. config_hash main `96aa166e` → `2a7d7d7f`, pilot → `6498596a`, external `0c3329a8` → `576f6068`.
- 바꾸지 않은 것: A–D·NG·SG 모델 구조 (head 앞 정규화 없음), 학습률·patience 5·min_delta 0.0005·batch 32·grid·gradient clip·dropout·weight decay, early stopping 은 최소치 이후에만·best checkpoint 평가(결정 12), outer 공통 E 고정 epoch 규칙. (ㄴ) BN 가설 측정은 하지 않았다.
- 다른 곳의 1,500·200 리터럴: `mobse/v2`·`configs` grep 결과 없음 (docstring 2곳 정정). `fit_mlp`·`train_fold`·구조 비교·`fit-s`·선택 함수는 호출 시점 `train` 상수 또는 config `train.min_updates` 를 읽는다 — CLI spy 시험 (`test_cli_fit`·`test_cli_fit_s`) 이 5,000 전달을 확인.

## AR.2 시험·돌연변이

- 고정 시험 갱신: `test_train` (상수 5,000/400, `min_epochs_for(544)=295 ≤ 400`, outer `min_epochs_for(808)=193`·`(800)=200`, 상한 경계 400/401), `test_fitting` (기본값 5,000, 상한 400), `test_cli_fit`·`test_cli_fit_s` (spy·보고서 `min_updates` 5,000). 시험 수 불변.
- Mac 전체 850 passed / 13 skipped.
- 돌연변이 (`.backup/slot_1715/mut_d15.py`, 파일별 원본 복원, `-B`·`PYTHONDONTWRITEBYTECODE`): `MIN_UPDATES` 1,500, `MAX_EPOCHS` 200·300, main.yaml `min_updates` 1,500·`max_epochs` 200, pilot.yaml `min_updates` 3,000, external.yaml `max_epochs` 200 = **7/7 검출** (상수 → `test_p8_constants…`, yaml → `test_shipped_config_validates` 잠금 대조).
- **새 사고 (이번 회차 발견·정정):** 첫 돌연변이 실행이 같은 크기 치환(400→300)을 같은 초 안에 복원해 `mobse/v2/__pycache__/train.cpython-311.pyc` 가 **돌연변이 판(300)** 으로 남았다 (pyc 는 원본 mtime·크기로만 무효화). rsync 가 그 pyc 를 h197 로 옮겨 h197 import 가 `MAX_EPOCHS=300` 을 읽었다 — 귀결 계산 출력에서 발견. 조치: Mac·h197 `mobse`·`tests`·`scripts` 의 `__pycache__` 전부 삭제, 돌연변이는 bytecode 를 쓰지 않게 다시 실행 (위 7/7 은 재실행 결과). 잠금 재생성·마감은 삭제 뒤에 했다. 이전 회차 돌연변이 결과가 같은 영향을 받았는지는 **확인하지 않았다** (검출 판정 방향으로만 틀릴 수 있음 — 놓친 것을 잡았다고 볼 위험).

## AR.3 main 귀결 (재계산 — folds.json subject 수 × 8 창, 창·라벨·예측 미열람)

h197 `derivatives_v3/splits_piop1_p7/folds.json` (split_hash `ace5f4a4…`) 에서 `train.updates_per_epoch`·`min_epochs_for` 로 다시 셈 (AH.3 은 같은 수를 손으로 셈):
- inner 학습 창 528–544 → 17 update/epoch → **최소 epoch 295** (15 fold 전부), 상한 400 까지 early stopping 여유 105 epoch.
- outer 학습 창 800–808 → 25–26 update/epoch → **outer 공통 E ≥ 193–200**. 선택된 inner best epoch 이 295 이상이므로 공통 E(중앙값 올림)는 295–400 범위이고, outer 최소치 조건은 자동으로 채워진다.
- pilot 창 규모 (pilot 31명 × 8 = 248 창, inner 학습 창 104–112 → 4 update/epoch) 에서는 최소 epoch 1,250 > 400 이라 **pilot 규모 fit 은 거부된다** — P8 구현 때와 같은 성질. pilot 측정은 계속 프로세스 안 `MAX_EPOCHS` 덮기로만 한다.
- 시간: AH.3 의 외삽(학습 상한 약 15 h, 결정성 적용 전 합성 벤치마크 기준) 은 **실측이 아니다**. 실제 fit 시간은 남은 작업 6 에서 pilot 창으로 잰다.

## AR.4 잠금

`mobse/v2/train.py`·`config.py`·`fitting.py`·configs·계획서 변경으로 재잠금 `64c4ef67f4d0` → **`4394c7a28252` (2026-09-24T08:22:37Z)**, code_hash `a9a0fcea2bcb` → `170629c693a3`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). **split_hash `ace5f4a4…` 불변**, N 126/189 불변. 창·코호트·분할 불변.

## AR.5 이번 회차에 확인하지 못한 것 · 남은 순서

- 5,000/400 에서의 실제 fit 시간 (pilot 창, 남은 작업 6) — 미측정. main 규모 epoch 당 시간도 미측정.
- 이전 회차 돌연변이의 stale pyc 영향 — 미확인 (AR.2).
- 결정 14 4c-ii (S 선택 기록 CLI), A–D inner 선택 기록 경로 — 남음.



# 부록 AS — 결정 14 4c-ii: S 선택 기록 하위 명령 `select-s` (rev45, 2026-09-24 예약 슬롯)

근거: 인수인계 결정 14 (선생님 원문 "(가) 독립 선택: 두 구조가 각자 8개 설정 중 inner 결과로 하나를 고르고, epoch은 baseline 규칙을 따르며, seed는 42–44입니다. 약 270 fit이고 슬롯 권고안입니다") 구현 순서 4c-ii, 결정 5 (S 후보 — 구현·합성 시험은 지금, 실자료 실행은 main OOF 와 같은 release). **실자료 fit 없음, main pool 미소비. 잠긴 값 변경 없음.**

## AS.1 사전 확인 (계획서 §6·§7 grep)

- §6: "S는 각 outer fold에서 inner subject-equal log loss가 가장 낮은 후보/설정으로 고른다. 외부 S도 PIOP1 main pool의 inner 결과로만 고른다." · [개정 P11] 미수렴 설정은 빼고 수를 보고.
- §7: "Baseline의 epoch는 해당 선택 모델의 3개 inner best epochs 중앙값 올림이다." · "Inner seed=42".
- **계획서가 정하지 않은 것**: S outer fit 의 seed 수. A–D 는 seeds 42–44 (§7), 구조 비교는 결정 14 가 42–44. S MLP 도 42–44 로, logistic 은 결정적이라 한 번으로 두었다 — **구현 선택**.
- 외부 S: `fitting.resolve_fold_subjects` 는 outer 0–4 만 안다 (folds.json 에 main pool 전체 inner 분할이 없음). 외부 S 선택은 그 분할이 생긴 뒤 같은 함수로 붙인다 — **이번에 구현하지 않음**.

## AS.2 바뀐 것

- 새 하위 명령 `select-s --config --splits --output-dir --outer-fold K --fit-report ×96`. `s_window_predictions.jsonl`·`s_model.npz` 는 각 `s_fit_report.json` 옆 고정 이름 (U20). 학습하지 않는다.
- 검사: schema·s_fit_id 중복·후보/설정 grid·setting_rank·inner role/eval_role·outer fold·split/config hash·logistic 에 seed·best_epoch 없음·MLP inner seed = `train.INNER_SEED`·MLP best_epoch 1–`MAX_EPOCHS`·**보고서 필드로 s_fit_id 재계산 대조**·fit_subjects = folds inner train·**s_model.npz·예측 파일 sha256 = 보고서**·예측 행 s_fit_id/candidate/setting/scope/model hash/truth·예측 subject = inner validation·**창 → run 재집계(`fitting.run_probabilities`) 손실 vs 보고서 `eval_loss` (1e-6)**·grid 완비 96 (4 후보 × 8 설정 × 3 inner fold)·code/env/source hash 일치 → `baselines.select_s`.
- 새 `baselines.s_outer_plan(candidate, setting_id, best_epochs)`: logistic → fit 한 번 (seed·epoch 없음, best epoch 주면 거부), MLP → 호출 시점 `train.MODEL_SEEDS` 마다 정확히 E = `train.baseline_epochs(3 best epochs)` (1–`MAX_EPOCHS`). `baselines.S_INNER_FOLDS = 3`.
- 산출물 `s_selection.json` (schema `d14-s-selection-0.1`, 덮어쓰기 거부): 선택 후보·설정·손실·best epochs·outer E·제외 목록/수 (P11)·설정 표 32 행·outer 계획 (`fit-s … --inner-fold 9` 인자 목록)·입력 96 fit sha256.
- **구현 선택 (표시함)**: 하위 명령 이름·입력 형식 (`select-comparator` 와 같은 모양), grid 완비 요구 (빠진 것 ≠ 미수렴), **설정의 수렴 = 3 inner fit 모두 수렴** (P11 은 fit 단위·설정 단위를 구별하지 않음), S outer seed 규칙 (AS.1).

## AS.3 시험·돌연변이

- 새 `tests/v2/test_cli_select_s.py` **27** (합성 inner 디렉터리 96개; logistic 선택·MLP 선택 각각 outer 계획, `MODEL_SEEDS` monkeypatch, 미수렴 설정 제외·기록, 가드 19종, `s_outer_plan` 가드, 실제 `fit_s` 손실 = CLI 재집계 함수 1e-9).
- Mac 전체 **877 passed / 13 skipped**.
- 돌연변이 (`.backup/slot_1815/mut_d14s4cii.py`, 파일별 원본 복원, `-B`·`PYTHONDONTWRITEBYTECODE=1`, 끝나고 `__pycache__` 삭제 뒤 rsync): grid 완비·수렴 all→any·손실 대조·MLP inner seed·s_fit_id 재계산·model sha·pred sha·scope·subject·fit_subjects·hash 일치·setting_rank·best_epoch 범위·logistic seed·role·truth·덮어쓰기·outer fold·plan seed 리터럴·outer E max·logistic plan epoch 허용 = **21/21 검출**.

## AS.4 잠금

`mobse/v2/cli.py`·`baselines.py` 변경으로 재잠금 `4394c7a28252` → **`60aa5987ef0c` (2026-09-24T09:22:52Z)**, code_hash `170629c693a3` → `cd9d823591fb`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). split_hash `ace5f4a4…` 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변.

## AS.5 확인하지 못한 것 · 남은 순서

- 외부 S 선택 (main pool 전체 inner 분할 필요) — 미구현.
- S·구조 비교 outer 예측의 집계·보고 경로 — 없음 (evaluate 는 A–D 만).
- A–D inner 선택(`train.select_config`)을 파일로 남기는 CLI 경로 — 없음 (다음 조각).
- 실자료 fit·시간 — 없음.


# 부록 AT — A–D 공동 선택 손실을 OOF 병합(subject 수 가중)으로 정정 (rev46, 2026-09-24 예약 슬롯)

근거: 인수인계 남은 작업 2 ("A–D inner 선택 기록 경로" 의 사전 확인). **새 결정 아님 — 계획서 §7 문장에 코드를 맞춘 정정. 실자료 fit 없음, main pool 미소비. 잠긴 값 변경 없음.**

## AT.1 사전 확인에서 발견한 것

- 계획서 §7 원문: "각 config의 inner OOF run loss를 subject별 동일 가중으로 합산하고 A–D 네 cell에 같은 가중을 주어 최소화한다. 동률(차이≤1e−6)은 공동 BA가 높은 것, 이후 config_id가 작은 것으로 정한다."
- 지침서 WI-07 출력: "selection, checkpoints, …" — 선택 기록 경로가 필요하다는 읽기는 그대로 (AQ.6).
- **어긋남**: `train.select_config` 는 cell 손실을 **3 inner fold 손실의 단순 평균** (`sum(r.loss) / n_folds`) 으로 냈다. 구조 비교(`select_comparator`, rev40)·S(`select_s`)는 같은 문장을 근거로 이미 **OOF 병합 subject 동일 가중** (`inner_loss`) 을 쓴다. inner validation 크기가 다르면 둘이 다르다.
- 현행 분할 (h197 `derivatives_v3/splits_piop1_p7/folds.json`, 그 자리에서 잼): main 126, outer test 26/25/25/25/25, inner validation 크기 outer 0 **34/33/33**, outer 1–4 **34/34/33** — 크기가 같지 않다. 차이는 작지만 동률 경계(1e−6)에서 선택이 갈릴 수 있고, 무엇보다 계획서 문장과 다르다.

## AT.2 바뀐 것

- `train.CellFoldResult` 에 **`n_subjects` (기본값 없음, 1 이상 정수)** 추가. 빠뜨리면 생성 자체가 실패한다 (fold 평균으로 조용히 돌아가지 않게).
- `train.select_config`: cell 손실·BA = Σ n_f · (fold 값) / Σ n_f. inner validation subject 는 fold 끼리 겹치지 않으므로 이는 OOF 하나로 합친 subject 동일 가중 log loss·`b_i` 평균과 **정확히 같다** (손계산 시험). 그 다음 네 cell 같은 가중 — 그대로. 동률 규칙·공통 E(12 best epoch 중앙값 올림)·완비 검사 — 그대로.
- 새 가드: 같은 inner fold 의 `n_subjects` 가 config·cell 사이에서 다르면 거부 (같은 inner 모집단 비교).
- 호출자: 라이브러리·CLI 에 `select_config` 호출자는 없다 (시험만, grep). 기존 산출물 영향 없음.

## AT.3 시험·돌연변이

- `tests/v2/test_train.py` 22 → **26**: fold 크기 3/3/1 에서 OOF 는 config 0, fold 평균은 config 1 을 뽑는 자료; subject 단위 손계산(OOF 병합 손실·BA, 1e−12)과 일치하고 fold 평균과 다름; `n_subjects` 필수·0/음수/bool/float 거부; fold subject 수 불일치 거부. 기존 시험은 `n_subjects=10` 만 덧붙임.
- Mac: `test_train`·`test_config_consumption`·`test_baselines` 111 passed. (Mac 전체 실행은 백그라운드 프로세스가 48% 에서 끊겨 결과 없음 — 최종 판정은 h197 마감 1번.)
- 돌연변이 (`.backup/slot_1915/mut_oof.py`, 원본 복원, `-B`·`PYTHONDONTWRITEBYTECODE=1`, 뒤 `__pycache__` 삭제): loss fold 평균·BA fold 평균·subject 수 가드 제거·n_subjects 검사 제거·n_subjects 기본값 추가·cell 가중 제거 = **6/6 검출**.

## AT.4 잠금

`mobse/v2/train.py` 변경으로 재잠금 `60aa5987ef0c` → **`b999c11f4c81` (2026-09-24T10:19:50Z)**, code_hash `cd9d823591fb` → `66cc8f11bf5b`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). split_hash `ace5f4a4…` 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변.

## AT.5 확인하지 못한 것 · 남은 순서

- A–D 선택 기록 CLI (`select-ad` 가칭, 96 fit_manifest → `train.select_config` → `selection.json` + outer 계획 4 cell × seed 42–44 × 공통 E) — 다음 조각. 입력은 `fit` 산출물(`fit_report.json`·`window_predictions.jsonl`)에서 fold 별 손실·BA·subject 수를 재계산해 `CellFoldResult` 로 넣는다.
- 이 정정이 구조 비교·S 와 "같은 함수" 인지는 수식 동치(시험)로만 확인 — A–D 는 fold 요약값에서, 나머지는 run 확률에서 계산한다.
- 외부 S, S·구조 비교 outer 집계, 실자료 fit·시간 — 없음.


# 부록 AU — A–D inner 선택 기록 CLI `select-ad` (WI-07 출력 "selection", rev47, 2026-09-24 예약 슬롯)

새 결정 아님. 규칙은 모두 계획서 §7 이 정한다 — "각 config의 inner OOF run loss를 subject별 동일 가중으로 합산하고 A–D 네 cell에 같은 가중을 주어 최소화", 동률(차이 ≤1e-6) → 공동 BA → 작은 config_id, 공통 E = 4 cells × 3 inner folds best epochs 중앙값 올림, "Inner seed=42", outer seed 42–44. 선택 함수는 rev46 에서 OOF 가중으로 정정한 `train.select_config` 이며 바꾸지 않았다. 하위 명령·산출물 형식만 구현 선택.

## AU.1 바뀐 것

- `mobse/v2/cli.py`: 하위 명령 **`select-ad --config --splits --output-dir --outer-fold K --fit-manifest ×96`** (4 cell × 8 config × 3 inner fold). `fit_report.json`·`window_predictions.jsonl` 은 manifest 옆 고정 이름 (U20, `select-comparator` 와 같음). 기존 `run_select_comparator` 는 **바꾸지 않았다** — 입력 검사는 같은 순서·같은 문구로 새 함수에 따로 둠 (구현 선택; 두 경로 공통화는 남은 작업).
- 검사: fit_manifest 스키마 · fit_id 중복 · cell ∈ A–D (NG·SG 거부) · inner role · outer fold · split/config hash · **model_seed = `train.INNER_SEED`** · 이웃 파일 · fit_report fit_id · config_id 로 fit_id 재계산 · fit_subjects = folds.json inner train · 예측 행 fit_id/cell/seed/scope/checkpoint/truth · 예측 subject = inner validation · 창 → run (`fitting.run_probabilities`) → **손실 (`train.subject_equal_loss`) 과 BA (`_balanced_accuracy_from_runs`) 를 fit_report `eval_loss`·`eval_balanced_accuracy` 와 1e-6 대조** · code/env/source hash 일치 → `CellFoldResult(n_subjects = folds.json inner validation 수)` → `train.select_config` (grid 완비·fold 크기 일치 가드는 거기서).
- 산출물 `selection.json` (schema `wi07-ad-selection-0.1`, 덮어쓰기 거부): 선택 config·공통 E·공동 손실·BA·동률 규칙·선택 config 12 best epoch·inner fold subject 수·config 8 행 표·outer 계획 (4 cell × 호출 시점 `train.MODEL_SEEDS`, 각 `fit --cell X --inner-fold 9 --config-id --epochs E --model-seed s` 인자)·입력 96 fit sha256.

## AU.2 시험·돌연변이

- 새 `tests/v2/test_cli_select_ad.py` **24** (inner validation 크기 4/4/3 — 공동 손실이 cell 별 OOF 병합 손계산과 1e-12 안에서 같고 fold 평균과는 다름을 확인, outer 계획 인자가 `fit` parser 로 다시 읽힘, `MODEL_SEEDS` monkeypatch, 경계·무결성 18). `test_cli_fit` 26 → **28**: 실제 A·D `run_fit` 산출물의 창 예측으로 다시 계산한 손실·BA 가 fit_report 와 1e-6 안.
- Mac: `test_cli_select_ad`·`test_cli_select_comparator`·`test_cli_prepare`·`test_evaluate_cli`·`test_config_consumption` 140 passed, `test_cli_fit -k ad_window` 2 passed.
- 돌연변이 (`.backup/slot_2015/mut_select_ad.py`, `run_select_ad` 본문 구간 안에서만 치환, 원본 복원, `-B`·`PYTHONDONTWRITEBYTECODE=1`, 뒤 `__pycache__` 삭제): inner seed 가드·subject 수 가중 → 1·BA 대조·손실 대조·cell 허용 넓힘·validation subject·scope·outer seed 리터럴·덮어쓰기·fit_id 재계산·계획 E·hash 일치·행 cell·checkpoint·fit_subjects·role·fit_id 중복·outer fold·truth·이웃 파일 = **20/20 검출**.

## AU.3 잠금

`mobse/v2/cli.py` 변경으로 재잠금 `b999c11f4c81` → **`5ed00c69c411` (2026-09-24T11:21:47Z)**, code_hash `66cc8f11bf5b` → `711b212fa011`. 검사 43/43, 창 4,728 (h197 재잠금 직후 19·25번). split_hash `ace5f4a4…` 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변.

## AU.4 확인하지 못한 것 · 남은 순서

- 실자료 inner fit 96 개로 돈 적 없음 (main OOF 승인 전). 합성 자료와 실제 `run_fit` 산출물 한 칸씩으로만 확인.
- `select-comparator` 와 입력 검사 코드가 중복 — 한쪽만 고치면 어긋날 수 있다 (공통화는 가역·결정 불요 후보).
- A–D outer 예측 → `evaluate` 경로는 기존 그대로 (`fit --inner-fold 9` × 12 → evaluate). 외부 선택(outer 9, main pool 전체 inner 분할)·S·구조 비교 outer 집계는 없음.


# 부록 AV — 결정 16: 이전 회차 돌연변이 stale pyc 재점검 (rev48, 2026-09-24 21:15 예약 슬롯)

선생님 결정 16 (09-24 20:1x, 대화 권고 "캐시를 끈 상태로 이전 돌연변이 스크립트를 다시 돌려 확인" 에 "ok"). 측정·시험 보강만 — 계획서·규칙·값 변경 없음, `mobse/v2` 변경 없음, main pool fit 없음.

## AV.1 방법

- 대상 (Mac `.backup` 에서 `ls` 로 확정): `slot_*/mut*.py` 12개 (`slot_0915/mut_mlp`·`slot_1015/mut_comparators`·`slot_1115/mut_consumption`·`slot_1215/mut_d14`·`slot_1315/mut_d14s3`·`slot_1415/mut_d14s4`·`slot_1515/mut_d14s4b`·`slot_1615/mut_d14s4c`·`slot_1715/mut_d15`·`slot_1815/mut_d14s4cii`·`slot_1915/mut_oof`·`slot_2015/mut_select_ad`) + `slot_2315/mut_best_ckpt.sh` (rev35) + 그 이전 회차 틀 `.backup/baselines_mutation.sh` (rev33)·`baselines_mutation_p11.sh` (rev34)·`report_mutation.sh` (rev31)·`prepare_mutation.sh` (rev32). `slot_2215/mut_p11.log` 의 틀은 `baselines_mutation_p11.sh` (gate evidence 인용).
- 현재 HEAD `9a3e6cd` (작업트리 깨끗) 에 대해 Mac `.venv` 로 실행. 옛 파이썬 틀은 subprocess env 를 `{"PYTHONPATH", "PATH"}` 로 새로 만들어 부모의 `PYTHONDONTWRITEBYTECODE` 가 전달되지 않으므로, 감싸개 `.backup/slot_2115/rerun_d16.py` 가 `subprocess.run` 을 가로채 python 호출에 `-B` 와 env `PYTHONDONTWRITEBYTECODE=1` 을 넣었다. 치환 원문 `assert … .count(…) == 1` 은 틀 사본에서 "NOT-APPLICABLE" 출력 + 다음 돌연변이로 바꿔 (c) 를 돌연변이별로 기록. 셸 틀은 `export PYTHONDONTWRITEBYTECODE=1` (원 틀이 `.backup` 원본 사본을 덮어쓰는 두 틀은 경로만 `slot_2115` 로 바꾼 사본). 치환 문구·시험 선택은 원 틀 그대로.
- 틀마다 전후 `find mobse scripts tests -name '*.pyc'` = **0**, `git status --porcelain -- mobse tests configs scripts` 비어 있음 — 17개 틀 전부 확인. 실행 21:17:04–21:31:00 KST. 로그 `.backup/slot_2115/rerun.log`·`rerun_old_sh.log`·`mut_seg.log` (커밋 안 함).
- 읽는 법 (결정 16 명세): stale pyc 는 "잡았다고 잘못 본" 방향으로만 작용 → 원래 검출이 재실행에서 **생존**으로 바뀐 것이 영향 받은 돌연변이. (c) 는 코드가 그 뒤 바뀐 것이라 판단 불가. 원래 틀이 rc≠0 을 검출로 세므로, 돌연변이 없는 HEAD 에서 해당 시험이 통과함(rev47 마감 908 passed, 같은 HEAD)과 `mut_best_ckpt.sh` 의 `-k` 선택이 4 시험을 모음(collect-only)을 확인했다.

## AV.2 결과

| 틀 (회차) | 당시 기록 | 재실행 (a) 검출 | (b) 생존 | (c) 적용 불가 |
|---|---|---|---|---|
| `report_mutation.sh` (rev31) | sha·group·부적격 검출, subject_scores·subject_differences 대조 단독 끔은 "중복 장치" | 3 | 2 (xcheck·xcheck2 — **당시와 같음**, 단독으로는 원래 생존으로 기록) | 0 |
| `prepare_mutation.sh` (rev32) | 5 검출 | 5 | 0 | 0 |
| `baselines_mutation.sh` (rev33) | 9/9 | 7 | 1 (`no_unconv` — 아래) | 1 (`no_tie_tol` sed no-op) |
| `baselines_mutation_p11.sh` (rev34) | 14/14 | 14 | 0 | 0 |
| `slot_2315/mut_best_ckpt.sh` (rev35) | 6/6 | 6 | 0 | 0 |
| `slot_0915/mut_mlp.py` (rev36) | 11/11 | 11 | 0 | 0 |
| `slot_1015/mut_comparators.py` (rev37) | 15/15 | 15 | 0 | 0 |
| `slot_1115/mut_consumption.py` (rev38) | 8/8 | 8 | 0 | 0 |
| `slot_1215/mut_d14.py` (rev39) | 8/8 | 8 | 0 | 0 |
| `slot_1315/mut_d14s3.py` (rev40) | 14/14 | 14 | 0 | 0 |
| `slot_1415/mut_d14s4.py` (rev41) | 9/9 | 9 | 0 | 0 |
| `slot_1515/mut_d14s4b.py` (rev42) | 16/16 | 6 | 0 | 10 → 구간 한정 재실행 10/10 검출 |
| `slot_1615/mut_d14s4c.py` (rev43) | 14/14 | 14 | 0 | 0 |
| `slot_1715/mut_d15.py` (rev44) | 7/7 | 7 | 0 | 0 |
| `slot_1815/mut_d14s4cii.py` (rev45) | 21/21 | 21 | 0 | 0 |
| `slot_1915/mut_oof.py` (rev46) | 6/6 | 6 | 0 | 0 |
| `slot_2015/mut_select_ad.py` (rev47) | 20/20 | 20 | 0 | 0 |

- **원래 검출 → 재실행 생존으로 바뀐 돌연변이: 0.** stale pyc 가 이전 회차 검출 판정을 부풀린 흔적은 없다.
- `slot_1515` s2–s11 (c): rev47 `select-ad` 가 같은 검사 문구를 복사해 `cli.py` 안 출현이 2–3 회가 됨 (PATTERN-COUNT). 치환 문구·시험은 그대로 두고 위치만 `run_select_comparator` 본문 구간으로 한정한 사본 `.backup/slot_2115/mut_d14s4b_seg.py` 로 **10/10 검출**.
- `baselines_mutation.sh` `no_unconv` (`^    if bad:$` → `if False:`): 원래 줄(미수렴 거부)은 rev34 P11 에서 없어졌고, 같은 패턴이 rev45 `baselines.s_outer_plan` 의 **inner best epoch 범위 가드**에 걸렸다 — 원 돌연변이로서는 (c) 이지만, 새 위치의 돌연변이가 `test_baselines`·`test_cli_select_s` 69 시험 전부를 통과했다 (`mut_s_outer_bad.log`). outer E 범위 검사가 [0,0,0]·[500,500,500] 은 잡지만 [1, 1, 401]·[0, 300, 300] 처럼 중앙값이 범위 안인 경우는 이 가드만 잡는다. `no_tie_tol` 은 P11 에서 식이 바뀌어 sed 가 no-op.

## AV.3 보강 시험 (가역, 결정 불요)

- `tests/v2/test_cli_select_s.py` 에 `test_s_outer_plan_refuses_each_best_epoch_out_of_range` 1개 (27 → **28**): [1, 1, MAX+1]·[0, 300, 300] 이 outer E 범위 안임을 먼저 확인한 뒤 `s_outer_plan` 거부 ("best epoch 가 1").
- 같은 돌연변이 재실행: **검출** (1 failed, 69 passed — 새 시험). `mobse/v2` 불변.
- `select-s` CLI 자체의 best_epoch 범위 가드는 rev45 돌연변이 "best_epoch 범위 끔" 에서 이미 검출 (이번 재실행에서도 검출) — 이번 것은 라이브러리 `s_outer_plan` 쪽의 두 번째 가드.

## AV.4 확인하지 못한 것

- 원래 실행 때 실제로 stale pyc 가 생겼는지 자체는 재현할 수 없다 — 재실행은 "지금 코드에서 bytecode 없이도 검출된다" 만 보인다. (c) 11개는 당시 판정을 직접 재현한 것이 아니다 (10개는 위치 한정 사본으로 같은 의미의 돌연변이를 재현).
- `slot_0915`·`slot_1015` 는 당시 로그 파일이 없어 당시 기록은 부록 AI·AJ 의 수치.
- 재실행은 Mac 만 (h197 은 마감 5단계만).

# 부록 AW — 남은 작업 2-c: 두 선택 CLI 입력 검사 공통화 (rev49, 2026-09-24 22:15 예약 슬롯)

새 결정 아님. 규칙·값·산출물 형식 불변 — rev47 에서 `select-ad` 가 `select-comparator` 의 입력 검사를 같은 순서·같은 문구로 복사해 둔 것을 한 곳으로 모았다 (부록 AU "확인 못 한 것", 부록 AV 에서 이 중복 때문에 옛 돌연변이 10개가 적용 불가가 된 것).

## AW.1 변경

- `mobse/v2/cli.py` 새 `_load_inner_fit(path, *, folds, outer_fold, cfg_hash, seen_ids, check_cell, require_inner_seed)`: 스키마 → fit_id 중복 → `check_cell` (호출자 칸 규칙) → inner role → outer fold → split/config hash → (`require_inner_seed` 이면 `train.INNER_SEED`) → 이웃 파일 (U20) → fit_report fit_id → config_id 로 fit_id 재계산 → fit_subjects = inner train → 예측 행 (fit_id/cell/seed·scope·checkpoint·창 번호·truth) → 예측 subject = inner validation → `fitting.run_probabilities`. 새 `_check_inner_hashes_uniform(inputs)` (code/env/source hash 하나씩).
- 호출자에 남긴 것 (두 CLI 가 원래 달랐던 부분): 칸 규칙 (`select-comparator` = `--structure` 하나, `select-ad` = `train.CELLS`), inner seed 요구 (`select-ad` 만 — `select-comparator` 는 원래대로 `baselines.select_comparator` 가 거부), 손실 재계산 함수 (`baselines.inner_loss` / `train.subject_equal_loss`), BA 대조 (`select-ad` 만), `CellFoldResult`·`ComparatorInner` 구성, 산출물. 오류 문구·검사 순서는 복사본과 같다 (fit 하나씩 읽고 바로 손실 대조하는 순서도 같음).

## AW.2 시험 보강 — 공통화 돌연변이에서 드러난, 원래도 시험이 없던 가드

- 공통화 뒤 돌연변이 틀 `.backup/slot_2215b/mut_2c.py` (helper 가드 17개는 **두 시험 파일 각각**이 잡아야 검출, 호출자 가드 13개는 해당 CLI 시험; `-B`·`PYTHONDONTWRITEBYTECODE=1`, 구간 한정 count==1, 원본 복원 확인). 첫 실행 **39/46** — 생존 7: split_hash 대조·config_hash 대조·fit_report fit_id 대조 (두 파일 모두), 예측 행 cell 대조 (`select-comparator` 만). 이 가드들은 rev42·rev47 복사본에도 있었고 시험이 없었다 (공통화가 만든 틈이 아님).
- 추가: `test_cli_select_ad.py` 24 → **27** (`test_other_split_hash_is_refused`·`test_other_config_hash_is_refused`·`test_report_of_other_fit_is_refused`), `test_cli_select_comparator.py` 22 → **26** (같은 셋 + `test_row_of_other_structure_is_refused`, 파일 안 `_one_bad` 도우미 추가).
- 재실행 **46/46 검출** (`mut_2c_r2.log`). 동작 불변 확인: 새 53 시험을 **HEAD `ed4668b` 의 `cli.py`** 로도 돌려 53 passed (공통화 전후 같은 판정).
- 옛 구간 한정 틀 `slot_2015/mut_select_ad.py`·`slot_2115/mut_d14s4b_seg.py` 는 치환 문구가 helper 로 옮겨 가 적용 불가 — `mut_2c.py` 가 그 두 틀의 공통 문구 돌연변이를 helper 구간에서, 나머지를 호출자 구간에서 대신한다.

## AW.3 잠금·gate

- `mobse/v2` 변경 → 재잠금 `5ed00c69c411` → **`aee2b7931538`** (2026-09-24T13:22:33Z), code_hash → `06d4403d67ff`. 19번 43/43, 25번 창 4,728. split_hash `ace5f4a4…`·config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변. gate evidence **rev49** (`ad_joint_selection.shared_input_checks_rev49`).
- main pool 미소비, 실자료 fit 없음.

## AW.4 확인하지 못한 것

- 실자료 inner fit 으로 두 CLI 실행 (main OOF 승인 전). 돌연변이는 Mac 만 (h197 은 마감 5단계).
- `select-s` 의 입력 검사는 입력 계약(`s_fit_report`)이 달라 이번 공통화 대상이 아니다.

# 부록 AX — 결정 17: 외부 최종 선택 3-fold 를 별도 파생 산출물 `external_folds.json` 으로 고정 (rev50, 2026-09-25 10:14 예약 슬롯)

선생님 원문 (09-25 07:2x KST 기록): 23:15 슬롯 선택지 중 **"(나) 별도 파생 산출물 external_folds.json을 두고 잠금 항목을 추가: split_hash가 그대로입니다. 이 방식을 권합니다."** 를 선택. 정한 것: 계획서 §4-3 external 최종 선택 seed 20262000 의 main pool 3-fold 경계를 `folds.json` 밖의 별도 파일로 두고 측정 잠금에 항목 추가, split_hash 불변. 정하지 않은 것: 분할 알고리즘·seed 변경, 외부 선택·외부 최종 fit 실행 (main OOF 착수 승인 전 금지), PIOP2 쪽 변경.

## AX.1 구현 (파일 이름 외 스키마는 구현 선택)

- `mobse/v2/splits.py`: `build_external_folds(groups, folds_manifest, *, n_folds=3, seed=EXTERNAL_SEED)` — 부모 manifest 의 pilot group 을 뺀 group 이 부모 `main_pool.subjects` 와 정확히 같아야 하고 (다르면 거부), `assign_to_folds(main pool, 3, 20262000)` 로 `inner` 0–2 = {inner_fold, seed, val_groups, val_subjects, train_subjects = main pool − val}. `verify_disjoint` 로 pilot 불교차. 기록: schema_version `external_folds_v1`, algorithm, numpy 버전, grouping_assumption (부모 그대로), `parent_split_hash`, seed, n_folds, main pool 수, pilot 수, 자체 `external_split_hash` (`split_hash` 와 같은 직렬화 — sort_keys JSON 의 sha256, 자기 자신만 제외). `external_invariants(ext, folds)` 11 불리언 (구조·스키마·부모 hash 일치·자체 hash 재계산·seed = 부모 `seeds.external`·inner seed·fold 번호 0..n−1·val 상호 불교차·val 합집합 = main pool·train = main pool − val·pilot 부재) + val 크기. **`build_folds` 는 바꾸지 않았다.** group 정보는 `split` 이 쓰는 subjects manifest 의 `group_id` 를 그대로 쓴다 (folds.json 에는 main pool 의 subject→group 대응이 없어서; 현 코호트는 1 subject = 1 group).
- `mobse/v2/cli.py`: `split` 이 `folds.json` 옆에 `external_folds.json` 을 함께 쓴다 — 두 파일 중 하나라도 있으면 아무것도 쓰기 전에 거부. seed·fold 수는 config `splits.external_seed`·`splits.n_inner_folds` (대응표 `test_config_consumption` 에 소비 지점 추가). 기존 디렉터리용 `run_external_split` (하위 명령 아님 — CLI 10개 불변): 같은 subjects manifest (sha256 = folds.json 기록) 와 config 로 `build_folds` 를 다시 계산해 **기존 split_hash 재현을 확인**한 뒤 새 파일만 쓰고, 쓰기 전후 folds.json sha256 동일을 확인. 새 `scripts/h197/26_write_external_folds.py` 가 부른다.
- `mobse/v2/fitting.py`: `resolve_fold_subjects(folds, outer, inner, external_folds=None)` — `outer == templates.EXTERNAL_OUTER_FOLD (9)` 이면 inner 0–2 를 `external_folds.json` 에서 (role inner, 평가 = val). 파일 없음·불변식 하나라도 실패 (부모 split_hash 불일치 포함)·없는 inner 번호는 `FitError`. **`(9, 9)` external final 은 PIOP2 평가 배선 전이라 거부.** outer 0–4 경로 불변 (pilot·겹침 검사는 `_checked_fold` 로 공유). 기존 호출자 4곳은 인자를 넘기지 않으므로 outer 9 는 여전히 거부된다 (외부 선택 CLI 는 다음 단위).
- `mobse/v2/locks.py`·`scripts/h197/18_build_measurement_lock.py`: 분할이 있는 코호트는 `external_folds` 레코드 필수 (없으면 18번이 잠그지 않고 19번은 `missing`). 레코드 = 파일 sha256·`external_split_hash`·`parent_split_hash`·seed·n_folds·불변식. `verify_lock` 이 파일을 다시 읽어 불변식 재계산, 기록된 parent/external hash·불변식과 대조.

## AX.2 시험·돌연변이

- 새 `tests/v2/test_external_folds.py` **34** (157 subject 합성: 42/42/42·train 84·합집합 = main pool·pilot 부재·seed = `assign_to_folds(…, 20262000)` 와 동일·결정성·다른 seed 는 다른 경계·부모 dict 불변 + `build_folds` split_hash 재현·자체 hash 정의·다른 코호트 group 거부·부모 구조/hash 형식 거부·불변식 9종 각각의 변조 검출·hash 재계산 없는 수정 검출·구조 누락 = 실패·`resolve_fold_subjects(9, 0/1/2)`·파일 없음/(9,9)/부모 hash 불일치/변조/없는 inner 거부·outer 0–4 는 인자와 무관·잠금 검증/레코드 없음/불변식 재계산). `test_cli_split.py` 17 → **25** (외부 파일 위치·42/42/42·부모 hash, folds.json 키 = `build_folds` + CLI 3 키 (외부 블록 없음)·split_hash = `build_folds`, 외부 파일이 있으면 folds.json 도 안 씀, `run_external_split` 새 파일만 추가·folds.json 바이트 불변·`split` 과 같은 바이트, 덮어쓰기·split_hash 불일치·다른 subjects manifest·folds.json 없음 거부). `test_locks.py` 25 (fixture 에 외부 분할 추가, 수 불변). `test_config_consumption` 수 불변.
- 돌연변이 `.backup/slot_1015/mut_d17.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, count==1, 원본 복원): 첫 실행 **27/28** — 생존 1 = `resolve_fold_subjects` 의 "external_folds 없음" 가드 제거 (없어도 불변식 단계가 구조 실패로 거부하고, 시험이 두 문구에 공통인 "external_folds.json" 만 봄). 시험 문구를 "external_folds.json 이 필요하다" 로 좁혀 재실행 **28/28** (`mut_d17_r2.log`). 시작·rsync 전 Mac `*.pyc` 0.

## AX.3 실제 산출물 (h197, 결정 17 명세 5 대조)

- `scripts/h197/26_write_external_folds.py --config configs/redesign_v1/main.yaml --subjects $D/derivatives_v3/cohort_piop1/subjects.jsonl --splits-dir $D/derivatives_v3/splits_piop1_p7` (`-B`, rc=0): 재계산 split_hash `ace5f4a41446…` = 기록, **folds.json sha256 `242ba87d6101…` 전후 동일**, 새 `external_folds.json` sha256 `698f7436b17c…`, `external_split_hash` **`40e50350e97a…`**, val 42/42/42.
- val subject 목록 (`"\n".join`) sha256 앞 12자 **`0df6870deca5` / `527f2effa569` / `60f3a21cde35`** — 23:15 슬롯 건식 계산과 **3/3 동일**.
- 디렉터리에는 `folds.json` 과 새 파일 둘뿐 (기존 파일 덮어쓰기 없음).

## AX.4 잠금·gate

- 재잠금 `aee2b7931538` → **`472bee47adcd`** (2026-09-25T01:25:01Z), code_hash `06d4403d67ff` → `13a051a6a663`. 19번 **45/45** (43 + external_folds 파일 1 + 불변식 11건 1). 25번 창 4,728. split_hash `ace5f4a4…` 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변. gate evidence **rev50** (`decision17_external_folds`).
- fit 없음, main pool 미소비.

## AX.5 확인하지 못한 것

- 외부 선택 CLI (A–D `select-ad`·`select-comparator`·`select-s` 의 outer 9 경로) — 다음 단위 (결정 17 명세 7). 실자료 실행은 main OOF 승인 전 금지.
- external final `(9, 9)` 의 PIOP2 평가 배선 — 거부로 막아 둠.
- 가족/중복 group 이 있는 코호트에서의 실측 (합성 시험은 1 subject = 1 group 과 group 불일치 거부만 덮음).
- 18번 스크립트의 external 거부 분기는 단위 시험이 아니라 이번 실행 (성공 경로) 으로만 확인.

# 부록 AY — 결정 17 명세 7 (a): `fit`·`fit-s` 의 outer 9 (외부 최종 선택 inner) 경로 배선 (rev51, 2026-09-25 11:15 예약 슬롯)

결정 17 (부록 AX) 의 남은 명세 7 을 둘로 나눈 첫 조각이다. 새 결정 아님 — 결정 17 범위 안의 배선. **외부 선택·외부 최종 fit 실행 승인 아님**: 합성 자료 시험만, 실자료 fit 없음, main pool 미소비.

## AY.1 구현

- `mobse/v2/cli.py` 새 `_external_folds_for(splits_path, outer_fold)`: outer fold 가 `templates.EXTERNAL_OUTER_FOLD` (9) 일 때만 `--splits` 와 같은 디렉터리의 `external_folds.json` 을 읽어 (내용, 파일 sha256) 을 돌려준다. 파일이 없으면 `CLIError` (대체 탐색 없음). outer 0–4 에서는 읽지 않는다 (None).
- **구현 선택 (결정 아님, 표시)**: 별도 `--external-splits` 인자 대신 `--splits` 옆 고정 이름 (U20 — 선택 CLI 가 이웃 `fit_report.json` 을 고정 이름으로 읽는 것과 같은 규칙; `split` 이 두 파일을 같은 디렉터리에 쓴다). 따라서 `fit`·`fit-s` 인자 목록·`REQUIRED_PATHS` 는 불변.
- `run_fit`·`run_fit_s`: `resolve_fold_subjects(folds, outer, inner, external_folds=…)` 로 넘긴다. 불변식 검사 (부모 split_hash·자체 hash·val 불교차 등 11종) 와 `(9, 9)` external final 거부는 `fitting.resolve_fold_subjects` (rev50) 가 그대로 한다.
- 기록 (**구현 선택**): outer 9 fit 은 `fit_manifest.json` (fit) / `s_fit_report.json` (fit-s) 에 `external_split_hash` 와 `external_folds_sha256` 을 덧붙인다. 기존 키 불변, outer 0–4 산출물에는 두 키가 없다. `fit_id`·`s_fit_id` payload 는 바꾸지 않았다 (outer_fold=9 가 이미 payload 에 있어 main fit 과 식별자가 갈린다).
- bank seed 는 기존 `templates.bank_seed(9, j)` = 30900 + j (0–9 범위 규칙 그대로).

## AY.2 시험·돌연변이

- `tests/v2/test_cli_fit.py` 26 → **33** (HEAD `a9fa70e` 판을 `--collect-only` 로 잰 값 26; 인수인계 문서 rev47 행의 "28" 과 다르다 — 이전 기록의 수를 이번에 정정하지는 않음): 외부 inner 0/1/2 fit 이 `external_folds.json` 의 train/val 을 쓰고 (fit_subjects·평가 subject·n_eval), 두 기록 키 값·bank seed 를 확인 (3), 파일 없음 거부, `(9, 9)` 거부, val subject 를 옮긴 변조 파일 거부, 파일이 있어도 outer 0 fit 은 folds.json 경계를 쓰고 두 키가 없음.
- `tests/v2/test_cli_fit_s.py` 17 → **22**: S1 logistic 으로 같은 구성 (외부 inner 0/1/2 · 파일 없음 · outer 0 은 무시). `_ns` 에 `outer` 인자 추가 (기본 0).
- 합성 fixture: 기존 folds.json 에 `pilot.groups`·`seeds.external` 을 채우고 `splits.build_external_folds` 로 외부 파일을 만든다 (main pool 16 명).
- 돌연변이 `.backup/slot_1115b/mut_ext_fit.py` (`slot_1015/mut_d17.py` 틀, `-B`·`PYTHONDONTWRITEBYTECODE=1`, count==1, 원본 복원, `-k external`): **13/13 검출** — 게이트 반전 2, 파일 없음 가드, 경로, sha 대상, fit·fit-s 전달 누락 2, 기록 게이트 2, 기록 키 제거 4. 시작 전·끝·rsync 전 Mac `*.pyc` 0.
- 관련 시험 8 파일 (fit·fit-s·external_folds·config_consumption·split·select 3종) Mac 238 passed.

## AY.3 잠금·gate

- 재잠금 `472bee47adcd` → **`edf57e93d6dd`** (2026-09-25T02:20:57Z), code_hash `13a051a6a663` → `a449af15ae36`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…` 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변. gate evidence **rev51** (`decision17_external_folds.spec7a_fit_wiring_rev51`).

## AY.4 확인하지 못한 것 · 다음

- (b) 선택 CLI 3종 (`select-ad`·`select-comparator`·`select-s`) 의 outer 9 경로 — `_load_inner_fit`·`run_select_s` 의 `resolve_fold_subjects` 호출은 아직 외부 파일을 넘기지 않아 outer 9 를 거부한다. 거기서 fit 기록의 `external_split_hash` 를 외부 파일과 대조할지, 외부 inner validation 수 (42) 가 `CellFoldResult.n_subjects` 로 들어가는지 확인.
- 실자료 외부 inner fit (승인 전 금지) · 외부 inner 창 수·시간 실측 없음.
- (9, 9) external final 의 PIOP2 평가 배선 — 여전히 거부.

# 부록 AZ — 결정 17 명세 7 (b): 선택 CLI 3종 (`select-ad`·`select-comparator`·`select-s`) 의 outer 9 경로 배선 (rev52, 2026-09-25 12:14 예약 슬롯)

부록 AY 의 다음 조각이다. 새 결정 아님 — 결정 17 범위 안의 배선. **외부 선택·외부 최종 fit 실행 승인 아님**: 합성 자료 시험만, 실자료 fit·선택 실행 없음, main pool 미소비.

## AZ.1 구현

- `mobse/v2/cli.py`: 세 선택 CLI 가 `_external_folds_for(--splits, outer_fold)` (rev51 과 같은 고정 이름 규칙, U20) 를 한 번 부르고, outer 9 이면 그 내용을 `resolve_fold_subjects(..., external_folds=…)` 에 넘긴다. `select-ad`·`select-comparator` 는 공유 helper `_load_inner_fit(..., external=)` (필수 키워드 인자 — 빠뜨리면 조용히 꺼지지 않고 TypeError), `select-s` 는 `run_select_s` 본문에서. outer 0–4 는 파일을 읽지 않는다.
- 새 `_check_external_record(ident, record, outer_fold, external)` — **구현 선택 (결정 아님, 표시)**: outer 9 fit 의 `fit_manifest.json` / `s_fit_report.json` 에 기록된 `external_split_hash`·`external_folds_sha256` (rev51) 이 지금 읽은 외부 파일의 값·파일 sha256 과 같아야 한다 (fit 뒤 파일 교체 검출 — 경계가 같아도 바이트가 바뀌면 거부). 기록이 없어도 거부. outer 0–4 fit 에 두 키가 있으면 거부 (경계 혼입). 위치: split/config hash 대조 바로 뒤.
- `select-ad` 의 `CellFoldResult.n_subjects` 는 원래부터 `resolve_fold_subjects` 가 준 `fold.evaluate` 수라, outer 9 에서는 외부 inner validation 수 (실자료 42/42/42) 가 된다 — 코드 변경 없이 성립, 시험으로 고정 (`inner_fold_n_subjects` = 외부 파일 val 수).
- 선택 기록 (`selection.json`·`comparator_selection.json`·`s_selection.json`): outer 9 에서만 `external_split_hash`·`external_folds_sha256`·`outer_plan_status` 를 덧붙인다 (**구현 선택**; 기존 키 불변, outer 0–4 기록에는 없음 — 시험). outer 계획의 `(9, 9)` external final 인자는 **기록만** 하며, 그 fit 은 `resolve_fold_subjects` 가 계속 거부한다 (PIOP2 평가 배선 전, 결정 17 범위 밖).
- `select-s` 의 grid 완비 96·`S_INNER_FOLDS = 3` 은 외부에서도 같다 (계획서 §6 "외부 S도 PIOP1 main pool의 inner 결과로만 고른다"). docstring 의 "외부 S 미구현" 문장 정정.

## AZ.2 시험·돌연변이

- 세 시험 파일의 합성 fit 생성기 `make_fit` 에 `outer` 인자 (기본 0) 와 `_inner_rec`·`_with_external` (rev51 `test_cli_fit.py` 방식: fixture folds.json 에 `pilot.groups`·`seeds.external`, `build_external_folds` 로 옆에 외부 파일) 추가. outer 9 fit 은 rev51 과 같은 두 기록 키를 가진다. `n_eval_subjects` 리터럴 4 → val 수 (outer 0 에서 같은 값).
- 시험 수 (HEAD `3e0a9a0` 판 81 → 108): `test_cli_select_ad.py` 27 → **36**, `test_cli_select_comparator.py` 26 → **35**, `test_cli_select_s.py` 28 → **37**. 파일마다 같은 9 개: 외부 inner 경계로 선택·기록 필드 (`select-ad` 는 fold subject 수), outer 0 기록에 외부 필드 없음, 파일 없음 거부, 기록 split hash 다름·없음 거부, 기록 파일 sha 다름 거부, fit 뒤 외부 파일 교체 (같은 경계, 다른 바이트) 거부, outer 0 fit 에 외부 기록 거부, outer 9 fit 이 folds.json outer 0 inner 경계로 학습한 경우 거부.
- 동작 확인: 새 시험 파일을 **HEAD 판 `cli.py`** 에 돌리면 기존 81 (`-k "not external"`) 통과 — fixture 변경이 outer 0 경로를 바꾸지 않음; 새 27 중 24 실패 (새 동작), 3 통과 (outer 0 기록에 외부 필드 없음 — HEAD 에서도 참).
- 돌연변이 `.backup/slot_1215b/mut_sel_ext.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, 출현 수 검사 + n 번째 출현 치환, 원본 복원, `-k external`; 공유 가드는 잡아야 할 시험 파일 **각각**이 rc≠0 이어야 검출 — `mut_2c.py` 방식): 첫 실행 12/13 (1 은 치환 원문이 `run_fit_s` 에도 있어 NOT-APPLICABLE → 뒤 문맥 추가), 재실행 **13/13 검출** — 공유 대조 가드 3 + 선택 기록 필드 (세 파일 각각), helper resolve·대조 호출 제거 (ad·comparator 각각), 호출자 전달 누락 2, `ext` 계산 제거 3, `select-s` 대조 호출·resolve 전달 제거 2. 시작 전·끝·rsync 전 Mac `*.pyc` 0.
- 관련 시험 8 파일 (fit·fit-s·external_folds·config_consumption·split·select 3종) Mac 265 passed (238 + 27).

## AZ.3 잠금·gate

- 재잠금 `edf57e93d6dd` → **`9afbfcff698e`** (2026-09-25T03:21:45Z), code_hash `a449af15ae36` → `b7fc265aa500`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…` (val 42/42/42) 불변, config_hash main `2a7d7d7f`·pilot `6498596a`·external `576f6068` 불변. gate evidence **rev52** (`decision17_external_folds.spec7b_selection_wiring_rev52`).

## AZ.4 확인하지 못한 것 · 다음

- 실자료 외부 inner fit·선택 (승인 전 금지) · 외부 inner 창 수·시간 실측 없음.
- (9, 9) external final 의 PIOP2 평가 배선 — 여전히 거부. 결정 17 명세 7 은 이것으로 끝나고, external final 은 범위 밖으로 남는다.
- `run_select_s` 의 입력 검사는 여전히 `_load_inner_fit` 과 따로 있다 (입력 계약이 달라 rev49 공통화 대상 아니었음) — 외부 대조는 같은 helper `_check_external_record` 를 쓴다.


# 부록 BA — 보조 비교 칸 (S·NG·SG) outer 예측 집계 함수 (rev53, 2026-09-25 13:15 예약 슬롯)

남은 작업 2-c 의 "구조 비교·S outer 예측 집계 경로" 중 **라이브러리 집계 함수** 조각이다. 새 결정 아님 — 계획서 §8 의 run 집계 규칙을 보조 비교 칸에 적용. 합성 자료 시험만, 실자료 fit 없음, main pool 미소비. CLI 배선 (`evaluate`/`report` 확장 또는 새 하위 명령) 은 하지 않았다.

## BA.1 계획서 근거 (grep, 13:1x)

- §8: "각 window의 세 seed 확률을 평균하고, 각 task의 네 window를 평균해 subject당 두 run probability를 얻는다. threshold=0.5이며 동일값은 class 1" · "A−S, interaction, macro-F1, AUROC, log loss, calibration, subgroup, routing diagnostics는 보조이며 95% 기술적 CI로 표시한다".
- §6: "no-graph FC comparator와 실제 parameter/비용을 함께 보고한다". §9: 보조 분석 목록에 "no-graph/average graph".
- 따라서 **A−S 는 계획서가 이름으로 정한 보조 contrast**, 구조 비교 (NG·SG) 는 보조 분석으로 나열만 되고 **A−NG·A−SG 같은 contrast 는 계획서에 없다** → 이번 조각은 NG·SG 의 칸별 b_i·BA 만 내고 contrast 는 만들지 않았다 (결정 요청 BA.4).

## BA.2 구현 (`mobse/v2/evaluate.py`)

- `aggregate_runs` 본체를 `_aggregate_grid(..., seeds_for, n_seeds)` 로 옮김. A–D 경로는 `seeds_for → None` 으로 **seed 개수만** 맞추는 기존 동작 그대로 (기존 시험 3 파일 evaluate_cli·cli_evaluate·cli_report 62 통과, seed 값 거부는 CLI 몫 — 시험으로 고정). 추가: `aggregate_runs` 는 `WindowPrediction` 이 아닌 행을 거부 (보조 비교 칸이 A–D 집계로 새지 않게).
- 새 `COMPARISON_CELLS = ("S", "NG", "SG")` (= `("S",) + baselines.COMPARATOR_ORDER`, 시험 고정), `COMPARISON_CONTRASTS = ("A_minus_S",)`.
- 새 `ComparisonWindowPrediction` (cell ∈ COMPARISON_CELLS, `model_seed=None` 은 S 만).
- 새 `aggregate_comparison_runs(preds, *, cell, seeds_by_subject)`: **구현 선택 (표시함)** — S 는 outer fold 마다 선택 후보가 다를 수 있어 (logistic 은 seed 없이 한 번, MLP 는 `train.MODEL_SEEDS` 3 개 — `baselines.s_outer_plan`, 부록 AS) seed 를 **subject 별 집합** 으로 받고, 그 집합과 **정확히** 같아야 한다 (A–D 는 개수만). 칸 섞임·예측 subject ≠ 지도 subject·빈/중복 seed 목록·None 이 S logistic 단독 밖에 있는 경우를 거부. run 확률은 A–D 와 같은 `statistics.run_probability` (window 안 seed 평균 → window 평균), 기록 `n_seeds` 는 실제 seed 수.
- 새 `comparison_contrasts(ad_runs, s_runs)`: A−S 의 subject 별 b 차이. subject 집합이 다르면 거부 (paired 불가). CI 계산 (§8 의 95% 기술적 CI) 은 기존 `statistics` 함수를 쓰면 되지만 이번에 배선하지 않았다.

## BA.3 시험·돌연변이·잠금

- 새 `tests/v2/test_evaluate_comparison.py` **17**: logistic·MLP subject 가 섞인 S 손계산 (run p·n_seeds·BA 2.5/3), 동일값 class 1, NG seed 3, seed 집합 ≠ (42,43,45), seed 누락, window 누락, (window, seed) 한 칸 누락, 중복, subject 추가/누락, 칸 섞임·모르는 칸, 두 예측 형식 교차 거부, seed 없음 규칙, 빈/중복 seed 목록, A−S 손계산 (+0.5/+1.0/−0.5), A−S subject 불일치, A–D 는 여전히 seed 개수만.
- 돌연변이 `.backup/slot_1315b/mut_cmp.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, count==1, 원본 복원): **15/15 검출**. 시작 전·끝·rsync 전 Mac `*.pyc` 0.
- 관련 5 파일 (evaluate_cli·cli_evaluate·cli_report·config_consumption·evaluate_comparison) Mac 122 passed.
- 재잠금 `9afbfcff698e` → **`2d2250119456`** (2026-09-25T04:18:29Z), code_hash `b7fc265aa500` → `45d312b905dd`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash 불변. gate evidence **rev53** (`comparison_aggregation_rev53`).

## BA.4 결정 요청 · 확인하지 못한 것

- **결정 요청**: 구조 비교 NG·SG 를 A 와 paired contrast (A−NG, A−SG, 95% 기술적 CI) 로 보고할지, 칸별 BA·비용만 보고할지. 계획서 §6·§9 는 보고 대상으로만 두고 contrast 를 정하지 않았다. 슬롯 권고: **A−NG·A−SG 를 A−S 와 같은 보조 contrast 로 추가** (같은 paired bootstrap seed 9001, 95% 기술적 CI; primary 가 아님을 표시) — 계산이 이미 있는 함수로 되고, 칸별 BA 만으로는 "graph prior 없이/단일 graph 로 얼마나 되는가" 를 subject 짝 없이 비교하게 된다. 결정 전에는 NG·SG contrast 를 만들지 않는다.
- CLI 배선 (S·NG·SG outer 산출물 → `ComparisonWindowPrediction` → 집계 → 통계) 없음 — S 는 `s_window_predictions.jsonl`, NG·SG 는 fit `window_predictions.jsonl` 로 입력 계약이 달라 다음 조각. 실자료 outer 예측 없음.



# 부록 BB — 구조 비교 (NG·SG) main outer fit 산출물 → 보조 비교 집계 helper (rev54, 2026-09-25 14:15 예약 슬롯)

남은 작업 2-c "CLI 배선" 의 첫 조각이다. 새 결정 아님 — 규칙은 계획서 §8 run 집계 (부록 BA) 와 결정 14 의 outer 계획 (부록 AP). 합성 자료 시험만, 실자료 fit 없음, main pool 미소비. **하위 명령은 만들지 않았다** (CLI 10 개 불변).

## BB.1 사전 확인 (grep, 14:1x)

- `manifests.SCHEMAS["s_window_predictions"]` 에는 **`model_seed` 자리가 없다** (후보·설정·`s_fit_id` 만). S MLP 행의 seed 는 `s_fit_report.json` 에서 와야 한다 → S 쪽은 입력 계약이 NG·SG 와 달라 다음 조각으로 미룸.
- NG·SG outer fit 은 `fit --cell NG|SG --inner-fold 9` 가 A–D 와 같은 `fit_manifest.json`·`fit_report.json` (`config_id`·`epochs_run`·`checkpoint_sha256`)·`window_predictions.jsonl`·`checkpoint.pt` 를 쓴다 (부록 AO). `comparator_selection.json` 의 `outer_plan` 행은 `config_id`·`model_seed`·`epochs_exact` 를 갖는다 (부록 AP).

## BB.2 구현 (`mobse/v2/cli.py`)

- 새 `_load_comparator_outer(manifest_paths, *, structure, folds, cfg_hash, selections)` + `COMPARATOR_OUTER_NEIGHBOURS = ("fit_report.json", "window_predictions.jsonl", "checkpoint.pt")` (manifest 옆 고정 이름, U20).
- 선택 기록 검사: outer fold 집합 = folds.json outer fold 전부, 스키마 `d14-comparator-selection-0.1`, 구조·outer_fold·split/config hash 일치, 외부 기록 (`external_split_hash`) 거부, outer 계획 seed 비었거나 중복 거부, **계획 seed = 잠긴 `train.MODEL_SEEDS`** (`_check_fit_grid` 와 같은 규칙), 계획 행의 config/E = 선택 기록.
- fit 검사: 스키마·fit_id 중복·cell = 구조·outer role·외부 분할 기록 거부·split/config hash·선택 기록 없는 outer fold·계획 밖 seed·(outer, seed) 중복·이웃 파일 3 개·fit_report fit_id·**config_id = 선택, epochs_run = outer E**·checkpoint sha256 = fit_report.
- 예측 행 검사: fit_id·cell/seed·scope outer_test·checkpoint sha·학습 subject 누설·outer test 밖 subject·**fit 하나가 그 outer test 를 빠짐없이 덮음**. 전체: 계획의 (outer, seed) 가 모두 있음, code/env/source hash 한 값, subject·task 당 run 하나.
- 행 → `evaluate.ComparisonWindowPrediction`, `seeds_by_subject` = subject 가 속한 outer fold 의 계획 seed → `evaluate.aggregate_comparison_runs` (부록 BA). 반환 runs·예측·seed 지도·fit 기록.
- **구현 선택 (표시함)**: helper 만 두고 하위 명령·산출물 파일은 만들지 않음 (`evaluate` 확장 대 새 하위 명령은 다음 조각에서 정함). A−NG·A−SG 는 만들지 않음 (결정 요청 대기).

## BB.3 시험·돌연변이·잠금

- 새 `tests/v2/test_cli_comparator_outer.py` **40** (outer 2 × seed 3 합성, 짝수 subject 의 WM 을 틀리게 해 b=0.5/1.0, BA 0.75 손계산; run p 0.2·n_seeds 3; 선택 기록 가드 6 + 계획 3; fit 가드; 이웃 파일 3; fit_report 가드 4; 예측 행 가드 7; 누락·중복·hash·run 여럿·격자 불완전; SG 칸; 예측이 A–D 집계로 새지 않음).
- 돌연변이 `.backup/slot_1415b/mut_cmp_outer.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, helper 구간 안 count==1, 원본 복원): 첫 실행 **35/37** — 생존 `no_plan` (선택 기록 없는 outer fold 의 fit — 시험 없음), `cell_pred` (예측 cell 을 구조 대신 "NG" 로 고정 — fixture 가 NG 만). 시험 2 추가 (outer_fold 5 fit, SG 칸) → 재실행 **37/37**. Mac `*.pyc` 0 (돌연변이 뒤·rsync 전).
- 관련 9 파일 Mac 205 passed.
- 재잠금 `2d2250119456` → **`850e7fce7b0a`** (2026-09-25T05:21:28Z), code_hash `45d312b905dd` → `0413a736dca1`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash 불변. gate evidence **rev54** (`comparator_outer_loader_rev54`).

## BB.4 확인하지 못한 것 · 다음

- S outer 쪽 (`s_fit_report.json` 의 seed·`s_selection.json` outer 계획 → `ComparisonWindowPrediction`) 없음. 하위 명령·산출물·A−S CI 없음. 실자료 outer 예측 없음.
- 결정 요청 (부록 BA.4, A−NG·A−SG) 은 여전히 대기.


# 부록 BC — S main outer fit 산출물 → 보조 비교 집계 helper (rev55, 2026-09-25 15:15 예약 슬롯)

남은 작업 2-c "CLI 배선" 의 두 번째 조각 (부록 BB 의 S 쪽). 새 결정 아님 — 규칙은 계획서 §8 run 집계 (부록 BA), S outer 계획은 결정 14 4c-ii (`baselines.s_outer_plan`, 부록 AS). 합성 자료 시험만, 실자료 fit 없음, main pool 미소비. **하위 명령은 만들지 않았다** (CLI 10 개 불변).

## BC.1 사전 확인 (grep, 15:1x)

- `fit-s --inner-fold 9` 산출물: `s_fit_report.json` (schema `d14-s-fit-report-0.1`; `s_fit_id`·candidate·setting_id·role·eval_role·folds·`model_seed` (logistic None)·converged·`fit` 기록 (MLP 는 `epochs_run`)·fit_subjects·`model_sha256`·`window_predictions_sha256`·hash 들) + 옆 `s_window_predictions.jsonl` (행에 seed 자리 없음) + `s_model.npz`.
- `s_selection.json`: `selected_candidate`·`selected_setting_id`·`outer_epochs` (logistic None)·`outer_plan` 행 (`candidate`·`setting_id`·`model_seed`·`epochs_exact`·`outer_fold`·`inner_fold` 9). logistic 은 seed·epoch 없는 한 행, MLP 는 `train.MODEL_SEEDS` × E.

## BC.2 구현 (`mobse/v2/cli.py`)

- 새 `_load_s_outer(report_paths, *, folds, cfg_hash, selections)` + `S_OUTER_NEIGHBOURS = ("s_window_predictions.jsonl", "s_model.npz")` (보고서 옆 고정 이름, U20). 가드 순서·고유 문구는 `_load_comparator_outer` (부록 BB) 틀을 따름.
- 선택 기록 검사: outer fold 집합 = folds.json 전부, 스키마, outer_fold·split/config hash, 외부 기록 거부, 선택 후보 ∈ S 후보, 계획 행 후보/설정·fold (outer, 9) = 선택 기록. **logistic**: seed·epoch 없는 한 행, `outer_epochs` None → 계획 seed `(None,)`. **MLP**: seed None·중복·빈 목록 거부, **seed 집합 = 호출 시점 잠긴 `train.MODEL_SEEDS`**, outer E 1–`MAX_EPOCHS`, 계획 행 E = outer E.
- 보고서 검사: 스키마·`s_fit_id` 중복·role/eval_role outer·외부 분할 기록 (두 키 각각) 거부·split/config hash·inner_fold 9·선택 기록 없는 outer fold·후보/설정 = 그 fold 선택·seed ∈ 계획·(outer, seed) 중복·**보고서 필드로 `s_fit_id` 재계산**·MLP `fit.epochs_run` = outer E·이웃 파일 2 개·`s_model.npz`·예측 파일 sha256 = 보고서.
- 예측 행 검사: 스키마 (`s_window_predictions`)·s_fit_id·후보/설정·scope outer_test·model_sha256·학습 subject 누설·outer test 밖·fit 하나가 그 outer test 전부를 덮음. 전체: 계획 (outer, seed) 빠짐 없음·code/env/source hash 한 값·subject·task 당 run 하나 → `ComparisonWindowPrediction(cell="S")` + subject 별 계획 seed → `aggregate_comparison_runs(cell="S")`.
- **구현 선택 (표시함)**: 행 seed 는 보고서 `model_seed` 에서 가져옴 (행에 seed 자리가 없어서). outer logistic 의 `converged` 는 거부하지 않고 `fits` 에 기록만 (P11 은 inner 선택 규칙 — outer 미수렴 처리는 계획서에 없음). helper 만, 하위 명령·산출물 없음.
- 첫 돌연변이에서 `len(rows) != 1` 조건이 `seeds != [None]` 에 포함돼 (seed 는 행마다 하나) 중복임을 확인 → 그 조건을 지우고 주석으로 이유를 적음 (동작 동치).

## BC.3 시험·돌연변이·잠금

- 새 `tests/v2/test_cli_s_outer.py` **67** (outer 0 = S1 logistic 한 fit, outer 1 = S2 MLP seed 3 fit 의 혼합 합성; 짝수 subject 의 WM 을 틀리게 해 b=0.5/1.0, BA 0.75 손계산; logistic run n_seeds 1·MLP 3; seed 지도 (None,)/(42,43,44); 두 fold 모두 MLP — 정상 경로 4; 선택 기록·계획 가드 23; 보고서 가드 27 (이웃 파일 2·모델 교체 포함); 예측 행 가드 13).
- 돌연변이 `.backup/slot_1515b/mut_s_outer.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, helper 구간 안 count==1, 원본 복원): 첫 실행 **53/54** — 생존 `logi_rows` (위 중복 조건, `mut_s_outer_r1.log`) → 조건 제거·돌연변이 목록 정정 → 재실행 **53/53** (`mut_s_outer_r2.log`). Mac `*.pyc` 0 (돌연변이 뒤·rsync 전).
- 관련 6 파일 Mac 226 passed.
- 재잠금 `850e7fce7b0a` → **`c96a74b297ec`** (2026-09-25T06:23:32Z), code_hash `0413a736dca1` → `e7f27665a89f`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash 불변. gate evidence **rev55** (`s_outer_loader_rev55`).

## BC.4 확인하지 못한 것 · 다음

- 하위 명령·산출물 (새 하위 명령 vs `evaluate` 확장), A−S 의 A–D run 입력 (`evaluate` 산출물 `run_predictions` 를 읽을지), §8 95% 기술적 CI 배선 없음. 실자료 outer 예측 없음.
- 결정 요청 (부록 BA.4, A−NG·A−SG) 은 여전히 대기.


# 부록 BD — 보조 비교 통계 하위 명령 `report-comparison` (rev56, 2026-09-25 16:15 예약 슬롯)

남은 작업 2-c "CLI 배선" 의 세 번째 조각 (부록 BB·BC 의 helper 를 부르는 하위 명령 + A−S 95% 기술적 CI). 새 결정 아님 — 규칙은 계획서 §8 "A−S, interaction, … 는 보조이며 95% 기술적 CI로 표시한다", §6 구조 비교는 보고 대상. 합성 자료 시험만, 실자료 fit 없음, main pool 미소비.

## BD.1 사전 확인 (grep, 16:1x)

- (i) CLI 수 고정 시험: 없음 (`test_every_subcommand_has_a_body` 가 `main` 분기만 확인). (ii) A–D run 입력: `run_report` 가 `evaluation.json`·`run_predictions.jsonl` (`wi06-run-predictions-0.1`) sha256 대조 + `_recompute_subject_scores` 로 b_i 재계산 — 같은 경로를 쓴다. (iii) bootstrap: `run_report` 가 `stats.bootstrap_seed` (9001)·`stats.n_bootstrap` (10,000)·`stats.nominal_pct` (2.5, 97.5) 로 `statistics.bootstrap_indices` 를 한 번 만들고 `paired_bootstrap` 에 공유 — 같은 함수·같은 config 키를 재사용. (iv) 산출물은 새 이름, 덮어쓰기 거부.

## BD.2 구현 (`mobse/v2/cli.py`)

- **구현 선택 (표시함)**: `evaluate`·`report` 확장이 아니라 **새 하위 명령 `report-comparison`** (CLI 10 → **11**). A–D 산출물 계약을 바꾸지 않고, 세 칸 입력을 모두 필수로 받는다 (빠진 칸 → argparse 거부). 인자: `--config --splits --evaluation --predictions --subjects --s-selection ×5 --s-fit-report ×N --ng-selection ×5 --ng-fit-manifest ×15 --sg-selection ×5 --sg-fit-manifest ×15 --output-dir`.
- `run_report` 앞부분 (evaluation config_hash·run_predictions sha256·스키마·b_i 재계산 대조·subjects group/적격/수) 을 **`_read_evaluated`** 로 옮겨 두 명령이 공유 — 검사 순서·문구 불변 (`test_cli_report.py` 새 2 시험을 HEAD 판 `cli.py` 에서도 통과).
- `run_report_comparison`: evaluation `split_hash` = `--splits` 확인 → 선택 기록을 outer fold 로 묶음 (`_read_selections`: fold 중복·outer_fold 없음 거부) → S `_load_s_outer`, NG·SG `_load_comparator_outer` → 칸별 run 마다 A run 존재·**truth = A run**·**group_id = subjects.jsonl** → `evaluate.subject_scores` (complete-case) → subject 집합 = A → A−S = `evaluate.comparison_contrasts` (A run 은 run 행의 prediction/truth 에서) → bootstrap index 한 번 (report 와 같은 인자·같은 subject 순서) → 칸 BA (S·NG·SG)·A−S 95% 기술적 CI (`role: auxiliary`, `primary: false`, `statistics.interpret` 문자열).
- 산출물 `comparison_statistics.json` (schema `d14-comparison-statistics-0.1`, 덮어쓰기 거부): bootstrap 설정·칸 BA·A−S·칸별 subject b_i·outer fold 별 S 선택 후보/설정/E·`not_reported` (A−NG·A−SG = 결정 요청 대기, parameter/비용 = 범위 밖)·입력 sha256 (folds·evaluation·run_predictions·subjects·선택 기록 15·fit 기록).
- 첫 작성에서 넣었던 도달 불가 대조 3 개 (칸 목록 상수, contrast 목록 상수, BA = b_i 평균) 는 같은 값에서 계산돼 돌연변이가 생존할 조건이라 뺐다 (부록 BC 의 중복 조건 교훈).

## BD.3 시험·돌연변이·잠금

- 새 `tests/v2/test_cli_report_comparison.py` **23**: evaluate 시험 합성 release (A–D, 10명, outer 2) 를 evaluate 로 돌리고 같은 folds 로 S (outer 0 S1 logistic / outer 1 S2 MLP seed 3)·NG (전부 맞힘)·SG (짝수 EM 틀림) outer fit 합성. 손계산: BA S 0.75·NG 1.0·SG 0.75, A−S 점추정 0.25 와 95% 구간을 `statistics.py` 없이 독립 재계산 (PCG64 seed 9001) 과 대조; A 가 홀수 EM 을 틀리는 변형에서 A−S 0.0 과 구간 대조; report 의 B 칸 구간 = 여기 S 칸 구간 (같은 b 벡터, 같은 index); bootstrap index 호출 1 회·seed 9001·10,000·정렬 subject (spy). 가드: 덮어쓰기, 여섯 칸 입력 각각 필수, 선택 fold 중복·outer_fold 없음, NG 자리에 SG 기록, split_hash, run_predictions sha, truth ≠ A, group ≠ subjects, A 에 없는 run, subject 집합 ≠ A, complete-case.
- `tests/v2/test_cli_report.py` 11 → **13**: evaluation.json b_i 만 고친 경우·counts 만 고친 경우 (이동한 `_read_evaluated` 의 두 가드가 기존 시험에서 생존 — 원래부터 시험 없음. b_i 가드는 뒤 subject 차이 대조와 같은 "evaluation.json 과 다르다" 문구라 가려졌음).
- 돌연변이 `.backup/slot_1615b/mut_rc.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, 구간 한정 count==1, 원본 복원): 첫 실행 **18/23** (`mut_rc_r1.log`) — 생존 `split` (시험 문구가 S helper 의 split_hash 오류와도 맞음 → 문구를 좁힘), `s_runs` (NG run 을 섞는 돌연변이는 `subject_scores(…, "S")` 가 걸러 동치 → 돌연변이를 S run 한 subject 제거로 교체), `boot_seed` (10명 이산 자료에서 seed+1 구간이 우연히 같음 → spy 시험), `ev_scores`·`ev_count` (위 report 시험 2) → 재실행 **23/23** (`mut_rc_r2.log`). Mac `*.pyc` 0 (돌연변이 뒤·rsync 전).
- 관련 8 파일 Mac 261 passed.
- 재잠금 `c96a74b297ec` → **`78ddd887253f`** (2026-09-25T07:23:32Z), code_hash `e7f27665a89f` → `fbd9fd7feee2`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash 불변. gate evidence **rev56** (`comparison_report_rev56`).

## BD.4 확인하지 못한 것 · 다음

- NG·SG parameter/비용 보고 (계획서 §6 "no-graph FC comparator와 실제 parameter/비용을 함께 보고한다") 없음. 실자료 outer 예측 없음 (main OOF 승인 전).
- 결정 요청 (부록 BA.4, A−NG·A−SG) 은 여전히 대기 — 결정되면 `evaluate.COMPARISON_CONTRASTS`·`comparison_contrasts` 와 이 명령의 `auxiliary_contrasts` 에 더하면 된다.

# 부록 BE — 구조 비교 NG·SG parameter/비용 측정을 자원 벤치마크에 추가 (rev57, 2026-09-25 17:15 예약 슬롯)

새 결정 아님. 계획서 §6 "no-graph FC comparator와 실제 parameter/비용을 함께 보고한다" 와 §9 "효율 측정은 동일 장비/batch/precision에서 FC·PCA 포함 end-to-end latency, 모델 latency, peak memory, parameter 수를 분리한다. 지원되지 않는 FLOPs는 NA다" 를 구조 비교 두 모델에 적용.

## BE.1 사전 확인 (grep)

- "parameter/비용" 의 정의: 계획서에 따로 없고 §9 효율 측정 문장이 가장 가깝다 (parameter 수·학습/추론 시간·peak memory 분리, FLOPs NA). 지침서 WI-09 "비용을 평가한다 … cost measurements", "실측 없는 FLOPs/latency 우위" 중단 조건.
- parameter 수: `models.FusionMLPComparator`·`SingleGraphComparator` 에 `trainable_parameter_count()` 가 이미 있다 — fit 없이 합성 입력으로 셀 수 있다.
- 비용 (시간·메모리): `fitting.train_fold` 가 이미 `timing` (`train_seconds`, `seconds_per_epoch`)·`memory` (`device`, CUDA 이면 `peak_gpu_bytes`) 를 내고 `fit_report.json` 에 쓴다 (NG·SG 도 같은 경로, rev41). 따라서 `fit` 산출물 계약 변경은 필요 없다.
- 기존 자원 벤치마크 `scripts/h197/21_resource_benchmark.py` 는 **A–D 만** 쟀다 (`sorted(CELL_SPEC)`).

## BE.2 변경

- **구현 선택 (표시함)**: 실자료 fit 기록이 아니라 §9 의 "동일 장비/batch/precision" 조건을 지키는 기존 합성 벤치마크에 NG·SG 를 더했다. `BENCH_CELLS = A, B, C, D, NG, SG`; A–D 는 bank `[I, I, I]`, SG 는 graph `I`, NG 는 graph 없음. 칸 기록에 `structure_comparator` 추가, NG 의 `bank_is_frozen` 은 `null` (graph 없음). 출력 schema `resource_benchmark_v1` → `resource_benchmark_v2` (+ `cells`). `mobse/v2` 불변 — 재잠금 없음 (잠금 `78ddd887253f` 유지).
- `report-comparison` 산출물에 parameter/비용을 넣는 일은 하지 않았다 (범위 밖 — 실자료 fit 의 `fit_report.json` timing 집계는 main OOF 뒤).
- 시험 새 `tests/v2/test_resource_benchmark.py` **4** (칸 목록, 여섯 칸 모두 측정, bank 기록, parameter 수 손계산: NG = encoder + Linear(42→32) + Linear(32→2), SG = encoder + graph 층 2 + head, graph 는 buffer). `test_h197_scripts.py` 의 호출부 시그니처 bind 시험이 새 `build_comparator` 호출도 덮는다. 돌연변이 `.backup/slot_1715b/mut_bench.py` (`-B`) **5/5**.

## BE.3 측정 (h197, 합성 자료, 2026-09-25 17:1x KST)

bmcws · RTX 3090 Ti · torch 2.10.0+cu128 · float32 (AMP 미사용) · batch 32 · repeats 5 (첫 회 warm-up 제외, 중앙값). 크기: inner 학습 창 536, outer 학습 창 808. 산출물 `resource_v2.json` sha256 `3b260a9c0250…` (h197 `$HOME/slot/rb_1715b/`, Mac `.backup/slot_1715b/` — 커밋 안 함).

| 칸 | 학습 parameter | inner 1 epoch (s) | outer 1 epoch (s) | inner 추론 전체 (s) | inner peak GPU (MB) |
|---|---|---|---|---|---|
| A | 6,469 | 0.149 | 0.226 | 0.0109 | 97.5 |
| B | 6,021 | 0.136 | 0.207 | 0.0103 | 97.4 |
| C | 6,469 | 0.148 | 0.226 | 0.0109 | 97.4 |
| D | 6,021 | 0.136 | 0.208 | 0.0103 | 97.4 |
| NG | 5,154 | 0.093 | 0.143 | 0.0061 | 94.7 |
| SG | 6,018 | 0.120 | 0.184 | 0.0084 | 94.7 |

- FC·PCA·bank 변환 한 번 (outer 규모 rest 창 404, CPU): 1.43 s (칸과 무관).
- 읽는 법: NG 는 A 보다 parameter 1,315 개 적고 epoch 시간 약 63%. SG 는 B·D 보다 parameter 3 개 적다 — B·D 의 `gate.logits` (3) 만 SG 에 없고 나머지 이름·크기는 같다 (Mac 에서 named_parameters 대조). 이 표는 **합성 자료·단일 장비** 값이라 효율 우위 주장의 근거가 아니다 (WI-09 중단 조건). peak GPU 는 칸 사이에 남아 있는 입력 텐서를 포함한다 (칸마다 `reset_peak_memory_stats` 만 함).
- GPU 0 에 다른 사용자의 sglang (약 19 GB, 측정 시작 시 사용률 0%) — 동시 부하 영향은 재지 않았다.

## BE.4 확인하지 못한 것 · 다음

- 실자료 fit 의 NG·SG `timing`·`memory` 집계 (main OOF 승인 전 없음). `report-comparison` 에 비용 칸을 넣을지는 그때 정한다.
- S 후보 (logistic·MLP) 의 fit 시간 — `mobse/v2/baselines.py` 에 timing 기록이 없다 (grep `timing\|perf_counter` 0건; `cli.py` 의 `"timing"` 은 `run_fit` 두 곳뿐). 넣으려면 `fit-s` 산출물 계약 변경 (별도 조각).
- 결정 요청 (부록 BA.4, A−NG·A−SG) 은 여전히 대기.

# 부록 BF. 남은 작업 6 — pilot 실측 기반 5,000/400 학습 예산 (2026-09-25 18:15 슬롯, gate rev58)

**새 결정 아님.** 계획서 §7 "표는 실행 횟수 계획이고 소요시간 보장이 아니다. pilot에서 peak memory·시간을 측정해 자원 계획을 만든다" 에 맞춰 pilot 창에서 fit 비용을 재고, 결정 15 값으로 예산을 다시 잡았다. 결과 본문은 `reports/resource_budget.md` 9절.

## BF.1 사전 확인 (grep)

- G1 행 (계획서 §10 표): "G1 Measurement lock | 재추출/QC, pilot/main IDs, split hashes, 정밀도·자원 계획 | 고정 rule와 실제 N, pilot 경계 확인". gate `gates[1].checks[7]` "resource plan from pilot measurement" 는 `fail` ("pilot fit 미구현으로 합성 측정으로 대체했다 … §7 요구는 미충족").
- 합성 측정 (rev57, 부록 BE) 은 §7 의 "pilot에서" 를 채우지 못한다 → pilot 기술 분할 실측을 새로 했다.

## BF.2 측정

- 틀 `.backup/slot_1815b/pilot_cost.py`·`run_cost.sh` (커밋 안 함): 시작 시점 HEAD `ee0a4d2` 의 `mobse` 사본 (`git archive`), `python -B`, pilot 기술 분할 outer 0 · inner 0 (학습 104창, 평가 56창), config 0, seed 42, 칸 A·B·C·D·NG·SG 각 1회 순차, 정확히 5,000 update (프로세스 안에서만 `MAX_EPOCHS` 덮기, d12 와 같은 우회). 산출물 h197 `$HOME/slot/pc_1815b/cost_*.json` (Mac `.backup/slot_1815b/` 사본). val 성능은 기록하지 않는다.
- s/epoch 0.034–0.060, 고정비 8.6–18.1 s, peak GPU ≤136.4 MiB, peak RSS 1.48–1.49 GiB. A·C (같은 구조) 차이로 보아 반복 1회의 칸 사이 차이는 해석하지 않는다.

## BF.3 예산 [추정]

순차 1 프로세스 학습 14.1–33.5 h + 고정비 ≤5.2 h (1,038 fit = §7 표 768 + 구조 비교 270). 하한·상한 식과 묶음별 값은 `resource_budget.md` 9절.

## BF.4 판정·확인하지 못한 것

- gate `gates[1].checks[7]` 의 `result` 는 **바꾸지 않았다** (`fail` 유지). 실패 사유 ("pilot fit 미구현") 는 해소됐으나 G1 판정 변경은 선생님 확인 사항으로 남긴다. rev58 는 측정 기록 블록 `resource_plan_pilot_rev58` 만 더한다.
- 미측정: S 후보 fit 시간, main 규모 실자료 epoch 시간, 동시 실행 처리량, 반복 측정에 의한 칸 간 차이.

# 부록 BG. 남은 작업 5 — 결합 설계 수치 안정성 (조건수) 전수 측정 (2026-09-25 19:15 슬롯, gate rev59)

**새 결정 아님.** 부록 Z.7·AA.5 의 미확인 항목 "1,295 run 전체에서 동시 회귀의 수치 안정성(결합 설계 조건수)을 재지 않았다" 를 잰다. 코드·시험·잠금 불변.

## BG.1 범위

- 설계행렬만 다시 만든다: `10_wi02_extract.process_run` 과 같은 순서 (`read_confounds_tsv` → `select_acompcor` → `build_design` → `add_stopband` → `summarize_design`), 경로는 그 스크립트의 `run_paths` 를 importlib 로 불러 쓴다. frame 수는 confounds 행 수 (manifest `n_frames` 와 대조). **BOLD·창·라벨·분할을 읽지 않고 fit 하지 않는다** — 추출 때 이미 한 설계 계산의 재현이라 잠긴 분할 소비가 아니다.
- 대상: v3 manifest 6개의 run 레코드 1,326 (skipped 31 제외 1,295). 틀 `.backup/slot_1915b/design_cond.py`·`summ_dc.py`·`probe_worst.py` (커밋 안 함), h197 HEAD `e8933dc` 사본, `python -B`, 약 19:16–19:26 KST (583 s). 산출물 h197 `$HOME/slot/dc_1915b/` (`design_cond.jsonl` sha256 `e4488380d43d…`, `summary.json` `1888b4a91a97…`; Mac `.backup/slot_1915b/out/` 사본).
- 지표 (run 마다): 특이값 σ; numpy 절단값 τ = σ_max·max(n,p)·ε (`matrix_rank`·`lstsq(rcond=None)` 와 같은 규칙); rank = #(σ > τ); 유효 조건수 κ = σ_max/σ_rank (원 설계, 열 노름 1 로 정규화한 설계 각각); 절단 여유 σ_rank/τ; 잔차 대조 — 고정 seed 난수 Y (n × 100, seed = run_key sha256 앞 8자리) 에 대해 `extract.regress_out` 잔차와 SVD 직교 사영 잔차 `Y − U_r U_rᵀ Y` 의 상대 차이 ‖·‖_F/‖사영 잔차‖_F.

## BG.2 결과

- 측정 1,291 run (ok 1,182 + excluded 109). excluded 4 run 은 설계를 만들 수 없는 기존 data_condition 제외 (aCompCor 메타데이터 — manifest 사유와 같음). **rank 결손 0 run.** manifest 대조 1,289 run (PIOP2 rest excluded 2 run 은 manifest 에 design 기록 없음): `design_rank`·`nuisance_rank`·`residual_dof`·`n_frames` **불일치 0**.
- ok run (분석에 들어가는 run):

| 조합 | ok run | frame | 열 (최소/중앙/최대) | κ 원 설계 중앙 / 최대 | κ 열 정규화 중앙 / 최대 | 잔차 상대 차이 최대 |
|---|---|---|---|---|---|---|
| PIOP1 emomatching | 183 | 135 | 61 / 61 / 69 | 2.7e7 / 4.2e8 | 188 / 639 | 3.2e-8 |
| PIOP1 workingmemory | 176 | 162 | 68 / 68 / 80 | 2.3e7 / 1.0e8 | 303 / 1.3e3 | 4.2e-9 |
| PIOP1 restingstate | 202 | 480 | 371 / 371 / 400 | 3.9e7 / 1.4e8 | 319 / 4.6e6 | 1.2e-8 |
| PIOP2 emomatching | 204 | 135 | 61 / 61 / 68 | 2.3e7 / 1.1e8 | 187 / 458 | 7.5e-9 |
| PIOP2 workingmemory | 214 | 160 | 67 / 67 / 73 | 2.3e7 / 3.1e8 | 285 / 565 | 2.0e-8 |
| PIOP2 restingstate | 203 | 240 | 85 / 85 / 95 | 2.2e7 / 1.2e8 | 375 / 658 | 7.1e-9 |

- ok run 절단 여유 최소: 원 설계 7.0e4, 열 정규화 2.0e6 — rank 판정이 절단값 근처에 있는 ok run 은 없다. 열 정규화 설계에서 lstsq 잔차 차이 최대 5.5e-9. 열 노름 비 최대 1.6e8 — 원 설계 κ 가 큰 것은 주로 열 크기 차이 (motion `*_power2` 등) 때문이고 열 정규화 κ 는 ok run 1,182 중 1,000 초과 18, 10,000 초과 1.
- 열 정규화 κ 최댓값 ok run: PIOP1 rest `ds002785/sub-0030` (392 열, spike 21, residual DOF 88) κ 4.6e6 (다음 값 8.9e3, `sub-0058`). 최소 특이 방향의 큰 계수는 연속 spike 열 (frame 337–341, 부호 교대) 과 고주파 차단대역 DCT 열 (k 468–478) — 11 frame 연속 spike 구간 (334–344) 의 부호 교대 조합이 0.75 s TR rest 의 넓은 차단대역 (0.2 Hz 초과) 기저와 거의 겹친다. 이 run 의 잔차 차이도 기준 안 (위 표 최댓값 이내).
- excluded run 에서만 나온 값: PIOP1 rest `sub-0200` (465 열, spike 94, DOF 15) κ 원 7.5e12 · 정규화 2.1e11, 절단 여유 1.25 (원) / 45.9 (정규화), 잔차 차이 2.7e-4; `sub-0013` (443 열, spike 72, DOF 37) κ 4.4e12 · 2.0e11, 여유 47.2 (정규화), 잔차 차이 1.3e-4. 둘 다 manifest 에서 `mean_fd>0.2` 등으로 이미 제외 (판정 불변, rank 는 manifest 와 같음).

## BG.3 읽는 법

- 분석에 쓰는 1,182 run 에서 동시 회귀는 float64 에서 수치적으로 안정하다: rank 판정 여유 ≥7.0e4, lstsq 잔차가 직교 사영 잔차와 상대 3.2e-8 이내로 같다. 조건수 기준으로 설계 변경이나 추가 규칙이 필요한 근거는 없다.
- 불안정에 가까운 설계 (κ ~1e12, 절단 여유 ~1) 는 spike 가 매우 많은 PIOP1 rest excluded 2 run 뿐이다. 현재 제외 규칙 (mean FD·spike 비율·DOF) 이 먼저 걸러낸다.
- [해석 한계] 잔차 대조는 난수 Y 기준이다 — 실제 ROI 시계열에서의 오차 크기는 재지 않았다 (BOLD 를 읽지 않음). κ 가 큰 방향이 신호 성분과 겹치는지는 모른다.

## BG.4 확인하지 못한 것

- 재추출 창의 통과대역 밖 잔여 전력 (AA.5 두 번째 항목) — BOLD 또는 창 파일을 읽어야 하므로 이번 범위에서 뺐다.
- 추출에 실제로 쓰인 잔차와의 대조 (창 `.npy` 재계산) — 하지 않았다.


# 부록 BH. 남은 작업 5-b — 재추출 창의 통과대역 밖 잔여 전력 (pilot 창, 2026-09-25 21:15 슬롯, gate rev60)

**새 결정 아님.** 부록 AA.5 의 미확인 항목 "재추출 창의 신호 수준 점검(통과대역 밖 잔여 전력)은 하지 않았다 — 합성 시험(Z.3)에만 근거" 를 잰다. 코드·시험·잠금 불변.

## BH.1 범위와 근거

- **pilot 31명 창만** 쓴다. 근거: 계획서 §3.2 "filter 종류·차수·padding·regression 순서는 pilot 기술 검증에서 기록하고 main 전에 동결한다" — 필터 점검은 pilot 기술 검증의 몫이다. main pool subject 의 창·confounds 는 읽지 않았다 (pilot 명단 밖 ok run 468 은 건너뛰고 수만 셈). 라벨·fold·fit 없음. pilot 명단은 `derivatives_v3/splits_piop1_p7/folds.json` 의 `pilot.subjects` (31).
- 대상: PIOP1 (ds002785) v3 manifest 3개의 ok run 중 pilot 93 run (rest·emo·wm 각 31), 창 **372** (run 당 4). 창 sha256 은 manifest 와 **372/372 일치**, 모양 (30, 100) 전부.
- 창에서 볼 수 있는 것: 창은 2 s 격자 30 frame (60 s) 이라 주파수 bin 은 k/60 Hz, k = 0–15 (Nyquist 0.25 Hz). 차단대역 **상단 (0.2, 0.25] Hz = k 13–15** 만 관측 가능하다. 하단 (< 0.008 Hz) 은 창 길이로 분해되지 않는다 (DC 만) — 이번 측정 밖. PIOP1 rest 원 TR 0.75 s 의 0.25–0.67 Hz 차단대역은 2 s 격자 재표집 뒤라 창에서 직접 볼 수 없다.
- 지표: ROI 마다 창 평균을 뺀 뒤 비-DC 전력 중 k 13–15 의 비율 (직사각, Hann 창 두 가지). 창마다 ROI 100개의 중앙값·p95·최댓값.
- 기준 (같은 run 의 설계·`10_wi02_extract.process_run` 과 같은 함수 순서 `regress_out` → `zscore_rois` → `resample_to_grid` → `cut_windows`, 고정 seed 난수 Y n × 100 — seed = run_key sha256 앞 8자리):
  - **ref_full**: nuisance + 차단대역 DCT 결합 설계로 회귀 — 필터가 적용됐을 때의 기대값.
  - **ref_nuis**: nuisance 만으로 회귀 — 필터가 빠졌을 때 (E21 유형) 의 기대값.
- 틀 `.backup/slot_2115b/stopband_power.py` (커밋 안 함), h197 HEAD `bbb4e67` 사본, `python -B`, 27 s (약 21:17 KST). 산출물 h197 `$HOME/slot/sp_2115b/` (`stopband_power.jsonl` sha256 `e78828ff728c…`, `summary.json` `9833a505cb99…`; Mac `.backup/slot_2115b/out/` 사본).

## BH.2 결과

창별 ROI 중앙값 비율 (0.2–0.25 Hz / 비-DC 전력) — 창 124개의 중앙값 [최소, 최대], 그리고 ROI 단위 최댓값:

| task (원 TR) | 창 | 실제 창 직사각 | ref_full 직사각 | ref_nuis 직사각 | 실제 창 Hann | ref_full Hann | ref_nuis Hann |
|---|---|---|---|---|---|---|---|
| restingstate (0.75 s) | 124 | 0.0038 [0.0009, 0.0273] · ROI 최대 0.124 | 0.0057 [0.0027, 0.0112] · 0.143 | 0.185 [0.146, 0.230] · 0.702 | 0.0014 [0.0004, 0.0063] | 0.0032 [0.0022, 0.0053] | 0.174 [0.132, 0.241] |
| emomatching (2.0 s) | 124 | 0.0041 [0.0012, 0.0167] · 0.124 | 0.0063 [0.0032, 0.0103] · 0.180 | 0.191 [0.138, 0.240] · 0.734 | 0.0027 [0.0008, 0.0072] | 0.0037 [0.0021, 0.0061] | 0.174 [0.134, 0.224] |
| workingmemory (2.0 s) | 124 | 0.0038 [0.0015, 0.0169] · 0.138 | 0.0059 [0.0037, 0.0107] · 0.183 | 0.187 [0.145, 0.226] · 0.695 | 0.0015 [0.0007, 0.0048] | 0.0030 [0.0015, 0.0045] | 0.177 [0.136, 0.228] |

- 372 창 모두 실제 창의 중앙 비율 (최대 0.027) 이 ref_nuis 의 최소 (0.138) 보다 작다 — 두 분포가 겹치지 않는다. 실제 창이 ref_full 보다 큰 창은 rest 42 · emo 28 · wm 22 / 124 (직사각).
- ROI 단위 최댓값 (0.12–0.14) 은 ref_full 의 최댓값 (0.14–0.18) 과 같은 수준이다 — 30 frame 창의 누설·표본 변동 범위.

## BH.3 읽는 법

- 실제 재추출 창의 0.2–0.25 Hz 전력은 필터를 적용한 기대값 (ref_full) 수준이고, 필터가 빠졌을 때의 기대값 (ref_nuis, 약 0.19) 보다 약 50배 작다. pilot 창에서 차단대역 회귀는 **실제 파일에 적용되어 있다** (E21 유형 "기록만 하고 적용 안 함" 아님).
- 실제 창이 ref_full 보다 조금 작은 것은 BOLD 가 통과대역 안에서 저주파 쪽에 전력이 몰려 비율의 분모가 커지기 때문으로 보인다 [추정 — 통과대역 안 스펙트럼 모양은 따로 재지 않음].
- 판정·규칙·설계 변경 근거 없음.

## BH.4 확인하지 못한 것

- main pool·PIOP2 창 (범위에서 뺌 — 계획서 §3.2 는 pilot 기술 검증에 둠).
- 차단대역 하단 (< 0.008 Hz) 과 PIOP1 rest 원 TR 의 0.25–0.67 Hz 대역 — 창 격자에서 관측 불가. 보려면 BOLD 를 원 TR 로 다시 읽어 잔차를 재계산해야 한다 (추출에 실제 쓰인 잔차와의 대조와 같은 작업, 부록 BG.4).
- 반복·다른 seed 의 기준 변동.


# 부록 BI. 남은 작업 6 잔여 — pilot fit 비용 반복 측정과 동시 실행 처리량 (2026-09-25 22:15 슬롯, gate rev61)

**새 결정 아님.** 부록 BF (rev58) 의 미측정 항목 중 "칸 사이 시간 차이 (반복 1회)" 와 "동시 실행 처리량" 을 잰다. 계획서 §7 "pilot에서 peak memory·시간을 측정해 자원 계획을 만든다" 의 범위 안. 코드·시험·잠금 불변 (78ddd887). G1 check 판정은 바꾸지 않는다 (결정 요청 대기).

## BI.1 조건

- 부록 BF 와 같은 틀 `pilot_cost.py` (사본 `.backup/slot_2215c/`), 같은 조건: pilot 기술 분할 `derivatives_v2/pilot_tech/splits/folds.json` outer 0 · inner 0 (학습 104창 = 4 update/epoch, 평가 56창), config 0, seed 42, 정확히 1,250 epoch = 5,000 update (프로세스 안에서만 `MAX_EPOCHS` 덮기), 해시 대조 켬. main pool 미사용. val 성능 기록 안 함.
- 코드는 시작 시점 HEAD `1e399ec` 사본 (`git archive`), `python -B`. h197 bmcws RTX 3090 Ti (GPU 1장), CPU 12, GPU 0 에 다른 사용자 sglang 19,222 MiB 상주 (사용률 0%, 전후 같음).
- (1) 반복: 2 라운드 순차 — 1 라운드 A B C D NG SG, 2 라운드 역순 (시간 추세와 칸 순서를 떼기 위해). 13:16:08Z–13:30:08Z. rev58 1회와 합쳐 칸당 3회.
- (2) 동시 실행: 칸 A 같은 인자로 k = 2, 4 프로세스를 동시에 띄움. 13:30:08Z–13:34:55Z. 틀 `run_rep.sh`, 요약 `summ_rep.py`.

## BI.2 결과 — 반복 (s/epoch, 1,250 epoch)

| 칸 | rev58 | 1 라운드 | 2 라운드 | 최대/최소 |
|---|---:|---:|---:|---:|
| A | 0.0600 | 0.0604 | 0.0458 | 1.32 |
| B | 0.0542 | 0.0541 | 0.0538 | 1.01 |
| C | 0.0339 | 0.0583 | 0.0608 | 1.79 |
| D | 0.0539 | 0.0442 | 0.0201 | 2.68 |
| NG | 0.0343 | 0.0344 | 0.0341 | 1.01 |
| SG | 0.0481 | 0.0470 | 0.0480 | 1.02 |

- 같은 인자·같은 코드의 반복에서 A·C·D 는 0.020–0.061 로 흔들리고 B·NG·SG 는 2% 안이다. rev58 의 "A 0.060 대 C 0.034" 는 C 가 이번 두 번 0.058·0.061 로 A 와 같은 범위에 들어 **칸 차이가 아니었다** (반복 사이 변동).
- end-to-end 34.4–89.4 s, 고정비 (end-to-end − 학습) 5.5–14.8 s (rev58 최대 18.1 s 보다 작음). peak GPU 133.4–136.4 MiB, peak RSS 1.47–1.49 GiB — rev58 과 같은 수준이다.
- 변동의 원인 (GPU 클럭·다른 사용자 부하·CPU 스케줄 등) 은 재지 않았다.

## BI.3 결과 — 동시 실행 (칸 A)

| k | 벽시계 (s) | 프로세스별 s/epoch | 프로세스별 fold 변환 + 창 부호화 (s) | fits/h |
|---|---:|---|---|---:|
| 1 (순차, A 3회 end-to-end 중앙값 86.3 s) | — | 0.046–0.060 | 5.7–9.5 | 41.7 |
| 2 | 131.9 | 0.061 · 0.058 | 52.3 · 51.2 | 54.6 |
| 4 | 154.7 | 0.040 · 0.037 · 0.058 · 0.043 | 78.1 · 76.3 · 77.9 · 78.9 | 93.1 |

- 학습 구간의 epoch 시간은 동시 실행에서도 순차 반복 범위 (0.02–0.06 s) 안이다 — pilot 규모 (104창, batch 32) 에서 GPU 는 4 프로세스까지 병목이 아니다.
- 대신 fold 변환 + 창 부호화 (CPU·파일 I/O, 해시 대조 포함) 가 k=2 에서 약 5–9 배, k=4 에서 약 8–14 배로 늘었다. 처리량 이득은 k=2 1.31 배, k=4 2.23 배 (순차 41.7 fits/h 기준).
- 동시 실행 중간 (시작 30 s 뒤) GPU 메모리가 19,222 MiB 그대로였던 것은 그 시점이 모든 프로세스의 CPU 단계였기 때문으로 보인다 [추정 — 위 단계별 시간과 맞음, 따로 확인 안 함].

## BI.4 예산에 주는 영향 [추정]

- rev58 상한은 update 당 pilot 최대 0.0600/4 s 를 썼다. 이번 최대 0.0608 (C 2 라운드) 로 바꾸면 순차 학습 상한 33.5 → **약 34.0 h** (1.3% 증가). 하한 (rev57 합성 main 규모 시간) 은 바뀌지 않는다. 고정비 상한 5.2 h 도 그대로 (이번 최대 14.8 s < 18.1 s).
- 동시 실행: pilot 규모에서는 4 프로세스로 처리량이 약 2.2 배다. main 규모 (inner 536창, 17 update/epoch) 는 학습 비중이 커서 이득이 다를 수 있다 — main 규모 실자료는 승인 전 금지라 재지 않았다. 따라서 예산 표는 순차 기준 약 14–39 h (학습 14.1–34.0 h + 고정비 ≤5.2 h) 를 유지하고 동시 실행은 "pilot 규모 k=4 에서 2.2 배" 로만 적는다.

## BI.5 확인하지 못한 것

- 반복 사이 s/epoch 변동의 원인, 3회보다 많은 반복.
- main 규모 동시 실행 처리량, k=3·k>4, CPU 단계를 캐시로 나누는 방식 (fold 변환 재사용 — 구현 변경이라 범위 밖).
- S 후보 fit 시간 (`fit-s` timing 기록 없음 — 남은 작업 2-c 선택 항목).
- 산출물: h197 `$HOME/slot/pc_2215c/` (Mac `.backup/slot_2215c/out/` 사본, 커밋 안 함), 요약 `.backup/slot_2215c/summary.json` (sha256 `33dc8a73d297…`).


# 부록 BJ. 남은 작업 5-c — 추출에 실제 쓰인 잔차 대조와 창 격자에서 안 보이는 차단대역 (pilot, 2026-09-25 23:15 슬롯, gate rev62)

**새 결정 아님.** 부록 BG.4 "추출에 실제 쓰인 잔차와의 대조" 와 부록 BH.4 "차단대역 하단 (< 0.008 Hz) 과 PIOP1 rest 원 TR 의 0.25–0.67 Hz 대역" 을 잰다. 범위는 계획서 §3.2 "filter 종류·차수·padding·regression 순서는 pilot 기술 검증에서 기록하고 main 전에 동결한다" 에 따라 **pilot 31명만** (`derivatives_v3/splits_piop1_p7/folds.json` `pilot.subjects`). main pool ok run 468 은 건너뛰고 수만 셈 (BOLD·창·confounds 안 읽음). 라벨·fold·fit 없음. 코드·시험·잠금 불변 (78ddd887).

## BJ.1 방법

- 틀 `.backup/slot_2315c/resid_check.py` (h197 HEAD `bf9f6d2` 사본, `python -B`, 14:18:11Z–약 14:22:17Z, 246 s). run 마다 `scripts/h197/10_wi02_extract.py` (importlib) 의 `run_paths`·`load_atlas_on_grid`·`roi_timeseries` 와 `mobse.v2.extract` 의 `build_design`·`add_stopband`·`regress_out`·`zscore_rois`, `mobse.v2.preprocess` 의 `original_times`·`resample_to_grid`·`cut_windows` 를 `process_run` 과 같은 순서로 불러 BOLD 를 원 TR 로 다시 읽는다 (atlas 는 v3 manifest header 경로).
- (i) 재계산 창을 추출과 같이 float32 로 바꿔 저장된 창 `.npy` 와 바이트 비교 + 최대 절대 차이. 저장 파일 sha256 = manifest 도 함께 대조.
- (ii) 원 TR 시계열의 DCT-II (orthonormal) 계수 전력 — k ≥ 1 전력 중 차단대역 하단 (f < 0.008 Hz) · 상단 (f > 0.2 Hz) 비율, ROI 마다. 추출이 쓰는 차단대역 기저도 같은 DCT-II 성분 (`dct_stopband_basis`) 이다. 세 가지를 나란히: `series` (회귀 전 ROI 평균), `resid` (결합 설계 = nuisance + 차단대역, 추출과 같음), `resid_nuis` (nuisance 만 — 필터 누락 시 기대값).

## BJ.2 결과

- pilot ok run **93** (task 별 31), 창 **372**. frame 수·창 수 manifest 와 93/93 일치. 저장 창 sha256 = manifest **372/372**.
- (i) 재계산 창 = 저장 창 **바이트 동일 372/372**, 최대 절대 차이 **0.0** (세 task 모두).
- (ii) 차단대역 성분 수 (하단, 상단): rest (TR 0.75 s, 480 frame) 5, 335 · emo (TR 2 s, 135) 4, 26 · wm (TR 2 s, 162) 5, 32. run 별 ROI 중앙 비율의 중앙 [최소, 최대]; ROI 최댓값:

| task | 대역 | series | resid (결합) | resid_nuis (nuisance 만) |
|---|---|---|---|---|
| rest | 하단 | 0.144 [0.060, 0.579]; 0.869 | 8.4e-19 [1.5e-20, 5.6e-18]; 7.0e-17 | 0.019 [0.006, 0.049]; 0.243 |
| rest | 상단 | 0.108 [0.039, 0.196]; 0.694 | 1.0e-17 [8.7e-19, 6.0e-17]; 7.5e-16 | 0.220 [0.153, 0.367]; 0.707 |
| emo | 하단 | 0.154 [0.064, 0.345]; 0.889 | 2.4e-19 [2.6e-20, 1.8e-17]; 2.2e-16 | 0.014 [0.003, 0.036]; 0.202 |
| emo | 상단 | 0.024 [0.013, 0.081]; 0.469 | 3.5e-18 [5.7e-19, 3.0e-16]; 3.1e-15 | 0.077 [0.058, 0.108]; 0.375 |
| wm | 하단 | 0.177 [0.051, 0.318]; 0.925 | 1.3e-19 [4.7e-21, 1.2e-18]; 1.4e-17 | 0.017 [0.005, 0.064]; 0.230 |
| wm | 상단 | 0.029 [0.015, 0.086]; 0.292 | 2.1e-18 [1.5e-19, 1.9e-17]; 9.4e-17 | 0.075 [0.058, 0.128]; 0.380 |

- 시간: run 당 중앙 rest 4.9 s · emo 1.42 s · wm 1.64 s (대부분 ROI 평균).

## BJ.3 읽는 법

- (i) pilot 창 파일은 지금 코드·지금 fMRIPrep 입력에서 **바이트 그대로 재현된다** — 창이 결합 설계 (차단대역 포함) 잔차에서 나왔다는 직접 확인. 부록 BH 의 간접 판독 (0.2–0.25 Hz 비율) 과 같은 방향.
- (ii) 결합 설계 잔차의 차단대역 DCT 전력은 하단·상단 모두 **float64 반올림 수준 (≤ 3.1e-15)** — 최소제곱 잔차가 설계 열에 직교하는 성질 그대로이고, 창 격자에서 안 보이던 하단과 rest 0.25–0.67 Hz 도 원 TR 에서 제거되어 있다. nuisance 만 회귀하면 같은 대역에 0.3%–37% (ROI 중앙) 가 남는다.
- [한계] (i) 은 추출과 **같은 코드**로 재계산한 재현성 확인이지 독립 구현 대조가 아니다. (ii) 는 DCT-II 기준 (추출 기저와 같은 기준) — 창 단위 Fourier 누설은 부록 BH 가 다룬다. 규칙·설계 변경 근거 없음.

## BJ.4 확인하지 못한 것

- main pool·PIOP2 run (범위 밖 — §3.2 는 pilot 기술 검증).
- 독립 구현 (다른 라이브러리의 필터·회귀) 과의 대조.
- 산출물: h197 `$HOME/slot/rc_2315c/resid_check.jsonl` (sha256 `e0310fc59e06…`), 요약 `.backup/slot_2315c/out/summary.json` (`6497f1791bd0…`), 로그 `rc_full.log` — Mac `.backup/slot_2315c/out/` 사본, 커밋 안 함.

# 부록 BK. 결정 20 — main OOF 착수 승인 전 G1 fail 나머지 확인과 다른 gate 목록 (2026-09-26 09:15 슬롯, gate rev63)

**읽기·보고만.** 선생님 결정 20 (09-26 02:2x KST 기록) 원문: "판단 전에 확인할 것: rev59 기준 G1에 fail이 4건 있습니다. 위 2번 외의 3건이 무엇인지는 이번에 확인하지 못했습니다. 지금 이 세션에서 선생님 컴퓨터에 연결되지 않아 gate evidence를 직접 열 수 없었습니다. 승인 전에 그 3건을 확인해 보고하도록 할 것". **판정 변경 없음**, 해소 작업 없음, main OOF 착수 승인 아님. 코드·시험·잠금 불변 (78ddd887).

## BK.1 방법

- 현행 gate evidence (rev62, Mac HEAD `a95d27d`, 작업트리 깨끗) 의 `gates[*].checks[*]` 를 파이썬으로 세고, `result != "pass"` 인 check 의 `check`·`result`·`note` (·`observed`) 원문을 읽었다 (09-26 09:15 KST).
- 근거 grep: 계획서 `docs/experiments/mobse_redesign_protocol_2026-09-17.md` (§4-1 개정 P4, §3.1 개정 P5, §8, §10), 작업 지침서 `docs/experiments/mobse_redesign_work_instructions_2026-09-17.md` (WI-03, WI-06, WI-07), 이 보고서 부록 F, gate evidence 의 다른 블록.

## BK.2 G1 check 수

rev62 `gates[1]` (G1 Measurement lock, `status: in_progress`) check **8건: pass 4 · fail 4** — 대화 세션이 옮긴 "rev59 기준 4건" 과 같다 (rev59–rev62 는 판정 변경 없음).

| # | check | result | note / observed (원문 요약 아님 — 핵심 구절 인용) | 무엇에 막혀 있나 | 계획서 근거 | 결정 없이 가역적으로 해소? | main OOF 전에 풀려야? |
|---|---|---|---|---|---|---|---|
| 0 | group_id constructible from local metadata | fail | "participants.tsv(piop1 13열/216행, piop2 12열/226행, id1000 31열/928행)에 가족·쌍둥이·중복 식별 열 없음" | **자료** (관계 metadata 부재, U10) | §4-1 [개정 P4] "`group_id`는 1 subject = 1 group 으로 퇴화시키고, 그 사실과 다음 미검증 범위를 결과에 함께 적는다 … 관계 metadata 를 공식 경로로 확보하면 새 탐색 버전으로 다시 분할한다" | 아니오 — 자료가 없으면 fail 은 관측 사실. 코드 쪽 대응 (P4) 은 이미 구현 (`cohort.py` `group_id = canonical_subject`, gate `wi03_cohort.group_id_policy`) | 계획서상 **아님** — P4 가 퇴화를 명시 항목으로 두고 진행하도록 정함. 판정을 `pass`/다른 값으로 바꿀지는 선생님 판단 |
| 1 | PIOP1/PIOP2 subject ID namespace | fail | "두 cohort 가 같은 sub-0001… 네임스페이스를 쓴다. 문자적 교집합 216, demographic 전체 일치 0/216 -> canonical_subject 에 dataset prefix 필수" | 관측 사실 (대응은 **코드로 완료**) | §3.1 [개정 P5] "`canonical_subject`는 dataset prefix 를 반드시 포함한다 … `validate_canonical_subject()` 가 이 규칙을 실행 시점에 강제한다" | 대응은 이미 됨 (`manifests.validate_canonical_subject`, cohort 가 prefix 없는 subject 거부 — `wi03_cohort.rejects_subject_without_dataset_prefix: true`). check 는 "문제가 있었다" 를 기록한 것이라 남은 작업은 판정 표기뿐 | 계획서상 **아님** (P5 로 처리). PIOP1/PIOP2 동일인 여부 판정 불가는 P4 (b) 의 제한으로 남음. 판정 변경은 선생님 판단 |
| 6 | precision for delta=0.02 | fail | observed `p_lower_gt_0_at_delta_0.02_N126` [0.048, 0.191], `delta80_N126` [0.041, 0.125]; "계획서 §8 의 'inconclusive 가능성을 명시한다'에 해당. 실행 gate 가 아니므로 계획대로 진행하되 불확실 결과를 보고할 준비를 하고 시작한다. δ·N 을 바꾸지 않는다" | **설계** (N 126 에서 δ=0.02 정밀도 부족) | §8 "목표δ를 검출할 정밀도가 부족하면 inconclusive 가능성을 명시한다. main OOF 후 δ나 분석 N을 유리하게 바꾸지 않는다"; WI-03 "단지 작은 N이면 임의 증원 대신 제한을 보고한다" | 아니오 — 해소하려면 δ·N 변경이 필요하고 계획서가 막음. fail 은 명시 항목 | 계획서상 **아님** — note 자체가 "실행 gate 가 아니므로 계획대로 진행" |
| 7 | resource plan from pilot measurement | fail | "pilot fit 미구현으로 합성 측정으로 대체했다 … §7 요구는 미충족" | 사유는 rev58·rev61 로 해소 | §7 "pilot에서 peak memory·시간을 측정해 자원 계획을 만든다" | **결정 19 로 `pass` 확정** (다음 단계에서 반영) | — |

- 요약: 결정 19 대상 (#7) 외 3건 중 **#0·#1 은 개정 P4·P5 로 계획서가 처리 방식을 정한 관측 기록**, **#6 은 계획서 §8 이 "명시하고 진행" 으로 정한 정밀도 한계**다. 셋 모두 코드·측정으로 더 할 일이 없고, 판정 표기 (`fail` 유지 / 다른 값) 는 선생님 판단 사항이다.
- G1 gate 수준 기록도 낡아 있다 (판정 아님, 정보): `status: in_progress`, `unresolved` 에 "band-pass 통과대역 상한 미결정" (결정 9 로 0.2 Hz, rev27–rev28 반영), "개정 P8 학습 예산 — 결정됐으나 구현 전" (rev29·rev44 반영), "pilot fit 미실행 — §7 의 peak memory·시간 실측 없음" (rev58·rev61 로 측정) 이 남아 있고, `status_note` 도 같은 시점 서술이다. 이 목록을 고칠지는 gate 표기이므로 이번에 건드리지 않았다.

## BK.3 다른 gate (판단용 참고, 해소 작업 아님)

| gate | status | check (pass/fail/기타) | pass 아닌 항목 · 기록 |
|---|---|---|---|
| G0 Provenance | conditionally_cleared | 10 (7/2/1) | [2] existing extraction TR correctness **fail** — "모든 run 에 0.75 적용 … 기존 파생물 주분석 재사용 불가 확정" (옛 파생물에 대한 관측; 재추출은 run 별 native TR); [7] BOLD present for the primary targets **fail**, observed 0 — "Wave 2 대상. Wave 1 은 메타데이터만 받았다" (기록 시점 값; 이후 Wave 2 받고 재추출함 — gate `wave2_fetch.status` 는 아직 "running"); [8] dummy volumes removed before archiving **undetermined** — U3 (부록 F.1·gate `u3_discarded_volumes.status: resolved` 에서 해소됐으나 check 는 그대로). `unresolved` U3·U6(targets, Wave 2)·U10, `status_note` "남은 것은 재추출 입력(BOLD)뿐" |
| G2 Implementation lock | planned | **0** | `unresolved` "blocked by G0". **`locks/implementation_lock.json` 없음** (release `locks/` 에는 `measurement_lock.json`·`superseded/` 만; 저장소에서 이 파일을 만드는 코드 grep 0건 — 지침서에만 등장) |
| G3 Internal release | planned | 1 (1/0/0) | [0] section 7 fit budget arithmetic pass. `unresolved` "blocked by G0" |
| G4 External release | planned | 1 (1/0/0) | [0] PIOP2 paired emomatching+workingmemory cohort pass. `unresolved` U17 (실제 overlap 은 공식 문서로만 판정), "blocked by G0/G1" |
| G5 Interpretation | planned | 0 | `unresolved` "blocked by G0" |

## BK.4 main OOF 착수와 관련해 새로 드러난 것 (판단 재료)

- 작업 지침서 WI-06 (G2) 완료 기준 "T01–T16 및 pilot end-to-end 통과", 출력 "`locks/implementation_lock.json`", 그리고 "**이 gate 전에는 main 학습을 시작하지 않는다**". WI-07 입력 "**G1/G2 잠금 artifact**". 계획서 §10 G2 행 "acceptance tests, config/code/environment hashes | leakage·연산·endpoint 검증 통과".
- 현재 gate evidence 에서 G2 는 check 0건·`planned` 이고 구현 잠금 파일이 없다. 측정 잠금 (`measurement_lock.json`, 78ddd887) 이 code_hash·config_hash 를 기록하지만, 그것이 G2 의 구현 잠금을 대신하는지는 **계획서·지침서에 문장이 없다** — 이 슬롯은 판단하지 않았다.
- 따라서 지침서 문장대로라면 main OOF 전에 **G2 (구현 잠금) 를 어떻게 다룰지** 가 G1 fail 3건보다 앞선 선결 사항일 수 있다. 어느 쪽으로 할지 (구현 잠금 산출물을 만들고 G2 check 를 채움 / 측정 잠금으로 갈음한다고 기록 / 다른 방식) 는 선생님 결정 사항으로 올린다.
- G0 는 `conditionally_cleared` 이고 G2·G3·G5 가 "blocked by G0" 로 적혀 있다. G0 의 pass 아닌 3건은 모두 기록 시점 이후 사정이 바뀐 것 (옛 파생물 관측·Wave 2 전 관측·부록 F 에서 해소된 U3) 이지만 gate 판정은 갱신되지 않았다.

## BK.5 확인하지 못한 것

- T01–T16 acceptance 시험이 `tests/v2` 의 어느 시험과 대응하는지 (대응표 없음 — 이번에 만들지 않음).
- G0·G1 gate 수준 기록 (`status`·`unresolved`·`status_note`) 이 어느 revision 부터 낡았는지.
- 산출물: 이 부록과 gate rev63 (이 부록 sha 만 반영, 판정 변경 없음). 조사 명령은 `.backup/slot_0915b/` 에 없음 (대화형 python 한 줄) — 수치는 gate evidence 에서 다시 셀 수 있다.

# 부록 BL. 결정 19 — G1 check "resource plan from pilot measurement" 판정 `fail` → `pass` (2026-09-26 10:14 슬롯, gate rev64)

**판정 한 필드만 바꾼다.** 선생님 결정 19 (09-26 02:2x KST 기록) — 결정 요청 (09-25 18:15 슬롯) 에 대한 대화 권고 문장 "권고: (가). 계획서 §7 문장("pilot에서 peak memory·시간을 측정해 자원 계획을 만든다")은 채웠습니다. S 후보는 입력 차원이 작은 logistic과 32-hidden MLP라서, 예산을 좌우하는 A–D·NG·SG fit(1,038개)에 비하면 비중이 작습니다. 다만 이것은 추정이고 실측은 아닙니다." 를 회신 — 선택지 (가) "`pass` 로 바꾸고, note 에 실측 내용과 한계(S 후보 시간 미측정, 반복 변동 최대 2.7배)를 적습니다" 채택. main OOF 착수 승인 아님. 코드·시험·잠금 불변 (78ddd887).

## BL.1 바뀐 필드

- `gates[1].checks[7]` (이름 "resource plan from pilot measurement" 로 확인, 인덱스 7): `result` `fail` → **`pass`**, `note` 교체 (아래). 이전 값은 gate 블록 `decision19_g1_resource_plan_rev64.previous` 에 원문 그대로 보존.
- 그 밖의 check 판정·gate `status` 는 불변 (갱신 틀이 assert 로 확인). G1 은 fail 3건 ([0] group_id · [1] 네임스페이스 · [6] δ=0.02 정밀도) 이 남아 `status: in_progress` 그대로. G1 `unresolved`·`status_note` 의 낡은 항목 (부록 BK.2) 도 결정 19 범위 밖이라 그대로.

## BL.2 새 note 의 근거 (그 자리에서 gate 블록을 다시 읽어 옮김)

- rev58 (부록 BF, `resource_budget.md` 9절): pilot 기술 분할 outer 0·inner 0, 칸 A·B·C·D·NG·SG 각 5,000 update 실측 — s/epoch 0.0339–0.0600, peak GPU ≤136.4 MiB, peak RSS ≤1.49 GiB. 예산 순차 학습 14.1–33.5 h + 고정비 ≤5.2 h (1,038 fit).
- rev61 (부록 BI, 9.1절): 칸당 3회 반복 — 같은 인자에서 s/epoch 최대 2.7 배 변동 (A·C·D), 칸 A 동시 실행 k=4 처리량 2.23 배, 순차 학습 상한 34.0 h.
- 한계 (note 에 그대로 적음): S 후보 fit 시간 미측정 (비중이 작다는 것은 추정), 반복 변동 원인 미확인, main 규모 실자료 시간·동시 실행 미측정 (main OOF 승인 전 금지).

## BL.3 확인하지 못한 것

- S 후보 fit 시간 (`fit-s` timing 기록 없음 — 선택 항목 그대로).
- 이 판정 변경이 G1 gate 전체 판정에 주는 영향은 없음 (다른 fail 3건 잔존) — G1 을 어떻게 닫을지는 결정 범위 밖.


# 부록 BM — 결정 18: 구조 비교 A−NG·A−SG 를 A−S 와 같은 보조 contrast 로 (rev65, 2026-09-26 11:14 예약 슬롯)

선생님 결정 원문 (2026-09-26 02:2x KST 기록, 결정 요청 09-25 13:15 슬롯의 선택지): **"(가) A−NG·A−SG를 A−S와 같은 보조 contrast로 추가합니다. 같은 subject끼리 짝지은 bootstrap(seed 9001, 10,000회)과 95% 기술적 CI를 쓰고, primary가 아니라고 표시합니다."**
정하지 않은 것 (넓히지 않음): primary endpoint 변경, 다중비교 보정 (A−S 와 같이 없음), NG−SG 등 다른 contrast, 해석 문구 규칙, 실자료 실행 (main OOF 승인 전 금지). 합성 자료 시험만, fit 없음, main pool 미소비.

## BM.1 계획서 먼저 (사전 등록)

- `docs/experiments/mobse_redesign_protocol_2026-09-17.md` §8 보조 목록 문장 뒤에 `[개정 P12]` 표시 — "구조 비교 A−NG·A−SG 도 A−S 와 같은 보조 contrast 로 보고한다 — 같은 subject 짝 paired bootstrap(A−S 와 같은 seed·반복 수, 같은 index), 95% 기술적 CI, primary 아님 (§11)".
- §11 개정 표에 **P12** 행 (P11 뒤): 개정 전 문장·결정 원문·바꾸지 않은 것·근거·"main 결과를 보기 전의 사전 등록 — main OOF 미착수 (실자료 outer 예측 없음)" 명시. 날짜 2026-09-26.

## BM.2 구현 (`mobse/v2/evaluate.py`, `mobse/v2/cli.py`)

- `evaluate.COMPARISON_CONTRASTS = ("A_minus_S", "A_minus_NG", "A_minus_SG")` (순서 고정), 새 `CONTRAST_CELL` (contrast → 비교 칸).
- `comparison_contrasts(ad_runs, *, s_runs, ng_runs, sg_runs)` — **구현 선택 (표시함)**: 세 칸을 필수 키워드 인자로 받는다 (위치 인자로 칸을 넘기면 `TypeError`; `report-comparison` 이 세 칸을 이미 필수로 받으므로 같은 계약). 칸마다 `subject_scores` 의 subject 집합이 A 와 다르면 `"<칸> 의 subject 집합이 A 와 다르다 — paired 불가"` 로 거부 (A−S 와 같은 규칙).
- `run_report_comparison`: 세 칸 run 을 넘기고, `auxiliary_contrasts` 를 `COMPARISON_CONTRASTS` 순서로 만든다 — 모두 같은 `_ci` (같은 `ST.bootstrap_indices` index 한 번, `stats.bootstrap_seed` 9001·`stats.n_bootstrap` 10,000·`stats.nominal_pct` (2.5, 97.5), `role: auxiliary`·`primary: false`). `not_reported` 에서 A−NG·A−SG 제거 (parameter/비용만 남음). 반환 요약에 세 contrast 의 [점, 하한, 상한]. 산출물 schema 이름 `d14-comparison-statistics-0.1` 은 바꾸지 않음 (키 추가만).
- bootstrap index 공유 (결정 18 명세 2): 세 contrast 와 칸 BA 3 개가 **같은 index 객체** 를 쓴다 — spy 시험으로 고정 (아래). 새 구현 선택 아님 (rev56 부터 한 번 만든 index 를 공유).

## BM.3 시험·돌연변이

- `tests/v2/test_evaluate_comparison.py` 17 → **20**: 이름 시험에 계획서 `[개정 P12]` 본문 문자열과 `| P12 | §8 |` 행 1 개를 묶음; 손계산 (A: s1 1·s2 1·s3 0.5 / NG: 0.5·1·1 / SG: 1·1·0 → A−NG +0.5·0·−0.5, A−SG 0·0·+0.5, A−S 기존 값 그대로); NG·SG 각각 unpaired 거부 (parametrize 2); 칸 위치 인자 거부 1.
- `tests/v2/test_cli_report_comparison.py` 23 → **25**: 기존 손계산 시험에 A−NG (NG 모두 맞힘 → 0, 구간 (0, 0))·A−SG (SG 짝수 EM 틀림 → 0.25, 독립 재계산 구간 = A−S 구간)·세 contrast `primary: false`·`role: auxiliary`·키 순서·`not_reported` = parameter/비용만 추가. 새 시험 2: (i) SG 가 모든 EM 을 틀리는 변형에서 A−S 0.25·A−NG 0·A−SG 0.5 — 기존 fixture 에서는 S·SG 의 b 벡터가 같아 칸을 바꿔 끼워도 안 보이므로 가르는 자료를 둠; (ii) `paired_bootstrap` spy — 호출 6 회 (칸 BA 3 + contrast 3), index 객체 하나, 정렬 subject 순서, 9001·10,000·(2.5, 97.5).
- 돌연변이 `.backup/slot_1115c/mut_d18.py` (`-B`·`PYTHONDONTWRITEBYTECODE=1`, 원본 복원) **11/12** + NOT-APPLICABLE 1 (`indices=idx,` 가 `run_report` 에도 있음) → 구간 한정 `mut_d18_idx.py` (`run_report_comparison` 안에서만) 검출 → **12/12**. 대상: 상수에서 A−NG 제거, contrast→칸 대응 2 종, 차이 부호, pairing 가드 제거, 칸 인자 바꿔 끼우기 (라이브러리 1·CLI 2), A−S 만 CI, 칸마다 새 index, `not_reported` 에 A−NG 재삽입, `primary: true`. Mac `*.pyc` 0 (돌연변이 뒤·rsync 전).
- 관련 4 파일 (위 둘 + `test_cli_report.py`·`test_config_consumption.py`) Mac 101 passed.

## BM.4 잠금·gate

- `mobse/v2` 변경 → 재잠금 `78ddd887253f` → **`9564cadb238b`** (2026-09-26T02:19:05Z), code_hash `fbd9fd7feee2` → `58c7152122a5`. 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash (main `2a7d7d7f`·pilot `6498596a`·external `576f6068`) 불변. 계획서 sha 도 바뀜 (gate 인용 치환).
- gate evidence **rev65** (`decision18_structure_contrasts_rev65`). 판정·gate status 변경 없음.

## BM.5 확인하지 못한 것

- 실자료 A−NG·A−SG (main OOF 승인 전 금지). 산출물 schema 판 번호를 올릴지 (키만 늘었음) — 이번엔 올리지 않음 (소비자 없음, 구현 선택).

# 부록 BN — 결정 22: 낡은 gate 표기 정리 — G0 [2]·[7]·[8]·G1 [1] `pass`, G1 `unresolved` 정리 (rev66, 2026-09-26 12:14 예약 슬롯)

**gate 표기만 바꾼다.** 선생님 결정 22 (09-26 11:1x KST 기록) — 대화 권고 "권고: 원인이 해소된 항목을 근거와 함께 갱신합니다. • G0 [2]·[7]·[8]과 G1 [1]을 pass로 바꾸고 note에 근거를 적습니다. • G1 `unresolved`에서 해결된 항목을 뺍니다." 를 회신. **바꾸지 않은 것**: G1 [0] (group_id)·[6] (δ 정밀도) 는 `fail` 그대로 (note 도 불변), 모든 gate 의 `status`, G0 `unresolved`·두 gate 의 `status_note`, G2·G3·G5 의 "blocked by G0" 표기. main OOF 착수 승인 아님. 코드·시험·잠금 불변 (9564cadb).

## BN.1 바뀐 check (이름·이전 값으로 대상 확인, 인덱스는 12:1x 에 확인)

| gate [i] | check | 이전 | 이후 | 근거 (이 슬롯에서 다시 잰 것 포함) |
|---|---|---|---|---|
| G0 [2] | existing extraction TR correctness | fail — "모든 run 에 0.75 적용 … 기존 파생물 주분석 재사용 불가 확정" | **pass** | 옛 파생물은 쓰지 않았다. P9 재추출 (부록 AA, rev28, `derivatives_v3*`) 은 dataset×task 별 native TR 을 받는다 (`10_wi02_extract.process_run(paths, native_tr, …)`, manifest header `native_tr`). 12:1x h197 에서 여섯 v3 manifest header 를 다시 읽음: ds002785 emo 2.0 · rest 0.75 · wm 2.0, ds002790 emo 2.0 · rest 2.0 · wm 2.0 — G0 [0]·[1] observed 와 6/6 일치 |
| G0 [7] | BOLD present for the primary targets | fail, observed 0 — "Wave 2 대상. Wave 1 은 메타데이터만 받았다" | **pass**, observed 교체 | Wave 2 수령 (부록 T.1 "ds002785 1,250 파일 + ds002790 1,340 파일 = FAIL 0", gate `wave2_complete.fail_count: 0`). 12:1x h197 `aomic_wave2/<ds>/fmriprep/*/func/*task-<t>*desc-preproc_bold.nii.gz` 수: ds002785 emo **208** · wm **207**, ds002790 emo **222** · wm **224** — 부록 F.1 raw sidecar run 수와 같고, v3 추출 ok+excluded (183+25 · 176+31 · 204+18 · 214+10) 와 같다 |
| G0 [8] | dummy volumes removed before archiving | undetermined — "… 이 파일들로 판정 불가(U3)" | **pass** | 부록 F.1: raw sidecar 1,295 개 전수, 6 조합 모두 `NumberOfVolumesDiscardedByScanner=2`, `ByUser` 없음, 조합 내 분산 0 — 스캐너가 보관 전에 앞 2 volumes 를 버렸다. gate `u3_discarded_volumes.status: resolved`, `derivative_start_sec = 2 × native_TR` 가 추출에 반영 (`DISCARDED_BY_SCANNER * native_tr`) |
| G1 [1] | PIOP1/PIOP2 subject ID namespace | fail — "… canonical_subject 에 dataset prefix 필수" | **pass** | 계획서 §3.1 [개정 P5] + `mobse/v2/manifests.validate_canonical_subject()` (prefix 없는 값은 명시적 실패), cohort 가 prefix 없는 subject 거부 (gate `wi03_cohort.rejects_subject_without_dataset_prefix: true`) — 부록 BK.2 |

- 새 note 에는 위 근거와 "결정 22" 를 적었고, 이전 check 원문 4 개는 gate 블록 `decision22_gate_record_refresh.previous` 에 그대로 보존했다.
- G0 [7] `observed` 는 0 → 위 네 수 (dict) 로 바꿨다 — pass 와 observed 0 이 한 check 에 함께 있으면 모순이라서. 구현 선택으로 표시한다.

## BN.2 G1 `unresolved` 정리

| 이전 항목 | 처리 | 근거 |
|---|---|---|
| U10 | 남김 | G1 [0] fail 그대로 (관계 metadata 부재) |
| U17(완화: dataset prefix 적용) | **남김** | 네임스페이스 쪽은 P5 로 해소됐지만 U17 의 나머지 "실제 overlap 은 공식 문서로만 판정" (부록 표 U17, G4 `unresolved`) 은 해소 근거가 없다 — 판단하지 않고 그대로 둠 |
| pilot fit 미실행 — §7 의 peak memory·시간 실측 없음 | **뺌** | rev58 (부록 BF)·rev61 (부록 BI) pilot 기술 분할 실측, 결정 19 로 G1 [7] pass (rev64, 부록 BL) |
| δ=0.02 정밀도 부족 — 차단이 아니라 명시 항목 (§8) | 남김 | G1 [6] fail 그대로 |
| band-pass 통과대역 상한 미결정 — … | **뺌** | 결정 9 "통과대역 0.2 Hz로" → P9 구현 (부록 Z, rev27)·재추출 (부록 AA, rev28), `BANDPASS_HIGH_HZ = 0.200` |
| 개정 P8 학습 예산 — 결정됐으나 구현 전 | **뺌** | P8 구현 (부록 AB, rev29), 값은 결정 15 로 5,000 / 400 (계획서 P8-b, 부록 AR, rev44) |

G1 `unresolved` 6 → **3** (U10 · U17 · δ 정밀도).

## BN.3 갱신 뒤 판정 (rev66, 다시 셈)

- G0 `conditionally_cleared` 10: **pass 10** (이전 7 · fail 2 · undetermined 1). `status` 그대로.
- G1 `in_progress` 8: **pass 6 · fail 2** ([0] group_id · [6] δ 정밀도). `status` 그대로.
- G2 planned 0 · G3 planned 1 pass · G4 planned 1 pass · G5 planned 0 — 불변.
- **"blocked by G0" (보고만, 바꾸지 않음)**: G2·G3·G5 의 `unresolved` 는 여전히 "blocked by G0" 이고 G4 는 "blocked by G0/G1". G0 check 는 이제 전부 pass 이지만 G0 `status` 는 `conditionally_cleared` 이고, G0 `unresolved` 에는 U3·"U6(targets, Wave 2)"·U10 이, `status_note` 에는 "남은 것은 재추출 입력(BOLD)뿐 … 실제 clearing 은 재추출과 QC(WI-02) 이후에 판정한다" 가 남아 있다. G0 `status` 를 `cleared` 로 올릴지, 그에 따라 "blocked by G0" 표기를 뺄지는 결정 22 범위 밖이라 선생님 판단 사항으로 남긴다.

## BN.4 확인하지 못한 것

- G0 `unresolved` 의 U3·U6 과 두 gate 의 `status_note` 가 해소 상태를 반영하는지 (범위 밖 — 바꾸지 않음. U3 은 F.1·`u3_discarded_volumes` 에서 resolved, U6 (targets) 는 Wave 2 수령으로 풀린 것으로 보이나 U6 원문을 이번에 다시 대조하지 않음).
- G1 [4] note 의 "검증 42/42" 는 현재 19번 45 건과 다르다 (rev50 이후 낡음) — 판정 아님, 범위 밖이라 그대로.
- gate `wave2_fetch.status` "running" (옛 기록) — 그대로.
- 산출물: 이 부록과 gate rev66 (틀 `.backup/slot_1215c/rev66_update.py`). h197 측정은 명령 출력만 (파일 없음) — 위 수는 같은 명령으로 다시 셀 수 있다.


# 부록 BO — 결정 21 명세 1: T01–T16 수용 시험 ↔ `tests/v2` 대응표 (rev67, 2026-09-26 13:14 예약 슬롯)

선생님 결정 21 (09-26 11:1x KST 기록) 원문: "(가) `implementation_lock.json`을 만들고 G2 check를 채운 뒤 main OOF로 갑니다. 담을 내용은 환경, code/config hash, acceptance 결과, pilot end-to-end입니다. 먼저 T01–T16 acceptance 항목과 `tests/v2` 시험의 대응표가 필요합니다. main pool을 쓰지 않으니 되돌릴 수 있습니다." 이 부록은 그중 **명세 1 (대응표, 읽기·기록)** 만 한다. 시험 추가·코드 변경·G2 check·`implementation_lock.json` 은 하지 않았다. main OOF 착수 승인이 아니다.

## BO.1 방법

- 항목 원문: 작업 지침서 §4 "필수 acceptance tests" 표 16 행을 생성 스크립트가 파일에서 직접 읽어 옮김 (정규식, 16 개 확인). 지침서 sha256 은 대응표 파일 `source_sha256` 에 기록.
- 대응 시험: 각 시험 파일의 T-ID 절 머리 (`# T0x — …`) 아래 함수, 그리고 기대 결과 문구별 grep (confounds 누락, single class, 금지 subject, config hash, 누락 window, bank hash 전후 비교). 부록 D.3 (2026-09-17) 의 파일 단위 대응을 출발점으로 삼고, 시험 이름 단위로 좁혔다.
- 대응 정도: **전부** = 기대 결과의 모든 절을 시험이 직접 검사 / **부분** = 일부만 (빠진 부분을 적음) / **없음**. 판정은 이 슬롯의 판단이며 항목 정의를 바꾸지 않았다.
- 검증: 대응표의 시험 이름 83 개를 AST 로 top-level 함수 존재 확인 (빠진 것 0), Mac `.venv` 에서 그 83 개 node id 를 `-B` 로 실행 — **90 passed** (parametrize 전개, 2.5 s). 통과 여부의 정본은 같은 회차 h197 마감 1단계.
- 산출물 (구현 선택 — 이름·형식): release `reports/acceptance_map_t01_t16.json` (schema `acceptance_map_v1`), 생성 틀 `.backup/slot_1315c/build_map.py` (덮어쓰기 거부). gate rev67 `decision21_acceptance_map_rev67.artifacts` 에 sha256 기록.

## BO.2 결과 요약

- **전부 13**: T01·T02·T05·T06·T07·T08·T09·T10·T12·T13·T14·T15·T16.
- **부분 3**: T03 (bank fit 금지 subject 실패 시험 없음) · T04 (bank hash 전후 비교 없음) · T11 (single class fold 거부가 A–D·NG·SG 학습 경로에 없음).
- **없음 0**.
- 부록 D.3 은 16 항목 모두 "통과" 로 적었다 — 파일 단위로는 맞지만 기대 결과 절 단위로 보면 위 3 항목에 빈틈이 있다. D.3 은 고치지 않는다 (기록 보존).

## BO.3 대응표

| ID | 기대 결과 (지침서 §4 원문) | 대응 | 대응 시험 (tests/v2) | 근거 · 빈틈 |
|---|---|---|---|---|
| T01 Timing | 원래 [12,252) 범위 보존, 120 target samples, guard 중복 없음 | 전부 | test_preprocess.py::test_target_grid_is_always_120_samples<br>test_preprocess.py::test_discarded_volumes_shift_the_clock_not_the_guard<br>test_preprocess.py::test_source_frame_range_matches_original_times_for_both_tr<br>test_preprocess.py::test_four_windows_each_30_samples_and_contiguous<br>test_preprocess.py::test_window_before_derivative_start_fails<br>test_preprocess.py::test_negative_start_and_bad_tr_fail | TR 2.0/0.75 와 폐기 volume 2·4 fixture, 창 [12,72,132,192]→252 초·120 sample, derivative 시작점에 guard 재가산 안 함 (첫 창 12 s) |
| T02 Provenance | 명시적 실패; 조용한 default 없음 | 전부 | test_evaluate_cli.py::test_validate_detects_tr_conflict_within_task<br>test_evaluate_cli.py::test_validate_rejects_null_without_reason<br>test_extract.py::test_read_confounds_tsv_missing_file<br>test_extract.py::test_missing_column_is_a_failure<br>test_manifests.py::test_duplicate_run_key_fails<br>test_manifests.py::test_missing_field_fails_explicitly<br>test_manifests.py::test_none_value_fails_rather_than_defaulting<br>test_config.py::test_missing_key_is_rejected | TR 충돌·confounds 파일/열 누락·중복 run key 각각 명시적 예외, None·누락 필드·이유 없는 null 을 default 로 채우지 않음 |
| T03 Subject isolation | 실패; 모든 fit IDs⊆허용 train, val/test 교집합 0 | **부분** | test_features.py::test_fit_rejects_forbidden_subjects<br>test_fitting.py::test_transform_is_fit_only_on_training_subjects<br>test_fitting.py::test_allowed_subjects_is_actually_passed_through<br>test_fitting.py::test_pilot_leaking_into_a_fold_is_rejected<br>test_splits.py::test_build_folds_boundaries_are_all_disjoint<br>test_splits.py::test_assert_fit_scope_rejects_forbidden_subject<br>test_splits.py::test_verify_disjoint_raises_on_overlap<br>test_cli_split.py::test_outer_test_never_appears_in_its_train_or_inner<br>test_cli_split.py::test_pilot_and_main_pool_are_disjoint | PCA fit 에 금지 subject 삽입 → FeatureError, fit_subjects ⊆ fold train, 분할 경계 교집합 0<br>**빈틈:** bank fit 에 금지 subject 를 넣어 '실패' 하는 시험 없음 — `templates.build_bank` 에 허용 subject 검사가 없고, `fitting.fit_fold_transform` 은 허용 밖 창을 걸러 낸다 (실패가 아니라 제외). PCA 쪽만 실패로 검증됨 |
| T04 Frozen transform | PCA/bank hash·parameters 불변 | **부분** | test_features.py::test_transform_does_not_change_fitted_parameters<br>test_features.py::test_transform_output_shape_and_determinism<br>test_features.py::test_refitting_on_more_data_changes_artifact_id<br>test_fitting.py::test_transform_fingerprint_is_stable_across_transforms<br>test_models.py::test_bank_is_buffer_not_parameter<br>test_templates.py::test_bank_id_is_content_bound | PCA/scaler parameter·fingerprint 가 transform 전후 불변, bank 는 buffer (optimizer 밖), bank_id 는 내용에 묶임<br>**빈틈:** val/test transform (또는 평가 forward) 전후 bank hash 를 비교하는 시험 없음 — bank 쪽 불변은 buffer 성질·content-bound id 로 간접 확인만 |
| T05 Graph/null | 대칭·finite·nonnegative, self-loop/정규화 일치; spectrum와 bank 거리 보존 | 전부 | test_templates.py::test_normalize_with_self_loop_hand_computed<br>test_templates.py::test_isolated_node_survives_via_self_loop<br>test_templates.py::test_sparsify_keeps_largest_positive_edges_only<br>test_templates.py::test_bank_templates_are_symmetric_finite_nonnegative<br>test_templates.py::test_null_preserves_spectrum_and_between_bank_distance<br>test_templates.py::test_null_uses_one_permutation_for_every_template<br>test_templates.py::test_invalid_permutation_is_rejected<br>test_h197_scripts.py::test_bank_demo_properties_report | 손계산 self-loop 정규화, 대칭·유한·비음수, joint permutation 하나로 spectrum·bank 간 거리 보존 |
| T06 ROI alignment | 다른 ROI encoder 결과 불변(eval mode) | 전부 | test_models.py::test_changing_one_roi_leaves_other_roi_encodings_untouched<br>test_models.py::test_encoder_is_shared_across_roi | eval 모드에서 한 ROI 입력만 바꾸면 다른 ROI encoder 출력 불변 |
| T07 FC information | FC features 차이; 출력 차이를 강요하지 않음 | 전부 | test_features.py::test_same_mean_different_correlation_gives_different_features | 평균 같고 correlation 다른 fixture 에서 FC feature 가 다름 (출력 차이 강요 없음) |
| T08 Routing | fixed weights 동일, dynamic finite·합1, 유한 gradient | 전부 | test_models.py::test_fixed_gate_ignores_input_and_dynamic_does_not<br>test_models.py::test_routing_weights_are_finite_and_sum_to_one<br>test_models.py::test_gradients_are_finite_for_every_cell | fixed gate 입력 무관, dynamic 유한·합 1, 모든 cell 유한 gradient |
| T09 Mixture | 직접 template/평균 bank/원 logits와 각각 일치 | 전부 | test_models.py::test_one_hot_override_equals_single_template<br>test_models.py::test_uniform_override_equals_bank_mean_without_renormalisation<br>test_models.py::test_override_reproduces_original_gate_output<br>test_templates.py::test_mixture_one_hot_equals_template<br>test_templates.py::test_mixture_uniform_equals_mean_and_is_not_renormalised | one-hot = template, uniform = bank 평균 (재정규화 없음), 원 logits override = 원 출력 |
| T10 Backend/checkpoint | 동일 명시 backend; eval logits 허용오차 내 동일 | 전부 | test_models.py::test_checkpoint_roundtrip_preserves_eval_logits<br>test_models.py::test_checkpoint_rejects_foreign_backend<br>test_models.py::test_checkpoint_rejects_wrong_cell<br>test_models.py::test_pyg_is_not_imported | CPU save/reload eval logits 동일, backend 'dense' 명시·다른 backend 거부, PyG 미사용<br>**빈틈:** §4 문단 'GPU 저장/재로드는 해당 backend의 근거를 기록한다' — GPU checkpoint 재로드 시험·기록 없음 (test_models 에 cuda 경로 없음). T10 기대 결과 자체는 CPU 로 충족 |
| T11 Target | 거부; label_source는 task metadata | **부분** | test_manifests.py::test_label_source_must_be_task_metadata<br>test_labels.py::test_cluster_id_can_never_become_a_label_source<br>test_labels.py::test_label_source_is_the_only_allowed_one<br>test_labels.py::test_unknown_task_is_rejected_not_defaulted<br>test_baselines.py::test_fit_logistic_guards<br>test_baselines.py::test_fit_mlp_guards | cluster ID label_source 거부 (스키마·labels 이중), label_source = task metadata; 한 class 학습 라벨 거부는 S 후보 (`fit_logistic`·`fit_mlp`) 에만<br>**빈틈:** single class fold 거부가 A–D·NG·SG 학습 경로 (`fitting.train_fold`/`encode_windows`) 에 없음 — 한 class 만 있는 training 집합을 넣어 실패하는 시험 없음 |
| T12 Selection boundary | test 선택 금지; tie rule와 ceil median E 정확 | 전부 | test_train.py::test_leakage_guard_rejects_outer_test_scores<br>test_train.py::test_tie_broken_by_joint_ba_then_smallest_id<br>test_train.py::test_common_epoch_is_ceil_of_median_over_12_values<br>test_train.py::test_baseline_epoch_is_ceil_median_of_three<br>test_train.py::test_incomplete_grid_is_rejected | outer test 점수로 선택 거부, 동률 → 공동 BA → 작은 config_id, 공통 E = 12 best epoch 중앙값 올림, baseline = 3 개 중앙값 올림 |
| T13 Endpoint | aggregation, threshold tie, BA, paired 차이 일치 | 전부 | test_statistics.py::test_full_endpoint_chain_two_subjects<br>test_statistics.py::test_run_probability_averages_seeds_then_windows<br>test_statistics.py::test_threshold_tie_goes_to_class_one<br>test_statistics.py::test_subject_score_and_ba_hand_computed<br>test_statistics.py::test_paired_difference_is_within_subject | 2 subject × 2 task × 4 window × 3 seed 손계산 체인, 0.5 동률 → class 1, BA·paired 차이 일치 |
| T14 Statistical unit | group 재표집·pair 유지; seed/window를 독립 N으로 쓰지 않음 | 전부 | test_statistics.py::test_bootstrap_resamples_groups_not_subjects<br>test_statistics.py::test_same_indices_applied_to_all_cells_preserves_pairing<br>test_statistics.py::test_n_is_subjects_never_windows_or_seeds<br>test_statistics.py::test_bootstrap_draw_size_equals_subject_count_for_equal_groups | 가족 fixture 에서 group 단위 재표집, 같은 index 로 pair 유지, N = subject |
| T15 Integrity | 실패; glob fallback·불완전 평균 없음 | 전부 | test_cli_evaluate.py::test_changed_checkpoint_fails<br>test_cli_evaluate.py::test_missing_checkpoint_file_fails_without_search<br>test_cli_evaluate.py::test_boundary_hash_mismatch_fails<br>test_cli_evaluate.py::test_dropped_window_fails_rather_than_partial_mean<br>test_evaluate_cli.py::test_missing_seed_fails_rather_than_averaging_partially<br>test_evaluate_cli.py::test_checkpoint_integrity_rejects_missing_and_mismatched<br>test_statistics.py::test_run_probability_rejects_incomplete_input<br>test_manifests.py::test_assert_no_glob_fallback | checkpoint 변경·파일 없음 (탐색 없이) 실패, config_hash/split_hash 불일치 실패, 창·seed 누락 시 부분 평균 대신 실패, glob fallback 금지 |
| T16 Scope | ETTh1 등 미학습 task 자동 평가 없음 | 전부 | test_evaluate_cli.py::test_only_trained_classification_tasks_are_evaluated<br>test_evaluate_cli.py::test_window_prediction_rejects_unknown_task_and_cell<br>test_models.py::test_model_has_no_forecasting_head | 평가 대상은 학습한 분류 task 두 개뿐, 알 수 없는 task 거부, forecasting head 없음 |

## BO.4 빈틈과 다음 단계 (명세 2 후보 — 이 슬롯에서는 하지 않음)

- **T03**: `templates.build_bank` 에 허용 subject 인자·검사가 없다. `fitting.fit_fold_transform` 은 `train_subjects` 밖 창을 **걸러 내므로** 금지 subject 가 bank 에 들어가는 경로는 막혀 있지만, 기대 결과의 "실패" 는 아니다 (PCA 쪽 `allowed_subjects` 검사는 같은 필터 뒤라 이 경로에서는 도달하지 않는다 — PCA 단독 시험이 따로 검증). 보강안: `build_bank` 에 `allowed_subjects` 검사 + 금지 subject 삽입 실패 시험 (가역, `mobse/v2` 변경 → 재잠금).
- **T04**: bank 는 buffer (`bank_is_frozen`) 이고 `bank_id` 는 내용에 묶여 있으나, 평가 forward·val/test transform 전후 bank hash 를 직접 비교하는 시험이 없다. 보강안: fit 뒤 평가 전후 bank 텐서·`bank_id` 동일 시험 (시험만 — 재잠금 불요).
- **T11**: 한 class 학습 라벨 거부는 S 후보 (`baselines.fit_logistic`·`fit_mlp`) 에만 있다. `fitting.train_fold`/`encode_windows` 는 한 class 만 있는 training 집합을 받는다. 실자료 분할에서는 subject 마다 두 task 를 갖지만 (창 누락·필터로 생길 수 있음) 방어선이 없다. 보강안: `train_fold` 에 training 라벨 두 class 검사 + 시험 (가역, `mobse/v2` 변경 → 재잠금).
- **T10 (정보)**: §4 문단 "GPU 저장/재로드는 해당 backend의 근거를 기록한다" 에 해당하는 기록이 없다 (시험은 CPU). T10 기대 결과는 충족으로 봄 — 기록 추가는 명세 3 (pilot end-to-end, h197 GPU) 때 함께 할 수 있다.
- 세 보강안은 항목 해석이 갈리지 않는다고 봄 (기대 결과 문장 그대로 "실패"·"불변"·"거부"). 다만 T03 의 "걸러 냄 대 실패" 를 실패로 바꾸면 `fit_fold_transform` 동작은 바뀌지 않는다 (필터가 먼저) — `build_bank` 직접 호출에만 영향.

## BO.5 확인하지 못한 것

- 대응 정도는 시험 이름·docstring·본문 일부를 읽고 정했다. 83 개 시험 본문을 모두 줄 단위로 대조하지는 않았다 (T01·T03·T04·T11·T15 는 본문 확인).
- `tests/v2/test_acceptance_coverage.py` 는 T-ID 참조만 검사한다 — 이 대응표와 묶는 시험은 아직 없다 (명세 4·5 에서 정할 구현 선택).
- 산출물: 이 부록, release `reports/acceptance_map_t01_t16.json`, gate rev67 (틀 `.backup/slot_1315c/rev67_update.py`). 코드·시험·잠금 불변 (9564cadb).


# 부록 BP — 결정 21 명세 2: acceptance 빈틈 보강 T03·T04·T11 (rev68, 2026-09-26 14:14 예약 슬롯)

선생님 결정 21 (09-26 11:1x KST 기록) — 선택지 "(가) `implementation_lock.json`을 만들고 G2 check를 채운 뒤 main OOF로 갑니다. … 먼저 T01–T16 acceptance 항목과 `tests/v2` 시험의 대응표가 필요합니다. main pool을 쓰지 않으니 되돌릴 수 있습니다." 의 명세 2 (부록 BO.4 보강안). **바꾸지 않은 것**: T01–T16 항목 정의, 계획서·지침서, 학습·선택 규칙과 값, gate 판정·status, G2 check (여전히 0건). fit 없음, main pool 미소비. main OOF 착수 승인 아님.

## BP.1 코드 (`mobse/v2`)

- **T03** `templates.build_bank(..., allowed_subjects=None)`: 주면 `fit_subjects` 가 그 부분집합인지 확인하고 아니면 `TemplateError` ("허용되지 않은 subject 가 bank fit 에 들어갔다"). PCA 쪽 `features.fit_transform_on_training_rest` 와 같은 규칙. `fitting.fit_fold_transform` 이 `allowed_subjects=sorted(train_subjects)` 를 넘긴다. 이 경로는 허용 밖 창을 먼저 걸러 내므로 실자료 결과는 바뀌지 않는다 (같은 입력에서 bank_id 동일 — 시험).
- **T11** `fitting.train_fold`: training 라벨 집합이 정확히 {0, 1} 가 아니면 `FitError` ("training 라벨이 두 class 가 아니다 … single class fold 거부, T11"). 위치는 role·공통 E 검사 뒤, P8 계산 앞 — inner·outer, A–D·NG·SG 모두 같은 경로. **구현 선택 (표시함)**: `encode_windows` 가 아니라 `train_fold` 에 두고 training 집합만 검사 (평가 집합은 subject 마다 두 task).
- **T04**: 코드 변경 없음 (시험만).

## BP.2 시험

- `test_templates.py` +2: `test_build_bank_rejects_a_forbidden_subject`, `test_build_bank_accepts_fit_subjects_within_the_allowed_set` (허용 집합이 fit subject 를 담으면 bank_id = 검사 없이 만든 bank).
- `test_fitting.py` +5 함수 (parametrize 전개 12): `test_bank_allowed_subjects_is_actually_passed_through` (spy), `test_bank_hash_is_unchanged_by_eval_transform_and_fit` [A, C] (평가 창 인코딩·학습·평가 forward 전후 brain/null fingerprint·bank_id·PCA fingerprint 동일, 모델 `template_bank` buffer = 변환 bank float32, parameter 아님), `test_single_class_training_set_is_refused` [A·D·NG·SG × 라벨 0·1], `test_single_class_outer_training_set_is_refused`.
- HEAD 판 `templates.py`·`fitting.py` 에 새 시험을 돌리면 12 실패 · 2 통과 (T04 두 개 — 시험만 추가한 항목이라 기대대로). 관련 7 파일 Mac `-B` 302 passed / 13 skipped.
- 돌연변이 `.backup/slot_1415c/mut_gap.py` (`-B`, `PYTHONDONTWRITEBYTECODE=1`) **8/8**: build_bank 가드 끔·None 분기 끔, fit_fold_transform 전달 뺌·None 전달, train_fold 가드 끔·약화 (`len > 2`), bank 를 parameter 로 등록, 평가 인코딩이 bank 를 건드림.

## BP.3 대응표 갱신 판

- release `reports/acceptance_map_t01_t16_v2.json` (**구현 선택: v1 은 명세 1 기록으로 보존, 새 파일** — 같은 release 결과 덮어쓰기 금지). `supersedes` 에 v1 경로·sha256, T03·T04·T11 은 `coverage: full`, 새 시험 추가, `previous_gap` 에 옛 gap. 요약 **전부 16 · 부분 0 · 없음 0**, 명명 시험 89 (83 + 6), 전부 AST 존재 확인. 틀 `.backup/slot_1415c/build_map_v2.py` (덮어쓰기 거부).
- 부록 BO.4 의 T10 정보 항목 (GPU 저장/재로드 근거 기록) 은 그대로 — 명세 3 때 기록.

## BP.4 재잠금·gate

- 재잠금 `9564cadb238b` → **`9b7b11cf8576`** (2026-09-26T05:22:16Z), code_hash `58c7152122a5` → `804d6ee17625` (h197 `$HOME/slot/t_rc_1415c.sh`). 19번 45/45, 25번 창 4,728. split_hash `ace5f4a4…`·external_split_hash `40e50350…`·config_hash (main `2a7d7d7f`·pilot `6498596a`·external `576f6068`) 불변.
- gate **rev68** (`decision21_acceptance_gaps_rev68`, 틀 `.backup/slot_1415c/rev68_update.py` — rev65 재잠금 틀 + rev67 새 산출물 `artifacts`; 판정·status·check 수 [10,8,0,1,1,0] 불변 assert).

## BP.5 확인하지 못한 것

- 실자료 fit 에서 T11 가드가 걸리는 경우가 있는지 (main pool fit 금지 — pilot end-to-end (명세 3) 에서 pilot 분할로 확인 가능).
- 명세 3–5 (pilot end-to-end, `implementation_lock.json`, G2 check) 는 다음 슬롯.


# 부록 BQ — 결정 21 명세 3: pilot end-to-end (CLI 전 경로, pilot 기술 분할) (rev69, 2026-09-26 21:15 예약 슬롯)

선생님 결정 21 (09-26 11:1x KST 기록) — 선택지 "(가) `implementation_lock.json`을 만들고 G2 check를 채운 뒤 main OOF로 갑니다. 담을 내용은 환경, code/config hash, acceptance 결과, pilot end-to-end입니다. … main pool을 쓰지 않으니 되돌릴 수 있습니다." 의 명세 3. 실행은 09-26 15:15 슬롯 착수, 20:15 슬롯 끝 확인, 이 부록은 21:15 슬롯 기록. **바꾸지 않은 것**: 코드·시험·config·잠금 (9b7b11cf), 학습·선택 규칙과 값, gate 판정·status, G2 check (여전히 0건). main pool 미소비. **성능은 해석하지 않는다.** main OOF 착수 승인 아님.

## BQ.1 범위와 방법

- 입력: pilot 31 명만 — v3 PIOP1 창 manifest 3 개로 `prepare` → pilot 명단 거르기 (`splits_piop1_p7/folds.json` `pilot.subjects`, 구동기 안에서 — CLI 단계 아님, 구현 선택) → `split` (`configs/redesign_v1/pilot.yaml`). real main pool (`folds_p7`) 과 subject 겹침 0.
- 최소 규모 (grep 근거): `select-ad` 는 4 cell × 8 config × 3 inner = 96 완비를, `evaluate` 는 A–D × outer 전부 × seed 3 격자 완비를 요구한다 → pilot 기술 분할 전체 격자 **inner 480 (5 outer × 96, seed 42) → `select-ad` 5 → outer 60 (5 × 4 cell × seed 42–44) → `evaluate` → `report`**. S·NG·SG·`report-comparison` 은 넣지 않았다 (명세 3 단계 목록이 A–D 경로 — 구현 선택).
- 코드: 시작 시점 HEAD `72cc1b3` 의 `git archive HEAD mobse configs` 사본 (작업트리 깨끗). h197 bmcws, python 3.11.5, torch 2.10.0+cu128, CUDA 12.8, `--device cuda`, k=4 동시 (CLI subprocess), `-B`·`PYTHONDONTWRITEBYTECODE=1`.
- **CLI 한계 (기록)**: CLI 에는 학습 상한을 바꿀 인자가 없다. `fitting.train_fold` 가 `n_epochs_planned > MAX_EPOCHS` (400) 를 거부하고, `select-ad`·`train.select_config` 가 best epoch·공통 E 를 1–`train.MAX_EPOCHS` 로 거부한다. pilot 규모 (inner 학습 104–112 창, 4 update/epoch) 는 최소 epoch 1,250 (= 5,000 update / 4) 이라 **CLI 경로 그대로는 실행 불가**다 (결정 15 절 5 와 같은 귀결).
- **방법 (구현 선택, 표시함)**: 감싸개 `.backup/slot_1515c/e2e_cli.py` 가 `mobse.v2.cli` 를 **먼저 import** 한 뒤 이 프로세스 안에서만 `train.MAX_EPOCHS`·`fitting.MAX_EPOCHS` 를 2000 으로 덮고 `cli.main(argv)` 를 그대로 부른다. config 값 (`train.max_epochs: 400`·`min_updates: 5000`)·다른 규칙 불변. inner `--epochs 2000` (pilot 판 상한). 구동기 `e2e_driver.py`, 설치 `e2e_setup.sh`, prep 대조 `cmp_prep.py`.
- **첫 시도 거부 (06:19:53Z)**: 덮은 뒤 cli 를 import 하자 `config.FieldSpec(locked_to=train.MAX_EPOCHS)` 가 2000 을 잡아 `prepare` 가 "train.max_epochs: 코드 상수와 불일치 (config=400, 코드=2000)" 로 거부했다 — config 잠금 가드가 작동한 것. import 순서를 바꿔 해결 (config 파일은 400 그대로 검증 통과). 실패 판은 지우지 않고 `pilot_e2e/try1_20260926_1515c_config_guard/` 에 둠.

## BQ.2 prep 대조 (06:21:22Z)

- `prepare` 산출 `windows.jsonl`·`subjects.jsonl`·`exclusions.jsonl` = 잠긴 `derivatives_v3/windows_piop1.jsonl`·`cohort_piop1/{subjects,exclusions}.jsonl` **바이트 동일** (sha256 앞 12자 `0750c81c0670`·`5ab193392202`·`2e51f25bf1df`). pilot 거르기 결과 = `derivatives_v2/pilot_tech/subjects.jsonl` 바이트 동일 (`45a02f0297fb`).
- `split` → split_hash `8bfd4ab54f52…` = pilot 기술 분할과 같음 (outer·inner 경계 동일, pilot 6 · main pool 25, outer test [5,5,5,5,5]). 새 folds.json 의 `config_hash` 는 `6498596a` (기존 파일은 09-18 config 판 `fd6c8a27` — split_hash 는 config 에 의존하지 않음). `external_folds.json` 도 쓰였으나 쓰지 않음 (outer 9 없음).

## BQ.3 단계 시간 (driver.log, UTC)

| 단계 | 시작 → 끝 | 벽시계 | rc |
|---|---|---|---|
| prep (prepare·거르기·split) | 06:21:22Z | 수 초 | 0 |
| inner fit 480 (k=4) | 06:22:44Z → 10:49:34Z | 4 h 27 m | 실패 0 |
| `select-ad` × 5 | 10:49:34Z → 10:49:36Z | 2 s | 전부 0 |
| outer fit 60 (k=4) | 10:49:36Z → 11:31:05Z | 41.5 분 (fit 당 약 142–176 s) | 실패 0 |
| `evaluate` (n_fits 60) | 11:31:05Z | 약 1 s | 0 |
| `report` | 11:31:06Z | 약 1 s | 0 |

`run_all.log` `ALL_RC=0`, `driver.log` `ALLDONE`. inner fit 벽시계는 15:15 마감 시험과 겹친 동안 157–172 s, 그 마감을 중단한 뒤 133–146 s (첫 fit 학습 부분 55.9 s, 0.0445 s/epoch, peak GPU 143 MB). GPU 0 에 다른 사용자 프로세스 약 19 GB 동시 상주.

## BQ.4 산출물 sha256 (h197 data root `pilot_e2e/20260926_1515c/`, 커밋 안 함)

- 요약 (`summary/`, 틀 `.backup/slot_2015c/e2e_summary.py` — 읽기만, 덮어쓰기 거부): `e2e_summary.json` `c639b1fb8cbc…`, `fit_list.json` `8eba4d23e1e2…` (경로·fit_id·checkpoint sha256 540 행 — 요약의 `fits.list_sha256`), `best_epochs.json` `85af06b39619…`.
- fit **540** (inner 480 · outer 60), checkpoint 빠짐 0, fit_id 고유 540.
- split `folds.json` `06b64ab0afe7…` · `external_folds.json` `e18366f36242…`. `selection.json` o0 `933ad373f3f4…` · o1 `211687f2afc1…` · o2 `fa2e2aed061d…` · o3 `e8d35410da06…` · o4 `ec839402ce70…`. `evaluation.json` `e5e9c1ae605a…` · `run_predictions.jsonl` `d2259b79a237…`. `statistics.json` `4832b102b8d6…`.
- **구현 선택 (표시함)**: 요약 3 파일은 release `reports/` 로 복사하지 않고 gate 새 블록에 data root 상대 경로와 sha256 만 적는다 (`data_root_outputs` — `artifacts` 가 아니므로 17번 검사 대상 아님, 2번 수 192 그대로). 이유: run 단위 산출물이고 `e2e_summary.json` 에 아래 BQ.5 의 틀 오류 필드가 있다. 명세 4 (`implementation_lock.json`) 에서 이 sha 들을 다시 재어 넣는다.

## BQ.5 선택 기록 (성능 해석 안 함)

- 선택 config: o0 1 · o1 1 · o2 0 · o3 1 · o4 4. 공통 E: o0 1252 · o1 1252 · o2 1256 · o3 1252 · o4 1252.
- 선택 config 의 inner best epoch (cell 4 × inner 3 = 12 개, `best_epochs.json`): o0 1250–1264 · o1 1250–1264 · o2 1250–1263 · o3 1250–1258 · o4 1250–1260 — 전부 최소 epoch 1,250 에서 14 epoch 안 (early stopping 이 최소치 직후 멈춤). pilot 규모 특성인지 규칙상 문제인지는 판단하지 않았다.
- **정정 (기록)**: `e2e_summary.json` 의 `selection.*.best_epoch_min` = 0 은 요약 틀 오류다 — selection.json `best_epochs` 행의 `inner_fold` 정수 (0–2) 까지 숫자로 모았다. 파일은 덮어쓰지 않고 행의 `best_epoch` 만 뽑은 `best_epochs.json` 을 따로 두었다. 위 값은 `best_epochs.json` 이다.

## BQ.6 acceptance 관련 관측

- T11 가드 (rev68, training 라벨 두 class): 540 fit 에서 걸리지 않음 (실패 0).
- T10 (GPU 저장/재로드 근거): CLI `evaluate` 는 `checkpoint.pt` 를 재로드하지 않고 존재·sha256 만 기록한다 (`cli.py` grep — `torch.load`·`load_state_dict` 없음; `fitting.py` 의 `load_state_dict` 는 inner best 가중치 복원). 따라서 이 end-to-end 는 GPU 저장 checkpoint 재로드 근거를 만들지 않는다 — 명세 4 에서 재로드 대조 (cuda 저장 → 로드 → 창 예측 재계산 = `window_predictions.jsonl`) 를 넣을지 구현 선택으로 정한다.
- fit 없는 상태의 마감 (h197 11:34:25Z–11:44:00Z): 시험 1173 passed / 12 skipped, 해시 192/192, 인용 0, 잠금 45/45, 창 4,728 — 전부 rc=0 (HEAD `72cc1b3`).

## BQ.7 확인하지 못한 것

- `evaluation.json`·`statistics.json` 내용 (sha 만 — 성능 해석 금지 범위와 별개로 필드 검토도 안 함), 선택 config 밖 칸별 best epoch 분포, fit 별 GPU peak 집계 (fit_report 에 있음), T10 재로드 대조.
- CLI 가 상한을 덮지 않고 pilot 규모를 돌 방법은 만들지 않았다 (CLI 계약 변경 — 범위 밖). main 규모에서는 최소 epoch 295 ≤ 400 이라 덮기가 필요 없다 (결정 15 절 5 계산).


# 부록 BR — 결정 21 명세 4: 구현 잠금 `locks/implementation_lock.json` (rev70–rev71, 2026-09-26 22:15 예약 슬롯)

선생님 결정 21 원문 (09-26 11:1x 기록): "(가) `implementation_lock.json`을 만들고 G2 check를 채운 뒤 main OOF로 갑니다. 담을 내용은 환경, code/config hash, acceptance 결과, pilot end-to-end입니다. …" 이 부록은 명세 4 (잠금 파일) 만 다룬다. G2 check 채우기 (명세 5) 와 main OOF 착수 승인은 아니다.

## BR.1 근거와 필드

지침서 WI-06 출력 문장: "runnable CLI와 실제 `--help`, acceptance 결과, 환경 lock, code/config hashes, `locks/implementation_lock.json`". 이것을 새 스크립트 `scripts/h197/27_build_implementation_lock.py` 의 필드로 옮겼다.

| 필드 | 내용 |
|---|---|
| `environment` | python 3.11.5 · torch 2.10.0+cu128 · CUDA 12.8 · cuda 사용 가능 · GPU NVIDIA GeForce RTX 3090 Ti · `pip freeze --all` 61 줄 전체와 sha256 (저장소 자신 `mobse` 는 뺌 — BR.3) |
| `code` | `mobse/v2/*.py` code_hash `804d6ee17625…` (측정 잠금과 같은 정의) + 모듈별 sha256 |
| `configs` | main `2a7d7d7f` · pilot `6498596a` · external `576f6068` (config_hash) + 파일 sha256 |
| `cli` | 최상위 + 하위 명령 11 개의 실제 `--help` 텍스트와 sha256 (COLUMNS=100 고정, 12 개) |
| `acceptance` | 대응표 v2 (`reports/acceptance_map_t01_t16_v2.json`, 전부 16 · 부분 0 · 없음 0) + pytest junit (data root `impl_lock/20260926_2215d/pytest_junit.xml`) 합계 1183 passed · 12 skipped · failed 0, 대응표 명명 시험 전부 통과 |
| `pilot_end_to_end` | gate rev69 `data_root_outputs` 7 개를 data root 에서 다시 재어 전부 일치, `run_all.log` `ALL_RC=0`, 로그 3 개 sha256 |
| `measurement_lock` | lock_hash `9b7b11cf8576` 과 파일 sha256 (참조) |
| `t10_gpu_reload` | `not_done` (구현 선택 — CLI evaluate 는 checkpoint 를 재로드하지 않는다) |

## BR.2 생성 결과 (h197, 2026-09-26T13:28:53Z)

- HEAD `ccb5587` (rev70 커밋), 작업트리 깨끗. 구현 잠금 lock_hash `bcf1fec22676`, 파일 sha256 `f2abd2735164…`, 143,250 bytes.
- junit 은 마감 1단계 (13:18:59Z–13:27:42Z) 를 `--junitxml` 로 돌려 얻었다. 그 실행은 rev70 커밋 직전 작업트리 (내용이 `82d767e`·`ccb5587` 과 같음) 에서 돌았다. sha256 `6aa7023543a6…`.
- `--verify` 38/38 일치 (13:29:01Z). 스크립트 정정 (BR.3) 뒤 `PYTHONPATH=.` 없이·있이 두 번 다시 돌려 38/38 (13:30:46Z 전후).

## BR.3 정정: pip freeze 가 호출 방식에 따라 한 줄 달라짐

건식 점검 (`PYTHONPATH=.`) 과 생성 (없이) 의 `pip freeze` sha 가 달랐다. h197 에서 두 방식을 diff 하니 `PYTHONPATH=.` 판에만 `mobse==0.1.0` 한 줄이 있었다 (61 대 62). 저장소 코드는 `code` 절이 기록하므로 `freeze_lines` 가 이름이 `mobse` 인 줄을 빼도록 고쳤다 (rev71). 잠금 파일은 생성 때 이미 61 줄이라 다시 만들지 않았다 — 정정 뒤 두 방식 모두 38/38. 시험 1 개 추가 (`test_freeze_lines_drop_the_repository_package_and_sort`). 따라서 잠금의 `acceptance.pytest_counts` (1183 passed) 는 이 시험 추가 전 수다 — T01–T16 명명 시험과 `mobse/v2` 는 그 사이 바뀌지 않았다. rev71 마감의 시험 수는 커밋 메시지와 인수인계 문서에 적는다 (보고서에 두면 gate 의 보고서 sha 와 어긋난다).

## BR.4 구현 선택 (표시)

- 생성과 검증을 한 스크립트에 둠 (`--verify`). 검증은 git HEAD 를 대조하지 않는다 (잠금을 커밋하면 HEAD 가 바뀐다 — 기록만).
- pytest 는 스크립트가 돌리지 않고 마감 1단계 junit 을 받는다. junit 은 data root 아래만 허용 (`/tmp` 거부).
- 깨끗한 작업트리에서만 생성, 덮어쓰기 거부 (`--overwrite` 없음). 대응표에 부분·없음이 있거나 실패 1 건·명명 시험 누락·skip 이 있으면 생성 거부. pilot e2e sha 가 하나라도 다르면 생성 거부.
- T10 GPU 재로드 대조는 넣지 않았다.
- 마감 5단계에 27 `--verify` 를 넣을지는 명세 6 — 이번에는 넣지 않음.

## BR.5 시험·돌연변이

`tests/v2/test_implementation_lock_script.py` 7 함수 (junit 합계·parametrize 괄호·skip/실패/error·누락·섞인 결과·freeze 필터). 돌연변이 `.backup/slot_2215d/mut27.py` (`-B`) **7/7** 검출.

## BR.6 확인하지 못한 것

- T10 GPU 재로드 근거 (구현 선택으로 뺌).
- `--help` 텍스트가 python 판에 따라 바뀌는지 (h197 3.11.5 에서만 잼).
- G2 check (명세 5) — 아직 0 건. 판정 변경 없음.

# 부록 BS — 결정 21 명세 5: G2 check 채우기 (rev72, 2026-09-26 23:15 예약 슬롯)

## BS.1 근거 원문

- 계획서 §10 G2 행: "G2 Implementation lock | acceptance tests, config/code/environment hashes | leakage·연산·endpoint 검증 통과".
- 작업 지침서 WI-06: "출력: runnable CLI와 실제 `--help`, acceptance 결과, 환경 lock, code/config hashes, `locks/implementation_lock.json`. 완료 기준: T01–T16 및 pilot end-to-end 통과. … 이 gate 전에는 main 학습을 시작하지 않는다."
- 결정 21 (09-26 11:1x KST 기록) 이 정한 범위는 구현 잠금을 만들고 G2 check 를 채우는 것까지다. main OOF 착수 승인이 아니다.

## BS.2 추가한 check 5 개 (`gates[2].checks`)

| # | check | 근거 원문 | result | 근거 |
|---|---|---|---|---|
| 0 | acceptance tests T01–T16 | §10 필수 산출물 · WI-06 완료 기준 | pass | 대응표 v2 (`reports/acceptance_map_t01_t16_v2.json`, 부록 BP) 전부 16 · 부분 0 · 없음 0. 구현 잠금 `acceptance`: 명명 시험 89 개가 T-ID 16 개 전부에서 통과 (junit 1183 passed / 12 skipped / 0 failed, 부록 BR.2) |
| 1 | config/code/environment hashes | §10 필수 산출물 · WI-06 출력 | pass | 구현 잠금 lock_hash `bcf1fec22676` (code_hash `804d6ee17625`, config_hash main `2a7d7d7f` · pilot `6498596a` · external `576f6068`, 환경 python 3.11.5 · torch 2.10.0+cu128 · CUDA 12.8 · pip freeze 61 줄 sha). 이번 슬롯 h197 (HEAD `89fd941`, 2026-09-26T14:15Z) `--verify` 38/38 |
| 2 | runnable CLI and actual --help | WI-06 출력 | pass | 구현 잠금 `cli`: 최상위 + 하위 명령 11 = `--help` 12 개 텍스트·sha. 실행 가능성은 pilot end-to-end (check 3) 가 CLI 하위 명령으로 돈 것으로 봄 |
| 3 | pilot end-to-end | WI-06 완료 기준 | pass | 부록 BQ: prepare → split → fit 540 → select-ad 5 → evaluate → report, `ALL_RC=0`, 실패 0. 구현 잠금 `pilot_end_to_end.outputs_match_gate` true (gate rev69 sha 7 개 재측정 — `--verify` 가 매번 다시 잰다) |
| 4 | leakage·연산·endpoint verification | §10 다음 단계 조건 | pass | 아래 BS.3 묶음의 T-ID 가 check 0 에서 전부 통과 |

## BS.3 구현 선택 (표시)

- check 를 원문 문구 단위로 나눴다 (§10 두 칸 + WI-06 출력·완료 기준). 하나로 묶지 않은 이유: 근거 산출물이 서로 다르다.
- "leakage·연산·endpoint" 를 지침서 §4 T-ID 에 대응시킨 것은 슬롯의 해석이다: leakage = T03 (subject isolation) · T04 (frozen transform) · T12 (selection boundary), 연산 = T05–T10 (graph/null · ROI alignment · FC information · routing · mixture · backend/checkpoint), endpoint = T13 (endpoint) · T14 (statistical unit). 나머지 T01 · T02 · T11 · T15 · T16 도 check 0 에서 통과한다. 선생님이 다른 묶음을 원하시면 check 4 의 note 만 바뀐다 (판정 근거는 같은 junit).
- G2 `status` (`planned`) 와 `unresolved` ("blocked by G0") 는 바꾸지 않았다 — 결정 21 범위가 check 채우기까지다. G2 `artifact_hashes` 도 비워 둔다 (구현 잠금 sha 는 rev71 블록 `artifacts` 에 있다).

## BS.4 한계

- T10: 지침서 §4 문단 "GPU 저장/재로드는 해당 backend의 근거를 기록한다" 의 근거는 없다 (구현 잠금 `t10_gpu_reload: not_done`). T10 기대 결과 자체는 CPU 시험으로 충족.
- pilot end-to-end 는 A–D 경로만 (S · NG · SG · `report-comparison` 제외, 부록 BQ.1). pilot 규모에서는 CLI 상한을 프로세스 안에서 덮어야 돌았다 (CLI 인자로는 불가 — 부록 BQ.1).
- 수용 시험 대응은 시험 이름·존재·통과를 기계로 확인한 것이고, 시험이 기대 결과를 실제로 검사하는지는 읽어서 판단한 것이다.

## BS.5 정정

부록 BR.5 의 "7 함수" 는 오기다 — `tests/v2/test_implementation_lock_script.py` 는 6 함수 7 경우 (parametrize 포함) 다.

# 부록 BT — 착수 전 측정: 스레드 고정 (pilot 기술 분할, main pool 미사용) (rev73, 2026-09-28)

main OOF 착수 전에 처리량만 재는 가역 측정이다. 결정 23 (착수 승인) 직전 슬롯에서 돌았고 main pool 을 쓰지 않았다.

## BT.1 방법

- 산출 h197 data root `pilot_threads/20260928_thr2/`. 틀 Mac `.backup/slot_thr_0928/{thr_driver.py, thr_setup.sh, thr_compare.py}` (gitignore 영역 — 커밋 안 함).
- pilot 기술 분할 outer 0 의 inner fit **96 개**, 동시 실행 k=4, 프로세스당 `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=2`.
- 대조 (base) 는 같은 fit 을 스레드 고정 없이 돌린 앞선 판이다. **같은 결과가 나오는지**와 **벽시계**를 함께 본다.
- 창 구간 `driver.log` 2026-09-28T06:06:58Z–06:37:14Z.

## BT.2 결과 (`compare.txt`, sha256 `f15c8cd601df…`)

| 항목 | 값 |
|---|---|
| fit 수 | 96 |
| 창 예측 동일 | 96 / 96 |
| checkpoint 동일 | 96 / 96 |
| eval_loss 동일 | 96 / 96 |
| 차이 목록 | 빈 목록 |

| 벽시계 (s) | 중앙 | 최소 | 최대 | 합 |
|---|---:|---:|---:|---:|
| 스레드 2 고정 | **73.5** | 65.3 | 93.6 | 7,191.3 |
| 대조 (고정 없음) | **158.9** | 121.2 | 175.0 | 14,874.1 |

- 학습 자체는 거의 같다: s/epoch 중앙 0.0512 → 0.0527, 학습 시간 중앙 64.4 s → 66.4 s (**조금 늘었다**).
- 줄어든 것은 학습 밖 CPU 단계다. 합계로 2.07 배 (14,874.1 / 7,191.3).

## BT.3 구현 선택 (표시)

- 대조군을 이 슬롯에서 다시 돌리지 않고 앞선 판의 기록을 썼다 (가역 판단, 시간 절약).
- 산출물은 data root 에 두고 저장소에 커밋하지 않는다 (release `fits/` 는 `.gitignore` 밖 — 부록 BQ.4 와 같은 선택).

## BT.4 확인하지 못한 것

- main 규모 (126 명·480 fit) 에서 스레드 2 가 최적인지. 잰 것은 pilot 규모뿐이다.
- 벽시계 감소의 원인을 단계별로 분해하지 않았다 (학습 밖 CPU 단계라는 것까지만).

# 부록 BU — 결정 23: A–D main OOF 실행 (WI-07) (rev73, 2026-09-28)

## BU.1 결정 원문과 범위

선생님 결정 23 (2026-09-28 15:4x KST, 대화): **"main OOF 착수 승인"**.

**정한 것**: A–D main OOF — WI-07 main inner 480 + outer 60 + select-ad 5 + evaluate + report.
**정하지 않은 것**: null 민감도 (WI-09), 외부 PIOP2 (WI-08), gate `status`·"blocked by G0" 표기, 결과를 본 뒤의 설계·grid·δ·N 변경 (계획서 §3·§8 금지).

## BU.2 산출 위치와 preflight

- 산출 h197 data root `main_oof/20260928_1cd4054_main_a2/` (**구현 선택** — 저장소 release `fits/` 는 `.gitignore` 밖).
- attempt 1 (`…_main`) 은 코드 사본 대조를 `diff -r` 로 해서 미추적 파일 때문에 멈췄다 (fit 0). 남겨 두고 **추적 파일 sha256 대조**로 attempt 2 를 돌렸다. 재발 방지: 코드 사본 대조는 추적 파일 sha256 으로 한다.
- 구동기 `main_driver.py` sha256 `b252d579394a…` + `main_setup.sh`.
- preflight: HEAD `1cd4054`, 작업트리 깨끗, 측정 잠금 45/45, 창 파일 rc=0, 구현 잠금 38/38, gate 해시 rc=0.
- 환경 (`env.txt`): python 3.11.5 · torch 2.10.0+cu128 · CUDA 12.8 · cuda 사용 가능 True.

## BU.3 입력 sha256 (`input_sha256.txt`)

| 입력 | sha256 앞 16자 |
|---|---|
| `derivatives_v3/splits_piop1_p7/folds.json` | `242ba87d6101f704` |
| `derivatives_v3/cohort_piop1/subjects.jsonl` | `5ab1933922027dee` |
| `derivatives_v3/windows_piop1.jsonl` | `0750c81c0670df1f` |
| `configs/redesign_v1/main.yaml` | `ef4b16509f2da80c` |
| `main_driver.py` | `b252d579394a0a58` |

## BU.4 단계 시간 (`driver.log`, UTC)

| 단계 | 시각 | 비고 |
|---|---|---|
| 시작 | 06:44:36Z | `stage=all k=4 threads=2 outers=[0,1,2,3,4]` |
| inner 480 | 06:44:36Z → 09:28:35Z | **2 h 44 m**, 실패 0 |
| select-ad 5 | 09:28:37Z → 09:28:46Z | 전부 rc=0, `stage select fails=0` |
| outer 60 | 09:28:46Z → 09:55:08Z | **26.4 분**, 실패 0 |
| evaluate | 09:55:09Z | rc=0, `n_fits=60` |
| report | 09:55:10Z | rc=0 |
| 종료 | 09:55:10Z | `ALLDONE`, `run_all.rc` = `ALL_RC=0` |

## BU.5 WI-07 완료 기준 (`summary/completion_check.json`, sha256 `1635d855f8c1…`)

`.backup/slot_thr_0928/main_check.py` 가 산출물을 다시 읽어 셌다. **전부 충족.**

| 검사 | 값 |
|---|---:|
| inner fit report | 480 |
| inner best epoch 범위 | 295 – 312 (295 미만 0) |
| driver rc≠0 줄 | 0 |
| outer fit | 60 |
| primary checkpoint 고유 | 60 (report 와 sha 불일치 0) |
| 창 예측 행 | 12,096 = 126 × 2 × 4 × 3 × 4 |
| run 예측 행 | 1,008 = 126 × 2 × 4 |
| 예측된 subject | 126 (= main pool) |
| (subject, 칸) 쌍 | 504 — 전부 24 행, 전부 outer fold 하나 |
| 학습 subject 가 자기 test 예측에 섞임 | **0** |
| 배정 밖 outer fold 예측 | **0** |

## BU.6 선택 기록 (성능 해석 안 함)

| outer | config | 공통 E | selection sha256 앞 12자 |
|---|---:|---:|---|
| o0 | 0 | 298 | `375b58ecb3b6` |
| o1 | 0 | 298 | `6c78a9abe83a` |
| o2 | 4 | 297 | `59fc09a2e4fc` |
| o3 | 1 | 297 | `b5421eb82b8a` |
| o4 | 0 | 298 | `6adc4ee3bbe0` |

## BU.7 산출물 sha256 (h197 data root 상대, 커밋 안 함)

| 파일 | sha256 |
|---|---|
| `…_main_a2/summary/completion_check.json` | `1635d855f8c12ab6f7d29a37ac752c0275a084b226c6e1678c494a531553a0ba` |
| `…_main_a2/evaluate/evaluation.json` | `02f6ac5e1feb665b0bd131db6d16d1833c710487a61361e90b81ac41b17ecb6c` |
| `…_main_a2/evaluate/run_predictions.jsonl` | `e377a18939de80306dd16017d6b62fe0f065e55d4fbc0178d7b2223f0e769184` |
| `…_main_a2/report/statistics.json` | `f0a9847bb61ca762ed69f3a72bdee006e085adf1b91b14950f89c799d0064569` |
| `…_main_a2/driver.log` | `adcd415b16c4903091210aa3d169b183586cb42028e093abab27df5a91b1f12c` |

## BU.8 확인하지 못한 것

- 산출물은 17번 해시 검사 대상이 아니다 (data root — 부록 BQ.4 와 같은 구현 선택). gate evidence `data_root_outputs` 블록에만 적힌다.
- attempt 1 의 부분 산출물은 지우지 않고 남겨 두었다 (`…_main`, fit 0).

# 부록 BV — main OOF primary 결과 (rev73, 2026-09-28 19:1x KST 열람)

결정 24 항목 1 ("결과 열람 후 보고") 에 따라 `report/statistics.json` (sha256 `f0a9847bb61c…`) 을 그대로 옮긴다. 해석 규칙은 계획서 §8 이고, 이 부록은 규칙을 새로 만들지 않는다.

## BV.1 통계 설정 (파일 기록)

- N = 126, 통계 단위 subject (group 재표집), group = subject.
- paired bootstrap seed 9001 · 10,000 회, 칸 간 **같은 재표집** (`shared_across_cells: true`).
- primary CI 는 97.5% (백분위 1.25–98.75), 보조·칸별은 95% (2.5–97.5). δ = 0.02, threshold 0.5.
- `config_hash` `2a7d7d7f`, `split_hash` `ace5f4a41446…`, fit·evaluator·report code_hash 전부 `804d6ee17625…`.

## BV.2 primary 두 contrast

| 비교 | 점추정 | CI (97.5%) | 파일 판독 문구 |
|---|---:|---|---|
| **H1 A−B** (입력 의존 routing) | **+0.1548** | [+0.0952, +0.2143] | "하한 0.0952 > delta 0.02 — 선택한 최소 효과 이상의 우월성 지지" |
| **H2 A−C** (정렬된 brain bank 대 공동 ROI-permuted null) | **−0.0159** | [−0.0516, +0.0198] | "CI 가 0 을 포함 — 불확실. 비유의를 효과 없음·동등성으로 바꾸지 않는다" |

`both_primary_lower_gt_0: false` → 계획서 §8 에 따라 **두 기여를 함께 주장할 수 없다.**

## BV.3 보조 contrast와 칸별 balanced accuracy

| 항목 | 점추정 | 95% CI | 판독 |
|---|---:|---|---|
| interaction (A−B)−(C−D) | +0.0516 | [+0.0040, +0.0992] | 하한 > 0 이나 δ 0.02 이하 — 추가 기여는 지지, 실질적 우월성 확정 아님 |
| A | 0.8770 | [0.8373, 0.9167] | — |
| B | 0.7222 | [0.6746, 0.7698] | — |
| C | 0.8929 | [0.8532, 0.9325] | — |
| D | 0.7897 | [0.7421, 0.8333] | — |

## BV.4 G3 판정 (파일 `g3_verdict`)

- `completeness_and_consistency: pass`, `significance_is_gate: false`.
- 검사 5 건: run_predictions sha256 = evaluation.json 기록 · run 행 재계산 b_i = evaluation.json subject_scores · 재계산 subject 차이 = evaluation.json · cell BA = evaluation.json · complete-case, cell 간 subject 동일, 부적격 0.

## BV.5 caveat (파일 기록 그대로)

"내부 OOF bootstrap 은 고정된 학습 결과에 조건부이며 training-set 변동을 완전히 반영하지 않는다 (계획서 §8)."

## BV.6 확인하지 못한 것

- H2 가 불확실하게 나온 **이유**. 이 부록은 결과만 옮긴다. 판단 재료는 `docs/handoff/mobse_h2_midreview_2026-09-29.md`·`mobse_interpretation_2026-09-29.md` 에 있고, 그 두 문서는 결정이 아니다.
- 검정력은 main 전부터 낮게 기록돼 있었다 (G1 check [6]: δ=0.02 에서 P(하한>0) 0.048–0.191). 이번 결과는 그 기록과 어긋나지 않는다.

# 부록 BW — 결정 24: 보조 비교 S 후보 4 · NG · SG (rev73, 2026-09-28)

## BW.1 결정 원문과 판단 근거

결정 24 (2026-09-28 19:1x KST) 항목 2 원문: **"S 후보와 구조 비교(NG·SG): 1의 결과에 종속적일 경우 결과 확인 후 권고, 독립적이면 바로 수행"**.

세션 판단 (보고): S 4 후보 grid·선택 규칙 (§6, 개정 P11), NG·SG 학습·선택 규칙 (결정 14), A−S·A−NG·A−SG 보조 contrast (§8 개정 P12 — main 결과 전 사전 등록) 가 모두 main 결과와 무관하게 정해져 있고, 실행 입력은 main pool 분할과 main evaluate 산출물뿐이다. 결과가 S·NG·SG 의 실행 여부·방식을 바꾸는 규칙은 계획서에 없다 (grep 확인). → **독립으로 보고 바로 실행.**

## BW.2 v1 결함과 정정 (재발 방지)

- `aux_driver.py` v1 이 S 후보 이름을 "S1" 로 줄여 써서 `fit-s` 의 argparse 가 거부했다 (rc=2, fit 미실행 480 호출). smoke 판 (`main_oof/20260928_aux_smoke/`) 에서 드러났다.
- v1 은 NG·SG inner 240 을 끝낸 뒤 11:14:12Z 멈췄다 (`run_all_v1.rc` = `ALL_RC=1`). `aux_resume.sh` 가 v2 로 **같은 root 에서** 이어 돌았다 (11:14:16Z `RESUME`, 끝난 fit 은 건너뜀). v2 이후 fit rc≠0 은 **0**.
- **재발 방지**: 새 구동기는 CLI 인자 값을 코드 상수에서 가져오거나, 첫 fit smoke 를 먼저 돌린다.

## BW.3 단계 시간 (`driver.log`, UTC) — 산출 `main_oof/20260928_1cd4054_aux_a1/`

| 단계 | 시각 |
|---|---|
| 시작 | 10:07:18Z (`k=4 threads=2`, main 산출 참조) |
| NG·SG inner 240 | 10:07Z → 11:14Z |
| v2 RESUME | 11:14:16Z |
| S inner 480 (`fit-s`) | 11:14Z → 11:48Z |
| select 15 (`select-comparator` 10 + `select-s` 5) | → 11:48:43Z, `stage select fails=0` |
| outer 43 | 11:50:18Z → 12:01:5xZ |
| `report-comparison` | 12:02:00Z rc=0 |
| 종료 | 12:02:00Z `ALLDONE`, `run_all.rc` = `ALL_RC=0` |

outer 43 = NG 15 + SG 15 + S 13 (S 는 MLP 4 fold × 3 seed + logistic 1 — logistic 은 seed 가 없다). 세션이 산출물을 다시 세어 확인했다.

## BW.4 완료 점검 (세션 재집계)

- S outer 예측 2,624 행, subject 126.
- **학습 subject 가 test 예측에 섞임 0**, 배정 밖 fold 0, 각 S outer fit 의 `fit_subjects` = 그 fold 의 train 전부.
- S 미수렴 제외 0 (5 fold 모두). 누설 점검은 코드 (`_load_s_outer`) 와 세션 독립 재집계 두 번 다 0.

## BW.5 선택 기록 (성능 해석 안 함)

| outer | S 후보 | S 설정 | S outer E | NG config | NG outer E | SG config | SG outer E |
|---|---|---|---:|---:|---:|---:|---:|
| o0 | S4 (FC Fisher-z MLP) | config=3 | 295 | 0 | 299 | 0 | 297 |
| o1 | S4 | config=4 | 295 | 0 | 299 | 0 | 299 |
| o2 | S4 | config=4 | 295 | 0 | 298 | 1 | 304 |
| o3 | **S3 (FC Fisher-z logistic)** | C=10000 | 없음 | 0 | 298 | 0 | 300 |
| o4 | S4 | config=2 | 296 | 3 | 304 | 1 | 302 |

## BW.6 결과 (`report_comparison/comparison_statistics.json`, sha256 `a62e6239fbab…`, 21:2x KST 열람)

**전부 보조 지표다 — primary 가 아니다.** 95% 기술적 CI, main 과 **같은 bootstrap 재표집** (`same_indices_as_report: true`, seed 9001 · 10,000 회, N=126).

| 비교 | 점추정 | 95% CI | 파일 판독 문구 |
|---|---:|---|---|
| **A−S** (MoBSE 대 최선 단순 기준선) | **−0.1230** | [−0.1627, −0.0833] | "상한 −0.0833 < 0 — 반대 방향" |
| A−NG (그래프 없는 fusion MLP) | −0.0119 | [−0.0516, +0.0278] | "CI 가 0 을 포함 — 불확실" |
| A−SG (평균 그래프 하나) | +0.0675 | [+0.0159, +0.1190] | 하한 > 0 이나 δ 이하 — 추가 기여 지지, 실질적 우월성 확정 아님 |

칸별 balanced accuracy (95%): **S 1.0000 [1.0000, 1.0000]** · NG 0.8889 [0.8452, 0.9286] · SG 0.8095 [0.7659, 0.8532].

- 읽는 법 (기록): 이 target (emomatching 대 workingmemory run identity) 은 FC Fisher-z 를 쓰는 단순 분류기 (S3·S4) 가 126 명 전원의 두 run 을 모두 맞혀 완전히 가른다. MoBSE A 는 그보다 12 %p 낮다. 계획서 §8 이 A−S 를 보조로 두었으므로 **primary 판정은 바뀌지 않는다.**
- 결과를 본 뒤 설계·grid 를 바꾸면 새 exploratory version 이다 (계획서 §3·§4-5).
- `not_reported`: parameter·비용 집계는 이 명령 범위 밖이다 (계획서 §6 — 별도 조각).

## BW.7 확인하지 못한 것

- 단순 FC 기준선이 100% 인 이유 (target 자체가 FC 로 쉽게 갈리는지, 다른 요인이 있는지). 추가 분석은 계획 밖이라 하지 않았다. 선생님 결정 25-6 으로 **새 학습 없는 진단**만 하기로 정해졌고, 이 부록 시점에는 아직 하지 않았다.
- NG·SG 실자료 parameter/비용 집계 (`not_reported`).
- smoke 판·v1 부분 산출물은 지우지 않고 남겨 두었다.

# 부록 BX — 결정 25: gate 표기 적용과 09-28 실행 기록 (rev73, 2026-09-29)

## BX.1 결정 원문과 수집 방식

2026-09-29 09:5x KST, 선택 TUI 5 문항으로 받았다. 선택지 문안은 `docs/handoff/mobse_main_oof_2026-09-28.md` "gate 표기 권고 1–6", `mobse_h2_midreview_2026-09-29.md` 3절 (가)/(나)/(다), `mobse_interpretation_2026-09-29.md` 3절 (PIOP2·WI-08) 에서 그대로 가져왔다. 원문 기록은 `docs/handoff/mobse_decisions_2026-09-29.md`.

| # | 물음 | 선택 |
|---|---|---|
| 25-1 | gate evidence 표기 | 권고 1–6 전부 적용 |
| 25-2 | H2 (A−C) 방향 | (다) WI-09 만 먼저 (PIOP2 미사용) 후 (나) 판단 |
| 25-3 | PIOP2 외부 평가 (WI-08) 착수 | 지금은 승인하지 않음 |
| 25-4 | A−S 처리 | 추가 분석 후 판단 |
| 25-5 | WI-09 일정 | 기록·커밋 마친 뒤 착수 |
| 25-6 | A−S 추가 분석 범위 | 새 학습 없는 진단만 |

이어서 2026-09-29 (대화): **"claude.ai Project 에 올리는 일은 하지말고 docs/handoff 문서 갱신만.., 그리고 개발 진행은 승인"** → 인수인계 정본은 저장소 `docs/handoff/` 하나로 하고, Project 사본 동기화는 하지 않는다.

## BX.2 rev73 이 바꾼 gate 표기 (결정 25-1 = 권고 1–6)

| gate | 이전 (rev72) | rev73 | 근거 |
|---|---|---|---|
| G0 Provenance | `conditionally_cleared`, unresolved U3·U6·U10 | **`cleared`**, unresolved 비움 | check 10/10 pass. U3·U6 은 낡은 표기, U10 은 G1 로 옮겨 적음 (권고 3) |
| G1 Measurement lock | `in_progress` | **`cleared_with_limitations`** (새 값) | check 판정은 `fail` 2 건 그대로 — [0] group_id·[6] δ 정밀도는 계획서 P4·§8 이 정한 알려진 한계 (권고 5) |
| G2 Implementation lock | `planned`, "blocked by G0" | **`cleared`**, unresolved 비움 | check 5/5 pass, 09-28 preflight 에서 구현 잠금 38/38 재확인, main 이 그 잠금 코드로 실행됨 (권고 2·4) |
| G3 Internal release | `planned`, "blocked by G0" | **`cleared`**, unresolved 비움, check 1 → 3 | 계획서 §10 조건 "완전성과 정합성 통과; 유의성 불요" 를 A–D (부록 BU·BV) 와 보조 비교 (부록 BW) 가 충족 (권고 1·4) |
| G4 External release | `planned`, U17 + "blocked by G0/G1" | `planned`, **U17 만** | "blocked by G0/G1" 삭제 (권고 4). status 는 그대로 (권고 6) |
| G5 Interpretation | `planned`, "blocked by G0" | `planned`, unresolved 비움 | "blocked by G0" 삭제 (권고 4). status 는 그대로 (권고 6) |

## BX.3 새 top-level 블록

- `thread_pinning_rev73` — 부록 BT.
- `decision23_main_oof_rev73` — 부록 BU·BV, `data_root_outputs` 5 개.
- `decision24_aux_comparison_rev73` — 부록 BW, `data_root_outputs` 1 개.
- `decision25_gate_status_rev73` — 이 부록. 결정 25 원문·표기 변경 목록·rev72 정정.

## BX.4 정정: rev72 `not_done` 의 "명세 6"

rev72 블록 `not_done` 은 "명세 6 마감 5단계에 27 `--verify` 추가 여부" 를 미결로 적었다. 그 뒤 2026-09-27 커밋 `1cd4054` (`docs(claude): add implementation lock verify as closure step 6`) 로 **마감 절차에 6단계로 추가됐다.** rev72 블록 자체는 그때의 기록이므로 고치지 않고, rev73 블록 `corrections` 에 적는다 (구현 선택 — 과거 revision 블록을 다시 쓰지 않는다).

## BX.5 구현 선택 (표시)

- G3 에 check 를 2 건 더했다 (A–D 완료 기준·보조 비교 완료). 권고 1 은 `status` 만 말했으나, `cleared` 의 근거를 gate 안에 남기려면 check 가 필요하다고 보았다. 판정 근거는 부록 BU.5·BV.4·BW.4 와 같은 산출물이다.
- G1 `status` 의 새 값 `cleared_with_limitations` 는 이 저장소에서 처음 쓰는 값이다 (권고 5 의 표현 그대로).
- 09-28 산출물은 data root 에 있어 17번 해시 검사 대상이 아니다. `data_root_outputs` 블록에만 적고, 값은 이 슬롯에서 h197 에서 다시 쟀다.

## BX.6 확인하지 못한 것

- G1 의 fail 2 건을 없앨 방법 (group_id 실자료·δ 정밀도) — 계획서 P4·§8 이 한계로 받아들인 항목이라 이번 범위 밖.
- `cleared_with_limitations` 를 읽는 쪽 (스크립트·시험) 이 새 값을 기대하는지 — 마감 절차에서 확인한다.

# 부록 BY — WI-09 null 민감도 (seed 1730–1733) (rev74, 2026-09-29)

## BY.1 결정과 범위

- 착수: 결정 25-2·25-5 (2026-09-29) — H2 방향 **(다)**, "WI-09 만 먼저 (PIOP2 미사용)", 일정은 "기록·커밋 마친 뒤".
- 구현: 결정 26 — 선생님 회신 원문 **"가. 로 진행"**.
- **범위는 null 민감도뿐이다.** WI-09 의 나머지 (routing 고정/shuffle, nuisance/time 기준선, 비용, window·atlas·GSR·K 민감도) 는 하지 않았다 — `reports/sensitivity.md` 는 아직 만들지 않는다.
- 재튜닝 없음: main 이 고른 config·epoch (`select/o*/selection.json` 의 `outer_plan`) 를 그대로 쓴다. inner 재실행 없음.

## BY.2 왜 240 fit 인가 (결정 26 (가))

`fit` CLI 는 null seed 를 config `bank.null_seed` 에서 읽고, `mobse/v2/config.py` 검증기가 그 값을 코드 상수 1729 로 잠근다. seed 를 바꾸면 `config_hash` 가 바뀌고 `evaluate` 는 fit manifest 의 `config_hash` 가 다르면 거부한다 (`cli.py:1738`). 그래서 main 의 A·B outer 예측을 그대로 붙일 수 없다.

- (가) 채택: seed 마다 A·B·C·D outer 60 fit 을 모두 돌린다 → **240 fit**. 이 중 seed 에 실제로 의존하는 것은 C·D **120** (계획서 수치) 이고, A·B **120** 은 `config_hash` 일치를 위한 재계산이다.
- (나) 기각: `config.py` 의 잠금을 풀면 측정 잠금 재생성 + gate 새 revision 이 따른다. `mobse/v2` 와 잠금은 **바꾸지 않았다.**
- null seed 는 구동기가 **프로세스 안에서만** `cli.load_config` 를 감싸 덮는다 (`null_cli.py`) — pilot end-to-end 가 `MAX_EPOCHS` 를 덮은 것과 같은 방식 (부록 BQ.1). 검증을 통과한 뒤 값만 바꾸고, 1729 가 아니거나 잠긴 민감도 목록 밖 seed 면 멈춘다.

## BY.3 착수 전 확인 — A 는 정말 null 과 무관한가

seed 1730 판으로 outer fold 0 의 `A_s42` 한 건을 돌려 main 과 대조했다 (`verify_ab/verify_ab.json`, sha256 `105316ef6499…`).

| 항목 | 값 |
|---|---|
| 창 수 | 208 (key 집합 동일) |
| `p_class1` 차이 | **0** |
| checkpoint sha256 동일 | **예** |
| `bank_id` 동일 | 예 |
| `null_seed` (민감도 / main) | 1730 / 1729 |
| `config_hash` (민감도 / main) | `fdbf7696` / `2a7d7d7f` |

→ 바뀌는 것은 기록 (config_hash·null_seed) 뿐이고 A 의 결과는 같다. 본 실행에서도 seed 마다 A·B 30 건씩 전부 main 과 같았다 (BY.5).

## BY.4 실행 (h197, 산출 `null_sens/20260929_97e434a_a1/`)

- HEAD `97e434a` (gate rev73 커밋), 작업트리 깨끗, 추적 파일 381 개 사본 동일.
- preflight 전부 rc=0: 측정 잠금 (19) · 창 파일 (25) · 구현 잠금 (27) · gate 해시 (17).
- 환경: python 3.11.5 · torch 2.10.0+cu128 · CUDA 12.8 · cuda True. k=4, 프로세스당 스레드 2.

| 단계 | 시각 (UTC) |
|---|---|
| verify-ab | 01:38:28Z → 01:40:27Z (1 fit, 119.6 s) |
| 시작 | 01:40:37Z (`seeds=[1730, 1731, 1732, 1733]`) |
| outer 240 fit | 01:40:37Z → 03:03:12Z — **1 h 22 m 35 s**, 실패 0 |
| evaluate 4 · report 4 | 03:03:13Z → 03:03:17Z, 전부 rc=0 (`n_fits=60` × 4) |
| 종료 | 03:03:17Z `ALLDONE`, `run_all.rc` = `ALL_RC=0` |

## BY.5 완료 점검 (`summary/null_sensitivity.json`, 산출물 재집계)

네 seed 모두 같은 값이다.

| 검사 | 값 |
|---|---:|
| outer fit | 60 |
| 고유 checkpoint | 60 |
| 창 예측 행 | 12,096 |
| 학습 subject 가 자기 test 예측에 섞임 | **0** |
| 배정 밖 outer fold 예측 | **0** |
| manifest 의 `null_seed` | 그 seed 하나 |
| manifest 의 `config_hash` | 그 seed 하나 (1730 `fdbf7696` · 1731 `0924b18e` · 1732 `e3a98487` · 1733 `f769e38e`) |
| A·B fit 을 main 과 대조 | 30 건 — **차이 0** |
| report `g3_verdict.completeness_and_consistency` | pass |

## BY.6 결과 — null 을 바꿔도 H2 는 불확실하다

primary (seed 1729) 는 main OOF 값이다 (부록 BV). A·B 는 null 과 무관하므로 다섯 판에서 모두 같다 (A 0.8770 · B 0.7222 · H1 A−B +0.1548 [+0.0952, +0.2143]).

| null seed | C | D | **H2 A−C** (97.5% CI) | interaction (95% CI) |
|---|---:|---:|---|---|
| **1729 (primary)** | 0.8929 | 0.7897 | **−0.0159** [−0.0516, +0.0198] | +0.0516 [+0.0040, +0.0992] |
| 1730 | 0.8770 | 0.7579 | 0.0000 [−0.0238, +0.0238] | +0.0357 [−0.0079, +0.0794] |
| 1731 | 0.8770 | 0.7579 | 0.0000 [−0.0357, +0.0357] | +0.0357 [−0.0079, +0.0833] |
| 1732 | 0.8770 | 0.7222 | 0.0000 [−0.0317, +0.0317] | 0.0000 [−0.0397, +0.0437] |
| 1733 | 0.8929 | 0.7659 | −0.0159 [−0.0437, +0.0119] | +0.0278 [−0.0079, +0.0635] |

읽는 법 (기록):

1. **A−C 는 다섯 판 전부 [−0.016, 0.000] 안에 있고, CI 가 모두 0 을 포함한다.** H2 가 불확실하게 나온 것은 하필 고른 순열 (seed 1729) 때문이 아니다. 해석 문서의 추정 (`mobse_interpretation_2026-09-29.md` 2절) 과 어긋나지 않는다.
2. **보조 interaction 의 판독은 null 에 따라 바뀐다.** primary 판에서는 하한 +0.0040 > 0 이었으나, 민감도 네 판은 모두 하한이 0 이하다 (CI 가 0 을 포함). 즉 "(A−B)−(C−D) 의 추가 기여" 라는 보조 판독은 **순열 하나에 기대고 있었다.** primary 판정은 바꾸지 않는다 (계획서 §8 — 민감도는 primary 에 역반영하지 않는다).
3. C 는 0.8770–0.8929 로 거의 움직이지 않고, D 가 0.7222–0.7897 로 더 흔들린다. interaction 의 변동은 주로 D 쪽에서 온다.
4. 순열 5 개는 분포를 만들기에 적다 (midreview 2절 약점 4). 이 표는 "퍼짐이 작다" 는 관측이지 null 분포 검정이 아니다.

## BY.7 산출물 sha256 (h197 data root 상대, 커밋 안 함)

| 파일 | sha256 |
|---|---|
| `null_sens/20260929_97e434a_a1/summary/null_sensitivity.json` | `5ddfee4b388324438ab5c660f3f78994e2f20481c4d973ee32dc839be7df6bf2` |
| `…/verify_ab/verify_ab.json` | `105316ef649937bae96c1d6c842067c6b253a398db6dcc95961636ec9c6fe667` |
| `…/report/s1730/statistics.json` | `b7b55b7b93c340aab993344b8b35ef49e9a18720e651df59ef56d5f9ee7dad40` |
| `…/report/s1731/statistics.json` | `0475562f941e486fe284061c9e998c06a09be2e7af47e776227e78e6f3b28619` |
| `…/report/s1732/statistics.json` | `c44a6e7065423a83745dbdffee78104af247c9eee1d1c1fc304a7f89a7ba1388` |
| `…/report/s1733/statistics.json` | `df3df8effd6ca5d1a5dc9f1de2d3511f9687fa5db5997674687543a022cce8d3` |
| `…/driver.log` | `c1f972774fe5220b0d87d160077c695d4a468f0c8bfa920347d71caa59547b93` |

구동기 `null_driver.py` `03607be3e99b…` · `null_cli.py` `a23c72e4718a…` (Mac `.backup/slot_wi09_0929/`, gitignore — 커밋 안 함).

## BY.8 확인하지 못한 것

- 순열 5 개로는 null 분포를 만들 수 없다. 공간 보존 null (spin) 이나 degree 보존 rewiring 은 계획 밖이다 (새 탐색 버전 후보 — midreview 3절 (나)).
- interaction 의 판독이 null 에 따라 바뀌는 이유 (D 의 변동) 를 더 파고들지 않았다 — 계획 밖.
- WI-09 의 나머지 항목 (routing 고정/shuffle, nuisance/time 기준선, 비용, window·atlas·GSR·K 민감도) 은 하지 않았다.
- A·B 120 fit 은 `config_hash` 검사를 통과시키기 위한 재계산이다. 결과가 같다는 것은 확인했지만 (BY.3·BY.5), 계산 자원은 썼다.
