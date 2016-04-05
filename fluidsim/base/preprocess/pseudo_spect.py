"""Preprocessing for pseudo-spectral solvers (:mod:`fluiddyn.simul.base.preprocess.pseudo_spect`)
================================================================================================

Provides:

.. autoclass:: PreprocessPseudoSpectral
   :members:
   :private-members:


"""
from __future__ import division

import numpy as np
from .base import PreprocessBase


class PreprocessPseudoSpectral(PreprocessBase):
    _tag = 'pseudo_spectral'

    def __call__(self):
        """Preprocesses if enabled."""

        super(PreprocessPseudoSpectral, self).__call__()
        if self.params.enable:
            if self.sim.params.FORCING:
                if 'forcing' in self.params.init_field_scale:
                    self.set_forcing_rate()
                    self.normalize_init_fields()
                else:
                    self.normalize_init_fields()
                    self.set_forcing_rate()
            else:
                self.normalize_init_fields()

            self.sim.state.clear_computed()
            self.set_viscosity()
            self.output.save_info_solver_params_xml(replace=True)

    def normalize_init_fields(self):
        """
        A non-dimensionalization procedure for the initialized fields.

        Parameters
        ----------------
        params.preprocess.init_field_scale : string
            Set quantity to normalize initialized fields with.
             (use 'energy', 'enstrophy', 'enstrophy_forcing' or 'unity')

        params.preprocess.init_field_const : float
            Non-dimensional ratio of the desired initialized field to the scale.

        """
        state = self.sim.state
        scale = self.params.init_field_scale
        C = self.params.init_field_const

        if scale == 'energy':
            try:
                Ek, = self.output.compute_quad_energies()
            except:
                Ek = self.output.compute_energy()

            ux_fft = state('ux_fft')
            uy_fft = state('uy_fft')

            if Ek != 0.:
                ux_fft = (C / Ek) ** 0.5 * ux_fft
                uy_fft = (C / Ek) ** 0.5 * uy_fft

            try:
                state.init_from_uxuyfft(ux_fft, uy_fft)
            except AttributeError:
                rot_fft = self.oper.rotfft_from_vecfft(ux_fft, uy_fft)
                state.init_statefft_from(rot_fft=rot_fft)
        elif scale == 'enstrophy':
            omega_0 = self.output.compute_enstrophy()
            rot_fft = state('rot_fft')

            if omega_0 != 0.:
                rot_fft = (C / omega_0) ** 0.5 * rot_fft
                state.init_from_rotfft(rot_fft)
            
        elif scale == 'enstrophy_forcing':
            P = self.sim.params.forcing.forcing_rate
            k_f = self.oper.deltakh * ((self.sim.params.forcing.nkmax_forcing +
                                        self.sim.params.forcing.nkmin_forcing) // 2)
            omega_0 = self.output.compute_enstrophy()
            rot_fft = state('rot_fft')

            if omega_0 != 0.:
                C_0 = omega_0 / (P ** (2. / 3) * k_f ** (4. / 3))
                rot_fft = (C / C_0) ** 0.5 * rot_fft
                state.init_from_rotfft(rot_fft)

        elif scale == 'unity':
            pass
        else:
            raise ValueError('Unknown initial fields scaling: ', scale)

    def set_viscosity(self):
        """Based on

        - the initial total enstrophy, :math:`\Omega_0`, or

        - the initial energy

        - the forcing rate, :math:`\epsilon`

        the viscosity scale or Reynolds number is set.

        Parameters
        ----------

        params.preprocess.viscosity_type : string
          Type/Order of viscosity desired

        params.preprocess.viscosity_scale : string
          Mean quantity to be scaled against

        params.preprocess.viscosity_const : float
          Calibration constant to set dissipative wave number

        Note
        ----

        Algorithm: Sets viscosity variable nu and reinitializes f_d array for
        timestepping

        """
        params = self.params
        viscosity_type = params.viscosity_type
        viscosity_scale = params.viscosity_scale
        C = params.viscosity_const

        delta_x = self.oper.deltax
        # Smallest resolved scale
        k_max = np.pi / delta_x * self.sim.params.oper.coef_dealiasing
        # OR np.pi / k_d, the dissipative wave number
        length_scale = C * np.pi / k_max

        if viscosity_scale == 'enstrophy':
            omega_0 = self.output.compute_enstrophy()
            eta = omega_0 ** 1.5                   # Enstrophy dissipation rate
            time_scale = eta ** (-1. / 3)
        elif viscosity_scale == 'enstrophy_forcing':
            omega_0 = self.output.compute_enstrophy()
            eta = omega_0 ** 1.5
            t1 = eta ** (-1. / 3)
            # Energy dissipation rate
            epsilon = self.sim.params.forcing.forcing_rate
            t2 = epsilon ** (-1./3) * length_scale ** (2./3)
            time_scale = min(t1, t2)
        elif viscosity_scale == 'energy_enstrophy':
            energy_0 = self.output.compute_energy()
            omega_0 = self.output.compute_enstrophy()
            epsilon = energy_0 * (omega_0 ** 0.5)
            time_scale = epsilon ** (-1./3) * length_scale ** (2./3)
        elif viscosity_scale == 'forcing':
            epsilon = self.sim.params.forcing.forcing_rate
            time_scale = epsilon ** (-1./3) * length_scale ** (2./3)
        else:
            raise ValueError('Unknown viscosity scale: %s' % viscosity_scale)

        self.sim.params.nu_2 = 0
        self.sim.params.nu_4 = 0
        self.sim.params.nu_8 = 0
        self.sim.params.nu_m4 = 0

        if viscosity_type == 'laplacian':
            self.sim.params.nu_2 = length_scale ** 2. / time_scale
        elif viscosity_type == 'hyper4':
            self.sim.params.nu_4 = -length_scale ** 4. / time_scale
        elif viscosity_type == 'hyper8':
            self.sim.params.nu_8 = length_scale ** 8. / time_scale
        elif viscosity_type == 'hypo':
            self.sim.params.nu_m4 = length_scale ** (-4.) / time_scale
        else:
            raise ValueError('Unknown viscosity type: %s' % viscosity_type)

        self.sim.time_stepping.__init__(self.sim)

    def set_forcing_rate(self):
        r""" Based on C, a non-dimensional ratio of forcing rate to one of the
        following forcing scales

        - the initial total energy, math::`E_0`
        - the initial total enstrophy, math::`\Omega_0`

        the forcing rate is set.

        Parameters
        ----------

        params.preprocess.forcing_const : float
          Non-dimensional ratio of forcing_scale to forcing_rate

        params.preprocess.forcing_scale : string
          Mean quantity to be scaled against

        .. TODO : Trivial error in computing forcing rate
        """
        params = self.params

        forcing_scale = params.forcing_scale
        C = params.forcing_const
        # Forcing wavenumber
        k_f = self.oper.deltakh * ((self.sim.params.forcing.nkmax_forcing +
                                    self.sim.params.forcing.nkmin_forcing) // 2)

        if forcing_scale == 'unity':
            self.sim.params.forcing.forcing_rate = C
        elif forcing_scale == 'energy':
            energy_0 = self.output.compute_energy()
            self.sim.params.forcing.forcing_rate = C * energy_0 ** 1.5 * k_f
        elif forcing_scale == 'enstrophy':
            omega_0 = self.output.compute_enstrophy()
            self.sim.params.forcing.forcing_rate = C * omega_0 ** 1.5 / k_f ** 2
        else:
            raise ValueError('Unknown forcing scale: %s' % forcing_scale)

        self.sim.forcing.__init__(self.sim)