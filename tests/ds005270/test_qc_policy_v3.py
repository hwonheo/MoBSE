"""Final pilot approvals cannot override failed or missing QC evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ds005270'))
from apply_qc_policy_v3 import classify_v3

POLICY = json.loads((ROOT / 'configs/ds005270/protocol_v3_qc_policy.json').read_text())
EVIDENCE = json.loads((ROOT / 'results/ds005270/qc_adoption_v3/subject_decisions.json').read_text())


class FinalPilotTests(unittest.TestCase):
    def row(self):
        return copy.deepcopy(next(r for r in EVIDENCE['subjects'] if r['subject'] == 'sub-001'))

    def test_six_current_decisions(self):
        included = []
        for row in EVIDENCE['subjects']:
            result = classify_v3(POLICY, row)
            self.assertEqual(result['status'], row['status'])
            self.assertEqual(result['analysis_inclusion_approved'], row['analysis_inclusion_approved'])
            if result['analysis_inclusion_approved']:
                included.append(row['subject'])
        self.assertEqual(included, ['sub-001', 'sub-002', 'sub-004', 'sub-013'])

    def test_approval_does_not_override_qc_failures(self):
        for changes, expected in [({'mean_fd_mm': .31}, 'exclude'),
                                  ({'main_windows': [4, 2, 4]}, 'exclude'),
                                  ({'fov_n_lt90': 1}, 'hold_fov'),
                                  ({'mean_fd_mm': None}, 'hold_missing_evidence')]:
            row = self.row()
            row['metrics'].update(changes)
            result = classify_v3(POLICY, row)
            self.assertEqual(result['status'], expected)
            self.assertFalse(result['analysis_inclusion_approved'])

    def test_scope_and_completed_review_required(self):
        for field, value in [('subject', 'sub-142'), ('targeted_visual_review', {}),
                             ('signal_review', 'pending')]:
            row = self.row()
            row[field] = value
            self.assertFalse(classify_v3(POLICY, row)['analysis_inclusion_approved'])

    def test_execution_remains_disabled_and_limitations_retained(self):
        self.assertFalse(any(POLICY['execution'].values()))
        self.assertFalse(POLICY['release_gate']['ready'])
        self.assertFalse(POLICY['qc']['coverage_automatic_exclusion'])
        self.assertEqual(POLICY['roi_scope']['model_roi_ids'], list(range(1, 101)))
        limits = POLICY['pilot_final_inclusion']['limitations']
        self.assertEqual([r['roi'] for r in limits['sub-004']], [33, 91])
        self.assertAlmostEqual(limits['sub-004'][0]['mask_fraction'], 0.505079006772009)


if __name__ == '__main__':
    unittest.main()
