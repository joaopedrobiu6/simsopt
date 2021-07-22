import numpy as np
import simsoptpp as sopp
from .graph_surface import Surface
from .graph_surfacerzfourier import SurfaceRZFourier


class SurfaceXYZFourier(sopp.SurfaceXYZFourier, Surface):
    r"""`SurfaceXYZFourier` is a surface that is represented in Cartesian
    coordinates using the following Fourier series:

    .. math::
        \hat x(\phi,\theta) &= \sum_{m=0}^{m_\text{pol}} \sum_{n=-n_{\text{tor}}}^{n_{tor}} [
              x_{c,m,n} \cos(m \theta - n_\text{ fp } n \phi)
            + x_{s,m,n} \sin(m \theta - n_\text{ fp } n \phi)]\\
        \hat y(\phi,\theta) &= \sum_{m=0}^{m_\text{pol}} \sum_{n=-n_\text{tor}}^{n_\text{tor}} [
              y_{c,m,n} \cos(m \theta - n_\text{fp} n \phi)
            + y_{s,m,n} \sin(m \theta - n_\text{fp} n \phi)]\\
        z(\phi,\theta) &= \sum_{m=0}^{m_\text{pol}} \sum_{n=-n_\text{tor}}^{n_\text{tor}} [
              z_{c,m,n} \cos(m \theta - n_\text{fp}n \phi)
            + z_{s,m,n} \sin(m \theta - n_\text{fp}n \phi)]

    where

    .. math::
        x &= \hat x \cos(\phi) - \hat y \sin(\phi)\\
        y &= \hat x \sin(\phi) + \hat y \cos(\phi)

    Note that for :math:`m=0` we skip the :math:`n<0` term for the cos
    terms, and the :math:`n \leq 0` for the sin terms.

    When enforcing stellarator symmetry, we set the

    .. math::
        x_{s,*,*}, ~y_{c,*,*}, \text{and} ~z_{c,*,*}

    terms to zero.
    """

    def __init__(self, nfp=1, stellsym=True, mpol=1, ntor=0, quadpoints_phi=32,
                 quadpoints_theta=32):
        if isinstance(quadpoints_phi, np.ndarray):
            quadpoints_phi = list(quadpoints_phi)
            quadpoints_theta = list(quadpoints_theta)
        sopp.SurfaceXYZFourier.__init__(self, mpol, ntor, nfp, stellsym,
                                        quadpoints_phi, quadpoints_theta)
        self.xc[0, ntor] = 1.0
        self.xc[1, ntor] = 0.1
        self.zs[1, ntor] = 0.1
        Surface.__init__(self, x0=self.get_dofs(),
                         external_dof_setter=SurfaceXYZFourier.set_dofs)

    def get_dofs(self):
        """
        Return the dofs associated to this surface.
        """
        return np.asarray(sopp.SurfaceXYZFourier.get_dofs(self))

    def to_RZFourier(self):
        """
        Return a SurfaceRZFourier instance corresponding to the shape of this
        surface.
        """
        ntor = self.ntor
        mpol = self.mpol 
        surf = SurfaceRZFourier(nfp=self.nfp, 
                                stellsym=self.stellsym, 
                                mpol=mpol, 
                                ntor=ntor, 
                                quadpoints_phi=self.quadpoints_phi, 
                                quadpoints_theta=self.quadpoints_theta)

        gamma = np.zeros((surf.quadpoints_phi.size, surf.quadpoints_theta.size, 3))
        for idx in range(gamma.shape[0]):
            gamma[idx, :, :] = self.cross_section(surf.quadpoints_phi[idx]*2*np.pi)

        surf.least_squares_fit(gamma)
        return surf

    def recompute_bell(self, parent=None):
        self.invalidate_cache()

    def set_dofs(self, dofs):
        """
        Set the dofs associated to this surface.
        """
        sopp.SurfaceXYZFourier.set_dofs(self, dofs)
