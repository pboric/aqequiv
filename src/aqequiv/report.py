"""Self-contained HTML reports of the evaluations."""

from __future__ import annotations

import base64
import datetime as _dt
import html
import io
from pathlib import Path

import pandas as pd

_HEADERS = {
    "n": "n",
    "u_slope": "u(slope)",
    "u_intercept": "u(intercept)",
    "r2": "R²",
    "random": "random term",
    "u_c": "u<sub>c</sub>",
    "W_pct": "W, %",
    "u_bs": "u<sub>bs</sub>",
    "capture_pct": "data capture, %",
    "U_LV": "U at LV",
    "U_UAT": "U at UAT",
    "U_LAT": "U at LAT",
    "limited_by": "limited by",
    "best_class": "best class",
    "passed": "result",
}

_CSS = """
:root { --ink:#1a1f24; --muted:#5b6670; --line:#d9dee3; --bg:#ffffff; --band:#f4f6f8;
        --good:#1b7f4b; --good-bg:#e6f4ec; --bad:#b3261e; --bad-bg:#fbeae8; --warn:#8a5a00; --warn-bg:#fdf3dc; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
main { max-width:980px; margin:0 auto; padding:32px 16px 48px; }
h1 { font-size:26px; line-height:1.2; margin:0 0 4px; }
h2 { font-size:17px; margin:32px 0 8px; }
p { margin:4px 0; }
.sub { color:var(--muted); }
.verdict { display:flex; flex-wrap:wrap; gap:12px; margin:20px 0 8px; }
.tile { flex:1 1 220px; border-radius:8px; padding:12px 16px; background:var(--band); }
.tile .k { font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
.tile .v { font-size:22px; font-weight:650; }
.tile.good { background:var(--good-bg); } .tile.good .v { color:var(--good); }
.tile.bad { background:var(--bad-bg); } .tile.bad .v { color:var(--bad); }
.tile.warn { background:var(--warn-bg); } .tile.warn .v { color:var(--warn); }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; font-size:14px; }
th, td { padding:6px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
th { font-weight:600; color:var(--muted); border-bottom:2px solid var(--line); }
th.t, td.t { text-align:left; }
.ok { color:var(--good); font-weight:600; } .no { color:var(--bad); font-weight:600; }
ul { margin:4px 0; padding-left:20px; }
figure { margin:12px 0; } figure img { max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
figcaption { color:var(--muted); font-size:13px; }
footer { margin-top:40px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }
@media print { main { padding:0; max-width:none; } h2 { break-after:avoid; } figure, table { break-inside:avoid; } }
"""


def _number(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if pd.isna(value):
            return "–"
        if value == int(value) and abs(value) >= 1000:
            return f"{value:.0f}"
        return f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
    return html.escape(str(value))


def _table(frame: pd.DataFrame) -> str:
    text = [c for c in frame.columns if not pd.api.types.is_numeric_dtype(frame[c]) or frame[c].dtype == bool]
    head = "".join(
        f'<th class="t">{_HEADERS.get(c, html.escape(str(c)))}</th>'
        if c in text
        else f"<th>{_HEADERS.get(c, html.escape(str(c)))}</th>"
        for c in frame.columns
    )
    rows = []
    for record in frame.itertuples(index=False):
        cells = []
        for column, value in zip(frame.columns, record):
            if column == "passed":
                ok = bool(value)
                cells.append(f'<td class="t {"ok" if ok else "no"}">{"✓ pass" if ok else "✗ fail"}</td>')
            elif column in text:
                cells.append(f'<td class="t">{html.escape(str(value))}</td>')
            else:
                value = value.item() if hasattr(value, "item") else value
                cells.append(f"<td>{_number(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _figure(fig, caption: str) -> str:
    import matplotlib.pyplot as plt

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        f'<figure><img alt="{html.escape(caption)}" src="data:image/png;base64,{data}">'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
    )


def _tile(label: str, value: str, state: str = "") -> str:
    return f'<div class="tile {state}"><div class="k">{html.escape(label)}</div><div class="v">{html.escape(value)}</div></div>'


def _dataset_tile(suitable: bool) -> str:
    return _tile("Dataset requirements", "✓ met" if suitable else "! not met", "good" if suitable else "warn")


def _pm_parts(result):
    c = result.criteria
    cal = f"calibrated, {result.calibration}" if result.calibration else "uncalibrated"
    worst = float(result.comparisons["W_pct"].max())
    return {
        "title": f"{c.pollutant} equivalence test",
        "basis": "Guide to the Demonstration of Equivalence of Ambient Air Monitoring Methods (2010); EN 16450:2017",
        "intro": [
            f"Candidate results: {cal}.",
            f"Uncertainty evaluated at {c.limit_value:g} µg/m³. Objective: expanded uncertainty of at most "
            f"{c.max_uncertainty:g} µg/m³ ({100 * c.max_uncertainty / c.limit_value:.1f} %).",
            f"Reference uncertainty {result.u_ref:.2f} µg/m³ ({result.u_ref_source}).",
        ],
        "tiles": [
            _tile("Uncertainty criteria", "✓ pass" if result.passed else "✗ fail", "good" if result.passed else "bad"),
            _tile("Highest expanded uncertainty", f"{worst:.1f} %"),
            _dataset_tile(result.dataset_suitable),
        ],
        "tables": [
            ("Comparison with the reference method", result.comparisons),
            ("Between-sampler uncertainty", result.between_sampler),
            ("Dataset suitability", result.dataset_checks),
        ],
        "notes": list(result.notes),
        "figures": [(result.plot, "Candidate against the reference method")],
    }


def _ongoing_parts(result):
    from .pm import ONGOING_MIN_PAIRS

    parts = _pm_parts(result.equivalence)
    parts["title"] = f"{result.equivalence.criteria.pollutant} ongoing verification of equivalence"
    parts["basis"] = "EN 16450:2017, clause 8.6"
    if result.action_required:
        action = _tile("Next year", "✗ corrective action", "bad")
    else:
        action = _tile("Sites to compare next year", str(result.sites_required), "good")
    parts["tiles"] = [_tile("Expanded uncertainty", f"{result.w_pct:.1f} %"), action, parts["tiles"][2]]
    parts["tables"].append((f"Valid pairs per site and period (at least {ONGOING_MIN_PAIRS})", result.pairs))
    return parts


def _sensor_parts(result):
    c = result.criteria
    cor = f"corrected, {result.correction}" if result.correction else "uncorrected"
    cls = result.sensor_class
    part = "2: Particulate matter" if c.period == "day" else "1: Gaseous pollutants"
    return {
        "title": f"{c.pollutant} sensor system classification",
        "basis": f"CEN/TS 17660-{part} (field test)",
        "intro": [
            f"Sensor results: {cor}.",
            f"Limit value {c.limit_value:g} {c.unit}. Maximum expanded uncertainty "
            f"{' / '.join(f'{d:g}' for d in c.dqo)} {c.unit} for Class 1 / 2 / 3.",
            f"Reference between-sampler uncertainty {result.u_ref:.2f} {c.unit}.",
        ],
        "tiles": [
            _tile(
                "Result",
                f"Class {cls}" if cls else "✗ not classified",
                {1: "good", 2: "good", 3: "warn"}.get(cls, "bad"),
            ),
            _dataset_tile(result.dataset_suitable),
        ],
        "tables": [
            (f"Field test, per site and sensor system (U = expanded uncertainty, {c.unit})", result.datasets),
            ("Between-sensor-system uncertainty", result.between_sensor),
            ("Other tests", result.other_tests),
            ("Dataset requirements", result.dataset_checks),
        ],
        "notes": list(result.notes),
        "figures": [
            (result.plot, "Sensor systems against the reference method"),
            (result.target_diagram, "Modified Target Diagram (Yatkin et al., 2022)"),
        ],
    }


def to_html(result, path=None, *, title: str | None = None, source: str | None = None) -> str:
    """Render an evaluation as one self-contained HTML page.

    Parameters
    ----------
    result
        What :func:`evaluate_pm`, :func:`verify_ongoing` or
        :func:`evaluate_sensor` returned.
    path
        Where to write the page. The HTML is returned either way.
    title
        Heading of the report; a description of the test by default.
    source
        Name of the data, shown under the heading (for example a file name).
    """
    from . import __version__
    from .pm import OngoingVerification, PMEquivalence
    from .sensors import SensorClassification

    if isinstance(result, OngoingVerification):
        parts = _ongoing_parts(result)
    elif isinstance(result, PMEquivalence):
        parts = _pm_parts(result)
    elif isinstance(result, SensorClassification):
        parts = _sensor_parts(result)
    else:
        raise TypeError(f"cannot make a report from {type(result).__name__}")

    heading = title or parts["title"]
    body = [f"<h1>{html.escape(heading)}</h1>"]
    if title:
        body.append(f'<p class="sub">{html.escape(parts["title"])}</p>')
    if source:
        body.append(f'<p class="sub">Data: {html.escape(source)}</p>')
    body.append(f'<div class="verdict">{"".join(parts["tiles"])}</div>')
    body += [f"<p>{html.escape(line)}</p>" for line in parts["intro"]]
    for name, frame in parts["tables"]:
        if len(frame):
            body.append(f"<h2>{html.escape(name)}</h2>{_table(frame)}")
    if parts["notes"]:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in parts["notes"])
        body.append(f"<h2>Notes</h2><ul>{items}</ul>")
    body.append("<h2>Figures</h2>")
    body += [_figure(make(), caption) for make, caption in parts["figures"]]
    body.append(
        f"<footer>Calculated with aqequiv {__version__} on {_dt.date.today().isoformat()}, "
        f"following {html.escape(parts['basis'])}. This page reports a calculation; it is not a test report "
        "of an accredited laboratory.</footer>"
    )
    page = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(heading)}</title><style>{_CSS}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )
    if path is not None:
        Path(path).write_text(page, encoding="utf-8")
    return page
