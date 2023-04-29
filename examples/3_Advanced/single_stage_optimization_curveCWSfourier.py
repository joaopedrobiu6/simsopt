#!/usr/bin/env python3
r"""
In this example we both a stage 1 and stage 2 optimization problems using the
single stage approach of R. Jorge et al in https://arxiv.org/abs/2302.10622
The objective function in this case is J = J_stage1 + coils_objective_weight*J_stage2
To accelerate convergence, a stage 2 optimization is done before the single stage one.
Rogerio Jorge, April 2023
"""
import os
import glob
import time
import numpy as np
from mpi4py import MPI
from pathlib import Path
from scipy.optimize import minimize
from simsopt import load
from simsopt.util import MpiPartition
from simsopt.geo import SurfaceRZFourier
from simsopt._core.derivative import Derivative
from simsopt.mhd import Vmec, QuasisymmetryRatioResidual
from simsopt._core.finite_difference import MPIFiniteDifference
from simsopt.field import BiotSavart, Current, coils_via_symmetries
from simsopt.objectives import SquaredFlux, QuadraticPenalty, LeastSquaresProblem
from simsopt.geo import (CurveLength, CurveCurveDistance, MeanSquaredCurvature, CurveCWSFourier,
                         LpCurveCurvature, ArclengthVariation, curves_to_vtk, create_equally_spaced_curves)
comm = MPI.COMM_WORLD


def pprint(*args, **kwargs):
    if comm.rank == 0:
        print(*args, **kwargs)


mpi = MpiPartition()
parent_path = str(Path(__file__).parent.resolve())
os.chdir(parent_path)
start = time.time()
##########################################################################################
############## Input parameters
##########################################################################################
max_mode = 1
MAXITER_stage_2 = 40
MAXITER_single_stage = 20
vmec_input_filename = os.path.join(parent_path, 'inputs', 'input.nfp2_QA')
ncoils = 5
nmodes_coils = 10
quadpoints = 13 * nmodes_coils
aspect_ratio_target = 7.0
CC_THRESHOLD = 0.1
LENGTH_THRESHOLD = 6.5
CURVATURE_THRESHOLD = 15
MSC_THRESHOLD = 15
nphi_VMEC = 32
ntheta_VMEC = 32
coils_objective_weight = 1e+3
aspect_ratio_weight = 1
diff_method = "forward"
R0 = 1.0
R1 = 0.6
minor_radius_factor_cws = 2.5
quasisymmetry_target_surfaces = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
finite_difference_abs_step = 1e-4
finite_difference_rel_step = 1e-3
JACOBIAN_THRESHOLD = 10000
LENGTH_CON_WEIGHT = 0.1  # Weight on the quadratic penalty for the curve length
LENGTH_WEIGHT = 1e-8  # Weight on the curve lengths in the objective function
CC_WEIGHT = 5e3  # Weight for the coil-to-coil distance penalty in the objective function
CURVATURE_WEIGHT = 1e-3  # Weight for the curvature penalty in the objective function
MSC_WEIGHT = 1e-3 # Weight for the mean squared curvature penalty in the objective function
ARCLENGTH_WEIGHT = 1e-9  # Weight for the arclength variation penalty in the objective function
##########################################################################################
##########################################################################################
directory = f'optimization_QA_cws_singlestage'
vmec_verbose = False
# Create output directories
this_path = os.path.join(parent_path, directory)
os.makedirs(this_path, exist_ok=True)
os.chdir(this_path)
vmec_results_path = os.path.join(this_path, "vmec")
coils_results_path = os.path.join(this_path, "coils")
if comm.rank == 0:
    os.makedirs(vmec_results_path, exist_ok=True)
    os.makedirs(coils_results_path, exist_ok=True)
##########################################################################################
##########################################################################################
# Stage 1
pprint(f' Using vmec input file {vmec_input_filename}')
vmec = Vmec(vmec_input_filename, mpi=mpi, verbose=vmec_verbose, nphi=nphi_VMEC, ntheta=ntheta_VMEC, range_surface='half period')
surf = vmec.boundary
##########################################################################################
##########################################################################################
#Stage 2
cws = SurfaceRZFourier.from_nphi_ntheta(nphi_VMEC, ntheta_VMEC, "half period", surf.nfp)
cws.set_dofs([surf.get_rc(0, 0), surf.get_zs(1, 0)*minor_radius_factor_cws, surf.get_zs(1, 0)*minor_radius_factor_cws])

if os.path.exists(os.path.join(coils_results_path, "biot_savart_opt.json")):
    bs_temporary = load(os.path.join(coils_results_path, "biot_savart_opt.json"))
    ncoils = int(len(bs_temporary.coils)/surf.nfp/2)
    base_curves = [bs_temporary.coils[i]._curve for i in range(ncoils)]
    base_currents = [bs_temporary.coils[i]._current for i in range(ncoils)]
else:
    base_curves = []
    for i in range(ncoils):
        curve_cws = CurveCWSFourier(
            mpol=cws.mpol,
            ntor=cws.ntor,
            idofs=cws.x,
            quadpoints=quadpoints,
            order=nmodes_coils,
            nfp=cws.nfp,
            stellsym=cws.stellsym,
        )
        angle = (i+0.5)*(2*np.pi)/((2)*cws.nfp*ncoils)
        curve_dofs = np.zeros(len(curve_cws.get_dofs()),)
        curve_dofs[0] = 1
        curve_dofs[2*nmodes_coils+2] = 0
        curve_dofs[2*nmodes_coils+3] = angle
        curve_cws.set_dofs(curve_dofs)
        curve_cws.fix(0)
        curve_cws.fix(2*nmodes_coils+2)
        base_curves.append(curve_cws)
    base_currents = [Current(1)*1e5 for i in range(ncoils)]
    base_currents[0].fix_all()

##########################################################################################
##########################################################################################
# Save initial surface and coil data
coils = coils_via_symmetries(base_curves, base_currents, surf.nfp, True)
curves = [c.curve for c in coils]
bs = BiotSavart(coils)
bs.set_points(surf.gamma().reshape((-1, 3)))
Bbs = bs.B().reshape((nphi_VMEC, ntheta_VMEC, 3))
BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
if comm.rank == 0:
    curves_to_vtk(curves, os.path.join(coils_results_path, "curves_init"))
    pointData = {"B_N": BdotN_surf[:, :, None]}
    surf.to_vtk(os.path.join(coils_results_path, "surf_init"), extra_data=pointData)
    cws.to_vtk(os.path.join(coils_results_path, "cws_init"))
##########################################################################################
##########################################################################################
Jf = SquaredFlux(surf, bs, local=True)
Jls = [CurveLength(c) for c in base_curves]
Jccdist = CurveCurveDistance(curves, CC_THRESHOLD, num_basecurves=len(curves))
Jcs = [LpCurveCurvature(c, 2, CURVATURE_THRESHOLD) for i, c in enumerate(base_curves)]
Jmscs = [MeanSquaredCurvature(c) for c in base_curves]
Jals = [ArclengthVariation(c) for c in base_curves]
J_LENGTH = LENGTH_WEIGHT * sum(Jls)
J_CC = CC_WEIGHT * Jccdist
J_CURVATURE = CURVATURE_WEIGHT * sum(Jcs)
J_MSC = MSC_WEIGHT * sum(QuadraticPenalty(J, MSC_THRESHOLD) for i, J in enumerate(Jmscs))
J_ALS = ARCLENGTH_WEIGHT * sum(Jals)
J_LENGTH_PENALTY = LENGTH_CON_WEIGHT * sum([QuadraticPenalty(Jls[i], LENGTH_THRESHOLD) for i in range(len(base_curves))])
JF = Jf + J_CC + J_LENGTH_PENALTY + J_LENGTH + J_CURVATURE + J_MSC
##########################################################################################
pprint(f'  Starting optimization')
##########################################################################################
# Initial stage 2 optimization
##########################################################################################


def fun_coils(dofss, info):
    info['Nfeval'] += 1
    JF.x = dofss
    J = JF.J()
    grad = JF.dJ()
    if mpi.proc0_world:
        jf = Jf.J()
        Bbs = bs.B().reshape((nphi_VMEC, ntheta_VMEC, 3))
        BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
        BdotN = np.mean(np.abs(BdotN_surf))
        # BdotNmax = np.max(np.abs(BdotN_surf))
        outstr = f"fcoils#{info['Nfeval']} - J={J:.1e}, Jf={jf:.1e}, ⟨B·n⟩={BdotN:.1e}"  # , B·n max={BdotNmax:.1e}"
        outstr += f", ║∇J coils║={np.linalg.norm(JF.dJ()):.1e}, C-C-Sep={Jccdist.shortest_distance():.2f}"
        cl_string = ", ".join([f"{j.J():.1f}" for j in Jls])
        kap_string = ", ".join(f"{np.max(c.kappa()):.1f}" for c in base_curves)
        msc_string = ", ".join(f"{j.J():.1f}" for j in Jmscs)
        outstr += f" lengths=sum([{cl_string}])={sum(j.J() for j in Jls):.1f}, curv=[{kap_string}],msc=[{msc_string}]"
        print(outstr)
    return J, grad
##########################################################################################
##########################################################################################


def fun(dofs, prob_jacobian=None, info={'Nfeval': 0}):
    info['Nfeval'] += 1
    JF.x = dofs[:-number_vmec_dofs]
    prob.x = dofs[-number_vmec_dofs:]
    bs.set_points(surf.gamma().reshape((-1, 3)))
    os.chdir(vmec_results_path)
    J_stage_1 = prob.objective()
    J_stage_2 = coils_objective_weight * JF.J()
    J = J_stage_1 + J_stage_2
    if J > JACOBIAN_THRESHOLD or np.isnan(J):
        pprint(f"Exception caught during function evaluation with J={J}. Returning J={JACOBIAN_THRESHOLD}")
        J = JACOBIAN_THRESHOLD
        grad_with_respect_to_surface = [0] * number_vmec_dofs
        grad_with_respect_to_coils = [0] * len(JF.x)
    else:
        pprint(f"fun#{info['Nfeval']}: Objective function = {J:.4f}")
        prob_dJ = prob_jacobian.jac(prob.x)
        ## Finite differences for the second-stage objective function
        coils_dJ = JF.dJ()
        ## Mixed term - derivative of squared flux with respect to the surface shape
        n = surf.normal()
        absn = np.linalg.norm(n, axis=2)
        B = bs.B().reshape((nphi_VMEC, ntheta_VMEC, 3))
        dB_by_dX = bs.dB_by_dX().reshape((nphi_VMEC, ntheta_VMEC, 3, 3))
        Bcoil = bs.B().reshape(n.shape)
        unitn = n * (1./absn)[:, :, None]
        Bcoil_n = np.sum(Bcoil*unitn, axis=2)
        mod_Bcoil = np.linalg.norm(Bcoil, axis=2)
        B_n = Bcoil_n
        B_diff = Bcoil
        B_N = np.sum(Bcoil * n, axis=2)
        assert Jf.local
        dJdx = (B_n/mod_Bcoil**2)[:, :, None] * (np.sum(dB_by_dX*(n-B*(B_N/mod_Bcoil**2)[:, :, None])[:, :, None, :], axis=3))
        dJdN = (B_n/mod_Bcoil**2)[:, :, None] * B_diff - 0.5 * (B_N**2/absn**3/mod_Bcoil**2)[:, :, None] * n
        deriv = surf.dnormal_by_dcoeff_vjp(dJdN/(nphi_VMEC*ntheta_VMEC)) + surf.dgamma_by_dcoeff_vjp(dJdx/(nphi_VMEC*ntheta_VMEC))
        mixed_dJ = Derivative({surf: deriv})(surf)
        ## Put both gradients together
        grad_with_respect_to_coils = coils_objective_weight * coils_dJ
        grad_with_respect_to_surface = np.ravel(prob_dJ) + coils_objective_weight * mixed_dJ
    grad = np.concatenate((grad_with_respect_to_coils, grad_with_respect_to_surface))

    # Remove spurious files
    for jac_file in glob.glob("jac_log_*"): os.remove(jac_file)
    os.chdir(parent_path)
    for jac_file in glob.glob("jac_log_*"): os.remove(jac_file)
    os.chdir(this_path)
    for jac_file in glob.glob("jac_log_*"): os.remove(jac_file)

    return J, grad


##########################################################################################
#############################################################
## Perform optimization
#############################################################
##########################################################################################
surf.fix_all()
surf.fixed_range(mmin=0, mmax=max_mode, nmin=-max_mode, nmax=max_mode, fixed=False)
surf.fix("rc(0,0)")
number_vmec_dofs = int(len(surf.x))
qs = QuasisymmetryRatioResidual(vmec, quasisymmetry_target_surfaces, helicity_m=1, helicity_n=0)
objective_tuple = [(vmec.aspect, aspect_ratio_target, aspect_ratio_weight), (qs.residuals, 0, 1)]
prob = LeastSquaresProblem.from_tuples(objective_tuple)
dofs = np.concatenate((JF.x, vmec.x))
pprint(f"  Aspect ratio before stage 2 optimization: {vmec.aspect()}")
pprint(f"  Mean iota before stage 2 optimization: {vmec.mean_iota()}")
pprint(f"  Quasisymmetry objective stage 2 before optimization: {qs.total()}")
pprint(f"  Squared flux before stage 2 optimization: {Jf.J()}")
pprint(f'Performing stage 2 optimization with ~{MAXITER_stage_2} iterations')
res = minimize(fun_coils, dofs[:-number_vmec_dofs], jac=True, args=({'Nfeval': 0}), method='L-BFGS-B', options={'maxiter': MAXITER_stage_2, 'maxcor': 300}, tol=1e-7)
bs.set_points(surf.gamma().reshape((-1, 3)))
Bbs = bs.B().reshape((nphi_VMEC, ntheta_VMEC, 3))
BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
if comm.rank == 0:
    curves_to_vtk(curves, os.path.join(coils_results_path, "curves_after_stage2"))
    pointData = {"B_N": BdotN_surf[:, :, None]}
    surf.to_vtk(os.path.join(coils_results_path, "surf_after_stage2"), extra_data=pointData)
pprint(f'Performing single stage optimization with ~{MAXITER_single_stage} iterations')
pprint(f"  Aspect ratio before single stage optimization: {vmec.aspect()}")
pprint(f"  Mean iota before single stage optimization: {vmec.mean_iota()}")
pprint(f"  Quasisymmetry objective before single stage optimization: {qs.total()}")
pprint(f"  Squared flux before single stage optimization: {Jf.J()}")
BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
BdotN = np.mean(np.abs(BdotN_surf))
BdotNmax = np.max(np.abs(BdotN_surf))
outstr = f"  Coil parameters: ⟨B·n⟩={BdotN:.1e}, B·n max={BdotNmax:.1e}"
outstr += f", ║∇J coils║={np.linalg.norm(JF.dJ()):.1e}, C-C-Sep={Jccdist.shortest_distance():.2f}"
cl_string = ", ".join([f"{j.J():.1f}" for j in Jls])
kap_string = ", ".join(f"{np.max(c.kappa()):.1f}" for c in base_curves)
msc_string = ", ".join(f"{j.J():.1f}" for j in Jmscs)
outstr += f" lengths=sum([{cl_string}])={sum(j.J() for j in Jls):.1f}, curv=[{kap_string}], msc=[{msc_string}]"
pprint(outstr)
x0 = np.copy(np.concatenate((JF.x, vmec.x)))
dofs = np.concatenate((JF.x, vmec.x))
with MPIFiniteDifference(prob.objective, mpi, diff_method=diff_method, abs_step=finite_difference_abs_step, rel_step=finite_difference_rel_step) as prob_jacobian:
    if mpi.proc0_world:
        res = minimize(fun, dofs, args=(prob_jacobian, {'Nfeval': 0}), jac=True, method='BFGS', options={'maxiter': MAXITER_single_stage}, tol=1e-7)
mpi.comm_world.Bcast(dofs, root=0)
Bbs = bs.B().reshape((nphi_VMEC, ntheta_VMEC, 3))
BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
if comm.rank == 0:
    curves_to_vtk(curves, os.path.join(coils_results_path, "curves_opt"))
    pointData = {"B_N": BdotN_surf[:, :, None]}
    surf.to_vtk(os.path.join(coils_results_path, "surf_opt"), extra_data=pointData)
    cws.to_vtk(os.path.join(coils_results_path, "cws_opt"))
bs.save(os.path.join(coils_results_path, "biot_savart_opt.json"))
vmec.write_input(os.path.join(this_path, f'input.final'))
pprint(f"  Aspect ratio after optimization: {vmec.aspect()}")
pprint(f"  Mean iota after optimization: {vmec.mean_iota()}")
pprint(f"  Quasisymmetry objective after optimization: {qs.total()}")
pprint(f"  Squared flux after optimization: {Jf.J()}")
BdotN_surf = np.sum(Bbs * surf.unitnormal(), axis=2)
BdotN = np.mean(np.abs(BdotN_surf))
BdotNmax = np.max(np.abs(BdotN_surf))
outstr = f"  Coil parameters: ⟨B·n⟩={BdotN:.1e}, B·n max={BdotNmax:.1e}"
outstr += f", ║∇J coils║={np.linalg.norm(JF.dJ()):.1e}, C-C-Sep={Jccdist.shortest_distance():.2f}"
cl_string = ", ".join([f"{j.J():.1f}" for j in Jls])
kap_string = ", ".join(f"{np.max(c.kappa()):.1f}" for c in base_curves)
msc_string = ", ".join(f"{j.J():.1f}" for j in Jmscs)
outstr += f" lengths=sum([{cl_string}])={sum(j.J() for j in Jls):.1f}, curv=[{kap_string}], msc=[{msc_string}]"
pprint(outstr)