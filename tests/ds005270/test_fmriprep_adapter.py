import unittest
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/ds005270"))
from validate_adapter import build_design, get_fd, psc, retain

class AdapterTests(unittest.TestCase):
    def test_fd_radians_and_first_difference(self):
        m=np.zeros((266,6));m[1:,0]=.01;m[2:,3]=.2
        np.testing.assert_allclose(get_fd(m)[:4],[0,.5,.2,0])

    def test_nonfinite_constant_and_zero_mean_rejected(self):
        for a in [np.ones((266,2)), np.full((266,2),np.nan),np.tile([-1.,1.],(2,133)).T]:
            with self.assertRaises(ValueError):psc(a)

    def test_derivative_zero_row_and_28_column_full_run_ols(self):
        rng=np.random.default_rng(20261019)
        motion=rng.normal(size=(266,6));wm=100+rng.normal(size=266);csf=200+rng.normal(size=266)
        x=build_design(motion,wm,csf)
        self.assertEqual(x.shape,(266,28));np.testing.assert_equal(x[0,8:14],0)
        y=rng.normal(size=(266,100));z=y-x@np.linalg.lstsq(x,y,rcond=None)[0]
        scaled=x/np.where(x.std(0)>0,x.std(0),1)
        zz=y-scaled@np.linalg.lstsq(scaled,y,rcond=None)[0]
        np.testing.assert_allclose(z,zz,atol=1e-9)
        np.testing.assert_allclose(scaled.T@z,0,atol=1e-8)

    def test_spike_adjacent_frames_reject_whole_window(self):
        fd=np.zeros(266);fd[30]=.50001
        w={'conditions':{c:{m:{'first_volume':[0,15,30,45],'starts_s':[0,30,60,90]} for m in ['main','sensitivity']} for c in ['ZeroBack','OneBack','TwoBack']}}
        flags,kept=retain(fd,w)
        self.assertEqual(np.flatnonzero(flags).tolist(),[29,30,31])
        self.assertEqual(list(kept['main']['ZeroBack']),[True,False,False,True])
        fd[30]=.5
        self.assertFalse(retain(fd,w)[0].any())

if __name__=='__main__':unittest.main()
