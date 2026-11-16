"""Desktop application: the evaluation behind the window, and the window itself."""

import numpy as np
import pandas as pd
import pytest

import aqequiv as aq
from aqequiv import app
from aqequiv.app import EQUIVALENCE, ONGOING, SENSOR, Settings, evaluate
from aqequiv.cli import CliError


@pytest.fixture
def sensor_frame():
    rng = np.random.default_rng(0)
    frames = []
    for site in ("A", "B"):
        true = rng.gamma(3.0, 7.0, 90)
        frame = pd.DataFrame({"site": site, "ref": true + rng.normal(0, 0.5, 90)})
        for name in ("s1", "s2", "s3"):
            frame[name] = 1.5 + 1.26 * true + rng.normal(0, 2.0, 90)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_evaluate_matches_the_python_functions(sensor_frame):
    settings = Settings(SENSOR, "PM2.5", ["ref"], ["s1", "s2", "s3"], site="site", adjustment="both", rh_factor=1.3)
    expected = aq.evaluate_sensor(sensor_frame, "ref", ["s1", "s2", "s3"], site="site", correction="both", rh_factor=1.3)
    assert str(evaluate(sensor_frame, settings)) == str(expected)

    data = aq.load_example("pm25_locA_cm1")
    settings = Settings(EQUIVALENCE, "PM2.5", ["rm1", "rm2"], ["cm"], adjustment="auto", standard="en16450")
    expected = aq.evaluate_pm(data, ["rm1", "rm2"], ["cm"], "PM2.5", calibration="auto", standard="en16450")
    assert str(evaluate(data, settings)) == str(expected)

    settings = Settings(ONGOING, "PM2.5", ["rm1"], ["cm"], network_sites=30)
    expected = aq.verify_ongoing(data, ["rm1"], ["cm"], "PM2.5", n_network_sites=30)
    assert str(evaluate(data, settings)) == str(expected)


def test_objectives_2030(sensor_frame):
    result = evaluate(sensor_frame, Settings(SENSOR, "PM2.5", ["ref"], ["s1", "s2", "s3"], objectives="2030"))
    assert result.criteria is aq.SENSOR_PM25_2030


@pytest.mark.parametrize(
    "settings, message",
    [
        (Settings(SENSOR, "PM2.5", [], ["s1"]), "reference column"),
        (Settings(SENSOR, "PM2.5", ["ref"], []), "sensor columns"),
        (Settings(SENSOR, "PM2.5", ["ref"], ["ref", "s1"]), "both"),
        (Settings(SENSOR, "PM2.5", ["ref", "s1"], ["s2"]), "one reference column"),
        (Settings(SENSOR, "PM2.5", ["ref"], ["site"]), "text instead of numbers"),
        (Settings(EQUIVALENCE, "PM10", ["ref"], ["s1", "s2", "s3"]), "one or two"),
        (Settings(SENSOR, "NO2", ["ref"], ["s1", "s2", "s3"], objectives="2030"), "PM10 and PM2.5 only"),
    ],
)
def test_mistakes_are_explained(sensor_frame, settings, message):
    with pytest.raises(CliError, match=message):
        evaluate(sensor_frame, settings)


def test_gas_needs_reference_uncertainty(sensor_frame):
    with pytest.raises(ValueError, match="u_ref"):
        evaluate(sensor_frame, Settings(SENSOR, "NO2", ["ref"], ["s1", "s2", "s3"]))


def test_typed_numbers():
    assert app._number(" 1,3 ", "x") == 1.3
    assert app._number("", "x") is None
    assert app._number("30", "x", int) == 30
    with pytest.raises(CliError, match="Humidity factor"):
        app._number("abc", "Humidity factor")


def test_selftest_writes_a_report(tmp_path):
    out = tmp_path / "selftest.html"
    assert app.main(["--selftest", str(out)]) == 0
    assert "PM2.5 equivalence test" in out.read_text(encoding="utf-8")


@pytest.fixture
def window():
    tk = pytest.importorskip("tkinter")
    try:
        win = app.build_window()
    except tk.TclError:
        pytest.skip("no display")
    win.withdraw()
    yield win
    win.destroy()


def test_window_runs_a_sensor_evaluation(window, sensor_frame, tmp_path, monkeypatch):
    path = tmp_path / "daily.csv"
    sensor_frame.to_csv(path, index=False, sep=";", decimal=",")
    window.open_file(str(path))
    assert window.reference.get(0, "end") == ("ref", "s1", "s2", "s3")  # numeric columns only
    assert "site" in window.site.cget("values")

    window.reference.selection_set(0)
    window.tested.selection_set(1, 3)
    window.site.set("site")
    window.adjustment.set("both")
    window.entries["rh_factor"][1].insert(0, "1,3")
    window.run()
    expected = aq.evaluate_sensor(sensor_frame, "ref", ["s1", "s2", "s3"], site="site", correction="both", rh_factor=1.3)
    assert window.text.get("1.0", "end").strip() == str(expected)
    assert str(window.save_button.cget("state")) == "normal"

    out = tmp_path / "report.html"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **_: str(out))
    window.save_report()
    assert "sensor system classification" in out.read_text(encoding="utf-8")


def test_window_switches_fields_with_the_evaluation(window):
    def state(widget):
        return str(widget.cget("state"))

    assert state(window.period) == "disabled" and state(window.entries["rh_factor"][1]) == "normal"
    window.pollutant.set("NO2")
    window._pollutant_changed()
    assert state(window.entries["rh_factor"][1]) == "disabled" and state(window.objectives) == "disabled"
    assert window.entries["u_ref"][0].cget("text").endswith("*")

    window.kind.set(ONGOING)
    window._kind_changed()
    assert window.pollutant.get() == "PM10"
    assert state(window.period) == "readonly" and state(window.entries["network_sites"][1]) == "normal"
    assert window.adjustment_label.cget("text") == "Calibration already applied"

    window.kind.set(EQUIVALENCE)
    window._kind_changed()
    assert state(window.standard) == "readonly" and "auto" in window.adjustment.cget("values")
