# -*- coding: utf-8 -*-

"""Stratified NS3D solver (:mod:`fluidsim.solvers.ns3d.strat.solver`)
=====================================================================

.. autoclass:: InfoSolverNS3DStrat
   :members:
   :private-members:

.. autoclass:: Simul
   :members:
   :private-members:

"""
from __future__ import division

from fluidsim.base.setofvariables import SetOfVariables

from ..solver import InfoSolverNS3D, Simul as SimulNS3D


class InfoSolverNS3DStrat(InfoSolverNS3D):
    def _init_root(self):

        super(InfoSolverNS3DStrat, self)._init_root()

        package = 'fluidsim.solvers.ns3d.strat'
        self.module_name = package + '.solver'
        self.class_name = 'Simul'
        self.short_name = 'ns3d.strat'

        classes = self.classes

        classes.State.module_name = package + '.state'
        classes.State.class_name = 'StateNS3DStrat'

        # classes.InitFields.module_name = package + '.init_fields'
        # classes.InitFields.class_name = 'InitFieldsNS3D'

        # classes.Output.module_name = package + '.output'
        # classes.Output.class_name = 'Output'

        # classes.Forcing.module_name = package + '.forcing'
        # classes.Forcing.class_name = 'ForcingNS3D'


class Simul(SimulNS3D):
    r"""Pseudo-spectral solver 3D incompressible Navier-Stokes equations.

    Notes
    -----

    .. |p| mathmacro:: \partial

    .. |vv| mathmacro:: \textbf{v}

    .. |kk| mathmacro:: \textbf{k}

    .. |ek| mathmacro:: \hat{\textbf{e}}_\textbf{k}

    .. |bnabla| mathmacro:: \boldsymbol{\nabla}

    This class is dedicated to solve with a pseudo-spectral method the
    incompressible Navier-Stokes equations (possibly with hyper-viscosity):

    .. math::
      \p_t \vv + \vv \cdot \bnabla \vv =
      - \bnabla p  - \nu_\alpha (-\Delta)^\alpha \vv,

    where :math:`\vv` is the non-divergent velocity (:math:`\bnabla
    \cdot \vv = 0`), :math:`p` is the pressure, :math:`\Delta` is the
    3D Laplacian operator.

    In Fourier space, these equations can be written as:

    .. math::
      \p_t \hat v = N(v) + L \hat v,

    where

    .. math::

      N(\vv) = -P_\perp \widehat{\bnabla \cdot \vv \vv},

    .. math::

      L = - \nu_\alpha |\kk|^{2\alpha},

    with :math:`P_\perp = (1 - \ek \ek \cdot)` the operator projection on the
    plane perpendicular to the wave number :math:`\kk`. Since the flow is
    incompressible (:math:`\kk \cdot \vv = 0`), the effect of the pressure term
    is taken into account with the operator :math:`P_\perp`.

    """
    InfoSolver = InfoSolverNS3DStrat

    @staticmethod
    def _complete_params_with_default(params):
        """This static method is used to complete the *params* container.
        """
        SimulNS3D._complete_params_with_default(params)
        attribs = {'N': 1., 'NO_SHEAR_MODES': False}
        params._set_attribs(attribs)

    def tendencies_nonlin(self, state_spect=None):
        oper = self.oper
        # fft3d = oper.fft3d
        ifft3d = oper.ifft3d

        if state_spect is None:
            vx = self.state.state_phys.get_var('vx')
            vy = self.state.state_phys.get_var('vy')
            vz = self.state.state_phys.get_var('vz')
            b = self.state.state_phys.get_var('b')
            vz_fft = self.state.state_spect.get_var('vz_fft')
            b_fft = self.state.state_spect.get_var('b_fft')
        else:
            vx_fft = state_spect.get_var('vx_fft')
            vy_fft = state_spect.get_var('vy_fft')
            vz_fft = state_spect.get_var('vz_fft')
            b_fft = state_spect.get_var('b_fft')
            vx = ifft3d(vx_fft)
            vy = ifft3d(vy_fft)
            vz = ifft3d(vz_fft)
            b = ifft3d(b_fft)

        Fvx_fft, Fvy_fft, Fvz_fft = oper.div_vv_fft_from_v(vx, vy, vz)
        
        Fvx_fft, Fvy_fft, Fvz_fft = -Fvx_fft, -Fvy_fft, -Fvz_fft
        Fvz_fft += b_fft

        Fb_fft = -oper.div_vb_fft_from_vb(vx, vy, vz, b) - \
                 self.params.N**2 * vz_fft
        
        oper.project_perpk3d(Fvx_fft, Fvy_fft, Fvz_fft)

        tendencies_fft = SetOfVariables(
            like=self.state.state_spect,
            info='tendencies_nonlin')

        tendencies_fft.set_var('vx_fft', Fvx_fft)
        tendencies_fft.set_var('vy_fft', Fvy_fft)
        tendencies_fft.set_var('vz_fft', Fvz_fft)
        tendencies_fft.set_var('b_fft', Fb_fft)

        if self.is_forcing_enabled:
            tendencies_fft += self.forcing.get_forcing()

        return tendencies_fft


if __name__ == "__main__":

    import numpy as np

    import fluiddyn as fld

    params = Simul.create_default_params()

    params.short_name_type_run = 'test'

    n = 16
    L = 2*np.pi
    params.oper.nx = n
    params.oper.ny = n
    params.oper.nz = n
    params.oper.Lx = L
    params.oper.Ly = L
    params.oper.Lz = L
    params.oper.type_fft = 'fluidfft.fft3d.mpi_with_fftwmpi3d'
    # params.oper.type_fft = 'fluidfft.fft3d.with_fftw3d'
    # params.oper.type_fft = 'fluidfft.fft3d.with_cufft'

    delta_x = params.oper.Lx / params.oper.nx
    # params.nu_8 = 2.*10e-1*params.forcing.forcing_rate**(1./3)*delta_x**8
    params.nu_8 = 2.*10e-1*delta_x**8

    params.time_stepping.USE_T_END = True
    params.time_stepping.t_end = 6.
    params.time_stepping.it_end = 2

    params.init_fields.type = 'noise'
    params.init_fields.noise.velo_max = 1.
    params.init_fields.noise.length = 1.

    # params.forcing.enable = False
    # params.forcing.type = 'random'
    # 'Proportional'
    # params.forcing.type_normalize

    params.output.periods_print.print_stdout = 0.00000000001

    params.output.periods_save.phys_fields = 1.
    # params.output.periods_save.spectra = 0.5
    # params.output.periods_save.spatial_means = 0.05
    # params.output.periods_save.spect_energy_budg = 0.5

    # params.output.periods_plot.phys_fields = 0.0

    params.output.ONLINE_PLOT_OK = True

    # params.output.spectra.HAS_TO_PLOT_SAVED = True
    # params.output.spatial_means.HAS_TO_PLOT_SAVED = True
    # params.output.spect_energy_budg.HAS_TO_PLOT_SAVED = True

    # params.output.phys_fields.field_to_plot = 'rot'

    sim = Simul(params)

    # sim.output.phys_fields.plot()
    sim.time_stepping.start()
    # sim.output.phys_fields.plot()

    fld.show()