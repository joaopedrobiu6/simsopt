import numpy as np
from simsopt.util.mpi import MpiPartition
from simsopt.mhd.vmec import Vmec
from simsopt.mhd.vmec_diagnostics import QuasisymmetryRatioResidual
from simsopt.objectives import ConstrainedProblem
from simsopt.solve.mpi import constrained_mpi_solve
import os

"""
Optimize a VMEC equilibrium for quasi-helical symmetry (M=1, N=1)
throughout the volume.

Solve as a constrained opt problem
min QH symmetry error
s.t. 
  aspect ratio <= 8
  -1.00 <= iota <= -1.05

Run with 
  mpiexec -n 9 constrained_optimization.py
"""

# This problem has 8 degrees of freedom, so we can use 8 + 1 = 9
# concurrent function evaluations for 1-sided finite difference
# gradients.
mpi = MpiPartition(9)

if mpi.proc0_world:
    print("Running 2_Intermediate/constrained_optimization.py")
    print("=============================================")


vmec_input = os.path.join(os.path.dirname(__file__), 'inputs', 'input.nfp4_QH_warm_start')
vmec = Vmec(vmec_input, mpi=mpi,verbose=False)
surf = vmec.boundary

# Configure quasisymmetry objective:
qs = QuasisymmetryRatioResidual(vmec,
                                np.arange(0, 1.01, 0.1),  # Radii to target
                                helicity_m=1, helicity_n=1)  # (M, N) you want in |B|
# nonlinear constraints
tuples_nlc = [(vmec.aspect,-np.inf,8),(vmec.mean_iota,-1.05,-1.0)]

# define problem
prob = ConstrainedProblem(qs.total,tuples_nlc=tuples_nlc)

vmec.run()
if mpi.proc0_world:
    print("Initial Quasisymmetry:", qs.total())
    print("Initial aspect ratio:", vmec.aspect())
    print("Initial rotational transform:", vmec.mean_iota())


# Fourier modes of the boundary with m <= max_mode and |n| <= max_mode
# will be varied in the optimization. A larger range of modes are
# included in the VMEC and booz_xform calculations.
for step in range(3):
    max_mode = step + 1

    # VMEC's mpol & ntor will be 3, 4, 5:
    vmec.indata.mpol = 3 + step
    vmec.indata.ntor = vmec.indata.mpol

    if mpi.proc0_world:
        print("Beginning optimization with max_mode =", max_mode, \
              ", vmec mpol=ntor=", vmec.indata.mpol, \
              ". Previous vmec iteration = ", vmec.iter)

    # Define parameter space:
    surf.fix_all()
    surf.fixed_range(mmin=0, mmax=max_mode, 
                     nmin=-max_mode, nmax=max_mode, fixed=False)
    surf.fix("rc(0,0)")  # Major radius

    # solver options
    options = {'disp':True, 'ftol':1e-7, 'maxiter':300}
    # solve the problem
    constrained_mpi_solve(prob,mpi,grad=True, rel_step=1e-5, abs_step=1e-7,options=options)
    xopt = prob.x

    # Preserve the output file from the last iteration, so it is not
    # deleted when vmec runs again:
    vmec.files_to_delete = []

    # evaluate the solution
    surf.x = xopt
    vmec.run()
    if mpi.proc0_world:
        print("")
        print(f"Complted optimization with max_mode ={max_mode}. ")
        print(f"Final vmec iteration = {vmec.iter}")
        print("Quasisymmetry:", qs.total())
        print("aspect ratio:", vmec.aspect())
        print("rotational transform:", vmec.mean_iota())


if mpi.proc0_world:
    print("")
    print("End of 2_Intermediate/constrained_optimization.py")
    print("============================================")

