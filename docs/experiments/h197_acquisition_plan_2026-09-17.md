# h197 자료 확보 계획 — 2단계 (Wave 1 / Wave 2)

**2026-09-17 · 적용 프로토콜 v1.1 · release `20260917_3c458d507e82_nocfg`**

관련: [WI-00/WI-01 실행 보고서](../../results/redesign_v1/20260917_3c458d507e82_nocfg/reports/wi00_wi01_execution_report_2026-09-17.md) · [재설계 프로토콜](mobse_redesign_protocol_2026-09-17.md) · [작업 지침서](mobse_redesign_work_instructions_2026-09-17.md)

## 0. 역할 분담

**h197이 실행 호스트다.** 따라서 다음 차단 항목은 프로젝트 차단이 아니라 h197 작업 항목으로 재분류한다.

| ID | 재분류 |
|---|---|
| U13 | `.venv/bin/python` broken → h197의 실제 인터프리터를 `00_record_environment.sh` 로 고정 |
| U14 | torch·scipy·sklearn·nilearn·nibabel·pytest 부재 → h197 환경에서 해소 |
| U15 | OpenNeuro/S3 egress 차단 → h197에서 직접 다운로드 |
| U16 | 4 core / 3 GB / GPU 없음 → h197 사양으로 대체 기록 |

위 네 항목은 **이 세션의 원격 셸 제약이었고 프로젝트의 제약이 아니다.** 단, h197의 실제 값이 기록되기 전까지는 `resource_budget.md`(WI-03)를 작성할 수 없다.

## 1. 왜 2단계인가

Wave 1은 **메타데이터만** 받는다(sidecar JSON, confounds TSV, events TSV). 이것만으로 U1′·U2·U4·U5가 전부 해소되고, 결정적으로 **두 primary target의 native TR이 확정**된다.

그 확정이 Wave 2의 전제인 이유:

- target TR = **2.0초**면 emomatching 270초 / workingmemory 324초로 `[12,252)` 구간이 성립한다. 설계 그대로 진행.
- target TR = **0.75초**면 101.25초 / 121.5초로 **주분석 구간이 성립하지 않는다.** window 길이·개수·guard를 다시 설계해야 하고, 그러면 어떤 run이 적격인지도 달라진다.

후자에서 BOLD 본체를 먼저 받으면 수백 GB를 받아놓고 설계를 고치게 된다. Wave 1은 수백 MB 수준이므로 왕복 비용이 사실상 없다.

PIOP1 restingstate(0.75초, acq-mb3)와 PIOP2 restingstate(2.00초, acq-seq)는 로컬 원본 헤더로 이미 확정되었다. **두 cohort의 rest가 서로 다른 TR을 쓴다**는 사실이 target TR을 추정으로 메울 수 없는 이유다.

## 2. Wave 1 — 메타데이터

### 2.1 받을 것

`s3://openneuro.org/{ds002785,ds002790}` 에서 task ∈ {restingstate, emomatching, workingmemory} 에 대해:

| 경로 | 파일 | 해소하는 항목 |
|---|---|---|
| `<ds>/` | `dataset_description.json`, `participants.tsv`, `participants.json` | 코호트 기술 |
| `<ds>/` | `task-<task>_bold.json` | **BIDS inheritance** — TR이 run별 sidecar가 아니라 여기에만 있을 수 있다 |
| `<ds>/sub-*/func/` | `*task-<task>*_bold.json` | U1′ native TR, SliceTiming, TaskName |
| `<ds>/sub-*/func/` | `*task-<task>*_events.tsv(.json)` | U5 onset 원점 |
| `<ds>/derivatives/fmriprep/sub-*/func/` | `*task-<task>*desc-confounds_{regressors,timeseries}.tsv` | volume 수, U2 `non_steady_state_outlier*`, U4 24 motion·aCompCor·FD |
| 〃 | 같은 이름의 `.json` | U4 aCompCor 설명분산 순서 (계획서 §3.2가 요구) |
| 〃 | `*space-MNI152NLin2009cAsym*desc-preproc_bold.json` | derivative grid TR — raw와 불일치하면 명시적 실패 |

fMRIPrep 버전에 따라 confounds 파일명이 `desc-confounds_regressors` 와 `desc-confounds_timeseries` 로 갈리므로 **둘 다** 받는다.

### 2.2 실행

```bash
cd <repo>/scripts/h197
bash 00_record_environment.sh --python $(which python3) --out h197_environment.json
bash 01_wave1_fetch_metadata.sh --dest /data/aomic_wave1 --dry-run   # 목록·용량 먼저
bash 01_wave1_fetch_metadata.sh --dest /data/aomic_wave1
python3 02_wave1_audit.py --root /data/aomic_wave1 --out /data/aomic_wave1/wave1_audit
```

`02_wave1_audit.py` 는 표준 라이브러리만 쓰므로 h197에 numpy/pandas가 없어도 돈다.

### 2.3 산출물과 판정

- `wave1_runs.jsonl` — run 단위 레코드. `canonical_subject` 에 **dataset prefix가 들어간다**(U17 대응: PIOP1/PIOP2가 같은 `sub-0001…` 네임스페이스를 쓴다).
- `wave1_summary.json` — task별 TR/volume/제거volume 분포와 `blocker_verdicts`.
- `wave1_files.sha256` — 받은 파일 전수 해시.

`blocker_verdicts` 는 다섯 항목을 `resolved` / `still_blocked` 로 판정한다: `U1_native_tr_targets`, `U2_discarded_volumes`, `U4_nuisance_constructible`, `U5_events_origin`, `window_12_252_supported_for_targets`.

**주의:** `resolved` 는 "해당 정보가 존재한다"는 뜻이지 QC 통과를 뜻하지 않는다. 스크립트는 자체 fixture로 양성·음성 두 경우를 검사했다 — 열이 모자라거나 sidecar가 없으면 조용히 넘어가지 않고 `unresolved` 에 사유를 남긴다.

### 2.4 Wave 1 이후의 분기

| `window_12_252_supported_for_targets` | 다음 단계 |
|---|---|
| `resolved` | 설계 동결 → Wave 2 진행 |
| `still_blocked` | **프로토콜 §3.1 window 설계를 먼저 개정**하고 버전·사유를 기록한 뒤 Wave 2 |

## 3. Wave 2 — BOLD 본체

Wave 1 판정 후에만 실행한다.

```bash
bash 03_wave2_size_probe.sh > wave2_size_probe.txt   # 다운로드 없이 용량만 실측 (U26)
```

받을 것은 `derivatives/fmriprep/sub-*/func/*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz` 와 대응 brain mask다. 용량이 h197 디스크에 여유 있게 들어가지 않으면 subject 단위 **streaming**(다운로드 → ROI 추출 → 원본 삭제)을 설계에 포함한다 — 기존 `scripts/stream_aomic_extract.py` 가 이미 그 구조이나, 아래 §5의 결함을 고치지 않고 재사용해서는 안 된다.

## 4. 대상 규모

| dataset | subject | task | 비고 |
|---|---:|---|---|
| ds002785 (PIOP1) | 216 | restingstate, emomatching, workingmemory | primary |
| ds002790 (PIOP2) | 226 | 동일 | external (G4) |

로컬 보유 파생물 기준 PIOP1의 task별 보유는 emo 207 / WM 204 / rest 210이며, 세 task를 모두 가진 subject는 196명이다. **실제 원본 보유 수는 Wave 1의 run 수로 확정된다.**

## 5. 재추출 시 고쳐야 할 기존 코드 결함

`scripts/stream_aomic_extract.py` 계열을 그대로 쓰면 같은 오류가 재발한다. 줄 번호는 현재 작업 트리 기준으로 확인한 값이다.

| ID | 위치 | 결함 | 요구 |
|---|---|---|---|
| — | `stream_aomic_extract.py:485` | `--tr default=0.75` 를 모든 dataset·task에 적용. `RepetitionTime` 을 읽는 경로가 코드 전체에 0건 | run별 sidecar TR을 **필수 입력**으로 받고, 없으면 실패 |
| U18 | `mobse/data/nuisance.py:21-48` | confounds 파일이 없으면 `None` 을 **조용히** 반환 | 누락 = 실패 |
| U18 | `mobse/data/nuisance.py:51-66` | 길이 불일치 시 warning 후 trim / **zero-pad** | 불일치 = 실패 |
| — | `stream_aomic_extract.py:78` | aCompCor를 이름순 `a_comp_cor_00..04` 고정 선택 | metadata JSON의 **설명분산 순서**로 선택 |
| — | `stream_aomic_extract.py:185-190` | 필요한 열의 50% 미만이어도 warning만 내고 진행 | 열 부족 = 실패 |
| — | `stream_aomic_extract.py:279-285` | confounds를 `glob(...)[0]` 로 채택 | run/acq entity 완전 일치로 매칭 |
| — | `stream_aomic_extract.py:230` | `fetch_atlas_schaefer_2018(n_rois=N)` 을 해상도 인자 없이 호출 → 기본 1 mm, 경로도 `~/nilearn_data` | atlas 경로·해상도·checksum을 **명시 고정**(U9) |
| U20 | `mobse/io.py:10-14`, `mobse/evaluate.py:94` | mtime 최신 파일 / glob 최후 항목 자동 채택 | 경로 필수 인자화 |
| U19 | `mobse/evaluate.py:107,132` | ETTh1을 무조건 평가 | classification-only 신규 작성 |

## 6. 반입 경로

h197 경로가 Mac에서 접근 가능하므로, Wave 1 산출 3종(`wave1_runs.jsonl`, `wave1_summary.json`, `wave1_files.sha256`)과 `h197_environment.json` 을 MoBSE 저장소 아래
`results/redesign_v1/<release_id>/provenance/h197_wave1/` 로 복사하면 그 값으로 `source_runs.jsonl` 을 갱신하고 G0 gate evidence를 다시 쓴다. **BOLD 본체는 h197에 두고 반입하지 않는다.**
