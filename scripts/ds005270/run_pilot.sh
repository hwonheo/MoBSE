#!/bin/bash
# Driver for the ds005270 n-back preprocessing pilot (run inside tmux).
# Verifies the lock before every subject, runs steps 01-03 one subject at a
# time with 2 threads, records rc / seconds / work disk per step, then step 04.
# A failed subject is recorded and the driver moves on to the next one.
# Usage: run_pilot.sh [sub-001 ...]   (default: the six locked pilot subjects)
set -u
REPO=/Users/hwon/projects/Git/Manuscript/MoBSE
PY=$REPO/.venv/bin/python
SD=$REPO/scripts/ds005270
DROOT=$REPO/data/openneuro/ds005270_derivatives/afni_nbk_pilot_20261017
WROOT=$REPO/data/openneuro/ds005270_work/afni_nbk_pilot_20261017
export PATH=/Users/hwon/abin:/opt/homebrew/opt/python/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/X11/bin
# rev4 (resource only, user approval 2026-10-17): AFNI OpenMP 2 -> 4 from sub-002 on;
# BLAS-type pools stay at 2. sub-001 step 02 ran under rev3 with OMP 2.
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 NUMEXPR_NUM_THREADS=2
unset DISPLAY PYTHONPATH
# rev3: Xvfb cannot create /tmp/.X11-unix without root and a TCP listener is
# not allowed, so the two Xvfb-starting snapshot helpers are replaced by no-op
# stubs placed first in PATH (QC images only; no processing output changes).
export PATH=$SD/no_snapshot_bin:$PATH
unset AFNI_DRIVE_OPTS_XVFB
xvfb_check() {  # fail the subject if any Xvfb is running under this user
    if pgrep -u "$(id -u)" -x Xvfb > /dev/null; then echo "Xvfb running"; return 1; fi
    return 0
}
SUBS=("$@")
[ ${#SUBS[@]} -gt 0 ] || SUBS=(sub-001 sub-002 sub-003 sub-004 sub-006 sub-013)

mkdir -p "$DROOT" "$WROOT"
STATUS=$DROOT/run_status.tsv
[ -f "$STATUS" ] || printf "subject\tstep\trc\tstart_kst\tseconds\twork_kib\tfree_disk_kib\tomp\tlock\n" > "$STATUS"
record() {  # subject step rc start seconds
    local wk free
    wk=$(du -sk "$WROOT/$1" 2>/dev/null | cut -f1)
    free=$(df -k "$REPO" | awk 'NR==2{print $4}')
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$4" "$5" "${wk:-0}" "$free" "$OMP_NUM_THREADS" "$LOCKH" >> "$STATUS"
}
now() { TZ=Asia/Seoul date +%Y-%m-%dT%H:%M:%S; }

$PY -I -B "$SD/build_lock.py" --verify || { echo "lock verify failed"; exit 20; }
LOCKH=$($PY -I -B -c "import json;print(json.load(open('$REPO/results/ds005270/locks/preproc_pilot_lock.json'))['lock_hash'][:12])")
if [ ! -f "$DROOT/reference/reference.json" ]; then
    $PY -I -B "$SD/00_reference.py" > "$DROOT/log_00_reference.txt" 2>&1 || { echo "reference failed"; exit 21; }
fi

for SUB in "${SUBS[@]}"; do
    echo "=== $SUB start $(now)"
    $PY -I -B "$SD/build_lock.py" --verify || { echo "lock verify failed before $SUB"; exit 20; }
    mkdir -p "$DROOT/$SUB"
    for STEP in ${STEPS:-01 02 03}; do  # rev4: STEPS=03 reruns only step 03
        t0=$(date +%s); st=$(now)
        case $STEP in
            01) $PY -I -B "$SD/01_prepare_inputs.py" "$SUB" > "$DROOT/$SUB/log_01.txt" 2>&1 ;;
            02) bash "$SD/02_afni_subject.sh" "$SUB" > "$DROOT/$SUB/log_02.txt" 2>&1 ;;
            03) $PY -I -B "$SD/03_extract_qc.py" "$SUB" > "$DROOT/$SUB/log_03.txt" 2>&1 ;;
        esac
        rc=$?
        xvfb_check || rc=30
        record "$SUB" "$STEP" "$rc" "$st" "$(( $(date +%s) - t0 ))"
        echo "$SUB step $STEP rc=$rc ($(( $(date +%s) - t0 )) s)"
        [ $rc -eq 0 ] || break
    done
done
$PY -I -B "$SD/04_pilot_summary.py" > "$DROOT/log_04_summary.txt" 2>&1
echo "=== pilot driver done $(now)"
