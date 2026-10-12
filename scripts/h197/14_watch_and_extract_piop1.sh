#!/usr/bin/env bash
# PIOP1(ds002785) 내려받기가 끝나는 즉시 WI-02 재추출을 시작한다.
#
# 목적은 대기 시간 제거다. ds002790(88.7 GiB, 약 4.5시간)이 내려오는 동안
# PIOP1 추출(3개 조합, 약 50분)을 병렬로 돌리면 그만큼 총 시간이 줄어든다.
#
# 완료 판정은 로그에 '=== ds002790 ===' 가 나타나는 것으로 한다. fetcher 가
# 다음 dataset 으로 넘어갔다는 뜻이므로 파일 수를 세는 것보다 모호하지 않다.
# 안전장치로 .part 가 0인지도 함께 본다.
#
# 사용: setsid nohup bash 14_watch_and_extract_piop1.sh > watch.log 2>&1 &

set -u

ROOT="/mnt/data/mp2026/MoBSE_dataset"
LOG="$ROOT/aomic_wave2/fetch2_j24.log"
W1="$ROOT/aomic_wave1"
W2="$ROOT/aomic_wave2"
ATLAS="$ROOT/atlas_2009c/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz"
OUT="$ROOT/derivatives_v2"
WORK="$ROOT/legacycheck"
VENV="$ROOT/venv-mobse-v2/bin/activate"
SCRIPTS="$ROOT/scripts_h197"

MAX_WAIT_SEC=${MAX_WAIT_SEC:-7200}   # 2시간이면 예상보다 훨씬 길다 — 그 뒤엔 포기하고 알린다
POLL_SEC=60

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
say()   { echo "[$(stamp)] $*"; }

say "watcher 시작. ds002785 완료를 기다린다 (최대 $((MAX_WAIT_SEC/60))분)"

waited=0
while :; do
    if grep -q "=== ds002790 ===" "$LOG" 2>/dev/null; then
        parts=$(find "$W2/ds002785" -name '*.part' 2>/dev/null | wc -l)
        files=$(find "$W2/ds002785" -name '*.nii.gz' 2>/dev/null | wc -l)
        say "ds002790 구간 진입 감지. ds002785 파일 $files, 남은 .part $parts"
        if [ "$parts" -eq 0 ]; then
            break
        fi
        say "  .part 가 남아 있어 더 기다린다"
    fi
    if [ "$waited" -ge "$MAX_WAIT_SEC" ]; then
        say "FAIL: $((MAX_WAIT_SEC/60))분 안에 ds002785 가 끝나지 않았다. 추출을 시작하지 않는다"
        exit 1
    fi
    sleep "$POLL_SEC"
    waited=$((waited + POLL_SEC))
done

files=$(find "$W2/ds002785" -name '*.nii.gz' | wc -l)
say "ds002785 완료 확인: $files 파일. WI-02 추출을 시작한다"

cd "$WORK" || { say "FAIL: $WORK 로 이동 실패"; exit 1; }
# shellcheck disable=SC1090
source "$VENV" || { say "FAIL: venv 활성화 실패"; exit 1; }
mkdir -p "$OUT"

rc_total=0
run_combo() {
    local task="$1" tr="$2"
    say "--- ds002785 / $task (TR $tr) 시작"
    PYTHONPATH=. python -u "$SCRIPTS/10_wi02_extract.py" \
        --wave1-root "$W1" --wave2-root "$W2" --atlas "$ATLAS" \
        --output-dir "$OUT" --dataset ds002785 --task "$task" --native-tr "$tr" \
        > "$OUT/extract_ds002785_${task}.log" 2>&1
    local rc=$?
    say "--- ds002785 / $task 종료 rc=$rc : $(tail -1 "$OUT/extract_ds002785_${task}.log")"
    [ "$rc" -ne 0 ] && rc_total=1
}

run_combo emomatching 2.0
run_combo workingmemory 2.0
run_combo restingstate 0.75

say "창 manifest 생성 (target task 만 — rest 는 분류 대상이 아니다)"
PYTHONPATH=. python -u "$SCRIPTS/12_build_windows_manifest.py" \
    --manifest "$OUT/wi02_ds002785_emomatching.jsonl" \
                "$OUT/wi02_ds002785_workingmemory.jsonl" \
    --output "$OUT/windows_piop1.jsonl" --overwrite \
    > "$OUT/windows_piop1.log" 2>&1
rc=$?
say "창 manifest rc=$rc : $(tail -2 "$OUT/windows_piop1.log" | tr '\n' ' ')"
[ "$rc" -ne 0 ] && rc_total=1

say "완료. rc_total=$rc_total"
exit "$rc_total"
