#!/usr/bin/env bash
# Wave 1 — AOMIC PIOP1/PIOP2 메타데이터만 확보 (BOLD 본체 제외).
#
# 목적: G0 차단 항목 U1'(target native TR), U2(제거 volume), U4(confounds 열 구성),
#       U5(events 원점), U9(atlas 신원의 일부)를 해소할 최소 파일 집합을 받는다.
#       BOLD 본체는 window 설계가 확정된 뒤 Wave 2 에서 받는다.
#
# 전제: h197 에 awscli v2 가 있고 공개 버킷에 익명 접근이 된다.
#       s3://openneuro.org 는 requester-pays 가 아니므로 --no-sign-request 로 충분하다.
#       (근거: scripts/stream_aomic_extract.py:57,125,148 가 같은 방식을 쓴다.)
#
# 사용:
#   bash 01_wave1_fetch_metadata.sh --dest /data/aomic_wave1            # 실제 다운로드
#   bash 01_wave1_fetch_metadata.sh --dest /data/aomic_wave1 --dry-run  # 목록·용량만 확인
#
set -euo pipefail

S3_BASE="s3://openneuro.org"
DS_PIOP1="ds002785"   # AOMIC PIOP1
DS_PIOP2="ds002790"   # AOMIC PIOP2
TASKS=(restingstate emomatching workingmemory)

DEST=""
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$DEST" ]] || { echo "--dest 필요" >&2; exit 2; }

command -v aws >/dev/null || { echo "aws CLI 없음" >&2; exit 3; }
mkdir -p "$DEST"
LOG="$DEST/wave1_fetch.log"
: > "$LOG"

log() { printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

log "aws version: $(aws --version 2>&1)"
log "dest=$DEST dry_run=$DRY_RUN"

# --- 1) 각 dataset 의 raw BIDS 메타데이터 -----------------------------------
# BIDS inheritance 때문에 RepetitionTime 이 run 별 sidecar 가 아니라
# 데이터셋 루트의 task-<name>_bold.json 에만 있을 수 있다. 둘 다 받는다.
fetch_raw() {
  local ds="$1"
  local out="$DEST/$ds/raw"
  mkdir -p "$out"
  local args=( s3 sync "--no-sign-request" "$S3_BASE/$ds/" "$out/" --exclude "*" )
  # 데이터셋 수준
  args+=( --include "dataset_description.json" --include "participants.tsv"
          --include "participants.json" --include "task-*_bold.json"
          --include "*README*" --include "*CHANGES*" )
  # run 수준 (task 별)
  local t
  for t in "${TASKS[@]}"; do
    args+=( --include "sub-*/func/*task-${t}*_bold.json"
            --include "sub-*/func/*task-${t}*_events.tsv"
            --include "sub-*/func/*task-${t}*_events.json" )
  done
  [[ $DRY_RUN -eq 1 ]] && args+=( --dryrun )
  log "raw  $ds -> $out"
  aws "${args[@]}" 2>&1 | tee -a "$LOG" | tail -5
}

# --- 2) fMRIPrep derivative 의 confounds 와 sidecar --------------------------
# confounds TSV 는 volume 수·FD·motion·aCompCor·non_steady_state 를 모두 준다.
# 같은 이름의 .json 은 aCompCor 성분의 설명분산 순서를 담는다(계획서 3.2 요구).
fetch_deriv() {
  local ds="$1"
  local out="$DEST/$ds/fmriprep"
  mkdir -p "$out"
  local args=( s3 sync "--no-sign-request" "$S3_BASE/$ds/derivatives/fmriprep/" "$out/" --exclude "*" )
  args+=( --include "dataset_description.json" )
  local t
  for t in "${TASKS[@]}"; do
    args+=( --include "sub-*/func/*task-${t}*desc-confounds_regressors.tsv"
            --include "sub-*/func/*task-${t}*desc-confounds_regressors.json"
            --include "sub-*/func/*task-${t}*desc-confounds_timeseries.tsv"
            --include "sub-*/func/*task-${t}*desc-confounds_timeseries.json"
            --include "sub-*/func/*task-${t}*space-MNI152NLin2009cAsym*desc-preproc_bold.json" )
  done
  [[ $DRY_RUN -eq 1 ]] && args+=( --dryrun )
  log "deriv $ds -> $out"
  aws "${args[@]}" 2>&1 | tee -a "$LOG" | tail -5
}

for ds in "$DS_PIOP1" "$DS_PIOP2"; do
  fetch_raw "$ds"
  fetch_deriv "$ds"
done

if [[ $DRY_RUN -eq 0 ]]; then
  log "downloaded bytes: $(du -sb "$DEST" | cut -f1)"
  log "file count: $(find "$DEST" -type f | wc -l)"
fi
log "done. 다음: python3 02_wave1_audit.py --root $DEST --out $DEST/wave1_audit"
