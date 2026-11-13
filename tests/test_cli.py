"""Command-line interface and HTML report."""

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq
from aqequiv.cli import main

PM_ARGS = ["--reference", "rm1", "rm2", "--candidate", "cm", "--pollutant", "PM2.5"]
SENSOR_ARGS = ["--reference", "ref", "--sensors", "s1", "s2", "s3"]


@pytest.fixture
def pm_csv(tmp_path):
    path = tmp_path / "pm.csv"
    aq.load_example("pm25_locA_cm1").to_csv(path, index=False)
    return path


@pytest.fixture
def sensor_frame():
    rng = np.random.default_rng(0)
    frames = []
    for site in ("A", "B"):
        true = rng.gamma(3.0, 7.0, 90)
        shared = rng.normal(0, 2.5, 90)
        frame = pd.DataFrame({"site": site, "ref": true + rng.normal(0, 0.5, 90)})
        for name in ("s1", "s2", "s3"):
            frame[name] = 1.5 + 1.26 * true + shared + rng.normal(0, 1.0, 90)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_pm_prints_the_report(pm_csv, capsys):
    assert main(["pm", str(pm_csv), *PM_ARGS]) == 0
    data = aq.load_example("pm25_locA_cm1")
    assert capsys.readouterr().out.strip() == str(aq.evaluate_pm(data, ["rm1", "rm2"], "cm", "PM2.5"))


def test_check_sets_the_exit_status(pm_csv):
    assert not aq.evaluate_pm(aq.load_example("pm25_locA_cm1"), ["rm1", "rm2"], "cm", "PM2.5").passed
    assert main(["pm", str(pm_csv), *PM_ARGS, "--quiet"]) == 0
    assert main(["pm", str(pm_csv), *PM_ARGS, "--quiet", "--check"]) == 1


def test_outputs_are_written(pm_csv, tmp_path):
    html, png = tmp_path / "r.html", tmp_path / "r.png"
    code = main(["pm", str(pm_csv), *PM_ARGS, "--calibration", "auto", "--html", str(html), "--plot", str(png),
                 "--quiet"])
    assert code == 0
    page = html.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and "data:image/png;base64," in page
    assert "pm.csv" in page
    assert "http" not in page  # self-contained: no external resources
    assert png.stat().st_size > 1000


def test_missing_column_is_explained(pm_csv, capsys):
    assert main(["pm", str(pm_csv), "--reference", "rm1", "--candidate", "nope"]) == 2
    err = capsys.readouterr().err
    assert "nope" in err and "rm1, rm2, cm" in err


def test_semicolon_and_decimal_comma_are_detected(sensor_frame, tmp_path, capsys):
    path = tmp_path / "s.csv"
    sensor_frame.to_csv(path, index=False, sep=";", decimal=",")
    args = ["sensor", str(path), *SENSOR_ARGS, "--site", "site", "--rh-factor", "1.3"]
    assert main(args) == 0
    expected = aq.evaluate_sensor(sensor_frame, "ref", ["s1", "s2", "s3"], site="site", rh_factor=1.3)
    assert expected.sensor_class == 2
    assert "Result: Class 2" in capsys.readouterr().out
    assert main([*args, "--quiet", "--check"]) == 0
    assert main([*args, "--quiet", "--check", "--required-class", "1"]) == 1


def test_gas_without_u_ref_is_an_error(sensor_frame, tmp_path, capsys):
    path = tmp_path / "s.csv"
    sensor_frame.to_csv(path, index=False)
    assert main(["sensor", str(path), *SENSOR_ARGS, "--pollutant", "NO2"]) == 2
    assert "u_ref" in capsys.readouterr().err


def test_objectives_2030(pm_csv, capsys):
    assert main(["pm", str(pm_csv), *PM_ARGS, "--objectives", "2030"]) == 0
    assert "evaluated at 25 µg/m³" in capsys.readouterr().out


def test_ongoing(tmp_path, capsys):
    rng = np.random.default_rng(1)
    frames = []
    for site in ("A", "B"):
        for year in (2023, 2024, 2025):
            true = rng.gamma(3.0, 9.0, 95)
            frames.append(pd.DataFrame({"site": site, "year": year, "rm": true + rng.normal(0, 0.7, 95),
                                        "ams": 1.03 * true + rng.normal(0, 1.5, 95)}))
    path, html = tmp_path / "o.csv", tmp_path / "o.html"
    pd.concat(frames).to_csv(path, index=False)
    code = main(["ongoing", str(path), "--reference", "rm", "--candidate", "ams", "--site", "site",
                 "--period", "year", "--network-sites", "30", "--html", str(html), "--check"])
    assert code == 0
    assert "Sites to compare with the reference method next year: 2" in capsys.readouterr().out
    assert "ongoing verification" in html.read_text(encoding="utf-8")


def test_example_command(tmp_path, capsys):
    assert main(["example"]) == 0
    assert "pm10_locC_cm1" in capsys.readouterr().out
    out = tmp_path / "e.csv"
    assert main(["example", "pm10_locC_cm1", "-o", str(out)]) == 0
    pd.testing.assert_frame_equal(pd.read_csv(out), aq.load_example("pm10_locC_cm1"))
    assert main(["example", "nope"]) == 2


def test_to_html_escapes_and_returns_the_page(sensor_frame):
    result = aq.evaluate_sensor(sensor_frame, "ref", ["s1", "s2", "s3"], site="site")
    page = result.to_html(title="Test <1>", source="a&b.csv")
    assert "Test &lt;1&gt;" in page and "a&amp;b.csv" in page and "Modified Target Diagram" in page
    with pytest.raises(TypeError):
        aq.to_html("not a result")
