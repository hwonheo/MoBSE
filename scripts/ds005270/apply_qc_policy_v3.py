"""Apply existing QC and scoped final pilot approvals; no image processing."""
import argparse
import json
from pathlib import Path
from apply_qc_policy_v2 import classify


def classify_v3(policy, row):
    decision = classify(policy, row['metrics'])
    approved = False
    if row['subject'] in policy['approved_primary_exclusions']:
        decision = {'status': 'exclude', 'reasons': [policy['approved_primary_exclusions'][row['subject']]]}
    elif (decision['status'] == 'review_required'
          and row['subject'] in policy.get('pilot_final_inclusion', {}).get('approved_subjects', [])
          and policy['pilot_final_inclusion'].get('limitations_accepted') is True
          and row.get('targeted_visual_review', {}).get('status') == 'complete'
          and row.get('signal_review') == 'completed_with_accepted_limitations'):
        decision = {'status': 'include_with_limitations', 'reasons': [
            'targeted_visual_and_signal_review_completed',
            'user_approved_pilot_inclusion_with_limitations']}
        approved = True
    return {'subject': row['subject'], 'rule_version': policy['rule_version'],
            'analysis_inclusion_approved': approved, **decision}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--policy', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    policy = json.loads(a.policy.read_text())
    evidence = json.loads(a.evidence.read_text())
    if policy['rule_version'] != evidence['rule_version']:
        raise ValueError('Policy/evidence version mismatch')
    if any(policy['execution'].values()) or policy['qc']['coverage_automatic_exclusion']:
        raise ValueError('This evaluator requires execution disabled and coverage review only')
    print(json.dumps({'subjects': [classify_v3(policy, r) for r in evidence['subjects']],
                      'release_ready': False}, indent=2))
