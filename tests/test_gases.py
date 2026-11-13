"""Field-test classification of gas sensor systems (CEN/TS 17660-1)."""

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq
from aqequiv.regression import LinearFit
from aqequiv.sensors import FieldUncertainty

SENSORS = ["s0", "s1", "s2"]


def hourly(level=40.0, slope=1.0, intercept=0.0, noise=5.0, spread=3.0, sites=2, hours=1920, seed=0):
    rng = np.random.default_rng(seed)
    frames = []
    for s in range(sites):
        true = rng.gamma(2.5, level / 2.5, hours)
        common = rng.normal(0, noise, hours)
        frame = pd.DataFrame({"site": f"S{s}", "ref": true + rng.normal(0, 1.0, hours)})
        for k in range(3):
            frame[f"s{k}"] = intercept + slope * true + common + rng.normal(0, spread, hours)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


@pytest.mark.parametrize(
    "intercept, slope, printed_slope, residual_sd, u_lat, u_uat, u_lv, u_at",
    [
        # sensor systems 1-3 of the worked NO2 example in Annex K; the slope is
        # printed to two decimals, so the third decimal is chosen within that rounding
        (0.75, 1.004, 1.00, 5.11, 10.2, 10.3, 10.4, 10.9),
        (-2.6, 1.036, 1.04, 5.3, 10.4, 11.3, 13.7, 25.6),
        (-0.8, 1.056, 1.06, 5.0, 13.6, 17.1, 22.9, 44.1),
    ],
)
def test_annex_k_example(intercept, slope, printed_slope, residual_sd, u_lat, u_uat, u_lv, u_at):
    n, u_ref = 967, 1.2
    fit = LinearFit(slope, intercept, 0.0, 0.0, n, residual_sd**2 * (n - 2), float("nan"))
    fu = FieldUncertainty(fit, u_ref, (residual_sd**2 - u_ref**2) ** 0.5, (0.0, 0.0))
    assert abs(slope - printed_slope) <= 0.005
    assert fu.expanded(100) == pytest.approx(u_lat, abs=0.25)
    assert fu.expanded(140) == pytest.approx(u_uat, abs=0.25)
    assert fu.expanded(200) == pytest.approx(u_lv, abs=0.25)
    assert fu.expanded(400) == pytest.approx(u_at, abs=1.0)


def test_criteria_values():
    assert aq.SENSOR_NO2.dqo == (50, 150, 400) and aq.SENSOR_NO2.limit_value == 200
    assert aq.SENSOR_O3.dqo == (36, 90, 240)
    assert aq.SENSOR_CO.unit == "mg/m³" and aq.SENSOR_CO.dqo == (2.5, 7.5, 20)
    assert aq.SENSOR_SO2.upper_assessment_threshold is None and aq.SENSOR_SO2.min_sites == 1
    for crit in (aq.SENSOR_NO2, aq.SENSOR_NO, aq.SENSOR_O3, aq.SENSOR_SO2, aq.SENSOR_CO, aq.SENSOR_BENZENE):
        assert crit.period == "hour" and crit.default_u_ref is None
        assert crit.slope_range == aq.SENSOR_PM10.slope_range


def test_gas_needs_reference_uncertainty():
    with pytest.raises(ValueError, match="u_ref"):
        aq.evaluate_sensor(hourly(hours=200), "ref", SENSORS, "NO2", site="site")


def test_no2_class_1():
    res = aq.evaluate_sensor(hourly(), "ref", SENSORS, "NO2", site="site", u_ref=1.2)
    assert res.sensor_class == 1
    assert res.dataset_suitable
    assert {"U_LV", "U_UAT", "U_LAT"} <= set(res.datasets)
    assert any("pre-test" in n for n in res.notes)
    assert not any("humidity" in n for n in res.notes)
    assert "fewest hours at a site" in res.report()


def test_no2_class_follows_bias_and_scatter():
    biased = aq.evaluate_sensor(hourly(slope=1.35), "ref", SENSORS, "NO2", site="site", u_ref=1.2)
    assert biased.sensor_class == 2  # slope outside 0.78-1.29, and U at 200 µg/m³ above 50
    fixed = aq.evaluate_sensor(hourly(slope=1.35), "ref", SENSORS, "NO2", site="site", u_ref=1.2, correction="slope")
    assert fixed.sensor_class == 1
    scattered = aq.evaluate_sensor(hourly(spread=12.0), "ref", SENSORS, "NO2", site="site", u_ref=1.2)
    assert scattered.between_sensor["class"].tolist() == ["Class 2", "Class 2"]


def test_co_in_mg_and_so2_without_thresholds():
    co = hourly(level=0.6, noise=0.05, spread=0.03)
    res = aq.evaluate_sensor(co, "ref", SENSORS, "CO", site="site", u_ref=0.5)
    assert "mg/m³" in res.report()
    so2 = aq.evaluate_sensor(hourly(level=8.0, noise=1.0, spread=0.5, sites=1), "ref", SENSORS, "SO2", site="site", u_ref=1.2)
    assert "U_UAT" not in so2.datasets
    assert so2.dataset_suitable  # one site is enough for SO2


def test_gas_plots():
    import matplotlib

    matplotlib.use("Agg")
    res = aq.evaluate_sensor(hourly(hours=300), "ref", SENSORS, "O3", site="site", u_ref=1.1)
    assert len(res.plot().axes) == 6
    assert len(res.target_diagram().axes) == 7
    with pytest.raises(ValueError):
        aq.target_diagram([1.0, 2, 3, 4], [1.0, 2, 3, 5], "O3")
