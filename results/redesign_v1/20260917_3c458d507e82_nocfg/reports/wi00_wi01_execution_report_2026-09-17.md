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
