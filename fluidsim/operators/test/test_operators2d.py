from __future__ import division

import unittest
import numpy as np
import sys

from fluiddyn.io import stdout_redirected
import fluiddyn.util.mpi as mpi
from fluiddyn.util.paramcontainer import ParamContainer

try:
    from fluidsim.operators.operators2d import OperatorsPseudoSpectral2D
except ValueError:
    NO_PYTHRAN = True
else:
    NO_PYTHRAN = False


def create_oper(type_fft=None):

    params = ParamContainer(tag='params')

    params._set_attrib('ONLY_COARSE_OPER', False)
    params._set_attrib('f', 0)
    params._set_attrib('c2', 100)
    params._set_attrib('kd2', 0)

    OperatorsPseudoSpectral2D._complete_params_with_default(params)

    nh = 8
    params.oper.nx = nh
    params.oper.ny = nh
    Lh = 6.
    params.oper.Lx = Lh
    params.oper.Ly = Lh

    if type_fft is not None:
        params.oper.type_fft = type_fft

    params.oper.coef_dealiasing = 2./3

    with stdout_redirected():
        oper = OperatorsPseudoSpectral2D(params=params)

    return oper


def compute_increments_dim1_old(var, irx):
    """Old version of the function compute_increments_dim1."""
    n0 = var.shape[0]
    n1 = var.shape[1]
    n1new = n1 - irx
    inc_var = np.empty([n0, n1new])
    for i0 in range(n0):
        for i1 in range(n1new):
            inc_var[i0, i1] = (var[i0, i1 + irx] - var[i0, i1])
    return inc_var


@unittest.skipIf(
    NO_PYTHRAN,
    'Pythran extension fluidsim.operators.util2d_pythran unavailable')
@unittest.skipIf(sys.platform.startswith('win'), 'Untested on Windows')
class TestOperators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oper = create_oper()
        cls.rtol = 1e-15
        cls.atol = 1e-14  # Absolute tolerance for double precision FFT

    def test_curl(self):
        """Test curl"""
        oper = self.oper
        rot = oper.random_arrayX()
        rot_fft = oper.fft2(rot)
        if mpi.rank == 0:
            rot_fft[0, 0] = 0.

        ux_fft, uy_fft = oper.vecfft_from_rotfft(rot_fft)
        rot2_fft = oper.rotfft_from_vecfft(ux_fft, uy_fft)

        np.testing.assert_allclose(rot2_fft, rot_fft, self.rtol, self.atol)

    def test_uxuyeta_qapam_conversion(self):
        """Test conversion back and forth from q,ap,am -> ux, uy, eta"""
        oper = self.oper
        q_fft = oper.random_arrayK()
        ap_fft = oper.random_arrayK()
        am_fft = oper.random_arrayK()
        if mpi.rank == 0:
            q_fft[0, 0] = ap_fft[0, 0] = am_fft[0, 0] = 0.

        ux_fft, uy_fft, eta_fft = oper.uxuyetafft_from_qapamfft(
            q_fft, ap_fft, am_fft)
        q2_fft, ap2_fft, am2_fft = oper.qapamfft_from_uxuyetafft(
            ux_fft, uy_fft, eta_fft)

        np.testing.assert_allclose(q2_fft, q_fft, self.rtol, self.atol)
        np.testing.assert_allclose(ap2_fft, ap_fft, self.rtol, self.atol)
        np.testing.assert_allclose(am2_fft, am_fft, self.rtol, self.atol)

    def test_laplacian2(self):
        oper = self.oper
        ff = oper.random_arrayX()
        ff_fft = oper.fft2(ff)
        if mpi.rank == 0:
            ff_fft[0, 0] = 0.

        lap_fft = oper.laplacian2_fft(ff_fft)
        ff_fft_back = oper.invlaplacian2_fft(lap_fft)

        np.testing.assert_allclose(ff_fft, ff_fft_back, self.rtol, self.atol)

    def test_compute_increments_dim1(self):
        """Test computing increments of var over the dim 1."""
        oper = self.oper
        var = oper.random_arrayX()
        def assert_increments_equal(irx):
            inc_var = oper.compute_increments_dim1(var, irx)
            inc_var_old = compute_increments_dim1_old(var, irx)
            np.testing.assert_equal(inc_var_old, inc_var)

        n1 = oper.shapeX[1]
        for irx in [n1, n1 // 2, 0]:
            assert_increments_equal(irx)

if __name__ == '__main__':
    unittest.main()