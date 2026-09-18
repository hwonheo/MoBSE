#!/usr/bin/env bash
# ds002790(PIOP2) 내려받기 완료 즉시 WI-02 추출 → 창 manifest → 코호트까지 처리한다.
#
# **분할(split)은 하지 않는다.** 계획서 §9 가 PIOP2 를 held-out 외부 코호트로
# 규정하기 때문이다 — "PIOP1 main pool(pilot 제외)에서 config/E를 정하고 …
# PIOP2 rest·labels·성능으로 fit/선택/calibration하지 않는다. PIOP2는 같은
# QC·window 규칙과 task pairing을 적용하고 cohort 차이·제외 수를 보고한다."
# 5-fold outer CV 구조를 만들어 두면 프로토콜에 없는 산출물이 남아 나중에
# 의미 있는 것으로 오인될 수 있다.
#
# 완료 판정은 **fetch 프로세스 종료 AND 남은 .part 0** 두 조건을 모두 본다.
# 7회차에서 로그의 구간 진입만 믿었다면 24개가 전송 중인 상태로 시작했을 것이다.

set -u

ROOT="/mnt/data/mp2026/MoBSE_dataset"
W1="$ROOT/aomic_wave1"
W2="$ROOT/aomic_wave2"
DS="ds002790"
ATLAS="$ROOT/atlas_2009c/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz"
OUT="$ROOT/derivatives_v2_piop2"
WORK="$ROOT/legacycheck"
VENV="$ROOT/venv-mobse-v2/bin/activate"
SCRIPTS="$ROOT/scripts_h197"
PIDFILE="$W2/fetch2.pid"

MAX_WAIT_SEC=${MAX_WAIT_SEC:-7200}
POLL_SEC=60

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
say()   { echo "[$(stamp)] $*"; }

say "watcher 시작. $DS 완료를 기다린다 (최대 $((MAX_WAIT_SEC/60))분)"

waited=0
while :; do
    alive=1
    if [ -f "$PIDFILE" ]; then
        ps -p "$(cat "$PIDFILE")" > /dev/null 2>&1 || alive=0
    else
        alive=0
    fi
    parts=$(find "$W2/$DS" -name '*.part' 2>/dev/null | wc -l)

    if [ "$alive" -eq 0 ] && [ "$parts" -eq 0 ]; then
        say "완료 확인: fetch 종료, 남은 .part 0"
        break
    fi
    if [ $((waited % 600)) -eq 0 ]; then
        say "  대기 중 (fetch alive=$alive, .part=$parts)"
    fi
    if [ "$waited" -ge "$MAX_WAIT_SEC" ]; then
        say "FAIL: $((MAX_WAIT_SEC/60))분 안에 끝나지 않았다 (alive=$alive, .part=$parts). 추출을 시작하지 않는다"
        exit 1
    fi
    sleep "$POLL_SEC"
    waited=$((waited + POLL_SEC))
done

files=$(find "$W2/$DS" -name '*.nii.gz' | wc -l)
say "$DS 파일 $files 개. WI-02 추출을 시작한다"

cd "$WORK" || { say "FAIL: $WORK 이동 실패"; exit 1; }
# shellcheck disable=SC1090
source "$VENV" || { say "FAIL: venv 활성화 실패"; exit 1; }
mkdir -p "$OUT"

rc_total=0
for task in emomatching workingmemory restingstate; do
    say "--- $DS / $task (TR 2.0) 시작"
    PYTHONPATH=. python -u "$SCRIPTS/10_wi02_extract.py" \
        --wave1-root "$W1" --wave2-root "$W2" --atlas "$ATLAS" \
        --output-dir "$OUT" --dataset "$DS" --task "$task" --native-tr 2.0 \
        > "$OUT/extract_${DS}_${task}.log" 2>&1
    rc=$?
    say "--- $DS / $task 종료 rc=$rc : $(tail -1 "$OUT/extract_${DS}_${task}.log")"
    [ "$rc" -ne 0 ] && rc_total=1
done

say "창 manifest 생성 (target 2종만 — rest 는 분류 대상이 아니다)"
PYTHONPATH=. python -u "$SCRIPTS/12_build_windows_manifest.py" \
    --manifest "$OUT/wi02_${DS}_emomatching.jsonl" \
               "$OUT/wi02_${DS}_workingmemory.jsonl" \
    --output "$OUT/windows_piop2.jsonl" --overwrite \
    > "$OUT/windows_piop2.log" 2>&1
rc=$?
say "창 manifest rc=$rc : $(tail -2 "$OUT/windows_piop2.log" | tr '\n' ' ')"
[ "$rc" -ne 0 ] && rc_total=1

say "코호트 생성 (세 task 전부)"
PYTHONPATH=. python -u "$SCRIPTS/15_build_subjects.py" \
    --manifest "$OUT/wi02_${DS}_emomatching.jsonl" \
               "$OUT/wi02_${DS}_workingmemory.jsonl" \
               "$OUT/wi02_${DS}_restingstate.jsonl" \
    --output-dir "$OUT/cohort_piop2" --overwrite \
    > "$OUT/cohort_piop2.log" 2>&1
rc=$?
say "코호트 rc=$rc"
sed -n '/\[cohort\]/,$p' "$OUT/cohort_piop2.log" | while read -r line; do say "   $line"; done
[ "$rc" -ne 0 ] && rc_total=1

say "분할은 하지 않는다 — 계획서 §9 에 따라 PIOP2 는 held-out 외부 코호트다"
say "완료. rc_total=$rc_total"
exit "$rc_total"
