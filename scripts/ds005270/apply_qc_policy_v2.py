"""Classify existing QC metrics only. Never process images or launch training."""
import argparse
import json
import math


def classify(policy, metrics):
    """Fail closed for missing evidence; low mask coverage is review, not exclusion."""
    q = policy['qc']
    mean = metrics.get('mean_fd_mm')
    fraction = metrics.get('fraction_fd_gt_0p5')
    wins = metrics.get('main_windows')
    if (not isinstance(mean, (float, int)) or not math.isfinite(mean) or mean < 0
            or not isinstance(fraction, (float, int)) or not math.isfinite(fraction)
            or not 0 <= fraction <= 1 or not isinstance(wins, list) or len(wins) != 3
            or any(type(x) is not int or not 0 <= x <= 4 for x in wins)):
        return {'status': 'hold_missing_evidence', 'reasons': ['motion_or_window_evidence_invalid']}
    reasons = []
    if mean > q['mean_fd_exclude_gt_mm'] or fraction > q['fraction_fd_gt_0p5_exclude_gt']:
        reasons.append('Q2_motion')
    if min(wins) < q['minimum_main_windows_per_condition']:
        reasons.append('Q3_main_windows')
    if reasons:
        return {'status': 'exclude', 'reasons': reasons}
    fov, mask = metrics.get('fov_n_lt90'), metrics.get('mask_n_lt90')
    if any(type(x) is not int or not 0 <= x <= 100 for x in (fov, mask)):
        return {'status': 'hold_missing_evidence', 'reasons': ['coverage_evidence_invalid']}
    if fov:
        return {'status': 'hold_fov', 'reasons': ['acquired_FOV_deficit', 'essential_ROI_unresolved']}
    return {'status': 'review_required', 'reasons': ['residual_mask_ROI_review'] if mask else ['final_multidomain_review_pending']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    with open(args.policy) as f:
        policy = json.load(f)
    with open(args.evidence) as f:
        evidence = json.load(f)
    if evidence['rule_version'] != policy['rule_version']:
        raise ValueError('Policy/evidence version mismatch')
    if any(policy['execution'].values()) or policy['qc']['coverage_automatic_exclusion']:
        raise ValueError('This review-only evaluator requires execution disabled and coverage review only')
    rows = [{'subject': row['subject'], 'rule_version': policy['rule_version'],
             'analysis_inclusion_approved': False, **classify(policy, row['metrics'])}
            for row in evidence['subjects']]
    print(json.dumps({'subjects': rows, 'release_ready': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
