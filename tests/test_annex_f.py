"""Reproduce the worked examples printed in Annex F of the 2010 Guide.

The Guide prints rounded results, and its examples take the reference
between-sampler uncertainty itself as the reference uncertainty, so the
tests pass ``u_ref`` explicitly.
"""

import pytest

import aqequiv as aq

# name, pollutant, u_ref ("ubs" = from the duplicate reference samplers),
# calibration, then the printed values:
# slope, u_slope, intercept, u_intercept, n, random, bias, u_c, relative %, pass
CASES = [
    ("pm25_locA_cm1", "PM2.5", "ubs", "none", 0.819, 0.019, 1.11, 0.74, 111, 3.6, -4.3, 5.6, 18.6, False),
    ("pm25_locA_cm1", "PM2.5", "ubs", "slope", 1.006, 0.023, 1.15, 0.90, 111, 4.4, 1.3, 4.6, 15.4, False),
    ("pm25_locA_cm2", "PM2.5", "ubs", "none", 1.018, 0.011, -4.53, 0.45, 88, 1.7, -4.0, 4.3, 14.4, False),
    ("pm25_locA_cm2", "PM2.5", "ubs", "intercept", 1.018, 0.011, 0.00, 0.45, 88, 1.7, 0.5, 1.8, 6.0, True),
    ("pm25_locB_cm2", "PM2.5", 0.8, "none", 0.934, 0.036, 0.977, 0.794, 63, 2.6, -1.0, 2.7, 9.2, True),
    ("pm10_locC_cm1", "PM10", 1.5, "none", 0.793, 0.024, 0.09, 0.81, 157, 3.5, -10.3, 10.8, 21.7, False),
    ("pm10_locC_cm1", "PM10", 1.5, "slope", 1.018, 0.030, -0.44, 1.03, 157, 4.7, 0.44, 4.8, 9.5, True),
    ("pm10_locC_cm2", "PM10", 1.5, "none", 0.829, 0.014, 0.88, 0.52, 159, 2.7, -7.7, 8.13, 16.3, False),
    ("pm10_locC_cm2", "PM10", 1.5, "slope", 1.004, 0.017, 0.93, 0.63, 159, 3.5, 1.1, 3.7, 7.3, True),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}-{c[3]}")
def test_annex_f_example(case):
    name, pollutant, u_ref, calibration, b, ub, a, ua, n, random, bias, uc, rel, passed = case
    data = aq.load_example(name)
    reference = ["rm1", "rm2"] if "rm1" in data else "rm"
    if u_ref == "ubs":
        u_ref = aq.between_sampler_uncertainty(data["rm1"], data["rm2"])

    result = aq.evaluate_pm(data, reference, "cm", pollutant, u_ref=u_ref, calibration=calibration)
    row = result.comparisons.query("dataset == 'all'").iloc[0]

    assert row["n"] == n
    assert row["slope"] == pytest.approx(b, abs=0.002)
    assert row["u_slope"] == pytest.approx(ub, abs=0.001)
    assert row["intercept"] == pytest.approx(a, abs=0.03)
    assert row["u_intercept"] == pytest.approx(ua, abs=0.01)
    assert row["random"] == pytest.approx(random, abs=0.15)
    assert row["bias"] == pytest.approx(bias, abs=0.06)
    assert row["u_c"] == pytest.approx(uc, abs=0.06)
    # the Guide prints the combined (not expanded) relative uncertainty
    assert row["W_pct"] / 2 == pytest.approx(rel, abs=0.2)
    assert bool(row["passed"]) is passed


@pytest.mark.parametrize(
    "name, expected",
    [("pm25_locA_cm1", "slope"), ("pm25_locA_cm2", "intercept"), ("pm10_locC_cm2", "slope")],
)
def test_auto_calibration_follows_significance(name, expected):
    data = aq.load_example(name)
    reference = ["rm1", "rm2"] if "rm1" in data else "rm"
    pollutant = "PM2.5" if "rm1" in data else "PM10"
    result = aq.evaluate_pm(data, reference, "cm", pollutant, calibration="auto")
    assert result.calibration.kind == expected
