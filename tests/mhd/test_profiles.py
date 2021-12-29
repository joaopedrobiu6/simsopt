import unittest
import logging
import numpy as np
from simsopt.mhd.profiles import ProfilePolynomial, ProfileScaled, ProfileSpline, \
    ProfilePressure

logger = logging.getLogger(__name__)
#logging.basicConfig(level=logging.DEBUG)


class ProfilesTests(unittest.TestCase):
    def test_polynomial(self):
        """
        Test the value and derivative of a polynomial profile
        """
        # Function: f(s) = 3 * (1 - s^3)
        prof = ProfilePolynomial([3, 0, 0, -3])
        s = np.linspace(0, 1, 10)
        np.testing.assert_allclose(prof.f(s), 3 * (1 - s ** 3))
        np.testing.assert_allclose(prof(s), 3 * (1 - s ** 3))
        np.testing.assert_allclose(prof.dfds(s), 3 * (- 3 * s ** 2))

    def test_plot(self):
        """
        Test the plotting function.
        """
        # Function: f(s) = 3 * (1 - s^3)
        prof = ProfilePolynomial([3, 0, 0, -3])
        prof.plot(show=False)

    def test_scaled(self):
        """
        Test ProfileScaled
        """
        prof1 = ProfilePolynomial([3, 0, 0, -3])
        scalefac = 0.6
        prof2 = ProfileScaled(prof1, scalefac)
        prof2.unfix_all()
        s = np.linspace(0, 1, 10)
        np.testing.assert_allclose(prof2(s), scalefac * prof1(s))
        np.testing.assert_allclose(prof2.dfds(s), scalefac * prof1.dfds(s))
        newscalefac = 1.3
        prof2.x = [newscalefac]
        np.testing.assert_allclose(prof2(s), newscalefac * prof1(s))
        np.testing.assert_allclose(prof2.dfds(s), newscalefac * prof1.dfds(s))

    def test_spline(self):
        """
        Test ProfileSpline.
        """
        s = np.linspace(0, 1, 5)
        s_fine = np.linspace(0, 1, 100)
        f = 1.2 + 0.7 * s + 0.3 * s * s
        f_fine = 1.2 + 0.7 * s_fine + 0.3 * s_fine * s_fine

        profile = ProfileSpline(s, f)
        np.testing.assert_allclose(profile(s), f)
        np.testing.assert_allclose(profile.dfds(s), 0.7 + 2 * 0.3 * s)
        np.testing.assert_allclose(profile(s_fine), f_fine)
        np.testing.assert_allclose(profile.dfds(s_fine), 0.7 + 2 * 0.3 * s_fine)

        # Try changing the dofs
        f2 = -2.1 - 0.4 * s + 0.7 * s * s
        f2_fine = -2.1 - 0.4 * s_fine + 0.7 * s_fine * s_fine
        profile.unfix_all()
        profile.x = f2
        np.testing.assert_allclose(profile(s), f2)
        np.testing.assert_allclose(profile.dfds(s), -0.4 + 2 * 0.7 * s)
        np.testing.assert_allclose(profile(s_fine), f2_fine)
        np.testing.assert_allclose(profile.dfds(s_fine), -0.4 + 2 * 0.7 * s_fine)

        # Try a case with extrapolation
        s = np.linspace(0.1, 0.9, 2)
        f = 0.3 - 0.5 * s
        f_fine = 0.3 - 0.5 * s_fine
        profile2 = ProfileSpline(s, f, degree=1)
        np.testing.assert_allclose(profile2(s), f)
        np.testing.assert_allclose(profile2.dfds(s), -0.5 * np.ones_like(s))
        np.testing.assert_allclose(profile2(s_fine), f_fine)
        np.testing.assert_allclose(profile2.dfds(s_fine), -0.5 * np.ones_like(s_fine))

    def test_pressure(self):
        """
        Try typical usage of ProfilePressure.
        """
        # Try a case with 2 species:
        ne = ProfilePolynomial(1.0e20 * np.array([1.0, 0.0, 0.0, 0.0, -1.0]))
        Te = ProfilePolynomial(8.0e3 * np.array([1.0, -1.0]))
        nH = ne
        TH = ProfilePolynomial(7.0e3 * np.array([1.0, -1.0]))
        pressure = ProfilePressure(ne, Te, nH, TH)

        s = np.linspace(0, 1, 20)
        atol = 1e-14
        np.testing.assert_allclose(pressure(s), ne(s) * (Te(s) + TH(s)), atol=atol)
        np.testing.assert_allclose(pressure.dfds(s),
                                   ne.dfds(s) * (Te(s) + TH(s)) \
                                   + ne(s) * (Te.dfds(s) + TH.dfds(s)),
                                   atol=atol)

        # Now try a case with 3 species:
        nD = ProfileScaled(ne, 0.55)
        nT = ProfileScaled(ne, 0.45)
        TD = ProfilePolynomial(12.0e3 * np.array([1.0, -1.0]))
        TT = TD
        pressure = ProfilePressure(ne, Te, nD, TD, nT, TT)
        ne.unfix_all()
        nD.unfix_all()
        nT.unfix_all()
        Te.unfix_all()
        TD.unfix_all()
        TT.unfix_all()
        for j in range(2):
            np.testing.assert_allclose(pressure(s), ne(s) * Te(s) + nD(s) * TD(s) + nT(s) * TT(s),
                                       atol=atol)
            np.testing.assert_allclose(pressure.dfds(s),
                                       ne.dfds(s) * Te(s) + ne(s) * Te.dfds(s) \
                                       + nD.dfds(s) * TD(s) + nD(s) * TD.dfds(s) \
                                       + nT.dfds(s) * TT(s) + nT(s) * TT.dfds(s),
                                       atol=atol)
            # Try changing some dofs before the 2nd loop iteration:
            ne.x = 2.0e20 * np.array([1.0, 0.0, 0.0, -1.0, 0.0])
            nD.local_x = [0.51]
            nT.local_x = [0.49]
            Te.x = 15.0e3 * np.array([1.0, -0.9])
            TD.x = 14.0e3 * np.array([1.0, -0.3])

    def test_pressure_exception(self):
        """
        ProfilePressure should raise an exception if an odd number of
        profiles are provided.
        """
        ne = ProfilePolynomial(1.0e20 * np.array([1.0, 0.0, 0.0, 0.0, -1.0]))
        Te = ProfilePolynomial(8.0e3 * np.array([1.0, -1.0]))
        nD = ProfileScaled(ne, 0.55)
        nT = ProfileScaled(ne, 0.45)
        TD = ProfilePolynomial(12.0e3 * np.array([1.0, -1.0]))
        TT = TD
        # Try zero profiles:
        with self.assertRaises(ValueError):
            pressure = ProfilePressure()
        with self.assertRaises(ValueError):
            pressure = ProfilePressure(ne)
        with self.assertRaises(ValueError):
            pressure = ProfilePressure(ne, Te, nD)
        with self.assertRaises(ValueError):
            pressure = ProfilePressure(ne, Te, nD, TD, nT)
