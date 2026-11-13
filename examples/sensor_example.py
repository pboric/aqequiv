"""Classify a simulated PM2.5 sensor system and draw its Modified Target Diagram.

The data are synthetic: three sensor systems at two sites that read 26 %
high, with some scatter. No public dataset with three replicate systems and
a reference method is bundled yet.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import aqequiv as aq

rng = np.random.default_rng(0)
frames = []
for site in ("A", "B"):
    true = rng.gamma(3.0, 7.0, 90)
    shared = rng.normal(0, 2.5, 90)
    frame = pd.DataFrame({"site": site, "ref": true + rng.normal(0, 0.5, 90)})
    for name in ("s1", "s2", "s3"):
        frame[name] = 1.5 + 1.26 * true + shared + rng.normal(0, 1.0, 90)
    frames.append(frame)
daily = pd.concat(frames, ignore_index=True)

raw = aq.evaluate_sensor(daily, "ref", ["s1", "s2", "s3"], "PM2.5", site="site", rh_factor=1.3)
corrected = aq.evaluate_sensor(
    daily, "ref", ["s1", "s2", "s3"], "PM2.5", site="site", rh_factor=1.3, correction="both"
)
print(raw, corrected, sep="\n\n")

one = daily[daily["site"] == "A"]
fig = aq.target_diagram(one["ref"], one["s1"], "PM2.5")
fig.savefig(Path(__file__).parent.parent / "docs" / "target_diagram.png", dpi=110)
