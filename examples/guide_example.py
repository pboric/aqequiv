"""Evaluate one of the Guide's PM10 examples and draw the README figure."""

from pathlib import Path

import matplotlib.pyplot as plt

import aqequiv as aq

data = aq.load_example("pm10_locC_cm2")
raw = aq.evaluate_pm(data, "rm", "cm", "PM10", u_ref=1.5)
calibrated = aq.evaluate_pm(data, "rm", "cm", "PM10", u_ref=1.5, calibration="auto")

print(raw, calibrated, sep="\n\n")

fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.6), constrained_layout=True)
raw.plot(axes=axes[0])
calibrated.plot(axes=axes[1])
axes[0].set_title("As measured", fontsize=10)
axes[1].set_title("After slope calibration", fontsize=10)
fig.savefig(Path(__file__).parent.parent / "docs" / "example.png", dpi=130)
