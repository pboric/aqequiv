import math

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq


def synthetic(n_sites=4, n=60, slope=1.0, intercept=0.0, noise=1.5, seed=0):
    rng = np.random.default_rng(seed)
    frames = []
    for s in range(n_sites):
        true = rng.gamma(4.0, 8.0, n)
        frames.append(pd.DataFrame({
            "site": f"S{s}",
            "rm1": true + rng.normal(0, 0.6, n),
            "rm2": true + rng.normal(0, 0.6, n),
            "cm1": intercept + slope * true + rng.normal(0, noise, n),
            "cm2": intercept + slope * true + rng.normal(0, noise, n),
        }))
    return pd.concat(frames, ignore_index=True)


def test_regression_recovers_exact_line():
    x = np.arange(1.0, 21.0)
    fit = aq.orthogonal_regression(x, 2.0 + 0.9 * x)
    assert fit.slope == pytest.approx(0.9)
    assert fit.intercept == pytest.approx(2.0)
    assert fit.rss == pytest.approx(0.0, abs=1e-18)
    assert fit.slope_significant and fit.intercept_significant


def test_regression_is_symmetric():
    rng = np.random.default_rng(1)
    x = rng.uniform(5, 60, 200)
    y = 1.0 + 0.8 * x + rng.normal(0, 3, 200)
    forward = aq.orthogonal_regression(x, y)
    backward = aq.orthogonal_regression(y, x)
    assert backward.slope == pytest.approx(1 / forward.slope)


def test_regression_through_origin():
    x = np.arange(1.0, 21.0)
    fit = aq.orthogonal_regression(x, 1.1 * x, through_origin=True)
    assert fit.slope == pytest.approx(1.1)
    assert fit.intercept == 0.0


def test_regression_ignores_missing_pairs():
    x = [1.0, 2.0, np.nan, 4.0, 5.0]
    y = [1.0, 2.1, 3.0, np.nan, 5.2]
    assert aq.orthogonal_regression(x, y).n == 3


def test_between_sampler_uncertainty():
    # differences 1, -1, 2 -> sqrt(6 / 6) = 1
    assert aq.between_sampler_uncertainty([10, 20, 30], [9, 21, 28]) == pytest.approx(1.0)
    assert aq.between_sampler_uncertainty([10, np.nan, 30], [9, 21, 28]) == pytest.approx(
        math.sqrt(5 / 4)
    )


def test_good_candidate_passes_everything():
    result = aq.evaluate_pm(synthetic(), ["rm1", "rm2"], ["cm1", "cm2"], "PM10", site="site")
    assert result.passed
    assert result.dataset_suitable
    assert result.u_ref_source == "reference u_bs / √2"
    datasets = set(result.comparisons["dataset"])
    assert {"all", ">= 30", "site S0", "site S3"} <= datasets
    assert set(result.comparisons["candidate"]) == {"cm1", "cm2"}
    assert list(result.between_sampler["method"]) == ["reference", "candidate", "candidate", "candidate"]
    assert "PASS" in result.report()


def test_biased_candidate_fails_then_passes_after_calibration():
    data = synthetic(slope=0.8, intercept=3.0)
    raw = aq.evaluate_pm(data, ["rm1", "rm2"], ["cm1", "cm2"], "PM10", site="site")
    assert not raw.passed
    assert raw.calibration is None

    cal = aq.evaluate_pm(data, ["rm1", "rm2"], ["cm1", "cm2"], "PM10", site="site", calibration="auto")
    assert cal.calibration.kind == "both"
    assert cal.calibration.slope == pytest.approx(0.8, abs=0.02)
    assert cal.passed
    assert cal.calibration.apply(np.array([43.0]))[0] == pytest.approx(
        (43.0 - cal.calibration.intercept) / cal.calibration.slope
    )


def test_no_calibration_when_nothing_is_significant():
    result = aq.evaluate_pm(synthetic(), ["rm1", "rm2"], ["cm1", "cm2"], "PM10", calibration="auto")
    assert result.calibration is None


def test_noisy_instruments_fail_between_sampler_criterion():
    result = aq.evaluate_pm(synthetic(noise=4.0), ["rm1", "rm2"], ["cm1", "cm2"], "PM10")
    assert not result.between_sampler.query("method == 'candidate'")["passed"].all()
    assert not result.passed


def test_single_reference_uses_guide_default():
    data = synthetic().rename(columns={"rm1": "rm"})
    result = aq.evaluate_pm(data, "rm", "cm1", "PM2.5")
    assert result.u_ref == pytest.approx(math.sqrt(0.67))
    assert result.criteria.limit_value == 30


def test_small_dataset_is_flagged():
    data = synthetic(n_sites=2, n=20)
    result = aq.evaluate_pm(data, ["rm1", "rm2"], "cm1", "PM10", site="site")
    assert not result.dataset_suitable


def test_bad_arguments():
    data = synthetic()
    with pytest.raises(ValueError):
        aq.evaluate_pm(data, "rm1", "cm1", "NO2")
    with pytest.raises(ValueError):
        aq.evaluate_pm(data, "rm1", "cm1", calibration="maybe")
    with pytest.raises(ValueError):
        aq.load_example("nope")


def test_plot_draws_one_panel_per_candidate():
    import matplotlib

    matplotlib.use("Agg")
    result = aq.evaluate_pm(synthetic(), ["rm1", "rm2"], ["cm1", "cm2"], "PM10")
    fig = result.plot()
    assert len(fig.axes) == 2
