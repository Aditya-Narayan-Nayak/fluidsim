#!/usr/bin/env python
"""
python simul_profile.py
mpirun -np 2 python simul_profile.py

FLUIDSIM_NO_FLUIDFFT=1 python simul_profile.py

"""

import os

# from fluidsim.solvers.ns2d import solver
from fluidsim.solvers.sw1l import solver

params = solver.Simul.create_default_params()

params.short_name_type_run = 'profile'

nh = 512//4
params.oper.nx = nh
params.oper.ny = nh
Lh = 6.
params.oper.Lx = Lh
params.oper.Ly = Lh

if 'FLUIDSIM_PRIORITY_FLUIDFFT' in os.environ:
    # params.oper.type_fft = 'fft2d.mpi_with_fftwmpi2d'
    pass

params.oper.coef_dealiasing = 2./3

params.FORCING = True
params.forcing.type = 'tcrandom'
params.forcing.nkmax_forcing = 5
params.forcing.nkmin_forcing = 4
params.forcing.forcing_rate = 1.


delta_x = Lh/nh
params.nu_8 = 2.*10e-1*params.forcing.forcing_rate**(1./3)*delta_x**8

try:
    params.f = 1.
    params.c2 = 200.
except (KeyError, AttributeError):
    pass

params.time_stepping.deltat0 = 1.e-4
params.time_stepping.USE_CFL = False

params.time_stepping.it_end = 10
params.time_stepping.USE_T_END = False


params.output.periods_print.print_stdout = 0

params.output.HAS_TO_SAVE = 1
params.output.periods_save.phys_fields = 0.1
params.output.periods_save.spatial_means = 0.1
params.output.periods_save.spectra = 0.1
params.output.periods_save.spect_energy_budg = 0.1
params.output.periods_save.increments = 0.1


sim = solver.Simul(params)

if __name__ == '__main__':
    from util_bench import profile
    profile(sim)