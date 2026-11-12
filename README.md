# aqequiv

Equivalence testing of ambient air monitoring methods in Python.

`aqequiv` implements the particulate matter procedure of the European
Commission's *Guide to the Demonstration of Equivalence of Ambient Air
Monitoring Methods* (January 2010, clauses 9.5–9.7 and Annex B). It takes
paired daily results from a candidate method and the reference method and
tells you whether the candidate meets the 25 % data quality objective.

The calculation is usually done in a spreadsheet. This package makes it
scriptable, testable and repeatable.

![Example: a candidate before and after slope calibration](docs/example.png)

## Install

```bash
pip install git+https://github.com/pboric/aqequiv
```

Requires Python 3.10 or newer, with numpy, pandas and matplotlib.

## Quick start

```python
import pandas as pd
import aqequiv as aq

data = pd.read_csv("campaigns.csv")   # one row per 24-hour period

result = aq.evaluate_pm(
    data,
    reference=["ref_1", "ref_2"],     # one or two reference samplers
    candidate=["cand_1", "cand_2"],   # one or two candidate instruments
    pollutant="PM10",                 # or "PM2.5"
    site="campaign",                  # optional: column naming each comparison
)

print(result)            # full text report
result.comparisons       # regression and uncertainty per candidate and dataset
result.between_sampler   # between-sampler uncertainties
result.dataset_checks    # is the dataset large and varied enough?
result.passed            # True if every uncertainty criterion is met
result.plot()            # scatter plot per candidate
```

If the slope or intercept is significant, calibrate and test again:

```python
calibrated = aq.evaluate_pm(data, ["ref_1", "ref_2"], ["cand_1", "cand_2"],
                            "PM10", site="campaign", calibration="auto")
calibrated.calibration                 # e.g. y_cal = (y - 1.204) / 0.871
calibrated.calibration.apply(values)   # apply it to new data
```

To try it without your own data, load one of the Guide's examples:

```python
data = aq.load_example("pm10_locC_cm2")
print(aq.evaluate_pm(data, "rm", "cm", "PM10", u_ref=1.5, calibration="auto"))
```

## What it calculates

| Step | Guide | Criterion |
|---|---|---|
| Between-sampler uncertainty of the reference method | eq. 9.4 | ≤ 2.0 µg/m³ |
| Between-sampler uncertainty of the candidate: all data, and above and below the split concentration | eq. 9.4 | ≤ 2.5 µg/m³ |
| Orthogonal regression of each candidate against the reference | Annex B | slope and intercept tested against 1 and 0 |
| Expanded relative uncertainty at the limit value: full dataset, high-concentration subset (if ≥ 40 pairs), each site | eq. 9.6–9.9 | ≤ 25 % |
| Calibration by intercept, slope or both, with the added uncertainty | eq. 9.10–9.19 | re-tested as above |
| Dataset suitability: share of results above the upper assessment threshold, number of comparisons, pairs per comparison | 9.4.2, 9.5.2 | ≥ 20 %, ≥ 4, ≥ 40 |

| | PM10 | PM2.5 |
|---|---|---|
| Concentration at which the uncertainty is evaluated | 50 µg/m³ | 30 µg/m³ |
| Split between low and high concentrations | 30 µg/m³ | 18 µg/m³ |
| Upper assessment threshold | 28 µg/m³ | 17 µg/m³ |

These are the values of the 2010 Guide. Pass your own `PMCriteria` to
`evaluate_pm` to change them.

The building blocks are available on their own: `orthogonal_regression`,
`between_sampler_uncertainty` and `comparability`.

## Validation

The test suite reproduces the five worked examples in Annex F of the Guide
(PM2.5 and PM10, before and after calibration) to the precision the Guide
prints. The example data ship with the package.

Two things to know when comparing with the Guide:

- **Reference uncertainty.** Clause 9.5.3.2 says the uncertainty of the
  reference results may be taken as the reference between-sampler
  uncertainty divided by √2. The Annex F examples use the between-sampler
  uncertainty itself. `aqequiv` follows the clause by default; pass `u_ref`
  to choose another value.
- **Printed uncertainty.** Annex F prints the combined relative uncertainty.
  `aqequiv` reports the expanded one (`W_pct`, coverage factor 2), which is
  the number compared with the 25 % objective.

## Limitations

- Particulate matter only. Gases and sensor systems (CEN/TS 17660) are
  planned.
- Outliers are not removed for you. The Guide allows removing up to 2.5 %
  of data pairs; do that before calling `evaluate_pm`.
- Calibration through the origin (eq. 9.11a–9.15a) is not wired into
  `evaluate_pm`; `orthogonal_regression(..., through_origin=True)` gives the
  fit.
- This is an independent implementation, not an official tool. Check the
  results before using them in a formal equivalence report.

## Development

```bash
uv sync
uv run pytest
uv run python examples/guide_example.py   # regenerates docs/example.png
```

## Reference

EC Working Group on Guidance for the Demonstration of Equivalence. *Guide to
the Demonstration of Equivalence of Ambient Air Monitoring Methods.*
January 2010.

## Licence

MIT
