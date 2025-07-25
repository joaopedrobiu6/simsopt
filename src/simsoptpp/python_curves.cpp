#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "xtensor-python/pyarray.hpp"     // Numpy bindings
typedef xt::pyarray<double> PyArray;
using std::shared_ptr;

namespace py = pybind11;

#include "curve.h"
#include "pycurve.h"

#include "curvexyzfourier.h"
typedef CurveXYZFourier<PyArray> PyCurveXYZFourier;
#include "curverzfourier.h"
typedef CurveRZFourier<PyArray> PyCurveRZFourier; 
#include "curveplanarfourier.h"
typedef CurvePlanarFourier<PyArray> PyCurvePlanarFourier;
#include "curvecwsfourier.h"
typedef CurveCWSFourier<PyArray> PyCurveCWSFourier;

template <class PyCurveCWSFourierBase = PyCurveCWSFourier> class PyCurveCWSFourierTrampoline : public PyCurveTrampoline<PyCurveCWSFourierBase> {
    public:
        using PyCurveTrampoline<PyCurveCWSFourierBase>::PyCurveTrampoline; // Inherit constructors

        int num_dofs() override {
            return PyCurveCWSFourierBase::num_dofs();
        }

        void set_dofs_impl(const vector<double>& _dofs) override {
            PyCurveCWSFourierBase::set_dofs_impl(_dofs);
        }

        vector<double> get_dofs() override {
            return PyCurveCWSFourierBase::get_dofs();
        }

        vector<double> get_dofs_surface() {
            return PyCurveCWSFourierBase::get_dofs_surface();
        }
        
        int num_dofs_surface() {
            return PyCurveCWSFourierBase::num_dofs_surface();
        }

        void gamma_impl(PyArray& data, PyArray& quadpoints) override {
            PyCurveCWSFourierBase::gamma_impl(data, quadpoints);
        }
};

template <class PyCurveXYZFourierBase = PyCurveXYZFourier> class PyCurveXYZFourierTrampoline : public PyCurveTrampoline<PyCurveXYZFourierBase> {
    public:
        using PyCurveTrampoline<PyCurveXYZFourierBase>::PyCurveTrampoline; // Inherit constructors

        int num_dofs() override {
            return PyCurveXYZFourierBase::num_dofs();
        }

        void set_dofs_impl(const vector<double>& _dofs) override {
            PyCurveXYZFourierBase::set_dofs_impl(_dofs);
        }

        vector<double> get_dofs() override {
            return PyCurveXYZFourierBase::get_dofs();
        }

        void gamma_impl(PyArray& data, PyArray& quadpoints) override {
            PyCurveXYZFourierBase::gamma_impl(data, quadpoints);
        }
};

template <class PyCurveRZFourierBase = PyCurveRZFourier> class PyCurveRZFourierTrampoline : public PyCurveTrampoline<PyCurveRZFourierBase> {
    public:
        using PyCurveTrampoline<PyCurveRZFourierBase>::PyCurveTrampoline; // Inherit constructors

        int num_dofs() override {
            return PyCurveRZFourierBase::num_dofs();
        }

        void set_dofs_impl(const vector<double>& _dofs) override {
            PyCurveRZFourierBase::set_dofs_impl(_dofs);
        }

        vector<double> get_dofs() override {
            return PyCurveRZFourierBase::get_dofs();
        }

        void gamma_impl(PyArray& data, PyArray& quadpoints) override {
            PyCurveRZFourierBase::gamma_impl(data, quadpoints);
        }
};

template <class PyCurvePlanarFourierBase = PyCurvePlanarFourier> class PyCurvePlanarFourierTrampoline : public PyCurveTrampoline<PyCurvePlanarFourierBase> {
    public:
        using PyCurveTrampoline<PyCurvePlanarFourierBase>::PyCurveTrampoline; // Inherit constructors

        int num_dofs() override {
            return PyCurvePlanarFourierBase::num_dofs();
        }

        void set_dofs_impl(const vector<double>& _dofs) override {
            PyCurvePlanarFourierBase::set_dofs_impl(_dofs);
        }

        vector<double> get_dofs() override {
            return PyCurvePlanarFourierBase::get_dofs();
        }

        void gamma_impl(PyArray& data, PyArray& quadpoints) override {
            PyCurvePlanarFourierBase::gamma_impl(data, quadpoints);
        }
};
template <typename T, typename S> void register_common_curve_methods(S &c) {
    c.def("gamma", &T::gamma)
     .def("gamma_impl", &T::gamma_impl)
     .def("gammadash", &T::gammadash)
     .def("gammadashdash", &T::gammadashdash)
     .def("gammadashdashdash", &T::gammadashdashdash)

     .def("dgamma_by_dcoeff", &T::dgamma_by_dcoeff)
     .def("dgammadash_by_dcoeff", &T::dgammadash_by_dcoeff)
     .def("dgammadashdash_by_dcoeff", &T::dgammadashdash_by_dcoeff)
     .def("dgammadashdashdash_by_dcoeff", &T::dgammadashdashdash_by_dcoeff)

     .def("dgamma_by_dcoeff_vjp_impl", &T::dgamma_by_dcoeff_vjp_impl)
     .def("dgammadash_by_dcoeff_vjp_impl", &T::dgammadash_by_dcoeff_vjp_impl)
     .def("dgammadashdash_by_dcoeff_vjp_impl", &T::dgammadashdash_by_dcoeff_vjp_impl)
     .def("dgammadashdashdash_by_dcoeff_vjp_impl", &T::dgammadashdashdash_by_dcoeff_vjp_impl)

     .def("incremental_arclength", &T::incremental_arclength)
     .def("dincremental_arclength_by_dcoeff", &T::dincremental_arclength_by_dcoeff)
     .def("kappa", &T::kappa)
     .def("dkappa_by_dcoeff", &T::dkappa_by_dcoeff)
     .def("torsion", &T::torsion)
     .def("dtorsion_by_dcoeff", &T::dtorsion_by_dcoeff)
     .def("invalidate_cache", &T::invalidate_cache)
     .def("least_squares_fit", &T::least_squares_fit)

     .def("set_dofs", &T::set_dofs)
     .def("set_dofs_impl", &T::set_dofs_impl)
     .def("get_dofs", &T::get_dofs)
     .def("num_dofs", &T::num_dofs)
     .def_readonly("quadpoints", &T::quadpoints);
}

void init_curves(py::module_ &m) {
    auto pycurve = py::class_<PyCurve, shared_ptr<PyCurve>, PyCurveTrampoline<PyCurve>>(m, "Curve")
        .def(py::init<vector<double>>());
    register_common_curve_methods<PyCurve>(pycurve);

    auto pycurvexyzfourier = py::class_<PyCurveXYZFourier, shared_ptr<PyCurveXYZFourier>, PyCurveXYZFourierTrampoline<PyCurveXYZFourier>, PyCurve>(m, "CurveXYZFourier")
        .def(py::init<vector<double>, int>())
        .def_readonly("dofs_matrix", &PyCurveXYZFourier::dofs)
        .def_readonly("order", &PyCurveXYZFourier::order);
    register_common_curve_methods<PyCurveXYZFourier>(pycurvexyzfourier);

    auto pycurverzfourier = py::class_<PyCurveRZFourier, shared_ptr<PyCurveRZFourier>, PyCurveRZFourierTrampoline<PyCurveRZFourier>, PyCurve>(m, "CurveRZFourier")
        //.def(py::init<int, int>())
        .def(py::init<vector<double>, int, int, bool>())
        .def_readwrite("rc", &PyCurveRZFourier::rc)
        .def_readwrite("rs", &PyCurveRZFourier::rs)
        .def_readwrite("zc", &PyCurveRZFourier::zc)
        .def_readwrite("zs", &PyCurveRZFourier::zs)
        .def_readonly("order", &PyCurveRZFourier::order)
        .def_readonly("stellsym", &PyCurveRZFourier::stellsym)
        .def_readonly("nfp", &PyCurveRZFourier::nfp);
    register_common_curve_methods<PyCurveRZFourier>(pycurverzfourier);

    auto pycurveplanarfourier = py::class_<PyCurvePlanarFourier, shared_ptr<PyCurvePlanarFourier>, PyCurvePlanarFourierTrampoline<PyCurvePlanarFourier>, PyCurve>(m, "CurvePlanarFourier")
        .def(py::init<vector<double>, int>())
        .def_readwrite("rc", &PyCurvePlanarFourier::rc)
        .def_readwrite("rs", &PyCurvePlanarFourier::rs)
        .def_readwrite("q", &PyCurvePlanarFourier::q)
        .def_readwrite("center", &PyCurvePlanarFourier::center)
        .def_readonly("order", &PyCurvePlanarFourier::order);
    register_common_curve_methods<PyCurvePlanarFourier>(pycurveplanarfourier);

    auto pycurvecwsfourier = py::class_<PyCurveCWSFourier, shared_ptr<PyCurveCWSFourier>, PyCurveCWSFourierTrampoline<PyCurveCWSFourier>, PyCurve>(m, "CurveCWSFourier")
        .def(py::init<int, int, vector<double>, int, int, int, bool>())
        .def("get_dofs_surface", &PyCurveCWSFourier::get_dofs_surface)
        .def("num_dofs_surface", &PyCurveCWSFourier::num_dofs_surface)
        .def_readonly("order", &PyCurveCWSFourier::order)
        .def_readonly("nfp", &PyCurveCWSFourier::nfp)
        .def_readonly("stellsym", &PyCurveCWSFourier::stellsym)
        .def_readwrite("phi_l", &PyCurveCWSFourier::phi_l)
        .def_readwrite("theta_l", &PyCurveCWSFourier::theta_l)
        .def_readwrite("phi_s", &PyCurveCWSFourier::phi_s)
        .def_readwrite("phi_c", &PyCurveCWSFourier::phi_c)
        .def_readwrite("theta_c", &PyCurveCWSFourier::theta_c)
        .def_readwrite("theta_s", &PyCurveCWSFourier::theta_s)
        .def_readwrite("mpol", &PyCurveCWSFourier::mpol)
        .def_readwrite("ntor", &PyCurveCWSFourier::ntor)
        .def_readwrite("idofs", &PyCurveCWSFourier::idofs)
        .def_readwrite("rc", &PyCurveCWSFourier::rc)
        .def_readwrite("rs", &PyCurveCWSFourier::rs)
        .def_readwrite("zc", &PyCurveCWSFourier::zc)
        .def_readwrite("zs", &PyCurveCWSFourier::zs);
    register_common_curve_methods<PyCurveCWSFourier>(pycurvecwsfourier);
}
