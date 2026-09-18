# WI-00 구현 지도 (existing-file reuse map)
생성 시각(UTC): 2026-09-17T03:22:57Z
release_id: 20260917_3c458d507e82_nocfg

이 문서는 지침서 §5 표에 명시된 12개 기존 경로의 **실제 파일 상태**(존재 여부/줄 수/SHA256/git 추적 상태)를 확인하고, v2 재설계를 위한 신규 경로들의 부재를 검증하며, 절대 덮어쓰지 않을 기존 산출물 범위를 기록한다. 모든 수치는 device_bash 셸에서 직접 실행한 명령의 실제 출력이다.

## 1. 기존 파일 재사용 지도 (§5 표 12개 경로 실측)

| 경로 | 존재 | 줄 수 | SHA256 (전체) | git 상태 | 분류 |
|---|---|---|---|---|---|
| `scripts/stream_aomic_extract.py` | 존재 | 627 | `35ba368013eeb15d71335632376fa44f276099fdcdd063f2c7384a933ff1cc83` | ?? (미추적, 신규) | 수정 금지(보존) — v2에서는 참고만: source fetch/ROI 추출 구조 참고, dataset 공통 TR/default 0.75 의존 부분은 v2에서 미채택 |
| `scripts/build_alltasks_windows.py` | 존재 | 235 | `6cdc3d6b5e76be3edddaf4841038b9826dcf6c7b4ff81dd1d6f950fafe343867` | ?? (미추적, 신규) | 수정 금지(보존) — v2에서는 참고만: 파일 I/O만 참고, centroid target 생성 로직은 v2에서 미채택 |
| `mobse/data/dfc.py` | 존재 | 605 | `fa4269e5bf513c00bd7658a6804f9ce049ce2a30b6b044c3e0a811718ae45992` | ?? (미추적, 신규) | 수정 금지(보존) — v2에서는 참고만: FC/clustering primitive만 검토, 전체 subject fit wrapper는 v2에서 미채택 |
| `mobse/templates/builder.py` | 존재 | 175 | `5522658e16dbc8f357bc502905c9dc387d925e09316dd408d64ef037431aa979` | M (수정됨, 원본 HEAD 보존 필요) | 수정 금지(보존) — v2에서는 참고만: graph serialization 아이디어만 참고, global records template은 v2에서 미채택 (MODIFIED tracked file - 원본 보존 필요) |
| `mobse/templates/dfc_bridge.py` | 존재 | 478 | `80edf8c789713ebc2ed970d34c8be0414870283b0613251bd08182c1f689b1c4` | ?? (미추적, 신규) | 수정 금지(보존) — v2에서는 참고만: 명시적 schema 보완 후 serialization 재사용, provenance 없는 template 연결은 미채택 |
| `mobse/data/os_data.py` | 존재 | 323 | `2c7184787a10c8e2c2cc88a212537c13f8c3d3c200c665664b5bfd64ce8bc586` | clean (tracked, 변경 없음) | 수정 금지(보존) — v2에서는 참고만: batch/loading, subject split 경험만 참고, default window shuffle split은 미채택 |
| `mobse/models/mobse.py` | 존재 | 211 | `811779e46cd93896750abd53f845ead07242da88b2bf334f1d30197126d2c335` | M (수정됨, 원본 HEAD 보존 필요) | 수정 금지(보존) — v2에서는 참고만: template mixing 구조만 참고. raw mean bottleneck/ROI 혼합/PyG-dependent fallback은 미채택 (MODIFIED tracked file - 원본 보존 필요) |
| `mobse/train.py` | 존재 | 459 | `daa532fdd7e3e881cbbe4b0d923f59a891233fa46acd0e70d6ea810536c537cb` | M (수정됨, 원본 HEAD 보존 필요) | 수정 금지(보존) — v2에서는 참고만: optimizer/checkpoint/logging 원리만 참고, dual-task/entropy 목적은 미채택 (MODIFIED tracked file - 원본 보존 필요) |
| `mobse/evaluate.py` | 존재 | 149 | `a05b800165aa71ebf90365370a842d561a1bd69e9c091ce96006277847da0bae` | clean (tracked, 변경 없음) | 수정 금지(보존) — v2에서는 참고만: 저장/집계 원리만 참고, 항상 두 task branch 평가하는 방식은 미채택 |
| `scripts/eval_routing.py` | 존재 | 501 | `0a3b3b631dfa91eff338b961cf87afcc0f68f89f45eb77bb82f8a2d5a4c2a87e` | ?? (미추적, 신규) | 수정 금지(보존) — v2에서는 참고만: 출력 형식만 참고, all-subject/default-seed pooled-window 해석은 미채택 |
| `mobse/profiling.py` | 존재 | 101 | `d5aee9b73e88f410c0b60754ebc8a48ae6f089e42afb1a2d670f06938756a888` | clean (tracked, 변경 없음) | 수정 금지(보존) — v2에서는 참고만: timer 틀만 참고, params×batch fallback을 FLOPs로 보고하는 방식은 미채택 |
| `mobse/io.py` | 존재 | 61 | `5b6b0819645fe497bb68cd14acb22603bb5d3b385aba72a4cd35a827d7a28217` | clean (tracked, 변경 없음) | 수정 금지(보존) — v2에서는 참고만: 일반 I/O helper만 검토, glob으로 다른 artifact 대체하는 패턴은 금지 |

주: 위 표에서 git 상태가 `M`인 파일(`mobse/templates/builder.py`, `mobse/models/mobse.py`, `mobse/train.py`)은 현재 작업 트리에 이미 dirty change가 있는 상태이며, HEAD 버전과 현재 버전 SHA256이 모두 `provenance/workspace_snapshot.json`의 `git.modified_tracked_files`에 기록되어 원본 보존 근거가 된다. 이 파일들을 v2 작업 중 추가로 손대야 한다면 최소 adapter만 새 파일로 추가하고 기존 내용을 직접 덮어쓰지 않는다.

## 2. 계획된 신규 경로 존재 여부 (모두 미존재 예상 — 실측 확인)

| 신규 경로 | 현재 존재 여부 |
|---|---|
| `mobse/v2/` | 부재 (예상대로 미구현) |
| `configs/redesign_v1/` | 부재 (예상대로 미구현) |
| `results/redesign_v1/` | 존재 (DIR) (본 WI-00 작업으로 output 디렉터리만 새로 생성됨: provenance/, reports/) |
| `tests/v2/` | 부재 (예상대로 미구현) |

`results/redesign_v1/`은 이번 WI-00 실행 자체가 만든 출력 디렉터리(`20260917_3c458d507e82_nocfg/provenance/`, `reports/`)만 존재하며, WI-04 이후 채워질 `qc/ splits/ locks/ fits/ predictions/ statistics/` 하위 구조는 아직 없다.

## 3. 절대 덮어쓰지 않을 기존 산출물

### 3.1 `artifacts/` 상위 디렉터리 (39개)

- `artifacts/20260415_164915/` (하위 항목 4개)
- `artifacts/20260416_092630/` (하위 항목 4개)
- `artifacts/20260416_102355/` (하위 항목 4개)
- `artifacts/20260416_102453/` (하위 항목 4개)
- `artifacts/20260416_103427/` (하위 항목 4개)
- `artifacts/20260416_110408/` (하위 항목 4개)
- `artifacts/20260416_133322/` (하위 항목 4개)
- `artifacts/20260416_134049/` (하위 항목 4개)
- `artifacts/20260416_134500/` (하위 항목 4개)
- `artifacts/20260416_140117/` (하위 항목 4개)
- `artifacts/20260416_141348/` (하위 항목 4개)
- `artifacts/20260416_142556/` (하위 항목 4개)
- `artifacts/abide_dfc_full/` (하위 항목 3개)
- `artifacts/abide_dfc_pca80_full/` (하위 항목 3개)
- `artifacts/abide_dfc_pca90_full/` (하위 항목 3개)
- `artifacts/abide_dfc_pca95_full/` (하위 항목 3개)
- `artifacts/abide_dfc_pca_pilot/` (하위 항목 3개)
- `artifacts/abide_dfc_pilot/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc100/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc10_noznorm/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc20_noznorm/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc30/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc30_noznorm/` (하위 항목 3개)
- `artifacts/abide_dfc_v2_pc50/` (하위 항목 3개)
- `artifacts/current_canonical/` (하위 항목 277개)
- `artifacts/eval_routing_alltasks/` (하위 항목 9개)
- `artifacts/legacy_misc/` (하위 항목 31개)
- `artifacts/legacy_openneuro/` (하위 항목 2개)
- `artifacts/legacy_phase1/` (하위 항목 4개)
- `artifacts/legacy_phase2/` (하위 항목 123개)
- `artifacts/legacy_poc1/` (하위 항목 10개)
- `artifacts/legacy_strict/` (하위 항목 6개)
- `artifacts/mobse_dfc_abide/` (하위 항목 3개)
- `artifacts/mobse_dfc_piop1_sch100/` (하위 항목 12개)
- `artifacts/mobse_paper_lock_20260330/` (하위 항목 1개)
- `artifacts/ops/` (하위 항목 1개)
- `artifacts/piop1_dfc_schaefer100/` (하위 항목 4개)
- `artifacts/piop1_dfc_schaefer200/` (하위 항목 3개)
- `artifacts/scratch_tmp/` (하위 항목 2개)

### 3.2 `docs/manuscript_final_2026-03-31/`

존재. 하위 항목:

```
figures
methods_lock_2026-03-31.md
mobse_abstract_kor_draft_2026-03-30.md
mobse_concept_vs_manuscript_gapfill_2026-03-31.md
mobse_integrated_storyline_2026-04-16.md
mobse_intro_literature_doi_analysis_2026-03-30.md
mobse_mainline_discussion_2026-03-30.md
mobse_paper_lock_2026-03-30.md
mobse_results_draft_2026-03-31.md
```

### 3.3 `docs/experiments/archive_*`

- `docs/experiments/archive_redesign/`
```
docs/experiments/archive_redesign
docs/experiments/archive_redesign/mobse_redesign_protocol_2026-09-17_v1.0.md
```
- `docs/experiments/archive_derived_2026-03-31/`
```
docs/experiments/archive_derived_2026-03-31
docs/experiments/archive_derived_2026-03-31/etth1_storyline_top_journal_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/benchmark_goal_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/baseline_benchmark_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/hcp_validation_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/phase2_report_2026-03-14_public.md
docs/experiments/archive_derived_2026-03-31/etth1_story_execution_log_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/development_note_etth1_story_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/etth1_figure_execution_plan_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/phase2_report_2026-03-14.md
docs/experiments/archive_derived_2026-03-31/history_index_2026-03-26.md
docs/experiments/archive_derived_2026-03-31/phase2_followup_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/etth1_full_line_rerun_2026-03-31.md
docs/experiments/archive_derived_2026-03-31/etth1_ett_family_extension_2026-03-31.md
docs/experiments/archive_derived_2026-03-31/etth1_journal_readiness_audit_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/mobse_baseline_todo_2026-03-30.md
docs/experiments/archive_derived_2026-03-31/cross_dataset_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/nuisance_sensitivity_2026-03-24.md
docs/experiments/archive_derived_2026-03-31/openneuro_usable_plan_2026-03-24.md
docs/experiments/archive_derived_2026-03-31/current_status_etth1_story_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/abide_control_mobse_baseline_2026-03-30.md
docs/experiments/archive_derived_2026-03-31/experiments_note_phase2_2026-03-14.md
docs/experiments/archive_derived_2026-03-31/strict_usable_execution_plan_2026-03-26.md
docs/experiments/archive_derived_2026-03-31/figure_plan_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/openneuro_extension_2026-03-24.md
docs/experiments/archive_derived_2026-03-31/openneuro_usable600_wave_2026-03-27.md
docs/experiments/archive_derived_2026-03-31/project_status_2026-03-23.md
docs/experiments/archive_derived_2026-03-31/experiments_note_2026-03-13.md
docs/experiments/archive_derived_2026-03-31/human_network_modeling_advantages_2026-03-30.md
docs/experiments/archive_derived_2026-03-31/mobse_remaining_tasks_2026-03-31.md
docs/experiments/archive_derived_2026-03-31/submission_package_index_2026-03-31.md
```

이상 artifacts/ 39개 상위 디렉터리, docs/manuscript_final_2026-03-31/, docs/experiments/archive_redesign/, docs/experiments/archive_derived_2026-03-31/ 는 기존 완료 산출물이며 이후 WI에서 어떤 신규 스크립트도 이 경로에 쓰기/삭제를 수행하지 않는다. v2 산출물은 오직 `results/redesign_v1/<release_id>/` 아래에만 기록한다.

## 4. WI-00 완료 기준 판정

**완료 기준: "수정 금지 기존 결과와 실제 편집 대상이 구분되어 있다"**

판정: **충족.** 근거 — (1) §1의 12개 경로 실측 결과 3개 파일(`mobse/templates/builder.py`, `mobse/models/mobse.py`, `mobse/train.py`)이 이미 tracked-dirty 상태이며 HEAD/현재 SHA256이 `workspace_snapshot.json`에 모두 기록되어 원본 복원 가능; (2) 나머지 9개 경로는 clean-tracked 또는 untracked 상태로 각각 SHA256이 고정 기록됨; (3) v2 신규 경로(`mobse/v2/`, `configs/redesign_v1/`, `tests/v2/`)는 모두 미존재가 실측으로 확인되어 기존 코드와 물리적으로 분리된 새 위치에서 시작함이 보장됨; (4) `artifacts/`(39개 상위 디렉터리), `docs/manuscript_final_2026-03-31/`, `docs/experiments/archive_*` 는 목록화되어 '절대 덮어쓰지 않을 기존 산출물'로 명시됨; (5) 본 WI-00 실행은 `results/redesign_v1/20260917_3c458d507e82_nocfg/{provenance,reports}/` 두 디렉터리와 그 안의 파일만 신규 생성했고 기존 파일은 전혀 수정/삭제하지 않음(파일 삭제 권한 자체가 없음).

## 5. 확인하지 못한 항목 (환경 제약)

- `.venv/bin/python`을 이용한 numpy/scipy/sklearn/nilearn/pandas/torch/nibabel 버전 확인 및 `.venv/bin/pip list --format=json` 실행: device_bash 셸이 사용자의 실제 macOS 기기가 아니라 별도 Linux VM (Ubuntu 22.04, aarch64)에서 실행되어 `.venv`가 참조하는 macOS Homebrew Python (`/opt/homebrew/opt/python@3.11/bin/python3.11`)이 이 VM 안에 존재하지 않기 때문에 실행 불가(broken symlink, `uname -a`로 확인). 대신 `.venv/lib/python3.11/site-packages/*.dist-info` 디렉터리명을 읽어 버전을 확인했으며 (numpy 2.4.3, scipy 1.17.1, scikit_learn 1.8.0, nilearn 0.13.1, pandas 3.0.1, torch 2.10.0, nibabel 5.4.2), 이는 실제 import 성공을 보증하지 않는 read-only 대체 확인임을 `workspace_snapshot.json`에 명시했다.
- `sysctl -n hw.model hw.ncpu hw.memsize`: 이 Linux VM에는 `sysctl` 명령 자체가 없어 실패. 실제 사용자 기기는 `get_device_info` 결과상 darwin/arm64(`bmc2025mp16-local`)이나 정확한 CPU 모델/코어수/메모리 용량은 이 세션에서 직접 조회하지 못했다.
- `.venv/bin/python -m pytest --collect-only`: 위와 동일한 이유로 실행 불가. 대신 시스템 python3(의존성 없음)로 동일 명령을 시도해 'No module named pytest'만 확인했고, `mobse.data.hcp` import 누락 주장은 pytest 실행이 아니라 `mobse/data/hcp.py` 파일 부재 확인 + `tests/test_hcp_templates.py`, `tests/test_subject_split.py`의 grep으로 정적으로 검증했다(실제 pytest 오류 메시지 원문은 얻지 못함).
