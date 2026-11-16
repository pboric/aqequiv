"""Desktop application: pick a file, pick the columns, get the report.

Start it with ``aqequiv-app`` or ``python -m aqequiv.app``. The Windows
download is this module packed into one ``.exe``.
"""

from __future__ import annotations

import sys
import tempfile
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import __version__
from .cli import CliError, _pm_criteria, _read, _sensor_criteria

NONE = "(none)"
SENSOR, EQUIVALENCE, ONGOING = "sensor", "pm", "ongoing"

KINDS = {
    SENSOR: "Sensor classification (CEN/TS 17660)",
    EQUIVALENCE: "Equivalence of a PM instrument (Guide 2010 / EN 16450)",
    ONGOING: "Ongoing verification of a PM instrument (EN 16450)",
}
POLLUTANTS = {
    SENSOR: ["PM2.5", "PM10", "NO2", "NO", "O3", "SO2", "CO", "benzene"],
    EQUIVALENCE: ["PM10", "PM2.5"],
    ONGOING: ["PM10", "PM2.5"],
}
ADJUSTMENTS = {
    SENSOR: ["none", "intercept", "slope", "both"],
    EQUIVALENCE: ["none", "auto", "intercept", "slope", "both"],
    ONGOING: ["none", "intercept", "slope", "both"],
}
ADJUSTMENT_LABEL = {
    SENSOR: "Correction to apply",
    EQUIVALENCE: "Calibration to apply",
    ONGOING: "Calibration already applied",
}
TESTED_LABEL = {SENSOR: "Sensor columns", EQUIVALENCE: "Candidate column(s)", ONGOING: "Candidate column(s)"}


@dataclass
class Settings:
    """Everything the window collects before an evaluation."""

    kind: str = SENSOR
    pollutant: str = "PM2.5"
    reference: list[str] = field(default_factory=list)
    tested: list[str] = field(default_factory=list)  # sensor systems or candidate instruments
    site: str | None = None
    period: str | None = None  # column with the year (ongoing verification)
    adjustment: str = "none"  # correction or calibration
    objectives: str = "2008"
    standard: str = "guide"
    u_ref: float | None = None
    rh_factor: float | None = None
    lab_factor: float | None = None
    network_sites: int | None = None


def _number(text: str, name: str, kind=float):
    """Read an optional number typed by the user; a decimal comma is accepted."""
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return kind(text)
    except ValueError:
        raise CliError(f"{name}: {text!r} is not a number") from None


def evaluate(data: pd.DataFrame, s: Settings):
    """Run the evaluation the settings describe and return its result."""
    from .pm import evaluate_pm, verify_ongoing
    from .sensors import evaluate_sensor

    if not s.reference:
        raise CliError("choose the reference column")
    if not s.tested:
        raise CliError(f"choose the {TESTED_LABEL[s.kind].lower()}")
    if set(s.reference) & set(s.tested):
        raise CliError("a column cannot be both the reference and the instrument under test")
    used = s.reference + s.tested
    text = [c for c in used if not pd.api.types.is_numeric_dtype(data[c])]
    if text:
        raise CliError(f"column(s) with text instead of numbers: {', '.join(text)}")

    if s.kind == SENSOR:
        if len(s.reference) != 1:
            raise CliError("sensor classification takes one reference column")
        return evaluate_sensor(
            data, s.reference[0], s.tested, s.pollutant, site=s.site, u_ref=s.u_ref,
            correction=s.adjustment, rh_factor=s.rh_factor, lab_factor=s.lab_factor,
            criteria=_sensor_criteria(s.pollutant, s.objectives),
        )
    if len(s.reference) > 2 or len(s.tested) > 2:
        raise CliError("choose one or two reference columns and one or two candidate columns")
    criteria = _pm_criteria(s.pollutant, s.objectives)
    if s.kind == EQUIVALENCE:
        return evaluate_pm(
            data, s.reference, s.tested, s.pollutant, site=s.site, u_ref=s.u_ref,
            calibration=s.adjustment, standard=s.standard, criteria=criteria,
        )
    return verify_ongoing(
        data, s.reference, s.tested, s.pollutant, site=s.site, period=s.period,
        applied_calibration=s.adjustment, n_network_sites=s.network_sites, u_ref=s.u_ref, criteria=criteria,
    )


def _selftest(path: str) -> int:
    """Evaluate a bundled example and write its report; used to check the packed app."""
    from .datasets import load_example

    data = load_example("pm25_locA_cm1")
    try:  # through an Excel file, if the Excel reader is installed
        sheet = Path(tempfile.mkdtemp(prefix="aqequiv-")) / "selftest.xlsx"
        data.to_excel(sheet, index=False)
        data, excel = _read(str(sheet), None, None), "Excel ok"
    except (ImportError, CliError):
        excel = "Excel not available"
    settings = Settings(EQUIVALENCE, "PM2.5", ["rm1", "rm2"], ["cm"], adjustment="auto")
    evaluate(data, settings).to_html(path, source=f"pm25_locA_cm1 (self-test, {excel})")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--selftest"] and len(argv) == 2:
        import matplotlib

        matplotlib.use("Agg")
        return _selftest(argv[1])
    if argv[:1] == ["--version"]:
        print(f"aqequiv {__version__}")
        return 0
    import matplotlib

    matplotlib.use("Agg")  # figures go into the report, never into a window
    build_window().mainloop()
    return 0


def build_window():
    """Create the application window (imports tkinter only when a window is wanted)."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    if sys.platform == "win32":  # sharp text on high-resolution screens
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title(f"aqequiv {__version__}")
            self.minsize(900, 640)
            if sys.platform not in ("win32", "darwin"):  # those two have a native look already
                ttk.Style(self).theme_use("clam")
            self.data: pd.DataFrame | None = None
            self.result = None
            self.source = ""
            self._build()
            self._kind_changed()

        # --- layout -----------------------------------------------------------
        def _build(self):
            pad = {"padx": 8, "pady": 4}
            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            self.rowconfigure(0, weight=1)
            left = ttk.Frame(self, padding=8)
            left.grid(row=0, column=0, sticky="ns")
            right = ttk.Frame(self, padding=(0, 8, 8, 8))
            right.grid(row=0, column=1, sticky="nsew")
            right.rowconfigure(1, weight=1)
            right.columnconfigure(0, weight=1)

            # 1. data
            box = ttk.LabelFrame(left, text="1. Data", padding=6)
            box.pack(fill="x", **pad)
            ttk.Button(box, text="Open file…", command=self.open_file).pack(side="left")
            self.file_label = ttk.Label(box, text="CSV or Excel, one row per day (or hour)", width=44)
            self.file_label.pack(side="left", padx=8)

            # 2. evaluation
            box = ttk.LabelFrame(left, text="2. Evaluation", padding=6)
            box.pack(fill="x", **pad)
            self.kind = tk.StringVar(value=SENSOR)
            for key, text in KINDS.items():
                ttk.Radiobutton(box, text=text, value=key, variable=self.kind, command=self._kind_changed).pack(anchor="w")
            row = ttk.Frame(box)
            row.pack(fill="x", pady=(6, 0))
            ttk.Label(row, text="Pollutant").pack(side="left")
            self.pollutant = ttk.Combobox(row, state="readonly", width=10)
            self.pollutant.pack(side="left", padx=8)
            self.pollutant.bind("<<ComboboxSelected>>", lambda _: self._pollutant_changed())

            # 3. columns
            box = ttk.LabelFrame(left, text="3. Columns", padding=6)
            box.pack(fill="x", **pad)
            lists = ttk.Frame(box)
            lists.pack(fill="x")
            self.reference_label = ttk.Label(lists, text="Reference column(s)")
            self.reference_label.grid(row=0, column=0, sticky="w")
            self.tested_label = ttk.Label(lists, text="Sensor columns")
            self.tested_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
            self.reference = tk.Listbox(lists, selectmode="extended", exportselection=False, height=7, width=24)
            self.reference.grid(row=1, column=0)
            self.tested = tk.Listbox(lists, selectmode="extended", exportselection=False, height=7, width=24)
            self.tested.grid(row=1, column=1, padx=(8, 0))
            ttk.Label(lists, text="Ctrl+click selects several columns", foreground="#666").grid(
                row=2, column=0, columnspan=2, sticky="w"
            )
            grid = ttk.Frame(box)
            grid.pack(fill="x", pady=(6, 0))
            ttk.Label(grid, text="Site column").grid(row=0, column=0, sticky="w")
            self.site = ttk.Combobox(grid, state="readonly", width=22, values=[NONE])
            self.site.set(NONE)
            self.site.grid(row=0, column=1, padx=8, pady=2)
            self.period_label = ttk.Label(grid, text="Year column")
            self.period_label.grid(row=1, column=0, sticky="w")
            self.period = ttk.Combobox(grid, state="readonly", width=22, values=[NONE])
            self.period.set(NONE)
            self.period.grid(row=1, column=1, padx=8, pady=2)

            # 4. options
            box = ttk.LabelFrame(left, text="4. Options", padding=6)
            box.pack(fill="x", **pad)
            self.adjustment_label = ttk.Label(box, text="Correction to apply")
            self.adjustment_label.grid(row=0, column=0, sticky="w")
            self.adjustment = ttk.Combobox(box, state="readonly", width=12)
            self.adjustment.grid(row=0, column=1, padx=8, pady=2, sticky="w")
            ttk.Label(box, text="Objectives").grid(row=1, column=0, sticky="w")
            self.objectives = ttk.Combobox(
                box, state="readonly", width=34,
                values=["2008 - Directive 2008/50/EC", "2030 - Directive (EU) 2024/2881"],
            )
            self.objectives.current(0)
            self.objectives.grid(row=1, column=1, padx=8, pady=2, sticky="w")
            self.standard_label = ttk.Label(box, text="Procedure")
            self.standard_label.grid(row=2, column=0, sticky="w")
            self.standard = ttk.Combobox(box, state="readonly", width=34, values=["guide - Guide 2010", "en16450 - EN 16450:2017"])
            self.standard.current(0)
            self.standard.grid(row=2, column=1, padx=8, pady=2, sticky="w")

            self.entries: dict[str, tuple[ttk.Label, ttk.Entry]] = {}
            for i, (key, text) in enumerate(
                [
                    ("u_ref", "Reference uncertainty"),
                    ("rh_factor", "Humidity factor"),
                    ("lab_factor", "Laboratory coarse factor"),
                    ("network_sites", "Sites in the network"),
                ],
                start=3,
            ):
                label = ttk.Label(box, text=text)
                label.grid(row=i, column=0, sticky="w")
                entry = ttk.Entry(box, width=10)
                entry.grid(row=i, column=1, padx=8, pady=2, sticky="w")
                self.entries[key] = (label, entry)
            ttk.Label(box, text="Leave a field empty to use the default.", foreground="#666").grid(
                row=7, column=0, columnspan=2, sticky="w"
            )

            # actions and result
            bar = ttk.Frame(right)
            bar.grid(row=0, column=0, sticky="ew", pady=(4, 6))
            ttk.Button(bar, text="Evaluate", command=self.run).pack(side="left")
            self.report_button = ttk.Button(bar, text="Open report in browser", command=self.open_report, state="disabled")
            self.report_button.pack(side="left", padx=8)
            self.save_button = ttk.Button(bar, text="Save report…", command=self.save_report, state="disabled")
            self.save_button.pack(side="left")
            self.status = ttk.Label(bar, text="")
            self.status.pack(side="left", padx=12)

            frame = ttk.Frame(right)
            frame.grid(row=1, column=0, sticky="nsew")
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            self.text = tk.Text(frame, wrap="none", font=self._fixed_font(), padx=8, pady=6)
            self.text.grid(row=0, column=0, sticky="nsew")
            ys = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
            ys.grid(row=0, column=1, sticky="ns")
            xs = ttk.Scrollbar(frame, orient="horizontal", command=self.text.xview)
            xs.grid(row=1, column=0, sticky="ew")
            self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
            self._show(
                "1. Open a file with your measurements.\n"
                "2. Choose the evaluation and the pollutant.\n"
                "3. Select the reference column and the columns of the instruments under test.\n"
                "4. Press Evaluate.\n\n"
                "The file needs one row per day (per hour for gases) and one column per instrument."
            )

        def _fixed_font(self):
            """A fixed-width font, which the tables of the text report need."""
            from tkinter import font

            installed = set(font.families(self))
            for family in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "Menlo"):
                if family in installed:
                    return (family, 10)
            return "TkFixedFont"

        # --- state ------------------------------------------------------------
        def _show(self, text: str):
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
            self.text.configure(state="disabled")

        def _kind_changed(self):
            kind = self.kind.get()
            self.pollutant.configure(values=POLLUTANTS[kind])
            if self.pollutant.get() not in POLLUTANTS[kind]:
                self.pollutant.current(0)
            self.adjustment.configure(values=ADJUSTMENTS[kind])
            if self.adjustment.get() not in ADJUSTMENTS[kind]:
                self.adjustment.current(0)
            self.adjustment_label.configure(text=ADJUSTMENT_LABEL[kind])
            self.tested_label.configure(text=TESTED_LABEL[kind])
            self.reference_label.configure(text="Reference column" if kind == SENSOR else "Reference column(s)")
            self._enable(self.period, self.period_label, kind == ONGOING)
            self._enable(self.standard, self.standard_label, kind == EQUIVALENCE)
            self._enable(*self.entries["network_sites"][::-1], kind == ONGOING)
            self._pollutant_changed()

        def _pollutant_changed(self):
            kind, pm = self.kind.get(), self.pollutant.get().upper().startswith("PM")
            self._enable(*self.entries["rh_factor"][::-1], kind == SENSOR and pm)
            self._enable(*self.entries["lab_factor"][::-1], kind == SENSOR and self.pollutant.get() == "PM10")
            if kind == SENSOR and not pm:
                self.objectives.current(0)
            self.objectives.configure(state="readonly" if pm else "disabled")
            needed = kind == SENSOR and not pm
            self.entries["u_ref"][0].configure(text="Reference uncertainty *" if needed else "Reference uncertainty")

        @staticmethod
        def _enable(widget, label, on: bool):
            normal = "readonly" if isinstance(widget, ttk.Combobox) else "normal"
            widget.configure(state=normal if on else "disabled")
            label.configure(state="normal" if on else "disabled")

        # --- actions ----------------------------------------------------------
        def open_file(self, path: str | None = None):
            if path is None:
                path = filedialog.askopenfilename(
                    title="Open measurements",
                    filetypes=[("Tables", "*.csv *.txt *.xlsx *.xls"), ("All files", "*.*")],
                )
            if not path:
                return
            try:
                data = _read(path, None, None)
            except Exception as error:
                messagebox.showerror("aqequiv", f"The file could not be read.\n\n{error}")
                return
            self.data, self.source = data, Path(path).name
            columns = [str(c) for c in data.columns]
            numeric = [str(c) for c in data.columns if pd.api.types.is_numeric_dtype(data[c])]
            for box in (self.reference, self.tested):
                box.delete(0, "end")
                box.insert("end", *numeric)
            for combo in (self.site, self.period):
                combo.configure(values=[NONE] + columns)
                combo.set(NONE)
            self.file_label.configure(text=f"{self.source}: {len(data)} rows, {len(columns)} columns")
            self.result = None
            self.report_button.configure(state="disabled")
            self.save_button.configure(state="disabled")
            self.status.configure(text="")
            self._show(data.head(15).to_string(index=False) + f"\n\n… {len(data)} rows in total")

        def settings(self) -> Settings:
            def chosen(box):
                return [box.get(i) for i in box.curselection()]

            def column(combo):
                return None if combo.get() == NONE or str(combo.cget("state")) == "disabled" else combo.get()

            def typed(key, name, kind=float):
                _, entry = self.entries[key]
                return None if str(entry.cget("state")) == "disabled" else _number(entry.get(), name, kind)

            return Settings(
                kind=self.kind.get(),
                pollutant=self.pollutant.get(),
                reference=chosen(self.reference),
                tested=chosen(self.tested),
                site=column(self.site),
                period=column(self.period),
                adjustment=self.adjustment.get(),
                objectives=self.objectives.get().split(" ")[0],
                standard=self.standard.get().split(" ")[0],
                u_ref=typed("u_ref", "Reference uncertainty"),
                rh_factor=typed("rh_factor", "Humidity factor"),
                lab_factor=typed("lab_factor", "Laboratory coarse factor"),
                network_sites=typed("network_sites", "Sites in the network", int),
            )

        def run(self):
            if self.data is None:
                messagebox.showinfo("aqequiv", "Open a file first.")
                return
            try:
                self.result = evaluate(self.data, self.settings())
            except (CliError, ValueError) as error:
                messagebox.showerror("aqequiv", str(error))
                return
            self._show(str(self.result))
            self.report_button.configure(state="normal")
            self.save_button.configure(state="normal")
            self.status.configure(text="Done")

        def open_report(self):
            folder = Path(tempfile.mkdtemp(prefix="aqequiv-"))
            path = folder / "report.html"
            self.result.to_html(path, source=self.source)
            webbrowser.open(path.as_uri())

        def save_report(self):
            path = filedialog.asksaveasfilename(
                title="Save report", defaultextension=".html", initialfile=f"{Path(self.source).stem}_report.html",
                filetypes=[("HTML report", "*.html")],
            )
            if not path:
                return
            self.result.to_html(path, source=self.source)
            self.status.configure(text=f"Saved {Path(path).name}")

    return App()


if __name__ == "__main__":
    sys.exit(main())
