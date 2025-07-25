import logging
import unittest
import json
import os


import numpy as np

from simsopt._core.json import GSONEncoder, GSONDecoder, SIMSON
from simsopt.geo.curvexyzfourier import CurveXYZFourier, JaxCurveXYZFourier
from simsopt.geo.curverzfourier import CurveRZFourier
from simsopt.geo.curvecwsfourier import CurveCWSFourier
from simsopt.geo.curveplanarfourier import CurvePlanarFourier
from simsopt.geo.curvehelical import CurveHelical
from simsopt.geo.curvexyzfouriersymmetries import CurveXYZFourierSymmetries
from simsopt.geo.curve import RotatedCurve, curves_to_vtk
from simsopt.geo import parameters
from simsopt.configs.zoo import get_ncsx_data, get_w7x_data
from simsopt.field import BiotSavart, Current, coils_via_symmetries, Coil
from simsopt.field.coil import coils_to_makegrid
from simsopt.geo import CurveLength, CurveCurveDistance
from math import gcd

try:
    import pyevtk
except ImportError:
    pyevtk = None

logger = logging.getLogger(__name__)
#logging.basicConfig(level=logging.INFO)

parameters['jit'] = False


def taylor_test(f, df, x, epsilons=None, direction=None):
    np.random.seed(1)
    if direction is None:
        direction = np.random.rand(*(x.shape))-0.5
    dfx = df(x)@direction
    if epsilons is None:
        epsilons = np.power(2., -np.asarray(range(7, 20)))
    print("################################################################################")
    err_old = 1e9
    counter = 0
    for eps in epsilons:
        if counter > 8:
            break
        fpluseps = f(x + eps * direction)
        fminuseps = f(x - eps * direction)
        dfest = (fpluseps-fminuseps)/(2*eps)
        err = np.linalg.norm(dfest - dfx)
        print(err, err/err_old)

        assert err < 1e-9 or err < 0.3 * err_old
        if err < 1e-9:
            break
        err_old = err
        counter += 1
    if err > 1e-10:
        assert counter > 3
    print("################################################################################")


def get_curve(curvetype, rotated, x=np.asarray([0.5])):
    np.random.seed(2)
    rand_scale = 0.01
    order = 4

    if curvetype == "CurveXYZFourier":
        curve = CurveXYZFourier(x, order)
    elif curvetype == "JaxCurveXYZFourier":
        curve = JaxCurveXYZFourier(x, order)
    elif curvetype == "CurveRZFourier":
        curve = CurveRZFourier(x, order, 2, True)
    elif curvetype == "CurveHelical":
        curve = CurveHelical(x, order, 5, 2, 1.0, 0.3)
    elif curvetype == "CurveHelicalInitx0":
        curve = CurveHelical(x, order, 5, 2, 1.0, 0.3, x0=np.ones(2 * order + 1))
    elif curvetype == "CurvePlanarFourier":
        curve = CurvePlanarFourier(x, order)
    elif curvetype == "CurveXYZFourierSymmetries1":
        curve = CurveXYZFourierSymmetries(x, order, 2, True)
    elif curvetype == "CurveXYZFourierSymmetries2":
        curve = CurveXYZFourierSymmetries(x, order, 2, False)
    elif curvetype == "CurveXYZFourierSymmetries3":
        curve = CurveXYZFourierSymmetries(x, order, 2, False, ntor=3)
    elif curvetype == "CurveCWSFourier":
        curve = CurveCWSFourier(mpol=1, ntor=1, idofs=[1, 0.2, 0.2], quadpoints=150, order=order, nfp=1, stellsym=True)
    else:
        assert False

    dofs = np.zeros((curve.dof_size, ))
    if curvetype in ["CurveXYZFourier", "JaxCurveXYZFourier"]:
        dofs[1] = 1.
        dofs[2*order + 3] = 1.
        dofs[4*order + 3] = 1.
    elif curvetype in ["CurveRZFourier", "CurvePlanarFourier"]:
        dofs[0] = 1.
        dofs[1] = 0.1
        dofs[order+1] = 0.1
    elif curvetype in ["CurveHelical", "CurveHelicalInitx0"]:
        dofs[0] = np.pi/2
    elif curvetype == "CurveXYZFourierSymmetries1":
        R = 1
        r = 0.5
        curve.set('xc(0)', R)
        curve.set('xc(1)', -r)
        curve.set('zs(1)', -r)
        dofs = curve.get_dofs()
    elif curvetype == "CurveXYZFourierSymmetries2":
        R = 1
        r = 0.5
        curve.set('xc(0)', R)
        curve.set('xs(1)', -0.1*r)
        curve.set('xc(1)', -r)
        curve.set('zs(1)', -r)
        curve.set('zc(0)', 1)
        curve.set('zs(1)', r)
        dofs = curve.get_dofs()
    elif curvetype == "CurveXYZFourierSymmetries3":
        R = 1
        r = 0.5
        curve.set('xc(0)', R)
        curve.set('xs(1)', -0.1*r)
        curve.set('xc(1)', -r)
        curve.set('zs(1)', -r)
        curve.set('zc(0)', 1)
        curve.set('zs(1)', r)
        dofs = curve.get_dofs()
    elif curvetype == "CurveCWSFourier":
        dofs[0] = 1.
        dofs[2*order + 2] = 1.
    else:
        assert False

    curve.x = dofs # + rand_scale * np.random.rand(len(dofs)).reshape(dofs.shape)

    if rotated:
        curve = RotatedCurve(curve, 0.5, flip=False)
    return curve


class Testing(unittest.TestCase):

    curvetypes = ["CurveXYZFourier", "JaxCurveXYZFourier", "CurveRZFourier", "CurvePlanarFourier", "CurveHelical", "CurveXYZFourierSymmetries1","CurveXYZFourierSymmetries2", "CurveXYZFourierSymmetries3", "CurveHelicalInitx0", "CurveCWSFourier"]
    
    def get_curvexyzfouriersymmetries(self, stellsym=True, x=None, nfp=None, ntor=1):
        # returns a CurveXYZFourierSymmetries that is randomly perturbed

        np.random.seed(1)
        rand_scale = 1e-2

        if nfp is None:
            nfp = 3
        if x is None:
            x = np.linspace(0, 1, 200, endpoint=False)

        order = 2
        curve = CurveXYZFourierSymmetries(x, order, nfp, stellsym, ntor=ntor)
        R = 1
        r = 0.25
        curve.set('xc(0)', R)
        curve.set('xc(2)', r)
        curve.set('ys(2)', -r)
        curve.set('zs(1)', -2*r)
        curve.set('zs(2)', r)
        dofs = curve.x.copy()
        curve.x = dofs + rand_scale * np.random.rand(len(dofs)).reshape(dofs.shape)

        return curve

    def test_curvexyzsymmetries_raisesexception(self):
        # test ensures that an exception is raised when you try and create a curvexyzfouriersymmetries
        # where gcd(ntor, nfp) != 1.

        order = 1
        nfp = 1
        ntor = 2
        # nfp = 1 and ntor = 2 here, so it should work
        curve = CurveXYZFourierSymmetries(100, order, nfp, True, ntor=ntor, x0=np.ones(3*order+1))
        print(curve.x)

        with self.assertRaises(Exception):
            order = 1
            nfp = 2
            ntor = 2
            # nfp = 2 and ntor = 2 here, so an exception should be raised
            _ = CurveXYZFourierSymmetries(100, order, nfp, True, ntor=ntor, x0=np.ones(3*order+1))

    def test_curvehelical_is_curvexyzfouriersymmetries(self):
        # this test checks that both helical coil representations can produce the same helical curve on a torus
        order = 1
        nfp = 2
        curve1 = CurveXYZFourierSymmetries(100, order, nfp, True)
        R = 1
        r = 0.5
        curve1.set('xc(0)', R)
        curve1.set('xc(1)', r)
        curve1.set('zs(1)', -r)
        curve2 = CurveHelical(np.linspace(0, 1, 100, endpoint=False), order, nfp, 1, R, r, x0=np.zeros(2 * order + 1))
        np.testing.assert_allclose(curve1.gamma(), curve2.gamma(), atol=1e-14)

    def test_trefoil_nonstellsym(self):
        r''' This test checks that a CurveXYZFourierSymmetries can represent a non-stellarator symmetric
        trefoil knot.  A parametric representation of a trefoil knot is given by:

            x(t) = sin(t) + 2sin(t)
            y(t) = cos(t) - 2cos(t)
            z(t) = -sin(3t)

        The above can be rewritten the CurveXYZFourierSymmetries representation, with
        order = 1, nfp = 3, and ntor = 2:

            x(t) = xhat(t) * cos(ntor*t) - yhat(t) * sin(ntor*t),
            y(t) = xhat(t) * sin(ntor*t) + yhat(t) * cos(ntor*t),
            z(t) = -sin(nfp*t),

        where
            xhat(t) = sin(nfp*t),
            yhat(t) = -2 + cos(nfp*t),

        i.e., The dofs are xs(1)=1, yc(0)=-2, yc(1)=1, zs(1)=-1, and zero otherwise.
        '''

        order = 1
        nfp = 3
        ntor = 2
        x = np.linspace(0, 1, 500, endpoint=False)
        curve = CurveXYZFourierSymmetries(x, order, nfp, False, ntor=ntor)

        X = np.sin(2*np.pi * x) + 2 * np.sin(2*2*np.pi * x)
        Y = np.cos(2*np.pi * x) - 2 * np.cos(2*2*np.pi * x)
        Z = -np.sin(3*2*np.pi*x)
        XYZ = np.concatenate([X[:, None], Y[:, None], Z[:, None]], axis=1)

        curve.set('xs(1)', 1.)
        curve.set('yc(0)', -2.)
        curve.set('yc(1)', 1.)
        curve.set('zs(1)', -1.)
        np.testing.assert_allclose(curve.gamma(), XYZ, atol=1e-14)

    def test_trefoil_stellsym(self):
        r''' This test checks that a CurveXYZFourierSymmetries can represent a stellarator symmetric
        trefoil knot.  A parametric representation of a trefoil knot is given by:

            x(t) = cos(t) - 2cos(t),
            y(t) =-sin(t) - 2sin(t),
            z(t) = -sin(3t).

        The above can be rewritten the CurveXYZFourierSymmetries representation, with
        order = 1, nfp = 3, and ntor = 2:

            x(t) = xhat(t) * cos(ntor*t) - yhat(t) * sin(ntor*t),
            y(t) = xhat(t) * sin(ntor*t) + yhat(t) * cos(ntor*t),
            z(t) = -sin(nfp*t),

        where

            xhat(t) = -2 + cos(nfp*t)
            yhat(t) = -sin(nfp*t)

        i.e., xc(0)=-2, xc(1)=1, ys(1)=-1, zs(1)=-1.
        '''

        order = 1
        nfp = 3
        ntor = 2
        x = np.linspace(0, 1, 500, endpoint=False)
        curve = CurveXYZFourierSymmetries(x, order, nfp, True, ntor=ntor)

        X = np.cos(2*np.pi * x) - 2 * np.cos(2*2*np.pi * x)
        Y = -np.sin(2*np.pi * x) - 2 * np.sin(2*2*np.pi * x)
        Z = -np.sin(3*2*np.pi*x)
        XYZ = np.concatenate([X[:, None], Y[:, None], Z[:, None]], axis=1)

        curve.set('xc(0)', -2)
        curve.set('xc(1)', 1)
        curve.set('ys(1)', -1)
        curve.set('zs(1)', -1)
        np.testing.assert_allclose(curve.gamma(), XYZ, atol=1e-14)

    def test_nonstellsym(self):
        # this test checks that you can obtain a stellarator symmetric magnetic field from two non-stellarator symmetric
        # CurveXYZFourierSymmetries curves.
        for nfp in [1, 2, 3, 4, 5, 6]:
            for ntor in [1, 2, 3, 4, 5, 6]:
                with self.subTest(nfp=nfp, ntor=ntor):
                    self.subtest_nonstellsym(nfp, ntor)

    def subtest_nonstellsym(self, nfp, ntor):
        if gcd(ntor, nfp) != 1:
            return

        # this test checks that you can obtain a stellarator symmetric magnetic field from two non-stellarator symmetric
        # CurveXYZFourierSymmetries curves.
        curve = self.get_curvexyzfouriersymmetries(stellsym=False, nfp=nfp, ntor=ntor)
        current = Current(1e5)
        coils = coils_via_symmetries([curve], [current], 1, True)
        bs = BiotSavart(coils)
        bs.set_points([[1, 1, 1], [1, -1, -1]])
        B = bs.B_cyl()
        np.testing.assert_allclose(B[0, 0], -B[1, 0], atol=1e-14)
        np.testing.assert_allclose(B[0, 1], B[1, 1], atol=1e-14)
        np.testing.assert_allclose(B[0, 2], B[1, 2], atol=1e-14)

    def test_xyzhelical_symmetries(self):
        # checking various symmetries of the CurveXYZFourierSymmetries representation
        for nfp in [1, 2, 3, 4, 5, 6]:
            for ntor in [1, 2, 3, 4, 5, 6]:
                with self.subTest(nfp=nfp, ntor=ntor):
                    self.subtest_xyzhelical_symmetries(nfp, ntor)

    def subtest_xyzhelical_symmetries(self, nfp, ntor):
        if gcd(nfp, ntor) != 1:
            return

        # does the stellarator symmetric curve have rotational symmetry?
        curve = self.get_curvexyzfouriersymmetries(stellsym=True, nfp=nfp, x=np.array([0.123, 0.123+1/nfp]), ntor=ntor)
        out = curve.gamma()

        # NOTE: the point at angle t+1/nfp is the point at angle t, but rotated by 2pi *(ntor/nfp) radians.
        alpha = 2*np.pi*ntor/nfp
        R = np.array([
            [np.cos(alpha), -np.sin(alpha), 0],
            [np.sin(alpha), np.cos(alpha), 0],
            [0, 0, 1]
        ])

        print(R@out[0], out[1])
        np.testing.assert_allclose(out[1], R@out[0], atol=1e-14)

        # does the stellarator symmetric curve indeed pass through (x0, 0, 0)?
        curve = self.get_curvexyzfouriersymmetries(stellsym=True, nfp=nfp, x=np.array([0]), ntor=ntor)
        out = curve.gamma()
        assert np.abs(out[0, 0]) > 1e-3
        np.testing.assert_allclose(out[0, 1], 0, atol=1e-14)
        np.testing.assert_allclose(out[0, 2], 0, atol=1e-14)

        # does the non-stellarator symmetric curve not pass through (x0, 0, 0)?
        curve = self.get_curvexyzfouriersymmetries(stellsym=False, nfp=nfp, x=np.array([0]), ntor=ntor)
        out = curve.gamma()
        assert np.abs(out[0, 0]) > 1e-3
        assert np.abs(out[0, 1]) > 1e-3
        assert np.abs(out[0, 2]) > 1e-3

        # is the stellarator symmetric curve actually stellarator symmetric?
        curve = self.get_curvexyzfouriersymmetries(stellsym=True, nfp=nfp, x=np.array([0.123, -0.123]), ntor=ntor)
        pts = curve.gamma()
        np.testing.assert_allclose(pts[0, 0], pts[1, 0], atol=1e-14)
        np.testing.assert_allclose(pts[0, 1], -pts[1, 1], atol=1e-14)
        np.testing.assert_allclose(pts[0, 2], -pts[1, 2], atol=1e-14)

        # is the field from the stellarator symmetric curve actually stellarator symmetric?
        curve = self.get_curvexyzfouriersymmetries(stellsym=True, nfp=nfp, x=np.linspace(0, 1, 200, endpoint=False), ntor=ntor)
        current = Current(1e5)
        coil = Coil(curve, current)
        bs = BiotSavart([coil])
        bs.set_points([[1, 1, 1], [1, -1, -1]])
        B = bs.B_cyl()
        np.testing.assert_allclose(B[0, 0], -B[1, 0], atol=1e-14)
        np.testing.assert_allclose(B[0, 1], B[1, 1], atol=1e-14)
        np.testing.assert_allclose(B[0, 2], B[1, 2], atol=1e-14)

        # does the non-stellarator symmetric curve have rotational symmetry still?
        # NOTE: the point at angle t+1/nfp is the point at angle t, but rotated by 2pi *(ntor/nfp) radians.
        curve = self.get_curvexyzfouriersymmetries(stellsym=False, nfp=nfp, x=np.array([0.123, 0.123+1./nfp]), ntor=ntor)
        out = curve.gamma()
        alpha = 2*np.pi*ntor/nfp
        R = np.array([
            [np.cos(alpha), -np.sin(alpha), 0],
            [np.sin(alpha), np.cos(alpha), 0],
            [0, 0, 1]
        ])
        print(R@out[0], out[1])
        np.testing.assert_allclose(out[1], R@out[0], atol=1e-14)

    def test_curve_helical_xyzfourier(self):
        x = np.asarray([0.6])
        curve1 = CurveHelical(x, 1, 5, 2, 1.0, 0.3)
        curve1.x = [np.pi/2, 0, 0]
        curve2 = CurveXYZFourier(x, 7)
        curve2.x = \
            [0, 0, 0, 0, 1, -0.15, 0, 0, 0, 0, 0, 0, 0, -0.15, 0,
             0, 0, 0, 1, 0, 0, -0.15, 0, 0, 0, 0, 0, 0, 0, 0.15,
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.3, 0, 0, 0, 0]
        assert np.allclose(curve1.gamma(), curve2.gamma())
        assert np.allclose(curve1.gammadash(), curve2.gammadash())

    def subtest_curve_first_derivative(self, curvetype, rotated):
        epss = [0.5**i for i in range(10, 15)]
        x = np.asarray([0.6] + [0.6 + eps for eps in epss])
        curve = get_curve(curvetype, rotated, x)
        f0 = curve.gamma()[0]
        deriv = curve.gammadash()[0]
        err_old = 1e6
        for i in range(len(epss)):
            fh = curve.gamma()[i+1]
            deriv_est = (fh-f0)/epss[i]
            err = np.linalg.norm(deriv_est-deriv)
            assert err < 0.55 * err_old
            err_old = err

    def test_curve_first_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_first_derivative(curvetype, rotated)

    def subtest_curve_second_derivative(self, curvetype, rotated):
        epss = [0.5**i for i in range(10, 15)]
        x = np.asarray([0.6] + [0.6 + eps for eps in epss])
        curve = get_curve(curvetype, rotated, x)
        f0 = curve.gammadash()[0]
        deriv = curve.gammadashdash()[0]
        err_old = 1e6
        for i in range(len(epss)):
            fh = curve.gammadash()[i+1]
            deriv_est = (fh-f0)/epss[i]
            err = np.linalg.norm(deriv_est-deriv)
            assert err < 0.55 * err_old
            err_old = err

    def test_curve_second_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_second_derivative(curvetype, rotated)

    def subtest_curve_third_derivative(self, curvetype, rotated):
        epss = [0.5**i for i in range(10, 15)]
        x = np.asarray([0.6] + [0.6 + eps for eps in epss])
        curve = get_curve(curvetype, rotated, x)
        f0 = curve.gammadashdash()[0]
        deriv = curve.gammadashdashdash()[0]
        err_old = 1e6
        for i in range(len(epss)):
            fh = curve.gammadashdash()[i+1]
            deriv_est = (fh-f0)/epss[i]
            err = np.linalg.norm(deriv_est-deriv)
            assert err < 0.55 * err_old
            err_old = err

    def subtest_coil_coefficient_derivative(self, curvetype, rotated):
        cfc = get_curve(curvetype, rotated)
        coeffs = cfc.x
        cfc.invalidate_cache()

        def f(dofs):
            cfc.x = dofs
            return cfc.gamma().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dgamma_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

        def f(dofs):
            cfc.x = dofs
            return cfc.gammadash().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dgammadash_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

        def f(dofs):
            cfc.x = dofs
            return cfc.gammadashdash().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dgammadashdash_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

        def f(dofs):
            cfc.x = dofs
            return cfc.gammadashdashdash().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dgammadashdashdash_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_coil_coefficient_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_coil_coefficient_derivative(curvetype, rotated)

    def subtest_coil_kappa_derivative(self, curvetype, rotated):
        # This implicitly also tests the higher order derivatives of gamma as these
        # are needed to compute the derivative of the curvature.
        cfc = get_curve(curvetype, rotated)
        coeffs = cfc.x

        def f(dofs):
            cfc.x = dofs
            return cfc.kappa().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dkappa_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_coil_kappa_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_coil_kappa_derivative(curvetype, rotated)

    def subtest_curve_kappa_first_derivative(self, curvetype, rotated):
        epss = [0.5**i for i in range(12, 17)]
        x = np.asarray([0.1234] + [0.1234 + eps for eps in epss])
        ma = get_curve(curvetype, rotated, x)
        f0 = ma.kappa()[0]
        deriv = ma.kappadash()[0]
        err_old = 1e6
        for i in range(len(epss)):
            fh = ma.kappa()[i+1]
            deriv_est = (fh-f0)/epss[i]
            err = np.linalg.norm(deriv_est-deriv)
            # print("err", err)
            assert err < 0.55 * err_old
            err_old = err

    def test_curve_kappa_first_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_kappa_first_derivative(curvetype, rotated)

    def subtest_curve_incremental_arclength_derivative(self, curvetype, rotated):
        # This implicitly also tests the higher order derivatives of gamma as these
        # are needed to compute the derivative of the curvature.
        ma = get_curve(curvetype, rotated)
        coeffs = ma.x

        def f(dofs):
            ma.x = dofs
            return ma.incremental_arclength().copy()

        def df(dofs):
            ma.x = dofs
            return ma.dincremental_arclength_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_curve_incremental_arclength_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_incremental_arclength_derivative(curvetype, rotated)

    def subtest_curve_kappa_derivative(self, curvetype, rotated):
        cfc = get_curve(curvetype, rotated)
        coeffs = cfc.x

        def f(dofs):
            cfc.x = dofs
            return cfc.kappa().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dkappa_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_curve_kappa_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_kappa_derivative(curvetype, rotated)

    def subtest_curve_torsion_derivative(self, curvetype, rotated):
        cfc = get_curve(curvetype, rotated)
        coeffs = cfc.x

        def f(dofs):
            cfc.x = dofs
            return cfc.torsion().copy()

        def df(dofs):
            cfc.x = dofs
            return cfc.dtorsion_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_curve_torsion_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_torsion_derivative(curvetype, rotated)

    def subtest_curve_frenet_frame(self, curvetype, rotated):
        ma = get_curve(curvetype, rotated)
        (t, n, b) = ma.frenet_frame()
        assert np.allclose(np.sum(n*t, axis=1), 0)
        assert np.allclose(np.sum(n*b, axis=1), 0)
        assert np.allclose(np.sum(t*b, axis=1), 0)
        assert np.allclose(np.sum(t*t, axis=1), 1)
        assert np.allclose(np.sum(n*n, axis=1), 1)
        assert np.allclose(np.sum(b*b, axis=1), 1)

    def test_curve_frenet_frame(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_frenet_frame(curvetype, rotated)

    def subtest_curve_frenet_frame_derivative(self, curvetype, rotated):
        ma = get_curve(curvetype, rotated)
        coeffs = ma.x

        def f(dofs):
            ma.x = dofs
            return ma.frenet_frame()[0].copy()

        def df(dofs):
            ma.x = dofs
            return ma.dfrenet_frame_by_dcoeff()[0].copy()
        taylor_test(f, df, coeffs)

        def f(dofs):
            ma.x = dofs
            return ma.frenet_frame()[1].copy()

        def df(dofs):
            ma.x = dofs
            return ma.dfrenet_frame_by_dcoeff()[1].copy()
        taylor_test(f, df, coeffs)

        def f(dofs):
            ma.x = dofs
            return ma.frenet_frame()[2].copy()

        def df(dofs):
            ma.x = dofs
            return ma.dfrenet_frame_by_dcoeff()[2].copy()
        taylor_test(f, df, coeffs)

    def test_curve_frenet_frame_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_frenet_frame_derivative(curvetype, rotated)

    def subtest_curve_dkappa_by_dphi_derivative(self, curvetype, rotated):
        ma = get_curve(curvetype, rotated)
        coeffs = ma.x

        def f(dofs):
            ma.x = dofs
            return ma.kappadash().copy()

        def df(dofs):
            ma.x = dofs
            return ma.dkappadash_by_dcoeff().copy()
        taylor_test(f, df, coeffs)

    def test_curve_dkappa_by_dphi_derivative(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_curve_dkappa_by_dphi_derivative(curvetype, rotated)

    @unittest.skipIf(pyevtk is None, "pyevtk not found")
    def test_curve_to_vtk(self):
        curve0 = get_curve(self.curvetypes[0], False)
        curve1 = get_curve(self.curvetypes[1], True)
        curves_to_vtk([curve0, curve1], '/tmp/curves')

    def test_plot(self):
        """
        Test the plot() function for curves. The ``show`` argument is set
        to ``False`` so the tests do not require human intervention to
        close plot windows.  However, if you do want to actually
        display the figure, you can change ``show`` to ``True`` in the
        first line of this function.
        """
        show = False

        engines = []
        try:
            import matplotlib
        except ImportError:
            pass
        else:
            engines.append("matplotlib")

        try:
            import mayavi
        except ImportError:
            pass
        else:
            engines.append("mayavi")

        try:
            import plotly
        except ImportError:
            pass
        else:
            engines.append("plotly")

        print(f'Testing these plotting engines: {engines}')
        c = CurveXYZFourier(30, 2)
        c.set_dofs(np.random.rand(len(c.get_dofs())) - 0.5)
        coils, currents, ma = get_ncsx_data(Nt_coils=25, Nt_ma=10)
        for engine in engines:
            for close in [True, False]:
                # Plot a single curve:
                c.plot(engine=engine, close=close, plot_derivative=True, show=show, color=(0.9, 0.2, 0.3))

                # Plot multiple curves together:
                ax = None
                for curve in coils:
                    ax = curve.plot(engine=engine, ax=ax, show=False, close=close)
                c.plot(engine=engine, ax=ax, close=close, plot_derivative=True, show=show)

    def test_rotated_curve_gamma_impl(self):
        rc = get_curve("CurveXYZFourier", True, x=100)
        c = rc.curve
        mat = rc.rotmat

        rcg = rc.gamma()
        cg = c.gamma()
        quadpoints = rc.quadpoints

        assert np.allclose(rcg, cg@mat)
        # run gamma_impl so that the `else` in RotatedCurve.gamma_impl gets triggered
        tmp = np.zeros_like(cg[:10, :])
        rc.gamma_impl(tmp, quadpoints[:10])
        assert np.allclose(cg[:10, :]@mat, tmp)

    def subtest_serialization(self, curvetype, rotated):
        epss = [0.5**i for i in range(10, 15)]
        x = np.asarray([0.6] + [0.6 + eps for eps in epss])
        curve = get_curve(curvetype, rotated, x)

        curve_json_str = json.dumps(SIMSON(curve), cls=GSONEncoder, indent=2)
        curve_regen = json.loads(curve_json_str, cls=GSONDecoder)
        self.assertTrue(np.allclose(curve.gamma(), curve_regen.gamma()))

    def test_serialization(self):
        for curvetype in self.curvetypes:
            for rotated in [True, False]:
                with self.subTest(curvetype=curvetype, rotated=rotated):
                    self.subtest_serialization(curvetype, rotated)

    def test_load_curves_from_makegrid_file(self):
        get_config_functions = [get_ncsx_data, get_w7x_data]
        order = 10
        ppp = 4

        for get_config_function in get_config_functions:
            curves, currents, ma = get_config_function(Nt_coils=order, ppp=ppp)

            # write coils to MAKEGRID file
            coils_to_makegrid("coils.file_to_load", curves, currents, nfp=1)
            loaded_curves = CurveXYZFourier.load_curves_from_makegrid_file("coils.file_to_load", order, ppp)

            assert len(curves) == len(loaded_curves)

            for j in range(len(curves)):
                np.testing.assert_allclose(curves[j].x, loaded_curves[j].x)

            gamma = [curve.gamma() for curve in curves]
            loaded_gamma = [curve.gamma() for curve in loaded_curves]

            np.testing.assert_allclose(gamma, loaded_gamma)

            kappa = [np.max(curve.kappa()) for curve in curves]
            loaded_kappa = [np.max(curve.kappa()) for curve in loaded_curves]

            np.testing.assert_allclose(kappa, loaded_kappa)

            length = [CurveLength(c).J() for c in curves]
            loaded_length = [CurveLength(c).J() for c in loaded_curves]

            np.testing.assert_allclose(length, loaded_length)

            ccdist = CurveCurveDistance(curves, 0).J()
            loaded_ccdist = CurveCurveDistance(loaded_curves, 0).J()

            np.testing.assert_allclose(ccdist, loaded_ccdist)

            os.remove("coils.file_to_load")

    def test_curverzfourier_dofnames(self):
        # test that the dof names correspond to how they are treated in the code
        order = 3

        # non-stellarator symmetric case
        curve = CurveRZFourier(32, order, 1, False)
        curve.set('rc(0)', 1)
        curve.set('rs(1)', 2)
        curve.set('zc(2)', 3)
        curve.set('zs(3)', 4)
        
        # test rc, rs, zc, and zs, note sine arrays start from mode number 1
        assert curve.rc[0] == curve.get('rc(0)')
        assert curve.zc[2] == curve.get('zc(2)')
        assert curve.rs[0] == curve.get('rs(1)')
        assert curve.zs[2] == curve.get('zs(3)')

        # stellarator symmetric case
        curve = CurveRZFourier(32, order, 1, True)
        curve.set('rc(1)', 1)
        curve.set('zs(2)', 2)
        
        # test rc and zs
        assert curve.rc[1] == curve.get('rc(1)')
        assert curve.zs[1] == curve.get('zs(2)')

    def test_curveplanarfourier_make_names(self):
        # Test that the _make_names function returns the correct dof names for a given order
        order = 3
        expected_names = [
            'rc(0)', 'rc(1)', 'rc(2)', 'rc(3)',
            'rs(1)', 'rs(2)', 'rs(3)',
            'q0', 'qi', 'qj', 'qk',
            'X', 'Y', 'Z'
        ]
        curve = CurvePlanarFourier(32, order)
        self.assertEqual(curve._make_names(order), expected_names, "The dof names are not consistent with the order")

        # Test setting dofs by names
        curve.set('rc(0)', 1)
        curve.set('q0', 1)
        curve.set('qi', 0)
        curve.set('qj', 0)
        curve.set('qk', 0)
        curve.set('X', 7)   
        curve.set('Y', 8)
        curve.set('Z', 9)

        # Test getting dofs by names
        assert np.allclose(curve.gamma()[:, 2], 9)
        assert curve.x[0] == 1
        assert curve.x[2*order + 1] == 1
        assert curve.x[2*order + 2] == 0
        assert curve.x[2*order + 3] == 0
        assert curve.x[2*order + 4] == 0
        assert curve.x[2*order + 5] == 7
        assert curve.x[2*order + 6] == 8
        assert curve.x[2*order + 7] == 9

        # repeat test with order 0
        order = 0
        expected_names = [
            'rc(0)',
            'q0', 'qi', 'qj', 'qk',
            'X', 'Y', 'Z'
        ]
        curve = CurvePlanarFourier(32, order)
        self.assertEqual(curve._make_names(order), expected_names, "The dof names are not consistent with the order")

        # Test setting dofs by names
        curve.set('rc(0)', 1)
        curve.set('q0', 1)
        curve.set('qi', 0)
        curve.set('qj', 0)
        curve.set('qk', 0)
        curve.set('X', 7)   
        curve.set('Y', 8)
        curve.set('Z', 9)

        # Test getting dofs by names
        assert np.allclose(curve.gamma()[:, 2], 9)
        assert curve.x[0] == 1
        assert curve.x[1] == 1
        assert curve.x[2] == 0
        assert curve.x[3] == 0
        assert curve.x[4] == 0
        assert curve.x[5] == 7
        assert curve.x[6] == 8
        assert curve.x[7] == 9

if __name__ == "__main__":
    unittest.main()
