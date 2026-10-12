#!/usr/bin/env bash
# ==============================================================================
# AOMIC Pilot Download Script
# Downloads fMRIPrep derivatives for a small pilot subset from AOMIC datasets.
#
# Usage:
#   bash scripts/download_aomic_pilot.sh [--full]
#
# Default: downloads 10 subjects per dataset (pilot mode)
# --full: downloads all subjects (full mode)
#
# Prerequisites:
#   pip install awscli
#
# Date: 2026-04-15
# ==============================================================================

set -euo pipefail

# --- Configuration ---
DATA_ROOT="${DATA_ROOT:-data/aomic}"
PILOT_SUBJECTS=10
FULL_MODE=false

if [[ "${1:-}" == "--full" ]]; then
    FULL_MODE=true
    echo "[INFO] Full download mode enabled."
fi

# Dataset registry
declare -A DATASETS
DATASETS[id1000]="ds003097"
DATASETS[piop1]="ds002785"
DATASETS[piop2]="ds002790"

# --- Functions ---

download_participants_tsv() {
    local name="$1"
    local ds_id="${DATASETS[$name]}"
    local out_dir="${DATA_ROOT}/${name}"

    echo "[INFO] Downloading participants.tsv for ${name} (${ds_id})..."
    mkdir -p "${out_dir}"
    aws s3 cp --no-sign-request \
        "s3://openneuro.org/${ds_id}/participants.tsv" \
        "${out_dir}/participants.tsv" 2>/dev/null || {
            echo "[WARN] Failed to download participants.tsv for ${name}, trying sync..."
            aws s3 sync --no-sign-request \
                "s3://openneuro.org/${ds_id}" "${out_dir}" \
                --exclude "*" --include "participants.tsv"
        }
}

get_subject_list() {
    local name="$1"
    local tsv="${DATA_ROOT}/${name}/participants.tsv"

    if [[ ! -f "${tsv}" ]]; then
        echo "[ERROR] participants.tsv not found for ${name}" >&2
        return 1
    fi

    # Extract subject IDs (first column, skip header)
    tail -n +2 "${tsv}" | cut -f1 | sort
}

download_fmriprep_derivatives() {
    local name="$1"
    local ds_id="${DATASETS[$name]}"
    local out_dir="${DATA_ROOT}/${name}"
    local subjects=("${@:2}")

    echo "[INFO] Downloading fMRIPrep derivatives for ${name}: ${#subjects[@]} subjects"

    for sub in "${subjects[@]}"; do
        echo "  [DL] ${sub} ..."

        # fMRIPrep preprocessed BOLD (MNI space) - all tasks
        aws s3 sync --no-sign-request \
            "s3://openneuro.org/${ds_id}/derivatives/fmriprep/${sub}" \
            "${out_dir}/derivatives/fmriprep/${sub}" \
            --exclude "*" \
            --include "func/*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz" \
            --include "func/*space-MNI152NLin2009cAsym*desc-preproc_bold.json" \
            --include "func/*space-MNI152NLin2009cAsym*desc-brain_mask.nii.gz" \
            --include "func/*desc-confounds_regressors.tsv" \
            --include "func/*desc-confounds_regressors.json" \
            2>/dev/null || echo "  [WARN] Partial failure for ${sub}"
    done
}

summarize_download() {
    local name="$1"
    local out_dir="${DATA_ROOT}/${name}"

    echo ""
    echo "=== ${name} Download Summary ==="

    # Count subjects with derivatives
    local n_subs=0
    if [[ -d "${out_dir}/derivatives/fmriprep" ]]; then
        n_subs=$(find "${out_dir}/derivatives/fmriprep" -maxdepth 1 -name "sub-*" -type d | wc -l)
    fi
    echo "  Subjects with derivatives: ${n_subs}"

    # Count BOLD files by task
    if [[ -d "${out_dir}/derivatives/fmriprep" ]]; then
        echo "  BOLD files by task:"
        find "${out_dir}/derivatives/fmriprep" -name "*desc-preproc_bold.nii.gz" | \
            sed 's/.*task-//' | sed 's/_acq.*//' | sed 's/_space.*//' | \
            sort | uniq -c | sort -rn | while read count task; do
                echo "    ${task}: ${count}"
            done
    fi

    # Disk usage
    local size=$(du -sh "${out_dir}" 2>/dev/null | cut -f1)
    echo "  Disk usage: ${size:-N/A}"
    echo ""
}

# --- Main ---

echo "============================================"
echo "  AOMIC Pilot Download"
echo "  Output: ${DATA_ROOT}"
echo "  Mode: $(${FULL_MODE} && echo 'FULL' || echo "PILOT (${PILOT_SUBJECTS} subjects)")"
echo "============================================"
echo ""

# Step 1: Download participants.tsv for all datasets
for name in id1000 piop1 piop2; do
    download_participants_tsv "${name}"
done

# Step 2: Select subjects
for name in id1000 piop1 piop2; do
    echo ""
    echo "--- Processing ${name} ---"

    all_subjects=($(get_subject_list "${name}"))
    echo "[INFO] Total subjects in ${name}: ${#all_subjects[@]}"

    if ${FULL_MODE}; then
        selected=("${all_subjects[@]}")
    else
        selected=("${all_subjects[@]:0:${PILOT_SUBJECTS}}")
    fi
    echo "[INFO] Selected: ${#selected[@]} subjects"

    # Step 3: Download fMRIPrep derivatives
    download_fmriprep_derivatives "${name}" "${selected[@]}"

    # Step 4: Summary
    summarize_download "${name}"
done

echo "============================================"
echo "  Download complete!"
echo "  Next: Run ROI extraction with Schaefer atlas"
echo "============================================"
