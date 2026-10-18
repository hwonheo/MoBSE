#!/bin/bash
# Step 2: AFNI preprocessing for one pilot subject (n-back run + T1w only).
#   A. sswarper2: T1w skull strip + nonlinear warp to MNI152_2009 (MNI_2009c_asym)
#   B. afni_proc.py: tshift (SliceTiming, tzero 0) / align (lpc+ZZ, check_flip)
#      / tlrc (sswarper2 warps) / volreg (MIN_OUTLIER, one-step warp onto the
#      atlas 2 mm grid) / mask (EPI automask, 3dSeg eroded WM/CSF)
# No despike, blur, scale, regress, blip (no fieldmap) or censoring here.
# Run with the clean environment set by run_pilot.sh (PATH without spaces,
# OMP_NUM_THREADS=2). Usage: 02_afni_subject.sh sub-001
set -u
SUB=$1
REPO=/Users/hwon/projects/Git/Manuscript/MoBSE
RAW=$REPO/data/openneuro/ds005270/1.0.0/$SUB
WORK=$REPO/data/openneuro/ds005270_work/afni_nbk_pilot_20261017/$SUB
MASTER=$REPO/data/openneuro/ds005270_derivatives/afni_nbk_pilot_20261017/reference/atlas_grid_master.nii.gz
TPL=MNI152_2009_template_SSW.nii.gz

mkdir -p "$WORK/anat" "$WORK/func"
[ -f "$WORK/inputs/slice_times.1D" ] || { echo "missing slice_times.1D (run step 1)"; exit 2; }

# ---- A. sswarper2 -------------------------------------------------------
if [ -e "$WORK/anat/anatQQ.$SUB.nii" ]; then
    echo "anat outputs already exist; refusing to overwrite"; exit 3
fi
cd "$WORK/anat" || exit 2
/usr/bin/time -l -o "$WORK/anat/time_sswarper2.txt" \
    sswarper2 -input "$RAW/anat/${SUB}_T1w.nii.gz" -base $TPL -subid "$SUB" \
              -odir "$WORK/anat" > "$WORK/anat/sswarper2.log" 2>&1
rcA=$?
echo "sswarper2 rc=$rcA"
for f in anatSS.$SUB.nii anatQQ.$SUB.nii anatQQ.$SUB.aff12.1D anatQQ.${SUB}_WARP.nii; do
    [ -e "$WORK/anat/$f" ] || { echo "missing $f"; rcA=4; }
done
[ $rcA -eq 0 ] || exit 10

# ---- B. afni_proc.py ----------------------------------------------------
cd "$WORK/func" || exit 2
[ -e "$WORK/func/$SUB.results" ] && { echo "results dir exists; refusing to overwrite"; exit 3; }
afni_proc.py -subj_id "$SUB" -script "proc.$SUB" -out_dir "$WORK/func/$SUB.results" \
    -blocks tshift align tlrc volreg mask \
    -copy_anat "$WORK/anat/anatSS.$SUB.nii" -anat_has_skull no \
    -dsets "$RAW/func/${SUB}_task-nbk_bold.nii.gz" \
    -tcat_remove_first_trs 0 \
    -tshift_opts_ts -tpattern "@$WORK/inputs/slice_times.1D" -tzero 0 \
    -align_unifize_epi local \
    -align_opts_aea -cost lpc+ZZ -giant_move -check_flip \
    -tlrc_base $TPL -tlrc_NL_warp \
    -tlrc_NL_warped_dsets "$WORK/anat/anatQQ.$SUB.nii" "$WORK/anat/anatQQ.$SUB.aff12.1D" \
                          "$WORK/anat/anatQQ.${SUB}_WARP.nii" \
    -volreg_align_to MIN_OUTLIER -volreg_align_e2a -volreg_tlrc_warp \
    -volreg_warp_master "$MASTER" -volreg_warp_final_interp wsinc5 \
    -volreg_compute_tsnr yes \
    -mask_epi_anat yes -mask_segment_anat yes -mask_segment_erode yes \
    -html_review_style none > "$WORK/func/afni_proc_gen.log" 2>&1
rcG=$?
echo "afni_proc generation rc=$rcG"
[ $rcG -eq 0 ] || exit 11
/usr/bin/time -l -o "$WORK/func/time_proc.txt" \
    tcsh -xef "proc.$SUB" > "$WORK/func/output.proc.$SUB" 2>&1
rcB=$?
echo "proc rc=$rcB"
[ $rcB -eq 0 ] || exit 12
exit 0
