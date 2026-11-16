"""Equivalence testing and sensor classification for ambient air measurements.

* :func:`evaluate_pm` - equivalence of a candidate method with the reference
  method (EC *Guide to the Demonstration of Equivalence*, January 2010).
* :func:`evaluate_sensor` - classification of sensor systems from field
  tests (CEN/TS 17660-2:2024 for PM, CEN/TS 17660-1:2021 for gases).
* :func:`verify_ongoing` - yearly ongoing verification of an equivalent PM
  instrument (EN 16450:2017).
"""

from .datasets import EXAMPLES, load_example
from .pm import (
    PM10,
    PM10_2030,
    PM25,
    PM25_2030,
    Calibration,
    Comparability,
    PMCriteria,
    OngoingVerification,
    PMEquivalence,
    between_sampler_uncertainty,
    comparability,
    evaluate_pm,
    ongoing_sites_required,
    verify_ongoing,
)
from .plotting import target_diagram
from .report import to_html
from .regression import LinearFit, OrthogonalFit, ols_regression, orthogonal_regression
from .sensors import (
    SENSOR_BENZENE,
    SENSOR_CO,
    SENSOR_NO,
    SENSOR_NO2,
    SENSOR_O3,
    SENSOR_SO2,
    SENSOR_PM10,
    SENSOR_PM10_2030,
    SENSOR_PM25,
    SENSOR_PM25_2030,
    CoarseTest,
    Correction,
    FieldUncertainty,
    RHFactor,
    SensorClassification,
    SensorCriteria,
    between_sensor_uncertainty,
    coarse_test,
    daily_means,
    evaluate_sensor,
    field_uncertainty,
    fine_coarse_factor,
    rh_factor,
)

__version__ = "0.6.1"

__all__ = [
    "EXAMPLES",
    "PM10",
    "PM10_2030",
    "PM25",
    "PM25_2030",
    "SENSOR_BENZENE",
    "SENSOR_CO",
    "SENSOR_NO",
    "SENSOR_NO2",
    "SENSOR_O3",
    "SENSOR_PM10",
    "SENSOR_PM10_2030",
    "SENSOR_PM25",
    "SENSOR_PM25_2030",
    "SENSOR_SO2",
    "Calibration",
    "CoarseTest",
    "Comparability",
    "Correction",
    "FieldUncertainty",
    "LinearFit",
    "OngoingVerification",
    "OrthogonalFit",
    "PMCriteria",
    "PMEquivalence",
    "RHFactor",
    "SensorClassification",
    "SensorCriteria",
    "between_sampler_uncertainty",
    "between_sensor_uncertainty",
    "coarse_test",
    "comparability",
    "daily_means",
    "evaluate_pm",
    "evaluate_sensor",
    "field_uncertainty",
    "fine_coarse_factor",
    "load_example",
    "ols_regression",
    "ongoing_sites_required",
    "orthogonal_regression",
    "rh_factor",
    "target_diagram",
    "to_html",
    "verify_ongoing",
]
