"""Classification of sensor systems from field tests.

Particulate matter follows CEN/TS 17660-2:2024 (24-hour values); gases
follow the field-test part of CEN/TS 17660-1:2021 (hourly values).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .regression import LinearFit, ols_regression, paired

#: Between-sampler standard uncertainty of the reference method, µg/m³, used
#: when no value for the instruments on site is given.
DEFAULT_REFERENCE_UBS = 0.67

_CORRECTIONS = ("none", "intercept", "slope", "both")
_NOT_CLASSIFIED = 4  # internal rank for "meets no class"


@dataclass(frozen=True)
class SensorCriteria:
    """Thresholds for one PM fraction. Tuples hold Class 1, 2 and 3 limits."""

    pollutant: str
    limit_value: float
    upper_assessment_threshold: float | None
    lower_assessment_threshold: float | None
    dqo: tuple[float, float, float]  # maximum expanded uncertainty at the limit value, µg/m³
    ubs_max: tuple[float, float, float] = (3.0, 5.0, 7.0)
    slope_range: tuple[tuple[float, float], ...] = ((0.78, 1.29), (0.60, 1.67), (0.43, 2.33))
    intercept_max: tuple[float, float, float] = (3.0, 5.0, 7.0)
    capture_min: tuple[float, float, float] = (0.90, 0.50, 0.0)
    rh_factor_max: tuple[float, float, float] = (1.5, 2.5, math.inf)
    min_sites: int = 2
    min_periods_per_site: int = 80  # two campaigns of at least 40 days
    min_sensors: int = 3
    unit: str = "µg/m³"
    period: str = "day"  # averaging period of the data: "day" or "hour"
    default_u_ref: float | None = DEFAULT_REFERENCE_UBS
    humidity_test: bool = True


SENSOR_PM10 = SensorCriteria("PM10", 50.0, 35.0, 25.0, dqo=(25.0, 50.0, 100.0))
SENSOR_PM25 = SensorCriteria("PM2.5", 30.0, 21.0, 15.0, dqo=(15.0, 30.0, 60.0))

#: Class limits re-derived from Directive (EU) 2024/2881 (Annex V, Table 2)
#: at the 24-hour limit values that apply from 2030. This mapping is not part
#: of CEN/TS 17660-2, which refers to Directive 2008/50/EC:
#: Class 1 = maximum uncertainty of indicative measurements;
#: Class 2 = objective estimation (indicative x maximum ratio, capped at 85 %
#: of the limit value); Class 3 = 200 % of the limit value, as in the
#: specification. The directive sets no 24-hour assessment thresholds for PM.
SENSOR_PM10_2030 = SensorCriteria("PM10", 45.0, None, None, dqo=(22.5, 38.25, 90.0))
SENSOR_PM25_2030 = SensorCriteria("PM2.5", 25.0, None, None, dqo=(8.8, 21.25, 50.0))


def _gas(pollutant, lv, uat, lat, dqo, ubs, intercept, *, sites=2, unit="µg/m³"):
    return SensorCriteria(
        pollutant, lv, uat, lat, dqo=dqo, ubs_max=ubs, intercept_max=intercept,
        capture_min=(0.90, 0.50, 0.0), rh_factor_max=(math.inf,) * 3,
        min_sites=sites, min_periods_per_site=1920,  # two seasons of 40 days, hourly
        unit=unit, period="hour", default_u_ref=None, humidity_test=False,
    )


#: Gases, evaluated on hourly values (CEN/TS 17660-1:2021, field tests).
#: The reference uncertainty depends on the analyser, so there is no default.
SENSOR_NO2 = _gas("NO2", 200.0, 140.0, 100.0, (50.0, 150.0, 400.0), (7.6, 15.0, 31.0), (9.8, 19.0, 33.0))
SENSOR_NO = _gas("NO", 200.0, 140.0, 100.0, (50.0, 150.0, 400.0), (5.0, 10.0, 20.0), (6.4, 12.0, 22.0))
SENSOR_O3 = _gas("O3", 120.0, 84.0, 60.0, (36.0, 90.0, 240.0), (8.0, 12.0, 24.0), (9.8, 19.0, 33.0))
SENSOR_SO2 = _gas("SO2", 350.0, None, None, (88.0, 263.0, 700.0), (10.6, 21.0, 43.0), (1.4, 2.5, 4.5), sites=1)
SENSOR_CO = _gas(
    "CO", 10.0, 7.0, 5.0, (2.5, 7.5, 20.0), (0.058, 0.116, 0.232), (0.18, 0.25, 0.40), unit="mg/m³"
)
SENSOR_BENZENE = _gas(
    "benzene", 5.0, 3.5, 2.0, (1.5, 5.0, 10.0), (1.3, 2.6, 5.2), (0.28, 0.58, 0.60), sites=1
)

_CRITERIA = {
    "PM10": SENSOR_PM10, "PM2.5": SENSOR_PM25, "PM25": SENSOR_PM25,
    "NO2": SENSOR_NO2, "NO": SENSOR_NO, "O3": SENSOR_O3, "SO2": SENSOR_SO2,
    "CO": SENSOR_CO, "BENZENE": SENSOR_BENZENE,
}


def _rank_upper(value: float, limits) -> int:
    """Best class (1-3) whose upper limit ``value`` respects, else 4."""
    for rank, limit in enumerate(limits, start=1):
        if value <= limit:
            return rank
    return _NOT_CLASSIFIED


def _rank_lower(value: float, limits) -> int:
    for rank, limit in enumerate(limits, start=1):
        if value >= limit:
            return rank
    return _NOT_CLASSIFIED


def _rank_range(value: float, ranges) -> int:
    for rank, (low, high) in enumerate(ranges, start=1):
        if low <= value <= high:
            return rank
    return _NOT_CLASSIFIED


def _label(rank) -> str:
    return "none" if rank >= _NOT_CLASSIFIED else f"Class {int(rank)}"


# --- building blocks ---------------------------------------------------------


def between_sensor_uncertainty(values) -> float:
    """Between-sensor-system standard uncertainty of replicate systems.

    ``values`` has one row per period and one column per sensor system.
    Only periods where every system has a value are used. With two columns
    this equals the between-sampler uncertainty of the 2010 Guide.
    """
    v = np.asarray(values, dtype=float)
    if v.ndim != 2 or v.shape[1] < 2:
        raise ValueError("give one column per sensor system, at least two")
    v = v[np.isfinite(v).all(axis=1)]
    n, ns = v.shape
    if n == 0:
        raise ValueError("no period where all sensor systems have a value")
    return float(np.sqrt(np.sum((v - v.mean(axis=1, keepdims=True)) ** 2) / (n * (ns - 1))))


def daily_means(hourly: pd.DataFrame | pd.Series, min_coverage: float = 0.90):
    """24-hour averages of hourly data with a datetime index.

    A day is valid only if at least ``min_coverage`` of its 24 hourly values
    are present (0.90 for Class 1, 0.50 for Class 2); other days become NaN.
    """
    days = hourly.index.floor("D")
    mean = hourly.groupby(days).mean()
    count = hourly.notna().groupby(days).sum()
    return mean.where(count >= min_coverage * 24)


@dataclass(frozen=True)
class RHFactor:
    """Change of the sensor response from low to high relative humidity."""

    factor: float  # NaN when either humidity range has too few hours
    n_low: int
    n_high: int
    median_low: float
    median_high: float

    @property
    def assessable(self) -> bool:
        return not math.isnan(self.factor)


def rh_factor(sensor, equivalent, rh, *, low=(30.0, 60.0), high=(85.0, 95.0), min_hours: int = 20) -> RHFactor:
    """Median sensor-to-equivalent ratio at high humidity over that at low humidity.

    All three inputs are hourly and aligned. ``rh`` must come from an
    independent humidity sensor, in percent.
    """
    s = np.asarray(sensor, dtype=float)
    e = np.asarray(equivalent, dtype=float)
    h = np.asarray(rh, dtype=float)
    ok = np.isfinite(s) & np.isfinite(e) & np.isfinite(h) & (e > 0)
    ratio, h = s[ok] / e[ok], h[ok]
    lo = ratio[(h >= low[0]) & (h <= low[1])]
    hi = ratio[(h >= high[0]) & (h <= high[1])]
    med_lo = float(np.median(lo)) if lo.size else math.nan
    med_hi = float(np.median(hi)) if hi.size else math.nan
    enough = lo.size >= min_hours and hi.size >= min_hours and med_lo > 0
    return RHFactor(med_hi / med_lo if enough else math.nan, int(lo.size), int(hi.size), med_lo, med_hi)


@dataclass(frozen=True)
class CoarseTest:
    """Field check that a PM10 sensor responds to coarse particles (PM10-2.5)."""

    slope: float
    r2: float
    n: int
    n_high_days: int  # days with reference PM10-2.5 of at least 10 µg/m³

    @property
    def assessable(self) -> bool:
        return self.n_high_days >= 10

    @property
    def passed(self) -> bool:
        return self.assessable and 0.5 < self.slope < 2.0 and self.r2 > 0.5


def coarse_test(sensor_pm10, sensor_pm25, reference_pm10, reference_pm25) -> CoarseTest:
    """Regress the sensor's daily PM10-2.5 on the reference method's PM10-2.5."""
    y = np.asarray(sensor_pm10, dtype=float) - np.asarray(sensor_pm25, dtype=float)
    x = np.asarray(reference_pm10, dtype=float) - np.asarray(reference_pm25, dtype=float)
    fit = ols_regression(x, y)
    return CoarseTest(fit.slope, fit.r2, fit.n, int(np.sum(x[np.isfinite(x)] >= 10.0)))


def fine_coarse_factor(pm25_sensor_fine, pm25_equivalent_fine, coarse_sensor, coarse_equivalent) -> float:
    """Laboratory factor of the response change from fine to coarse particles.

    Arguments are test averages: sensor and equivalent-method PM2.5 during
    the fine test, and sensor and equivalent-method PM10-2.5 during the
    coarse test. Class 1 for PM10 requires a factor below 2.
    """
    return (pm25_sensor_fine / pm25_equivalent_fine) / (coarse_sensor / coarse_equivalent)


@dataclass(frozen=True)
class FieldUncertainty:
    """Sensor-versus-reference comparison for one dataset."""

    fit: LinearFit
    u_ref: float
    random_term: float
    u_correction_terms: tuple[float, float]  # u(a), u(b) of the correction, 0 if unused

    def bias(self, level: float) -> float:
        return self.fit.intercept + (self.fit.slope - 1.0) * level

    def expanded(self, level: float) -> float:
        """Expanded uncertainty (k = 2) at a concentration level, µg/m³."""
        ua, ub = self.u_correction_terms
        return 2.0 * math.sqrt(self.random_term**2 + self.bias(level) ** 2 + ua**2 + (level * ub) ** 2)

    def relative_components(self, level):
        """Relative random and bias parts of the expanded uncertainty at ``level``.

        Returns ``(RR, RB)`` as fractions of ``level``; ``level`` may be an
        array. Their quadratic sum is the relative expanded uncertainty.
        These are the two axes of the Modified Target Diagram.
        """
        level = np.asarray(level, dtype=float)
        ua, ub = self.u_correction_terms
        rr = 2.0 * np.sqrt(self.random_term**2 + ua**2 + (level * ub) ** 2) / level
        rb = 2.0 * (self.fit.intercept + (self.fit.slope - 1.0) * level) / level
        return rr, rb


def field_uncertainty(x, y, *, u_ref: float = DEFAULT_REFERENCE_UBS, u_correction_terms=(0.0, 0.0)) -> FieldUncertainty:
    """Uncertainty of sensor results ``y`` against reference results ``x``.

    Uses ordinary least squares. ``u_ref`` is the between-sampler standard
    uncertainty of the reference (or equivalent) method. A negative random
    term is set to zero.
    """
    fit = ols_regression(x, y)
    random_var = max(fit.rss / (fit.n - 2) - u_ref**2, 0.0)
    return FieldUncertainty(fit, u_ref, math.sqrt(random_var), tuple(u_correction_terms))


@dataclass(frozen=True)
class Correction:
    """Universal slope and/or intercept correction for all sensor systems."""

    kind: str
    slope: float
    intercept: float
    u_slope: float
    u_intercept: float

    def apply(self, y):
        if self.kind == "intercept":
            return y - self.intercept
        if self.kind == "slope":
            return y / self.slope
        return (y - self.intercept) / self.slope

    @property
    def u_terms(self) -> tuple[float, float]:
        return (
            self.u_intercept if self.kind in ("intercept", "both") else 0.0,
            self.u_slope if self.kind in ("slope", "both") else 0.0,
        )

    def __str__(self) -> str:
        if self.kind == "intercept":
            return f"y_corr = y - {self.intercept:.3f}"
        if self.kind == "slope":
            return f"y_corr = y / {self.slope:.3f}"
        return f"y_corr = (y - {self.intercept:.3f}) / {self.slope:.3f}"


# --- full evaluation ---------------------------------------------------------


@dataclass
class SensorClassification:
    """Outcome of :func:`evaluate_sensor`."""

    criteria: SensorCriteria
    datasets: pd.DataFrame  # one row per site and sensor system
    between_sensor: pd.DataFrame  # one row per site
    other_tests: pd.DataFrame  # humidity, coarse fraction, laboratory
    dataset_checks: pd.DataFrame
    u_ref: float
    correction: Correction | None
    rank: int
    notes: list[str] = field(default_factory=list)
    _points: dict = field(default_factory=dict, repr=False)

    @property
    def sensor_class(self) -> int | None:
        """1, 2 or 3; None if the sensor system meets no class."""
        return None if self.rank >= _NOT_CLASSIFIED else self.rank

    @property
    def dataset_suitable(self) -> bool:
        return bool(self.dataset_checks["passed"].all())

    def report(self) -> str:
        from .pm import _format

        c = self.criteria
        cor = f"corrected, {self.correction}" if self.correction else "uncorrected"
        lines = [
            f"{c.pollutant} sensor system classification ({cor})",
            f"Limit value {c.limit_value:g} {c.unit}; maximum expanded uncertainty "
            f"{' / '.join(f'{d:g}' for d in c.dqo)} {c.unit} for Class 1 / 2 / 3",
            f"Reference between-sampler uncertainty {self.u_ref:.2f} {c.unit}",
            "",
            f"Field test, per site and sensor system (U = expanded uncertainty, {c.unit})",
            _format(self.datasets),
            "",
            "Between-sensor-system uncertainty",
            _format(self.between_sensor),
        ]
        if len(self.other_tests):
            lines += ["", "Other tests", _format(self.other_tests)]
        lines += ["", "Dataset requirements", _format(self.dataset_checks)]
        if self.notes:
            lines += ["", "Notes"] + [f"- {n}" for n in self.notes]
        verdict = _label(self.rank) if self.rank < _NOT_CLASSIFIED else "not classified"
        lines += [
            "",
            f"Result: {verdict}",
            f"Dataset requirements: {'met' if self.dataset_suitable else 'NOT met'}",
        ]
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.report()

    def to_html(self, path=None, **kwargs) -> str:
        """Self-contained HTML report; written to ``path`` if given."""
        from .report import to_html

        return to_html(self, path, **kwargs)

    def plot(self):
        """Scatter plots of every sensor system against the reference, per site."""
        from .plotting import plot_sensor

        return plot_sensor(self)

    def target_diagram(self):
        """Modified Target Diagram for every site and sensor system."""
        from .plotting import plot_target_grid

        return plot_target_grid(self)


def evaluate_sensor(
    data: pd.DataFrame,
    reference: str,
    sensors,
    pollutant: str = "PM2.5",
    *,
    site: str | None = None,
    u_ref: float | None = None,
    correction: str = "none",
    rh_factor=None,
    coarse: CoarseTest | None = None,
    lab_factor: float | None = None,
    criteria: SensorCriteria | None = None,
) -> SensorClassification:
    """Classify a sensor system from co-location with the reference method.

    Parameters
    ----------
    data
        One row per averaging period of the field test, both seasons
        together: 24-hour values for PM, hourly values for gases. Periods
        in which a sensor delivered no valid average are NaN.
    reference
        Column with the reference method results.
    sensors
        Columns with the replicate sensor systems (normally three).
    pollutant
        ``"PM2.5"``, ``"PM10"``, ``"NO2"``, ``"NO"``, ``"O3"``, ``"SO2"``,
        ``"CO"`` (in mg/m³) or ``"benzene"``.
    site
        Column naming the test site. Every site is evaluated separately.
    u_ref
        Between-sampler standard uncertainty of the reference method, in the
        unit of the data. Defaults to 0.67 µg/m³ for PM; for gases it depends
        on the analyser and must be given.
    correction
        ``"none"``, ``"intercept"``, ``"slope"`` or ``"both"``. The correction
        is derived once from all sensor systems at all sites and applied to
        every dataset.
    rh_factor
        Humidity factor from :func:`rh_factor`: one value, or a mapping from
        site name to value. Values may be floats or ``RHFactor`` objects.
    coarse
        Result of :func:`coarse_test` (PM10 only).
    lab_factor
        Laboratory fine/coarse factor from :func:`fine_coarse_factor` (PM10 only).
    criteria
        Override the thresholds for the pollutant.
    """
    if criteria is None:
        try:
            criteria = _CRITERIA[pollutant.upper().replace(",", ".")]
        except KeyError:
            raise ValueError(f"unknown pollutant {pollutant!r}; choose from {sorted(_CRITERIA)}") from None
    if u_ref is None:
        u_ref = criteria.default_u_ref
    if u_ref is None:
        raise ValueError(
            f"give u_ref, the between-instrument standard uncertainty of the {criteria.pollutant} "
            f"reference analyser in {criteria.unit} (from its type-approval report)"
        )
    if correction not in _CORRECTIONS:
        raise ValueError(f"correction must be one of {_CORRECTIONS}")
    cols = [sensors] if isinstance(sensors, str) else list(sensors)
    crit = criteria
    notes: list[str] = []

    x = data[reference].astype(float)
    ys = data[cols].astype(float)
    sites = data[site] if site is not None else pd.Series("all", index=data.index)
    site_names = list(sites.dropna().unique())

    # --- universal correction from all systems at all sites ----------------
    cor = None
    if correction != "none":
        fit = ols_regression(np.tile(x.to_numpy(), len(cols)), ys.to_numpy().T.ravel())
        cor = Correction(correction, fit.slope, fit.intercept, fit.u_slope, fit.u_intercept)
        ys = cor.apply(ys)
    u_terms = cor.u_terms if cor else (0.0, 0.0)

    # --- per site and sensor system -----------------------------------------
    rows, points = [], {}
    for name in site_names:
        at_site = sites == name
        n_days = int(at_site.sum())
        for col in cols:
            sel = at_site & x.notna() & ys[col].notna()
            if sel.sum() < 3:
                notes.append(f"site {name}, {col}: fewer than 3 valid pairs, not evaluated")
                rows.append({"site": name, "sensor": col, "n": int(sel.sum()), "class": _NOT_CLASSIFIED})
                continue
            fu = field_uncertainty(x[sel], ys.loc[sel, col], u_ref=u_ref, u_correction_terms=u_terms)
            capture = float(ys.loc[at_site, col].notna().sum() / n_days)
            u_lv = fu.expanded(crit.limit_value)
            ranks = {
                "uncertainty": _rank_upper(u_lv, crit.dqo),
                "slope": _rank_range(fu.fit.slope, crit.slope_range),
                "intercept": _rank_upper(abs(fu.fit.intercept), crit.intercept_max),
                "data capture": _rank_lower(capture, crit.capture_min),
            }
            worst = max(ranks.values())
            rows.append({
                "site": name, "sensor": col, "n": fu.fit.n, "capture_pct": 100 * capture,
                "slope": fu.fit.slope, "intercept": fu.fit.intercept, "r2": fu.fit.r2,
                "U_LV": u_lv,
                **{
                    name_: fu.expanded(level)
                    for name_, level in (
                        ("U_UAT", crit.upper_assessment_threshold),
                        ("U_LAT", crit.lower_assessment_threshold),
                    )
                    if level is not None
                },
                "limited_by": ", ".join(k for k, r in ranks.items() if r == worst) if worst > 1 else "",
                "class": worst,
            })
            points[(name, col)] = (x[sel].to_numpy(), ys.loc[sel, col].to_numpy(), fu, u_lv, worst)
    datasets = pd.DataFrame(rows)
    rank = int(datasets["class"].max())

    # --- between-sensor-system uncertainty, per site ------------------------
    bs_rows = []
    if len(cols) >= 2:
        for name in site_names:
            block = ys[sites == name].dropna()
            if len(block) == 0:
                notes.append(f"site {name}: no day with all sensor systems valid")
                continue
            ubs = between_sensor_uncertainty(block)
            bs_rows.append({"site": name, "n": len(block), "u_bs": ubs, "class": _rank_upper(ubs, crit.ubs_max)})
    else:
        notes.append("one sensor system: between-sensor-system uncertainty not assessed")
    between = pd.DataFrame(bs_rows, columns=["site", "n", "u_bs", "class"])
    if len(between):
        rank = max(rank, int(between["class"].max()))

    # --- humidity, coarse fraction and laboratory tests ---------------------
    other = []
    if not crit.humidity_test:
        notes.append(
            "field test only: the final class is the lowest of the pre-test, laboratory and field classes"
        )
    elif rh_factor is None:
        notes.append("humidity factor not given: Class 1 and Class 2 also require the humidity test")
    if crit.humidity_test and rh_factor is not None:
        per_site = rh_factor if isinstance(rh_factor, dict) else {"all sites": rh_factor}
        usable = {k: getattr(v, "factor", v) for k, v in per_site.items()}
        usable = {k: float(v) for k, v in usable.items() if not math.isnan(float(v))}
        for k in set(per_site) - set(usable):
            notes.append(f"humidity factor at {k} could not be estimated and is ignored")
        for k, v in usable.items():
            r = _rank_upper(v, tuple(np.nextafter(m, 0) for m in crit.rh_factor_max))  # strict "<"
            other.append({"test": f"humidity factor, {k}", "value": v, "best_class": r})
            rank = max(rank, r)
    if crit.pollutant == "PM10":
        if coarse is None or not coarse.assessable:
            notes.append(
                "coarse fraction field test not assessed"
                + ("" if coarse is None else f" (only {coarse.n_high_days} days with PM10-2.5 >= 10 µg/m³)")
            )
        else:
            r = 1 if coarse.passed else 2
            other.append({"test": "coarse fraction, slope", "value": coarse.slope, "best_class": r})
            other.append({"test": "coarse fraction, R²", "value": coarse.r2, "best_class": r})
            rank = max(rank, r) if rank < _NOT_CLASSIFIED else rank
        if lab_factor is None:
            notes.append("laboratory coarse test not given: Class 1 for PM10 also requires it")
        else:
            r = 1 if lab_factor < 2 else 2
            other.append({"test": "laboratory fine/coarse factor", "value": lab_factor, "best_class": r})
            rank = max(rank, r) if rank < _NOT_CLASSIFIED else rank
    other_tests = pd.DataFrame(other, columns=["test", "value", "best_class"])

    for table in (datasets, between, other_tests):
        for c in ("class", "best_class"):
            if c in table:
                table[c] = table[c].map(_label)

    # --- size of the field test ---------------------------------------------
    fewest = int(min((sites == s).sum() for s in site_names))
    checks = [
        ("number of sensor systems", str(len(cols)), f">= {crit.min_sensors}", len(cols) >= crit.min_sensors),
        ("number of test sites", str(len(site_names)), f">= {crit.min_sites}", len(site_names) >= crit.min_sites),
        (f"fewest {crit.period}s at a site", str(fewest), f">= {crit.min_periods_per_site}", fewest >= crit.min_periods_per_site),
    ]
    dataset_checks = pd.DataFrame(checks, columns=["requirement", "value", "required", "passed"])

    return SensorClassification(
        criteria=crit,
        datasets=datasets,
        between_sensor=between,
        other_tests=other_tests,
        dataset_checks=dataset_checks,
        u_ref=float(u_ref),
        correction=cor,
        rank=rank,
        notes=notes,
        _points=points,
    )
