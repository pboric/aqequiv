"""Command-line interface: ``aqequiv pm | sensor | ongoing | example``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import __version__


class CliError(Exception):
    """A problem with the input that the user can fix."""


def _read(path: str, sep: str | None, decimal: str | None) -> pd.DataFrame:
    """Read a CSV file, working out separator and decimal mark if not given."""
    file = Path(path)
    if not file.exists():
        raise CliError(f"file not found: {path}")
    if file.suffix.lower() in (".xlsx", ".xls"):
        try:
            return pd.read_excel(file)
        except ImportError:
            raise CliError("reading Excel files needs openpyxl; save the sheet as CSV instead") from None
    if sep is None:
        with file.open(encoding="utf-8-sig") as handle:
            head = handle.readline()
        sep = max(";\t,", key=head.count)
    if decimal is None:
        decimal = "," if sep != "," else "."
        frame = pd.read_csv(file, sep=sep, decimal=decimal, encoding="utf-8-sig")
        if decimal == "," and not any(pd.api.types.is_float_dtype(t) for t in frame.dtypes):
            frame = pd.read_csv(file, sep=sep, decimal=".", encoding="utf-8-sig")
        return frame
    return pd.read_csv(file, sep=sep, decimal=decimal, encoding="utf-8-sig")


def _columns(frame: pd.DataFrame, *names) -> None:
    missing = [n for group in names if group for n in ([group] if isinstance(group, str) else group) if n not in frame]
    if missing:
        raise CliError(
            f"column(s) not in the file: {', '.join(missing)}. Columns found: {', '.join(map(str, frame.columns))}"
        )


def _pm_criteria(pollutant: str, objectives: str):
    from . import pm

    if objectives == "2008":
        return None
    key = pollutant.upper().replace(",", ".")
    try:
        return {"PM10": pm.PM10_2030, "PM2.5": pm.PM25_2030, "PM25": pm.PM25_2030}[key]
    except KeyError:
        raise CliError(f"unknown pollutant {pollutant!r}; use PM10 or PM2.5") from None


def _sensor_criteria(pollutant: str, objectives: str):
    from . import sensors

    if objectives == "2008":
        return None
    key = pollutant.upper().replace(",", ".")
    table = {"PM10": sensors.SENSOR_PM10_2030, "PM2.5": sensors.SENSOR_PM25_2030, "PM25": sensors.SENSOR_PM25_2030}
    if key not in table:
        raise CliError("--objectives 2030 is available for PM10 and PM2.5 only")
    return table[key]


def _run_pm(args):
    from .pm import evaluate_pm

    data = _read(args.file, args.sep, args.decimal)
    _columns(data, args.reference, args.candidate, args.site)
    return evaluate_pm(
        data, args.reference, args.candidate, args.pollutant, site=args.site, u_ref=args.u_ref,
        calibration=args.calibration, standard=args.standard, applied_calibration=args.applied_calibration,
        criteria=_pm_criteria(args.pollutant, args.objectives),
    ), lambda r: r.passed


def _run_ongoing(args):
    from .pm import verify_ongoing

    data = _read(args.file, args.sep, args.decimal)
    _columns(data, args.reference, args.candidate, args.site, args.period)
    return verify_ongoing(
        data, args.reference, args.candidate, args.pollutant, site=args.site, period=args.period,
        applied_calibration=args.applied_calibration, n_network_sites=args.network_sites, u_ref=args.u_ref,
        criteria=_pm_criteria(args.pollutant, args.objectives),
    ), lambda r: not r.action_required


def _run_sensor(args):
    from .sensors import evaluate_sensor

    data = _read(args.file, args.sep, args.decimal)
    _columns(data, args.reference, args.sensors, args.site)
    return evaluate_sensor(
        data, args.reference, args.sensors, args.pollutant, site=args.site, u_ref=args.u_ref,
        correction=args.correction, rh_factor=args.rh_factor, lab_factor=args.lab_factor,
        criteria=_sensor_criteria(args.pollutant, args.objectives),
    ), lambda r: r.sensor_class is not None and r.sensor_class <= args.required_class


def _run_example(args) -> int:
    from .datasets import EXAMPLES, load_example

    if args.name is None:
        for name, text in EXAMPLES.items():
            print(f"{name:16}{text}")
        return 0
    if args.name not in EXAMPLES:
        raise CliError(f"unknown example {args.name!r}; run 'aqequiv example' for the list")
    frame = load_example(args.name)
    if args.output:
        frame.to_csv(args.output, index=False)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        frame.to_csv(sys.stdout, index=False)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aqequiv",
        description="Equivalence testing and sensor classification for ambient air quality measurements.",
    )
    parser.add_argument("--version", action="version", version=f"aqequiv {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def common(sub, *, objectives=True):
        sub.add_argument("file", help="CSV (or Excel) file, one row per averaging period")
        sub.add_argument("--site", metavar="COLUMN", help="column naming the site or comparison")
        sub.add_argument("--u-ref", type=float, metavar="VALUE", help="uncertainty of the reference results")
        if objectives:
            sub.add_argument(
                "--objectives", choices=("2008", "2030"), default="2008",
                help="data quality objectives: Directive 2008/50/EC (default) or (EU) 2024/2881",
            )
        out = sub.add_argument_group("output")
        out.add_argument("--html", metavar="FILE", help="write a self-contained HTML report")
        out.add_argument("--plot", metavar="FILE", help="save the scatter plot (png, svg or pdf)")
        out.add_argument("--quiet", action="store_true", help="do not print the text report")
        out.add_argument("--check", action="store_true", help="exit with status 1 if the criteria are not met")
        fmt = sub.add_argument_group("file format")
        fmt.add_argument("--sep", help="column separator (detected by default)")
        fmt.add_argument("--decimal", choices=(".", ","), help="decimal mark (detected by default)")

    pm = commands.add_parser("pm", help="equivalence of a candidate PM method with the reference method")
    pm.add_argument("--reference", nargs="+", required=True, metavar="COLUMN", help="one or two reference columns")
    pm.add_argument("--candidate", nargs="+", required=True, metavar="COLUMN", help="one or two candidate columns")
    pm.add_argument("--pollutant", default="PM10", help="PM10 (default) or PM2.5")
    pm.add_argument("--calibration", choices=("none", "auto", "intercept", "slope", "both"), default="none")
    pm.add_argument("--applied-calibration", choices=("none", "intercept", "slope", "both"), default="none",
                    help="calibration already applied to the candidate results")
    pm.add_argument("--standard", choices=("guide", "en16450"), default="guide")
    common(pm)
    pm.set_defaults(run=_run_pm)

    ongoing = commands.add_parser("ongoing", help="yearly ongoing verification of equivalence (EN 16450)")
    ongoing.add_argument("--reference", nargs="+", required=True, metavar="COLUMN")
    ongoing.add_argument("--candidate", nargs="+", required=True, metavar="COLUMN")
    ongoing.add_argument("--pollutant", default="PM10", help="PM10 (default) or PM2.5")
    ongoing.add_argument("--period", metavar="COLUMN", help="column with the year")
    ongoing.add_argument("--applied-calibration", choices=("none", "intercept", "slope", "both"), default="none")
    ongoing.add_argument("--network-sites", type=int, metavar="N", help="sites operating this instrument type")
    common(ongoing)
    ongoing.set_defaults(run=_run_ongoing)

    sensor = commands.add_parser("sensor", help="classification of a sensor system (CEN/TS 17660)")
    sensor.add_argument("--reference", required=True, metavar="COLUMN")
    sensor.add_argument("--sensors", nargs="+", required=True, metavar="COLUMN", help="replicate sensor systems")
    sensor.add_argument("--pollutant", default="PM2.5", help="PM2.5 (default), PM10, NO2, NO, O3, SO2, CO or benzene")
    sensor.add_argument("--correction", choices=("none", "intercept", "slope", "both"), default="none")
    sensor.add_argument("--rh-factor", type=float, metavar="VALUE", help="humidity factor (PM)")
    sensor.add_argument("--lab-factor", type=float, metavar="VALUE", help="laboratory fine/coarse factor (PM10)")
    sensor.add_argument("--target-diagram", metavar="FILE", help="save the Modified Target Diagram")
    sensor.add_argument("--required-class", type=int, choices=(1, 2, 3), default=3,
                        help="class that --check requires (default 3)")
    common(sensor)
    sensor.set_defaults(run=_run_sensor)

    example = commands.add_parser("example", help="list or export the example datasets of the Guide")
    example.add_argument("name", nargs="?", help="name of the example; omit to list them")
    example.add_argument("-o", "--output", metavar="FILE", help="write the CSV here instead of the terminal")
    example.set_defaults(run=None)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "example":
            return _run_example(args)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        result, passed = args.run(args)
        if not args.quiet:
            print(result)
        if args.plot:
            fig = result.equivalence.plot() if args.command == "ongoing" else result.plot()
            fig.savefig(args.plot, dpi=130, bbox_inches="tight")
            plt.close(fig)
            print(f"wrote {args.plot}", file=sys.stderr)
        if getattr(args, "target_diagram", None):
            fig = result.target_diagram()
            fig.savefig(args.target_diagram, dpi=130, bbox_inches="tight")
            plt.close(fig)
            print(f"wrote {args.target_diagram}", file=sys.stderr)
        if args.html:
            result.to_html(args.html, source=Path(args.file).name)
            print(f"wrote {args.html}", file=sys.stderr)
        return 1 if args.check and not passed(result) else 0
    except (CliError, ValueError) as error:
        print(f"aqequiv: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
