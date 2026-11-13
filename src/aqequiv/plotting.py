"""Scatter plot of candidate against reference results."""

from __future__ import annotations

import numpy as np


def plot_equivalence(result, *, axes=None):
    """Draw one panel per candidate instrument for the full dataset.

    Returns the matplotlib figure.
    """
    import matplotlib.pyplot as plt

    crit = result.criteria
    names = list(result._points)
    if axes is None:
        fig, axes = plt.subplots(
            1, len(names), figsize=(4.6 * len(names), 4.6), squeeze=False, constrained_layout=True
        )
        axes = axes[0]
    else:
        axes = np.atleast_1d(axes)
        fig = axes[0].figure

    for ax, name in zip(axes, names):
        x, y, comp = result._points[name]
        fit = comp.fit
        top = 1.05 * max(x.max(), y.max(), crit.limit_value)
        line = np.array([0.0, top])

        ax.plot(line, line, color="0.6", lw=1, ls="--", label="1:1")
        ax.axvline(crit.limit_value, color="0.8", lw=1)
        ax.axhline(crit.limit_value, color="0.8", lw=1)
        ax.scatter(x, y, s=14, alpha=0.6, edgecolor="none")
        ax.plot(line, fit.predict(line), color="C3", lw=1.5, label="orthogonal fit")

        sign = "+" if fit.intercept >= 0 else "−"
        verdict = "pass" if comp.passed else "fail"
        ax.text(
            0.04, 0.96,
            f"y = {fit.slope:.3f}x {sign} {abs(fit.intercept):.2f}\n"
            f"n = {fit.n}, r² = {fit.r2:.3f}\n"
            f"W = {100 * comp.w_expanded:.1f}% at {crit.limit_value:g} µg/m³ ({verdict})",
            transform=ax.transAxes, va="top", fontsize=9,
        )
        ax.set(
            xlim=(0, top), ylim=(0, top), aspect="equal",
            xlabel=f"Reference {crit.pollutant} (µg/m³)",
            ylabel=f"{name}{' calibrated' if result.calibration else ''} (µg/m³)",
        )
        ax.legend(loc="lower right", fontsize=8, frameon=False)
    return fig


def plot_sensor(result):
    """Draw one panel per site (row) and sensor system (column).

    Returns the matplotlib figure.
    """
    import matplotlib.pyplot as plt

    crit = result.criteria
    sites = list(dict.fromkeys(site for site, _ in result._points))
    sensors = list(dict.fromkeys(sensor for _, sensor in result._points))
    fig, axes = plt.subplots(
        len(sites), len(sensors), figsize=(3.6 * len(sensors), 3.6 * len(sites)),
        squeeze=False, constrained_layout=True, sharex=True, sharey=True,
    )
    top = 1.05 * max(
        [crit.limit_value] + [max(x.max(), y.max()) for x, y, *_ in result._points.values()]
    )
    line = np.array([0.0, top])

    for i, site in enumerate(sites):
        for j, sensor in enumerate(sensors):
            ax = axes[i, j]
            if (site, sensor) not in result._points:
                ax.set_axis_off()
                continue
            x, y, fu, u_lv, rank = result._points[(site, sensor)]
            fit = fu.fit
            ax.plot(line, line, color="0.6", lw=1, ls="--")
            ax.axvline(crit.limit_value, color="0.8", lw=1)
            ax.scatter(x, y, s=12, alpha=0.6, edgecolor="none")
            ax.plot(line, fit.predict(line), color="C3", lw=1.5)
            sign = "+" if fit.intercept >= 0 else "−"
            label = "no class" if rank > 3 else f"Class {rank}"
            ax.text(
                0.04, 0.96,
                f"y = {fit.slope:.2f}x {sign} {abs(fit.intercept):.1f}\n"
                f"R² = {fit.r2:.2f}, n = {fit.n}\n"
                f"U = {u_lv:.1f} µg/m³ ({label})",
                transform=ax.transAxes, va="top", fontsize=8,
            )
            ax.set(xlim=(0, top), ylim=(0, top), aspect="equal")
            ax.set_title(f"{site} · {sensor}", fontsize=9)
            if i == len(sites) - 1:
                ax.set_xlabel(f"Reference {crit.pollutant} (µg/m³)")
            if j == 0:
                ax.set_ylabel(f"Sensor{' corrected' if result.correction else ''} (µg/m³)")
    return fig


def _draw_target(ax, fu, x, crit, *, colorbar=True):
    """Draw one Modified Target Diagram on ``ax``; return the line collection."""
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    lv = crit.limit_value
    radii = [100 * d / lv for d in crit.dqo]
    extent = 1.15 * radii[-1]

    # target circles: the class limits as a share of the limit value
    theta = np.linspace(-np.pi / 2, np.pi / 2, 181)
    for k, r in enumerate(radii, start=1):
        ax.plot(r * np.cos(theta), r * np.sin(theta), color="0.55", lw=1)
        ax.annotate(
            f"Class {k}: {r:g} %", (r * np.cos(-1.15), r * np.sin(-1.15)), fontsize=7,
            color="0.35", ha="left", va="top", xytext=(2, -2), textcoords="offset points",
        )
    ax.axhline(0, color="0.8", lw=0.8)

    # the curve: one point per concentration, from the lowest to the highest reference value
    lo = max(float(np.min(x)), 0.02 * lv)
    levels = np.geomspace(lo, max(float(np.max(x)), lv), 300)
    rr, rb = (100 * v for v in fu.relative_components(levels))
    pts = np.column_stack([rr, rb]).reshape(-1, 1, 2)
    cmap = LinearSegmentedColormap.from_list("conc", ["#b7d3ec", "#1f5fa8", "#0b2545"])
    lc = LineCollection(
        np.concatenate([pts[:-1], pts[1:]], axis=1), cmap=cmap,
        norm=Normalize(levels[0], levels[-1]), linewidth=2.5, capstyle="round",
    )
    lc.set_array(levels[:-1])
    ax.add_collection(lc)

    # contribution of the slope alone: the curve tends to it at high concentrations
    slope_part = 200 * (fu.fit.slope - 1.0)
    ax.axhline(slope_part, color="0.45", lw=0.8, ls=":")
    ax.annotate(
        "slope only", (extent, slope_part), fontsize=7, color="0.35",
        ha="right", va="bottom", xytext=(-2, 1), textcoords="offset points",
    )

    marks = [("LV", lv), ("UAT", crit.upper_assessment_threshold), ("LAT", crit.lower_assessment_threshold)]
    offsets = {"LV": (9, -12), "UAT": (11, -3), "LAT": (9, 7)}
    for label, level in marks:
        if level is None:
            continue
        mr, mb = (100 * float(v) for v in fu.relative_components(level))
        ax.plot(mr, mb, "o", ms=6.5, mfc="white" if label != "LV" else "0.1", mec="0.1", mew=1.2, zorder=3)
        ax.annotate(f"{label} {level:g}", (mr, mb), fontsize=7.5, xytext=offsets[label], textcoords="offset points")

    ax.set(xlim=(0, extent), ylim=(-extent, extent), aspect="equal")
    if colorbar:
        ax.figure.colorbar(lc, ax=ax, shrink=0.8, pad=0.02, label="Reference concentration (µg/m³)")
    return lc


def target_diagram(x, y, pollutant: str = "PM2.5", *, u_ref: float | None = None, criteria=None, ax=None):
    """Modified Target Diagram of sensor results ``y`` against reference results ``x``.

    The horizontal axis is the relative random part of the expanded
    uncertainty and the vertical axis the relative bias, both evaluated along
    the range of reference concentrations (Yatkin et al., 2022). The distance
    of a point from the origin is the relative expanded uncertainty at that
    concentration; the circles are the class limits. Returns the figure.
    """
    import matplotlib.pyplot as plt

    from . import sensors

    if criteria is None:
        criteria = sensors._CRITERIA[pollutant.upper().replace(",", ".")]
    fu = sensors.field_uncertainty(x, y, u_ref=sensors.DEFAULT_REFERENCE_UBS if u_ref is None else u_ref)
    if ax is None:
        _, ax = plt.subplots(figsize=(5.2, 6.4), constrained_layout=True)
    _draw_target(ax, fu, np.asarray(x, dtype=float)[np.isfinite(np.asarray(x, dtype=float))], criteria)
    ax.set_xlabel("Relative random uncertainty (%)")
    ax.set_ylabel("Relative bias (%)")
    ax.set_title(f"{criteria.pollutant}: relative expanded uncertainty by concentration", fontsize=10)
    return ax.figure


def plot_target_grid(result):
    """Modified Target Diagrams, one panel per site (row) and sensor system (column)."""
    import matplotlib.pyplot as plt

    crit = result.criteria
    sites = list(dict.fromkeys(site for site, _ in result._points))
    names = list(dict.fromkeys(sensor for _, sensor in result._points))
    fig, axes = plt.subplots(
        len(sites), len(names), figsize=(3.0 * len(names) + 0.8, 5.0 * len(sites)),
        squeeze=False, constrained_layout=True, sharex=True, sharey=True,
    )
    lc = None
    for i, site in enumerate(sites):
        for j, name in enumerate(names):
            ax = axes[i, j]
            if (site, name) not in result._points:
                ax.set_axis_off()
                continue
            x, _, fu, _, _ = result._points[(site, name)]
            lc = _draw_target(ax, fu, x, crit, colorbar=False)
            ax.set_title(f"{site} · {name}", fontsize=9)
            if i == len(sites) - 1:
                ax.set_xlabel("Relative random uncertainty (%)")
            if j == 0:
                ax.set_ylabel("Relative bias (%)")
    if lc is not None:
        fig.colorbar(lc, ax=axes, shrink=0.6, pad=0.02, label="Reference concentration (µg/m³)")
    return fig
