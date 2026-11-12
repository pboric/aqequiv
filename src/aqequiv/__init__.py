"""Equivalence testing of ambient air monitoring methods.

Implements the particulate matter procedure of the European Commission's
*Guide to the Demonstration of Equivalence of Ambient Air Monitoring
Methods* (January 2010).
"""

from .datasets import EXAMPLES, load_example
from .pm import (
    PM10,
    PM25,
    Calibration,
    Comparability,
    PMCriteria,
    PMEquivalence,
    between_sampler_uncertainty,
    comparability,
    evaluate_pm,
)
from .regression import OrthogonalFit, orthogonal_regression

__version__ = "0.1.0"

__all__ = [
    "EXAMPLES",
    "PM10",
    "PM25",
    "Calibration",
    "Comparability",
    "OrthogonalFit",
    "PMCriteria",
    "PMEquivalence",
    "between_sampler_uncertainty",
    "comparability",
    "evaluate_pm",
    "load_example",
    "orthogonal_regression",
]
