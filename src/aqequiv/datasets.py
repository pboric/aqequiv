"""Example datasets printed in Annex F of the 2010 Guide."""

from __future__ import annotations

from importlib import resources

import pandas as pd

EXAMPLES = {
    "pm25_locA_cm1": "PM2.5, location A, candidate 1 (two reference samplers)",
    "pm25_locA_cm2": "PM2.5, location A, candidate 2 (two reference samplers)",
    "pm25_locB_cm2": "PM2.5, location B, candidate 2 (two reference samplers)",
    "pm10_locC_cm1": "PM10, location C, candidate 1 (one reference sampler)",
    "pm10_locC_cm2": "PM10, location C, candidate 2 (one reference sampler)",
}


def load_example(name: str) -> pd.DataFrame:
    """Load one Annex F example as a DataFrame of daily values in µg/m³.

    PM2.5 examples have the columns ``rm1``, ``rm2`` and ``cm``; PM10
    examples have ``rm`` and ``cm``. See :data:`EXAMPLES` for the names.
    """
    if name not in EXAMPLES:
        raise ValueError(f"unknown example {name!r}; choose from {sorted(EXAMPLES)}")
    with resources.files("aqequiv").joinpath("data", f"{name}.csv").open() as f:
        return pd.read_csv(f)
