"""EN 16450 variations of the equivalence test and ongoing verification."""

import math

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq


def parallel(slope=1.0, intercept=0.0, noise=1.5, sites=3, years=1, pairs=90, seed=0):
    """One reference sampler and one instrument, sampled at several sites."""
    rng = np.random.default_rng(seed)
    frames = []
    for s in range(sites):
        for y in range(years):
            true = rng.gamma(4.0, 8.0, pairs)
            frames.append(pd.DataFrame({
                "site": f"S{s}", "year": 2023 + y,
                "rm": true + rng.normal(0, 0.6, pairs),
                "ams": intercept + slope * true + rng.normal(0, noise, pairs),
            }))
    return pd.concat(frames, ignore_index=True)


def test_reference_uncertainty_default_differs_between_documents():
    data = parallel()
    assert aq.evaluate_pm(data, "rm", "ams").u_ref == pytest.approx(math.sqrt(0.67))
    assert aq.evaluate_pm(data, "rm", "ams", standard="en16450").u_ref == pytest.approx(0.67)


def test_small_significant_slope_needs_no_calibration_under_en16450():
    data = parallel(slope=1.015, noise=0.3, pairs=300)
    guide = aq.evaluate_pm(data, "rm", "ams", calibration="auto", u_ref=0.2)
    assert guide.calibration.kind == "slope"
    en = aq.evaluate_pm(data, "rm", "ams", calibration="auto", standard="en16450", u_ref=0.2)
    assert en.calibration is None
    assert any("0.98-1.02" in n for n in en.notes)
    # a larger slope is still calibrated
    big = aq.evaluate_pm(
        parallel(slope=1.10, noise=0.3), "rm", "ams", calibration="auto", standard="en16450", u_ref=0.2
    )
    assert big.calibration.kind == "slope"


def test_32_high_results_are_enough_under_en16450():
    rng = np.random.default_rng(1)
    rm = np.r_[rng.uniform(5, 25, 300), rng.uniform(30, 60, 35)]  # 10 % above 28 µg/m³
    data = pd.DataFrame({"rm": rm, "ams": rm + rng.normal(0, 1.5, rm.size)})
    guide = aq.evaluate_pm(data, "rm", "ams").dataset_checks.iloc[0]
    en = aq.evaluate_pm(data, "rm", "ams", standard="en16450").dataset_checks.iloc[0]
    assert not guide["passed"] and en["passed"]
    assert "(35 results)" in en["value"]


def test_applied_calibration_adds_its_uncertainty():
    data = parallel(noise=3.0)
    plain = aq.evaluate_pm(data, "rm", "ams", standard="en16450").comparisons.iloc[0]
    both = aq.evaluate_pm(data, "rm", "ams", standard="en16450", applied_calibration="both").comparisons.iloc[0]
    expected = math.sqrt(plain["u_c"] ** 2 + plain["u_intercept"] ** 2 + (50 * plain["u_slope"]) ** 2)
    assert both["u_c"] == pytest.approx(expected)
    slope = aq.evaluate_pm(data, "rm", "ams", standard="en16450", applied_calibration="slope").comparisons.iloc[0]
    assert slope["u_c"] == pytest.approx(math.sqrt(plain["u_c"] ** 2 + (50 * plain["u_slope"]) ** 2))
    with pytest.raises(ValueError):
        aq.evaluate_pm(data, "rm", "ams", calibration="auto", applied_calibration="slope")


@pytest.mark.parametrize(
    "w, network, expected",
    [
        (8.0, None, 2), (12.0, None, 3), (18.0, None, 4), (24.0, None, 5), (26.0, None, None),
        (12.0, 12, 2),   # 10 % of 12 sites = 2, smaller than 3
        (24.0, 12, 3),   # 20 % of 12 sites = 3, smaller than 5
        (24.0, 60, 5),   # 20 % of 60 sites = 12, so the fixed number applies
        (24.0, 4, 2),    # never fewer than two
        (10.0, None, 2), (15.0, None, 3),  # upper bounds are inclusive
    ],
)
def test_ongoing_sites_required(w, network, expected):
    assert aq.ongoing_sites_required(w, network) == expected


def test_verify_ongoing():
    res = aq.verify_ongoing(parallel(years=3), "rm", "ams", "PM10", site="site", period="year", n_network_sites=30)
    assert not res.action_required
    assert res.w_pct == pytest.approx(res.equivalence.comparisons.iloc[0]["W_pct"])
    assert res.sites_required == aq.ongoing_sites_required(res.w_pct, 30)
    assert len(res.pairs) == 9 and res.pairs["passed"].all()
    assert "Sites to compare" in res.report()

    thin = aq.verify_ongoing(parallel(pairs=50), "rm", "ams", site="site", period="year")
    assert not thin.pairs["passed"].any()
    assert "Fewer than 80" in thin.report()

    drifted = aq.verify_ongoing(parallel(slope=0.8), "rm", "ams", site="site")
    assert drifted.action_required and drifted.sites_required is None
    assert "corrective action" in drifted.report()
