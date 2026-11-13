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
