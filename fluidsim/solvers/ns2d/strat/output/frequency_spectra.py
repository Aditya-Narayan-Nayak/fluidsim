"""
FrequencySpectra (:mod:`fluidsim.solvers.ns2d.strat.output.frequency_spectra`)
==============================================================================


Provides:

.. autoclass:: FrequencySpectra
   :members:
   :private-members:

"""

import os
import sys
import time
import numpy as np
import h5py
import math
import matplotlib.pyplot as plt

from math import pi
from glob import glob
from scipy import signal

from fluiddyn.util import mpi
from fluidsim.base.output.base import SpecificOutput


class FrequencySpectra(SpecificOutput):
    """
    Computes the frequency spectra.
    """

    _tag = "frequency_spectra"
    _name_file = _tag + ".h5"

    @staticmethod
    def _complete_params_with_default(params):
        tag = "frequency_spectra"

        params.output.periods_save._set_attrib(tag, 0)
        params.output._set_child(
            tag,
            attribs={
                "HAS_TO_PLOT_SAVED": False,
                "time_start": 1,
                "time_decimate": 1,
                "spatial_decimate": 2,
                "size_max_file": 0.1,
            },
        )

    def __init__(self, output):
        params = output.sim.params
        pfreq_spectra = params.output.frequency_spectra
        super(FrequencySpectra, self).__init__(
            output,
            period_save=params.output.periods_save.frequency_spectra,
            has_to_plot_saved=pfreq_spectra.HAS_TO_PLOT_SAVED,
        )

        # Parameters
        self.time_start = pfreq_spectra.time_start
        self.time_decimate = pfreq_spectra.time_decimate
        self.spatial_decimate = pfreq_spectra.spatial_decimate
        self.size_max_file = pfreq_spectra.size_max_file
        self.periods_save = params.output.periods_save.frequency_spectra

        # Number points each direction
        n0 = len(list(range(0, params.oper.ny, self.spatial_decimate)))
        n1 = len(list(range(0, params.oper.nx, self.spatial_decimate)))

        # Compute number array in file
        nb_bytes = np.empty([n0, n1], dtype=float).nbytes
        self.nb_arr_in_file = int(self.size_max_file * (1024 ** 2) // nb_bytes)
        if mpi.rank == 0:
            print("nb_arr_in_file_frequency_spectra = ", self.nb_arr_in_file)

        # Check: duration file <= duration simulation
        self.duration_file = (
            self.nb_arr_in_file
            * self.params.time_stepping.deltat0
            * self.time_decimate
        )
        if (
            self.duration_file > self.params.time_stepping.t_end
            and self.periods_save > 0
        ):
            raise ValueError(
                "The duration of the simulation is not enough to fill a file."
            )

        # Check: self.nb_arr_in_file should be > 0
        if self.nb_arr_in_file <= 0 and self.periods_save > 0:
            raise ValueError("The size of the file should be larger.")

        else:
            self.temp_array = np.empty([self.nb_arr_in_file, n0, n1], dtype=float)

            # Array 4D (2 keys, times, n0, n1)
            self.temp_array_new = np.empty(
                [2, self.nb_arr_in_file, n0, n1], dtype=float
            )

        # Convert time_start to it_start
        self.it_start = int(self.time_start / self.params.time_stepping.deltat0)

        # Create empty array with times
        self.times_arr = np.empty([self.nb_arr_in_file])

        if (
            params.time_stepping.USE_CFL
            and params.output.periods_save.frequency_spectra > 0
        ):
            raise ValueError(
                "To compute the frequency spectra: \n"
                + "USE_CFL = FALSE and periods_save.frequency_spectra > 0"
            )

        # Create directory to save files
        if mpi.rank == 0:
            dir_name = "temporal_data"
            self.path_dir = os.path.join(self.sim.output.path_run, dir_name)

            if not os.path.exists(self.path_dir):
                os.mkdir(self.path_dir)

        # Start loop in _online_save
        self.it_last_run = self.it_start
        self.nb_times_in_temp_array = 0

    def _init_files(self, dict_arrays_1time=None):
        # we can not do anything when this function is called.
        pass

    def _write_to_file(self, temp_arr, times_arr):
        """Writes a file with the temporal data"""
        if mpi.rank == 0:
            # Name file
            it_start = int(times_arr[0] / self.sim.params.time_stepping.deltat0)
            name_file = "temp_array_it={}.h5".format(it_start)
            path_file = os.path.join(self.path_dir, name_file)

            # Dictionary arrays
            dict_arr = {
                "it_start": it_start,
                "times_arr": times_arr,
                "temp_arr": temp_arr,
            }

            # Write dictionary to file
            with h5py.File(path_file, "w") as f:
                for k, v in list(dict_arr.items()):
                    f.create_dataset(k, data=v)

    def _online_save(self):
        """Computes and saves the values at one time."""
        if self.periods_save == 0:
            pass
        else:
            itsim = int(
                self.sim.time_stepping.t / self.sim.params.time_stepping.deltat0
            )

            if itsim - self.it_last_run >= self.time_decimate:
                self.it_last_run = itsim

                # Save the field to self.temp_array_new
                field_ap = self.sim.state.compute("ap")
                field_am = self.sim.state.compute("am")

                field_ap_seq = None
                field_am_seq = None

                field = self.sim.state.compute("ap")
                field_seq = None
                # print("rank = {} ; kx_loc = {}".format(mpi.comm.Get_rank(), self.sim.oper.kx_loc))
                # Create empty array in process 0.
                if mpi.rank == 0:
                    field_ap_seq = np.empty(
                        (self.sim.params.oper.nx, self.sim.params.oper.ny),
                        dtype=float,
                    )

                    field_am_seq = np.empty(
                        (self.sim.params.oper.nx, self.sim.params.oper.ny),
                        dtype=float,
                    )

                    field_seq = np.empty(
                        (self.sim.params.oper.nx, self.sim.params.oper.ny),
                        dtype=float,
                    )

                if mpi.nb_proc > 1:
                    mpi.comm.Gather(field, field_seq, root=0)

                    mpi.comm.Gather(field_ap, field_ap_seq, root=0)

                    mpi.comm.Gather(field_am, field_am_seq, root=0)

                    # Transpose of the array.
                    if mpi.rank == 0:
                        field = np.transpose(field_seq)

                        field_ap = np.transpose(field_ap_seq)
                        field_am = np.transpose(field_am_seq)
                # else:
                #     # I remove the last kx to be coherent with arrays in MPI.
                #     # Consequences: Remove energy in last kx ONLY for computing
                #     # the frequency spectra
                #     field = field[:, :-1]

                #     field_ap = field_ap[:, :-1]
                #     field_am = field_am[:, :-1]

                # Decimation of the field
                if mpi.rank == 0:
                    field_decimate = field[
                        :: self.spatial_decimate, :: self.spatial_decimate
                    ]

                    field_ap_decimate = field_ap[
                        :: self.spatial_decimate, :: self.spatial_decimate
                    ]

                    field_am_decimate = field_am[
                        :: self.spatial_decimate, :: self.spatial_decimate
                    ]

                    self.temp_array[
                        self.nb_times_in_temp_array, :, :
                    ] = field_decimate

                    self.temp_array_new[
                        0, self.nb_times_in_temp_array, :, :
                    ] = field_ap_decimate
                    self.temp_array_new[
                        1, self.nb_times_in_temp_array, :, :
                    ] = field_am_decimate

                # Save the time to self.times_arr
                self.times_arr[self.nb_times_in_temp_array] = (
                    itsim * self.sim.params.time_stepping.deltat0
                )

                # Check if self.temp_array_new is filled. If yes, writes to a file.
                if self.nb_times_in_temp_array == self.nb_arr_in_file - 1:
                    if mpi.rank == 0:
                        print("Saving temporal data...")
                    self._write_to_file(self.temp_array_new, self.times_arr)

                    self.nb_times_in_temp_array = 0
                else:
                    self.nb_times_in_temp_array += 1

    def compute_frequency_spectra(self):
        """
        Computes and saves the frequency spectra.
        """
        # Define list of path files
        list_files = glob(os.path.join(self.path_dir, "temp_array_it=*"))

        # Compute sampling frequency
        freq_sampling = 1.0 / (
            self.time_decimate * self.params.time_stepping.deltat0
        )

        for index, file_path in enumerate(list_files):

            # Generating counter
            print(
                "Computing frequency spectra = {}/{}".format(
                    index, len(list_files) - 1
                ),
                end="\r",
            )

            # Load data from file
            with h5py.File(file_path, "r") as f:
                temp_array = f["temp_arr"].value
                times = f["times_arr"].value

            # Compute the temporal spectrum of a 3D array
            omegas, freq_spectrum = signal.periodogram(
                temp_array,
                fs=freq_sampling,
                window="hann",
                nfft=temp_array.shape[1],
                detrend="constant",
                return_onesided=False,
                scaling="spectrum",
                axis=1,
            )

            # Save array omegas and spectrum to file
            dict_arr = {"omegas": omegas, "freq_spectrum": freq_spectrum}

            with h5py.File(file_path, "r+") as f:
                for k, v in list(dict_arr.items()):
                    f.create_dataset(k, data=v)

            # Flush buffer and sleep time
            sys.stdout.flush()
            time.sleep(0.2)