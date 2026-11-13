"""Equivalence test for particulate matter (Guide 2010, clauses 9.5-9.7)."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .regression import OrthogonalFit, orthogonal_regression, paired

#: Default variance of the reference method, (µg/m³)², when it cannot be
#: derived from duplicate reference samplers (clause 9.5.3.2).
DEFAULT_REFERENCE_VARIANCE = 0.67


@dataclass(frozen=True)
class PMCriteria:
    """Numbers the Guide prescribes for one PM fraction (all in µg/m³)."""

    pollutant: str
    limit_value: float  # concentration at which the uncertainty is evaluated
    split: float  # boundary between the low and high concentration subsets
    upper_assessment_threshold: float
    dqo: float = 0.25  # data quality objective for the expanded uncertainty
    dqo_absolute: float | None = None  # µg/m³; if set, the higher of the two applies
    ubs_candidate_max: float = 2.5
    ubs_reference_max: float = 2.0
    min_pairs: int = 40
    min_fraction_above_uat: float = 0.20
    min_comparisons: int = 4

    @property
    def max_uncertainty(self) -> float:
        """Largest acceptable expanded uncertainty at the limit value, µg/m³."""
        return max(self.dqo * self.limit_value, self.dqo_absolute or 0.0)


PM10 = PMCriteria("PM10", limit_value=50.0, split=30.0, upper_assessment_threshold=28.0)
PM25 = PMCriteria("PM2.5", limit_value=30.0, split=18.0, upper_assessment_threshold=17.0)

#: Objectives for fixed measurements of 24-hour means in Directive (EU)
#: 2024/2881 (Annex V, Table 2), evaluated at the limit values that apply
#: from 2030. The Guide has not been revised for the new directive, so its
#: concentration split and threshold for the dataset are kept.
PM10_2030 = PMCriteria("PM10", 45.0, split=30.0, upper_assessment_threshold=28.0, dqo_absolute=11.3)
PM25_2030 = PMCriteria("PM2.5", 25.0, split=18.0, upper_assessment_threshold=17.0, dqo_absolute=6.3)

_CRITERIA = {"PM10": PM10, "PM2.5": PM25, "PM25": PM25}
_CALIBRATIONS = ("none", "auto", "intercept", "slope", "both")


def between_sampler_uncertainty(y1, y2) -> float:
    """Between-sampler (or between-instrument) uncertainty, eq. 9.4.

    Periods where either of the two parallel results is missing are ignored.
    """
    y1, y2 = paired(y1, y2)
    if y1.size == 0:
        raise ValueError("no periods with both parallel results")
    return float(np.sqrt(np.sum((y1 - y2) ** 2) / (2 * y1.size)))


@dataclass(frozen=True)
class Comparability:
    """Candidate-versus-reference comparison for one dataset."""

    fit: OrthogonalFit
    limit_value: float
    u_ref: float
    random_term: float  # sqrt(RSS/(n-2) - u_ref²)
    bias: float  # a + (b-1)*LV
    u_calibration: float  # extra term carried over from a calibration
    u_combined: float
    dqo: float
    dqo_absolute: float | None = None

    @property
    def w_expanded(self) -> float:
        """Expanded relative uncertainty at the limit value (k = 2)."""
        return 2.0 * self.u_combined / self.limit_value

    @property
    def passed(self) -> bool:
        limit = max(self.dqo * self.limit_value, self.dqo_absolute or 0.0)
        return 2.0 * self.u_combined <= limit


def comparability(
    x,
    y,
    *,
    limit_value: float,
    u_ref: float,
    dqo: float = 0.25,
    dqo_absolute: float | None = None,
    u_calibration: float = 0.0,
) -> Comparability:
    """Uncertainty of candidate results ``y`` against reference results ``x``.

    Implements eq. 9.6-9.9. ``u_ref`` is the standard uncertainty of the
    reference results. The result passes if the expanded uncertainty is at
    most ``dqo`` times the limit value or ``dqo_absolute`` (µg/m³), whichever
    is higher. ``u_calibration`` is the extra term of eq. 9.12, 9.15
    or 9.17 when ``y`` has already been calibrated.
    """
    fit = orthogonal_regression(x, y)
    random_var = fit.rss / (fit.n - 2) - u_ref**2
    if random_var < 0:
        warnings.warn(
            "the residual variance is smaller than the reference variance; "
            "the random term is set to zero",
            stacklevel=2,
        )
        random_var = 0.0
    bias = fit.intercept + (fit.slope - 1.0) * limit_value
    u_combined = math.sqrt(random_var + bias**2 + u_calibration**2)
    return Comparability(
        fit=fit,
        limit_value=limit_value,
        u_ref=u_ref,
        random_term=math.sqrt(random_var),
        bias=bias,
        u_calibration=u_calibration,
        u_combined=u_combined,
        dqo=dqo,
        dqo_absolute=dqo_absolute,
    )


@dataclass(frozen=True)
class Calibration:
    """Calibration function derived from the full dataset (clause 9.7)."""

    kind: str  # "intercept", "slope" or "both"
    slope: float
    intercept: float
    u_slope: float
    u_intercept: float

    def apply(self, y):
        """Return calibrated candidate results."""
        y = np.asarray(y, dtype=float) if not isinstance(y, (pd.Series, pd.DataFrame)) else y
        if self.kind == "intercept":
            return y - self.intercept
        if self.kind == "slope":
            return y / self.slope
        return (y - self.intercept) / self.slope

    def u_extra(self, concentration: float) -> float:
        """Uncertainty the calibration adds at a given concentration."""
        var = 0.0
        if self.kind in ("intercept", "both"):
            var += self.u_intercept**2
        if self.kind in ("slope", "both"):
            var += (concentration * self.u_slope) ** 2
        return math.sqrt(var)

    def __str__(self) -> str:
        if self.kind == "intercept":
            return f"y_cal = y - {self.intercept:.3f}"
        if self.kind == "slope":
            return f"y_cal = y / {self.slope:.3f}"
        return f"y_cal = (y - {self.intercept:.3f}) / {self.slope:.3f}"


@dataclass
class PMEquivalence:
    """Outcome of :func:`evaluate_pm`."""

    criteria: PMCriteria
    comparisons: pd.DataFrame  # one row per candidate and dataset
    between_sampler: pd.DataFrame  # between-sampler uncertainties
    dataset_checks: pd.DataFrame  # suitability of the dataset (clause 9.5.2)
    u_ref: float
    u_ref_source: str
    calibration: Calibration | None
    notes: list[str] = field(default_factory=list)
    _points: dict = field(default_factory=dict, repr=False)

    @property
    def passed(self) -> bool:
        """True if every uncertainty criterion is met."""
        return bool(self.comparisons["passed"].all() and self.between_sampler["passed"].all())

    @property
    def dataset_suitable(self) -> bool:
        """True if the dataset meets the size and concentration requirements."""
        return bool(self.dataset_checks["passed"].all())

    def report(self) -> str:
        """Plain-text summary of the evaluation."""
        c = self.criteria
        cal = f"calibrated, {self.calibration}" if self.calibration else "uncalibrated"
        lines = [
            f"{c.pollutant} equivalence test ({cal})",
            f"Uncertainty evaluated at {c.limit_value:g} µg/m³; objective: expanded uncertainty "
            f"<= {c.max_uncertainty:g} µg/m³ ({100 * c.max_uncertainty / c.limit_value:.1f} %)",
            f"Reference uncertainty {self.u_ref:.2f} µg/m³ ({self.u_ref_source})",
            "",
            "Comparison with the reference method",
            _format(self.comparisons),
        ]
        if len(self.between_sampler):
            lines += ["", "Between-sampler uncertainty", _format(self.between_sampler)]
        lines += ["", "Dataset suitability", _format(self.dataset_checks)]
        if self.notes:
            lines += ["", "Notes"] + [f"- {n}" for n in self.notes]
        lines += [
            "",
            f"Uncertainty criteria: {'PASS' if self.passed else 'FAIL'}",
            f"Dataset requirements: {'met' if self.dataset_suitable else 'NOT met'}",
        ]
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.report()

    def plot(self, **kwargs):
        """Scatter plot of each candidate against the reference."""
        from .plotting import plot_equivalence

        return plot_equivalence(self, **kwargs)


def _format(table: pd.DataFrame) -> str:
    return table.to_string(index=False, float_format=lambda v: f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}")


def _as_list(columns) -> list[str]:
    return [columns] if isinstance(columns, str) else list(columns)


def evaluate_pm(
    data: pd.DataFrame,
    reference,
    candidate,
    pollutant: str = "PM10",
    *,
    site: str | None = None,
    u_ref: float | None = None,
    calibration: str = "none",
    criteria: PMCriteria | None = None,
) -> PMEquivalence:
    """Test a candidate PM method for equivalence with the reference method.

    Parameters
    ----------
    data
        One row per 24-hour period.
    reference
        Column name, or two column names, with reference method results.
        With two columns their mean is used; a period with only one of
        them is still used.
    candidate
        Column name, or two column names, with candidate results. Each
        candidate instrument is evaluated on its own.
    pollutant
        ``"PM10"`` or ``"PM2.5"``.
    site
        Optional column that identifies the comparison (site or campaign).
        Each one is also evaluated separately.
    u_ref
        Standard uncertainty of the reference results, µg/m³. By default it
        is the reference between-sampler uncertainty divided by √2 when two
        reference columns are given, otherwise √0.67.
    calibration
        ``"none"`` evaluates the data as given. ``"intercept"``, ``"slope"``
        and ``"both"`` first calibrate the candidate with the regression of
        the full dataset. ``"auto"`` picks whichever of those the
        significance of slope and intercept calls for.
    criteria
        Override the limits prescribed for the pollutant.
    """
    if criteria is None:
        try:
            criteria = _CRITERIA[pollutant.upper().replace(",", ".")]
        except KeyError:
            raise ValueError(f"unknown pollutant {pollutant!r}; use 'PM10' or 'PM2.5'") from None
    if calibration not in _CALIBRATIONS:
        raise ValueError(f"calibration must be one of {_CALIBRATIONS}")
    ref_cols, cand_cols = _as_list(reference), _as_list(candidate)
    if not 1 <= len(ref_cols) <= 2 or not 1 <= len(cand_cols) <= 2:
        raise ValueError("give one or two reference columns and one or two candidate columns")

    crit = criteria
    notes: list[str] = []
    x = data[ref_cols].astype(float).mean(axis=1, skipna=True)
    cands = data[cand_cols].astype(float)
    high = x >= crit.split

    # --- between-sampler uncertainties -------------------------------------
    bs_rows = []
    ubs_ref = None
    if len(ref_cols) == 2:
        r1, r2 = paired(data[ref_cols[0]], data[ref_cols[1]])
        ubs_ref = between_sampler_uncertainty(r1, r2)
        bs_rows.append(("reference", "all", r1.size, ubs_ref, crit.ubs_reference_max))
    if len(cand_cols) == 2:
        both = cands.notna().all(axis=1) & x.notna()
        subsets = [
            ("all", cands.notna().all(axis=1)),
            (f">= {crit.split:g}", both & high),
            (f"< {crit.split:g}", both & ~high),
        ]
        for label, mask in subsets:
            if mask.sum() == 0:
                notes.append(f"no paired candidate results in subset '{label}'")
                continue
            ubs = between_sampler_uncertainty(cands.loc[mask, cand_cols[0]], cands.loc[mask, cand_cols[1]])
            bs_rows.append(("candidate", label, int(mask.sum()), ubs, crit.ubs_candidate_max))
    else:
        notes.append("one candidate instrument: between-sampler uncertainty not assessed")
    between = pd.DataFrame(bs_rows, columns=["method", "dataset", "n", "u_bs", "limit"])
    between["passed"] = between["u_bs"] <= between["limit"]

    # --- uncertainty of the reference results ------------------------------
    if u_ref is not None:
        u_ref_source = "given"
    elif ubs_ref is not None:
        u_ref, u_ref_source = ubs_ref / math.sqrt(2), "reference u_bs / √2"
    else:
        u_ref, u_ref_source = math.sqrt(DEFAULT_REFERENCE_VARIANCE), "Guide default"

    # --- calibration from the full dataset, all candidates together --------
    cal = None
    if calibration != "none":
        fit = orthogonal_regression(np.tile(x.to_numpy(), len(cand_cols)), cands.to_numpy().T.ravel())
        kind = calibration
        if kind == "auto":
            kind = {
                (True, True): "both",
                (True, False): "slope",
                (False, True): "intercept",
                (False, False): "none",
            }[(fit.slope_significant, fit.intercept_significant)]
            if kind == "none":
                notes.append("slope and intercept are not significant: no calibration applied")
        if kind != "none":
            cal = Calibration(kind, fit.slope, fit.intercept, fit.u_slope, fit.u_intercept)
            cands = cal.apply(cands)
    u_cal = cal.u_extra(crit.limit_value) if cal else 0.0

    # --- comparison with the reference, per candidate and dataset ----------
    datasets = [("all", pd.Series(True, index=data.index), False)]
    datasets.append((f">= {crit.split:g}", high, True))
    sites = None
    if site is not None:
        sites = data[site]
        if sites.nunique() > 1:
            datasets += [(f"site {name}", sites == name, False) for name in sites.dropna().unique()]

    rows, points = [], {}
    for col in cand_cols:
        valid = x.notna() & cands[col].notna()
        for label, mask, needs_min in datasets:
            sel = valid & mask
            n = int(sel.sum())
            if n < (crit.min_pairs if needs_min else 3):
                if n:
                    notes.append(f"{col}, dataset '{label}': only {n} pairs, not evaluated")
                continue
            comp = comparability(
                x[sel], cands.loc[sel, col],
                limit_value=crit.limit_value, u_ref=u_ref, dqo=crit.dqo,
                dqo_absolute=crit.dqo_absolute, u_calibration=u_cal,
            )
            f = comp.fit
            rows.append({
                "candidate": col, "dataset": label, "n": f.n,
                "slope": f.slope, "u_slope": f.u_slope,
                "intercept": f.intercept, "u_intercept": f.u_intercept, "r2": f.r2,
                "random": comp.random_term, "bias": comp.bias, "u_c": comp.u_combined,
                "W_pct": 100 * comp.w_expanded, "passed": comp.passed,
            })
            if label == "all":
                points[col] = (x[sel].to_numpy(), cands.loc[sel, col].to_numpy(), comp)
                if cal is None and (f.slope_significant or f.intercept_significant):
                    what = " and ".join(
                        w for w, s in (("slope", f.slope_significant), ("intercept", f.intercept_significant)) if s
                    )
                    notes.append(f"{col}: {what} significant on the full dataset; calibration may be applied")
    if not rows:
        raise ValueError("no dataset has enough valid pairs to evaluate")
    comparisons = pd.DataFrame(rows)

    # --- suitability of the dataset (clause 9.5.2 and 9.4.2) ---------------
    frac = float((x.dropna() > crit.upper_assessment_threshold).mean())
    checks = [(
        f"share of reference results > {crit.upper_assessment_threshold:g}",
        f"{100 * frac:.1f}%", f">= {100 * crit.min_fraction_above_uat:g}%",
        frac >= crit.min_fraction_above_uat,
    )]
    if sites is not None:
        n_sites = int(sites.nunique())
        per_site = min(
            int((x.notna() & cands[col].notna() & (sites == s)).sum())
            for col in cand_cols for s in sites.dropna().unique()
        )
        checks.append(("number of comparisons", str(n_sites), f">= {crit.min_comparisons}", n_sites >= crit.min_comparisons))
        checks.append(("fewest pairs in a comparison", str(per_site), f">= {crit.min_pairs}", per_site >= crit.min_pairs))
    else:
        n_all = int(comparisons.loc[comparisons["dataset"] == "all", "n"].min())
        checks.append(("number of pairs", str(n_all), f">= {crit.min_pairs}", n_all >= crit.min_pairs))
        notes.append(
            f"no site column given: the Guide asks for at least {crit.min_comparisons} comparisons "
            f"of {crit.min_pairs} pairs each"
        )
    dataset_checks = pd.DataFrame(checks, columns=["requirement", "value", "required", "passed"])

    return PMEquivalence(
        criteria=crit,
        comparisons=comparisons,
        between_sampler=between,
        dataset_checks=dataset_checks,
        u_ref=float(u_ref),
        u_ref_source=u_ref_source,
        calibration=cal,
        notes=notes,
        _points=points,
    )
