"""Behaviour fixed after running the package on a full year of real co-location data."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq
from aqequiv.pm import Calibration, _format
from aqequiv.sensors import Correction


def deming(x, y, ratio):
    """Textbook closed form of Deming regression, written independently of the package."""
    sxx, syy = np.var(x, ddof=1), np.var(y, ddof=1)
    sxy = np.cov(x, y)[0, 1]
    slope = (syy - ratio * sxx + np.sqrt((syy - ratio * sxx) ** 2 + 4 * ratio * sxy**2)) / (2 * sxy)
    return slope, y.mean() - slope * x.mean()


@pytest.fixture
def one_site():
    """Three sensor systems at one site that read high with a negative intercept."""
    rng = np.random.default_rng(7)
    true = rng.gamma(2.0, 8.0, 360)
    frame = pd.DataFrame({"ref": true + rng.normal(0, 0.6, 360)})
    for i, name in enumerate(("s1", "s2", "s3")):
        frame[name] = -5.0 + (1.3 + 0.05 * i) * true + rng.normal(0, 2.0, 360)
    return frame


@pytest.mark.parametrize("seed", range(5))
def test_comparability_matches_independent_deming(seed):
    rng = np.random.default_rng(seed)
    true = rng.gamma(2.0, 12.0, 300)
    x = true + rng.normal(0, 1.0, 300)
    y = -4.0 + 1.4 * true + rng.normal(0, 3.0, 300)
    slope, intercept = deming(x, y, 1.0)  # ratio 1 is orthogonal regression
    rss = np.sum((y - intercept - slope * x) ** 2)
    expected = 2 * np.sqrt(rss / (len(x) - 2) - 1.5**2 + (intercept + (slope - 1) * 50) ** 2) / 50
    result = aq.comparability(x, y, limit_value=50.0, u_ref=1.5)
    assert result.fit.slope == pytest.approx(slope, rel=1e-10)
    assert result.fit.intercept == pytest.approx(intercept, rel=1e-10)
    assert result.w_expanded == pytest.approx(expected, rel=1e-10)


def test_negative_intercept_is_printed_as_an_addition():
    assert str(Correction("both", 1.25, -8.574, 0.0, 0.0)) == "y_corr = (y + 8.574) / 1.250"
    assert str(Correction("intercept", 1.0, 2.0, 0.0, 0.0)) == "y_corr = y - 2.000"
    assert str(Calibration("both", 1.5, -13.626, 0.0, 0.0)) == "y_cal = (y + 13.626) / 1.500"
    assert str(Calibration("intercept", 1.0, -1.0, 0.0, 0.0)) == "y_cal = y + 1.000"


def test_a_column_uses_one_number_of_decimals():
    text = _format(pd.DataFrame({"u": [9.165, 10.1], "slope": [1.117, 0.902]}))
    assert "9.2" in text and "10.1" in text and "9.165" not in text
    assert "1.117" in text and "0.902" in text


def test_class_without_humidity_test_is_provisional(one_site):
    result = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], "PM2.5", correction="both")
    assert result.sensor_class == 1 and result.provisional
    assert result.pending == ["humidity test"]
    assert "Result: Class 1 (provisional: humidity test not supplied)" in result.report()
    assert "provisional: humidity test not supplied" in result.to_html()

    complete = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], "PM2.5", correction="both", rh_factor=1.2)
    assert not complete.provisional and complete.verdict == "Class 1"
    assert "Result: Class 1\n" in complete.report()


def test_class_3_needs_no_humidity_test(one_site):
    crit = aq.SensorCriteria("PM2.5", 30.0, 21.0, 15.0, dqo=(0.1, 0.2, 60.0))
    result = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], correction="both", criteria=crit)
    assert result.sensor_class == 3 and not result.provisional


def test_unclassified_result_is_not_provisional(one_site):
    low = one_site.assign(**{name: one_site[name] - 6.0 for name in ("s1", "s2", "s3")})  # intercept beyond ±7
    result = aq.evaluate_sensor(low, "ref", ["s1", "s2", "s3"], "PM2.5")
    assert result.sensor_class is None and not result.provisional and result.pending == []
    assert "Result: not classified" in result.report()


def test_pm10_class_1_lists_every_missing_test(one_site):
    result = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], "PM10", correction="both")
    assert result.sensor_class == 1
    assert result.pending == ["humidity test", "coarse fraction field test", "laboratory coarse test"]


def test_gas_class_is_always_provisional(one_site):
    result = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], "NO2", correction="both", u_ref=0.5)
    assert result.sensor_class is not None
    assert result.pending == ["pre-test and laboratory tests"]


def test_plots_without_site_column(one_site):
    result = aq.evaluate_sensor(one_site, "ref", ["s1", "s2", "s3"], "PM2.5", correction="both")
    for fig in (result.plot(), result.target_diagram()):
        titles = [ax.get_title() for ax in fig.axes if ax.get_title()]
        assert titles == ["s1", "s2", "s3"]
    legend = fig.legends[0]
    assert [t.get_text() for t in legend.get_texts()] == [
        "limit value, 30 µg/m³", "upper assessment threshold, 21 µg/m³", "lower assessment threshold, 15 µg/m³",
    ]
    assert not [t for ax in fig.axes for t in ax.texts if t.get_text().startswith(("LV", "UAT", "LAT"))]

    single = aq.target_diagram(one_site["ref"], one_site["s1"], "SO2", u_ref=0.5)  # SO2 has no thresholds
    assert [t.get_text() for t in single.legends[0].get_texts()] == ["limit value, 350 µg/m³"]
