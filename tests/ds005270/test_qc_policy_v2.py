"""Boundary and fail-closed checks for the adopted existing-metrics policy."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('policy', ROOT/'scripts/ds005270/apply_qc_policy_v2.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
POLICY = json.loads((ROOT/'configs/ds005270/protocol_v2_qc_policy.json').read_text())


class PolicyTests(unittest.TestCase):
    def metric(self, **overrides):
        return dict(mean_fd_mm=.3, fraction_fd_gt_0p5=.2, main_windows=[3,3,3],
                    fov_n_lt90=0, mask_n_lt90=100, **overrides)

    def test_exact_boundaries_and_low_mask_do_not_exclude(self):
        self.assertEqual(module.classify(POLICY,self.metric())['status'],'review_required')

    def test_motion_above_boundary_excludes(self):
        for field, value in [('mean_fd_mm',.300001),('fraction_fd_gt_0p5',.200001)]:
            m=self.metric();m[field]=value
            self.assertIn('Q2_motion',module.classify(POLICY,m)['reasons'])

    def test_sensitivity_cannot_rescue_main_windows(self):
        m=self.metric();m['main_windows']=[3,2,3];m['sensitivity_windows']=[4,4,4]
        self.assertIn('Q3_main_windows',module.classify(POLICY,m)['reasons'])

    def test_fov_is_hold_and_missing_values_never_pass(self):
        m=self.metric();m['fov_n_lt90']=1
        self.assertEqual(module.classify(POLICY,m)['status'],'hold_fov')
        m['mean_fd_mm']=float('nan')
        self.assertEqual(module.classify(POLICY,m)['status'],'hold_missing_evidence')

    def test_pilot_decisions_reproduced_without_subject_special_cases(self):
        evidence=json.loads((ROOT/'results/ds005270/qc_adoption_v2/subject_decisions.json').read_text())
        for row in evidence['subjects']:
            self.assertEqual(module.classify(POLICY,row['metrics'])['status'],row['status'])


if __name__ == '__main__':
    unittest.main()
