#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MODULE(DataLayer, m) {
py::class_<Tick>(m, "Tick")
// Add constructors and methods for the Tick class
;

py::class_<DataSource, std::shared_ptr<DataSource>>(m, "DataSource")
.def("next", &DataSource::next)
;

py::class_<SpecificDataSource, DataSource>(m, "SpecificDataSource")
.def(py::init<>())
.def("next", &SpecificDataSource::next)
;

py::class_<DataLayer>(m, "DataLayer")
.def(py::init<>())
.def("addProvider", &DataLayer::addProvider)
.def("getTick", &DataLayer::getTick)
;
}