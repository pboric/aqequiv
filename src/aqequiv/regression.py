"""Orthogonal regression as defined in Annex B of the 2010 Guide."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OrthogonalFit:
    """Result of an orthogonal regression ``y = intercept + slope * x``."""

    slope: float
    intercept: float
    u_slope: float
    u_intercept: float
    n: int
    rss: float
    r2: float

    @property
    def slope_significant(self) -> bool:
        """True if the slope differs from 1 by more than twice its uncertainty."""
        return abs(self.slope - 1.0) > 2.0 * self.u_slope

    @property
    def intercept_significant(self) -> bool:
        """True if the intercept differs from 0 by more than twice its uncertainty."""
        return abs(self.intercept) > 2.0 * self.u_intercept

    def predict(self, x):
        return self.intercept + self.slope * np.asarray(x, dtype=float)


def paired(x, y) -> tuple[np.ndarray, np.ndarray]:
    """Return x and y as float arrays with incomplete pairs removed."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.shape != y.shape:
        raise ValueError(f"x and y differ in length ({x.size} vs {y.size})")
    keep = np.isfinite(x) & np.isfinite(y)
    return x[keep], y[keep]


def orthogonal_regression(x, y, *, through_origin: bool = False) -> OrthogonalFit:
    """Fit ``y = a + b*x`` treating both variables symmetrically.

    Implements equations B.1-B.9 of the Guide, or B.10-B.14 when
    ``through_origin`` is True (``y = b*x``). Pairs with a missing value
    are ignored.
    """
    x, y = paired(x, y)
    n = x.size
    if n < 3:
        raise ValueError(f"orthogonal regression needs at least 3 pairs, got {n}")

    if through_origin:
        xm = ym = 0.0
        dof = n - 1
    else:
        xm, ym = x.mean(), y.mean()
        dof = n - 2

    sxx = np.sum((x - xm) ** 2)
    syy = np.sum((y - ym) ** 2)
    sxy = np.sum((x - xm) * (y - ym))
    if sxx == 0 or sxy == 0:
        raise ValueError("x has no spread, or x and y are uncorrelated")

    slope = (syy - sxx + np.sqrt((syy - sxx) ** 2 + 4 * sxy**2)) / (2 * sxy)
    intercept = ym - slope * xm
    u_slope = np.sqrt(max(syy - sxy**2 / sxx, 0.0) / (dof * sxx))
    u_intercept = 0.0 if through_origin else np.sqrt(u_slope**2 * np.sum(x**2) / n)
    rss = np.sum((y - intercept - slope * x) ** 2)
    r2 = np.corrcoef(x, y)[0, 1] ** 2

    return OrthogonalFit(
        slope=float(slope),
        intercept=float(intercept),
        u_slope=float(u_slope),
        u_intercept=float(u_intercept),
        n=int(n),
        rss=float(rss),
        r2=float(r2),
    )
