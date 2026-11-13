import math

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq


def field_test(slope=1.0, intercept=0.0, noise=2.0, spread=1.0, n_sites=2, days=90, missing=0.0, seed=0):
    """Daily co-location data for three sensor systems at each site."""
    rng = np.random.default_rng(seed)
    frames = []
    for s in range(n_sites):
        true = rng.gamma(3.0, 7.0, days)
        common = rng.normal(0, noise, days)  # error shared by the three systems
        frame = pd.DataFrame({"site": f"S{s}", "ref": true + rng.normal(0, 0.5, days)})
        for k in range(3):
            y = intercept + slope * true + common + rng.normal(0, spread, days)
            y[rng.random(days) < missing] = np.nan
            frame[f"s{k}"] = y
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


SENSORS = ["s0", "s1", "s2"]


def test_ols_matches_numpy():
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 60, 80)
    y = 2 + 0.7 * x + rng.normal(0, 4, 80)
    fit = aq.ols_regression(x, y)
    (b, a), cov = np.polyfit(x, y, 1, cov="unscaled")
    s2 = fit.rss / (fit.n - 2)
    assert fit.slope == pytest.approx(b)
    assert fit.intercept == pytest.approx(a)
    assert fit.u_slope == pytest.approx(math.sqrt(s2 * cov[0, 0]))
    assert fit.u_intercept == pytest.approx(math.sqrt(s2 * cov[1, 1]))
    assert fit.r2 == pytest.approx(np.corrcoef(x, y)[0, 1] ** 2)


def test_between_sensor_uncertainty():
    # each row deviates from its mean by (-1, 0, 1): sqrt(2n / (n * 2)) = 1
    v = np.array([[9.0, 10, 11], [19, 20, 21], [4, 5, 6]])
    assert aq.between_sensor_uncertainty(v) == pytest.approx(1.0)
    # rows with a gap are skipped
    assert aq.between_sensor_uncertainty(np.vstack([v, [1, np.nan, 50]])) == pytest.approx(1.0)
    # two systems: same as the Guide's between-sampler uncertainty
    two = np.array([[10.0, 9], [20, 21], [30, 28]])
    assert aq.between_sensor_uncertainty(two) == pytest.approx(
        aq.between_sampler_uncertainty(two[:, 0], two[:, 1])
    )


def test_field_uncertainty_formula():
    rng = np.random.default_rng(5)
    x = rng.uniform(5, 60, 100)
    y = 1.5 + 1.1 * x + rng.normal(0, 3, 100)
    fu = aq.field_uncertainty(x, y, u_ref=0.67)
    f = fu.fit
    expected = 2 * math.sqrt(f.rss / 98 - 0.67**2 + (f.intercept + (f.slope - 1) * 30) ** 2)
    assert fu.expanded(30) == pytest.approx(expected)
    # correction terms add u(a)² and (L·u(b))²
    fc = aq.field_uncertainty(x, y, u_ref=0.67, u_correction_terms=(0.5, 0.02))
    assert fc.expanded(30) == pytest.approx(2 * math.sqrt((expected / 2) ** 2 + 0.25 + 0.36))


def test_random_term_never_negative():
    x = np.arange(1.0, 40.0)
    fu = aq.field_uncertainty(x, x, u_ref=0.67)
    assert fu.random_term == 0.0
    assert fu.expanded(30) == pytest.approx(0.0, abs=1e-9)


def test_rh_factor():
    rng = np.random.default_rng(2)
    rh = np.r_[rng.uniform(30, 60, 200), rng.uniform(85, 95, 200), rng.uniform(60, 85, 100)]
    eq = rng.uniform(5, 40, 500)
    ratio = np.where(rh > 80, 1.81, 1.32)
    res = aq.rh_factor(eq * ratio, eq, rh)
    assert res.factor == pytest.approx(1.81 / 1.32)
    assert (res.n_low, res.n_high) == (200, 200)
    few = aq.rh_factor(eq[:210] * ratio[:210], eq[:210], rh[:210])  # only 10 humid hours
    assert not few.assessable


def test_daily_means_coverage():
    idx = pd.date_range("2025-01-01", periods=72, freq="h")
    s = pd.Series(10.0, index=idx)
    s.iloc[24:28] = np.nan  # day 2: 20 of 24 hours (83 %)
    s.iloc[48:64] = np.nan  # day 3: 8 of 24 hours (33 %)
    assert aq.daily_means(s, 0.90).notna().tolist() == [True, False, False]
    assert aq.daily_means(s, 0.50).notna().tolist() == [True, True, False]


def test_coarse_test():
    rng = np.random.default_rng(4)
    fine = rng.uniform(5, 25, 60)
    coarse = rng.uniform(2, 30, 60)
    good = aq.coarse_test(fine + 0.9 * coarse + rng.normal(0, 1, 60), fine, fine + coarse, fine)
    assert good.passed
    blind = aq.coarse_test(1.3 * fine, fine, fine + coarse, fine)  # PM10 estimated from PM2.5
    assert blind.assessable and not blind.passed
    clean = aq.coarse_test(fine + 3, fine, fine + 3, fine)
    assert not clean.assessable


def test_fine_coarse_factor():
    assert aq.fine_coarse_factor(20, 20, 10, 40) == pytest.approx(4.0)


def test_good_sensor_is_class_1():
    res = aq.evaluate_sensor(field_test(), "ref", SENSORS, "PM2.5", site="site", rh_factor=1.2)
    assert res.sensor_class == 1
    assert res.dataset_suitable
    assert len(res.datasets) == 6
    assert "Class 1" in res.report()


def test_class_follows_worst_criterion():
    data = field_test()
    assert aq.evaluate_sensor(data, "ref", SENSORS, site="site", rh_factor=1.8).sensor_class == 2
    assert aq.evaluate_sensor(data, "ref", SENSORS, site="site", rh_factor=3.0).sensor_class == 3
    by_site = aq.evaluate_sensor(data, "ref", SENSORS, site="site", rh_factor={"S0": 1.37, "S1": 1.62})
    assert by_site.sensor_class == 2

    gappy = aq.evaluate_sensor(field_test(missing=0.3), "ref", SENSORS, site="site", rh_factor=1.2)
    assert gappy.sensor_class == 2
    assert "data capture" in gappy.datasets["limited_by"].iloc[0]

    scattered = aq.evaluate_sensor(field_test(spread=4.5), "ref", SENSORS, site="site", rh_factor=1.2)
    assert scattered.between_sensor["class"].tolist() == ["Class 2", "Class 2"]

    hopeless = aq.evaluate_sensor(field_test(slope=3.0), "ref", SENSORS, site="site", rh_factor=1.2)
    assert hopeless.sensor_class is None
    assert "not classified" in hopeless.report()


def test_slope_correction_recovers_class_1():
    data = field_test(slope=1.5)
    raw = aq.evaluate_sensor(data, "ref", SENSORS, "PM2.5", site="site", rh_factor=1.2)
    assert raw.sensor_class > 1
    fixed = aq.evaluate_sensor(data, "ref", SENSORS, "PM2.5", site="site", rh_factor=1.2, correction="slope")
    assert fixed.correction.slope == pytest.approx(1.5, abs=0.05)
    assert fixed.sensor_class == 1


def test_pm10_class_1_needs_coarse_tests():
    data = field_test()
    fine = np.linspace(5, 25, 40)
    coarse = np.linspace(2, 30, 40)[::-1].copy()
    blind = aq.coarse_test(1.3 * fine, fine, fine + coarse, fine)
    res = aq.evaluate_sensor(data, "ref", SENSORS, "PM10", site="site", rh_factor=1.2, coarse=blind, lab_factor=1.4)
    assert res.sensor_class == 2
    res = aq.evaluate_sensor(data, "ref", SENSORS, "PM10", site="site", rh_factor=1.2, lab_factor=2.6)
    assert res.sensor_class == 2
    assert any("coarse fraction field test not assessed" in n for n in res.notes)


def test_small_field_test_is_flagged():
    res = aq.evaluate_sensor(field_test(n_sites=1, days=30), "ref", SENSORS[:2], site="site")
    assert not res.dataset_suitable
    assert any("humidity" in n for n in res.notes)


def test_sensor_plot():
    import matplotlib

    matplotlib.use("Agg")
    fig = aq.evaluate_sensor(field_test(), "ref", SENSORS, site="site").plot()
    assert len(fig.axes) == 6


def test_target_diagram_components():
    rng = np.random.default_rng(7)
    x = rng.uniform(5, 70, 120)
    y = 2.0 + 1.2 * x + rng.normal(0, 3, 120)
    fu = aq.field_uncertainty(x, y, u_ref=0.67, u_correction_terms=(0.3, 0.01))
    levels = np.array([10.0, 30.0, 60.0])
    rr, rb = fu.relative_components(levels)
    for level, r, b in zip(levels, rr, rb):
        # the distance from the origin is the relative expanded uncertainty
        assert math.hypot(r, b) == pytest.approx(fu.expanded(level) / level)
        assert b == pytest.approx(2 * fu.bias(level) / level)
    # the bias tends to the slope contribution at high concentrations
    assert fu.relative_components(1e9)[1] == pytest.approx(2 * (fu.fit.slope - 1), abs=1e-6)


def test_target_diagram_plots():
    import matplotlib

    matplotlib.use("Agg")
    data = field_test(slope=1.26)
    fig = aq.target_diagram(data["ref"], data["s0"], "PM2.5")
    assert fig.axes[0].get_xlabel().startswith("Relative random")
    grid = aq.evaluate_sensor(data, "ref", SENSORS, site="site").target_diagram()
    assert len(grid.axes) == 7  # six panels and the colour bar
    new = aq.evaluate_sensor(data, "ref", SENSORS, site="site", criteria=aq.SENSOR_PM25_2030).target_diagram()
    assert len(new.axes) == 7
