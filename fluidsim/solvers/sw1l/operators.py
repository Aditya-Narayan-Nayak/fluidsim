"""Operators sw1l (:mod:`fluidsim.operators.operators`)
=======================================================

Provides

.. autoclass:: OperatorsPseudoSpectralSW1L
   :members:
   :private-members:

"""

from fluidsim.operators.operators2d import OperatorsPseudoSpectral2D, rank

from . import util_oper_pythran


class OperatorsPseudoSpectralSW1L(OperatorsPseudoSpectral2D):

    def qapamfft_from_uxuyetafft(self, ux_fft, uy_fft, eta_fft, params=None):
        """ux, uy, eta (fft) ---> q, ap, am (fft)"""

        if params is None:
            params = self.params

        n0 = self.nK0_loc
        n1 = self.nK1_loc

        KX = self.KX
        KY = self.KY
        K2 = self.K2
        Kappa_over_ic = self.Kappa_over_ic
        f = float(params.f)
        c2 = float(params.c2)

        return util_oper_pythran.qapamfft_from_uxuyetafft(
            ux_fft,
            uy_fft,
            eta_fft,
            n0,
            n1,
            KX,
            KY,
            K2,
            Kappa_over_ic,
            f,
            c2,
            rank,
        )

    def vecfft_from_rotdivfft(self, rot_fft, div_fft):
        """Inverse of the Helmholtz decomposition."""
        # TODO: Pythranize
        urx_fft, ury_fft = self.vecfft_from_rotfft(rot_fft)
        udx_fft, udy_fft = self.vecfft_from_divfft(div_fft)
        ux_fft = urx_fft + udx_fft
        uy_fft = ury_fft + udy_fft
        return ux_fft, uy_fft
