"""Objectives of Directive (EU) 2024/2881 applied through the criteria objects."""

import sys
from pathlib import Path

import pytest

import aqequiv as aq

sys.path.insert(0, str(Path(__file__).parent))
from test_sensors import SENSORS, field_test  # noqa: E402


def test_fixed_measurement_objectives():
    assert aq.PM10_2030.limit_value == 45 and aq.PM25_2030.limit_value == 25
    # the absolute value is the higher of the two at the limit value
    assert aq.PM10_2030.max_uncertainty == pytest.approx(11.3)
    assert aq.PM25_2030.max_uncertainty == pytest.approx(6.3)
    # the 2010 Guide criteria are unchanged
    assert aq.PM10.max_uncertainty == pytest.approx(12.5)
    assert aq.PM25.max_uncertainty == pytest.approx(7.5)


def test_equivalence_at_2030_limit_value():
    data = aq.load_example("pm10_locC_cm2")
    old = aq.evaluate_pm(data, "rm", "cm", "PM10", u_ref=1.5, calibration="slope")
    new = aq.evaluate_pm(data, "rm", "cm", u_ref=1.5, calibration="slope", criteria=aq.PM10_2030)
    row_old = old.comparisons.iloc[0]
    row_new = new.comparisons.iloc[0]
    # same regression, uncertainty evaluated at 45 instead of 50 µg/m³
    assert row_new["slope"] == row_old["slope"]
    assert row_new["bias"] == pytest.approx(row_old["intercept"] + (row_old["slope"] - 1) * 45)
    assert row_new["W_pct"] == pytest.approx(100 * 2 * row_new["u_c"] / 45)
    assert "11.3 µg/m³" in new.report()


def test_absolute_objective_decides():
    x = [10.0, 20, 30, 40, 50, 60, 70, 80]
    y = [v + d for v, d in zip(x, [3, -3, 3, -3, 3, -3, 3, -3])]
    strict = aq.comparability(x, y, limit_value=45, u_ref=0.0, dqo=0.10)
    relaxed = aq.comparability(x, y, limit_value=45, u_ref=0.0, dqo=0.10, dqo_absolute=11.3)
    assert strict.w_expanded == relaxed.w_expanded
    assert not strict.passed and relaxed.passed


def test_sensor_class_limits_from_directive():
    pm10, pm25 = aq.SENSOR_PM10_2030, aq.SENSOR_PM25_2030
    assert pm10.dqo == (22.5, min(2.2 * 22.5, 0.85 * 45), 2 * 45)
    assert pm25.dqo == (8.8, min(2.5 * 8.8, 0.85 * 25), 2 * 25)


def test_sensor_classification_is_stricter_for_pm25():
    data = field_test(noise=5.0)
    now = aq.evaluate_sensor(data, "ref", SENSORS, "PM2.5", site="site", rh_factor=1.2)
    later = aq.evaluate_sensor(data, "ref", SENSORS, site="site", rh_factor=1.2, criteria=aq.SENSOR_PM25_2030)
    assert now.sensor_class == 1
    assert later.sensor_class == 2
    assert "U_UAT" in now.datasets and "U_UAT" not in later.datasets
    assert later.datasets["U_LV"].max() < now.datasets["U_LV"].max() + 1e-9  # evaluated at 25, not 30
