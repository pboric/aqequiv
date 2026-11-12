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
