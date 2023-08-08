import unittest
from simsopt.geo import FrameRotation, ZeroRotation, FramedCurveCentroid, FramedCurveFrenet
from simsopt.configs.zoo import get_ncsx_data
from simsopt.geo.strain_optimization import LPBinormalCurvatureStrainPenalty, LPTorsionalStrainPenalty
import numpy as np


class StrainOptTesting(unittest.TestCase):

    def test_torsion(self):
        for centroid in [True, False]:
            for order in [None, 1]:
                with self.subTest(order=order):
                    self.subtest_torsion(order, centroid)

    def test_binormal_curvature(self):
        for centroid in [True, False]:
            for order in [None, 1]:
                with self.subTest(order=order):
                    self.subtest_binormal_curvature(order, centroid)

    def subtest_binormal_curvature(self, order, centroid):
        assert order in [1, None]
        curves, currents, ma = get_ncsx_data(Nt_coils=6, ppp=120)
        c = curves[0]

        if order == 1:
            rotation = FrameRotation(c.quadpoints, order)
            rotation.x = np.array([0, 0.1, 0.3])
            rotationShared = FrameRotation(curves[0].quadpoints, order, dofs=rotation.dofs)
            assert np.allclose(rotation.x, rotationShared.x)
            assert np.allclose(rotation.alpha(c.quadpoints), rotationShared.alpha(c.quadpoints))
        else:
            rotation = ZeroRotation(c.quadpoints)

        if centroid:
            framedcurve = FramedCurveCentroid(c, rotation)
        else:
            framedcurve = FramedCurveFrenet(c, rotation)

        J = LPBinormalCurvatureStrainPenalty(framedcurve, width=1e-3, p=2, threshold=1e-4)

        if (not (not centroid and order is None)):
            dofs = J.x

            np.random.seed(1)
            h = np.random.standard_normal(size=dofs.shape)
            df = np.sum(J.dJ()*h)

            errf_old = 1e10
            for i in range(9, 14):
                eps = 0.5**i
                J.x = dofs + eps*h
                f1 = J.J()
                J.x = dofs - eps*h
                f2 = J.J()
                errf = np.abs((f1-f2)/(2*eps) - df)
                errf_old = errf
        else:
            # Binormal curvature vanishes in Frenet frame
            assert J.J() < 1e-12

    def subtest_torsion(self, order, centroid):
        assert order in [1, None]
        curves, currents, ma = get_ncsx_data(Nt_coils=6, ppp=120)
        c = curves[0]

        if order == 1:
            rotation = FrameRotation(c.quadpoints, order)
            rotation.x = np.array([0, 0.1, 0.3])
            rotationShared = FrameRotation(curves[0].quadpoints, order, dofs=rotation.dofs)
            assert np.allclose(rotation.x, rotationShared.x)
            assert np.allclose(rotation.alpha(c.quadpoints), rotationShared.alpha(c.quadpoints))
        else:
            rotation = ZeroRotation(c.quadpoints)

        if centroid:
            framedcurve = FramedCurveCentroid(c, rotation)
        else:
            framedcurve = FramedCurveFrenet(c, rotation)

        J = LPTorsionalStrainPenalty(framedcurve, width=1e-3, p=2, threshold=1e-4)

        dofs = J.x

        np.random.seed(1)
        h = np.random.standard_normal(size=dofs.shape)
        df = np.sum(J.dJ()*h)

        errf_old = 1e10
        for i in range(9, 14):
            eps = 0.5**i
            J.x = dofs + eps*h
            f1 = J.J()
            J.x = dofs - eps*h
            f2 = J.J()
            errf = np.abs((f1-f2)/(2*eps) - df)
            errf_old = errf

