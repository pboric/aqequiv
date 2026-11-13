"""Equivalence testing and sensor classification for ambient PM measurements.

* :func:`evaluate_pm` - equivalence of a candidate method with the reference
  method (EC *Guide to the Demonstration of Equivalence*, January 2010).
* :func:`evaluate_sensor` - classification of sensor systems from field
  tests (CEN/TS 17660-2:2024).
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
    PMEquivalence,
    between_sampler_uncertainty,
    comparability,
    evaluate_pm,
)
from .plotting import target_diagram
from .regression import LinearFit, OrthogonalFit, ols_regression, orthogonal_regression
from .sensors import (
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

__version__ = "0.3.0"

__all__ = [
    "EXAMPLES",
    "PM10",
    "PM10_2030",
    "PM25",
    "PM25_2030",
    "SENSOR_PM10",
    "SENSOR_PM10_2030",
    "SENSOR_PM25",
    "SENSOR_PM25_2030",
    "Calibration",
    "CoarseTest",
    "Comparability",
    "Correction",
    "FieldUncertainty",
    "LinearFit",
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
    "orthogonal_regression",
    "rh_factor",
    "target_diagram",
]
