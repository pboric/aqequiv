"""Open the application with simulated data and save a picture of its window.

Used by the Windows build to produce docs/app.png. Usage: screenshot.py OUT.png
"""

import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
from PIL import ImageGrab

from aqequiv import app

rng = np.random.default_rng(0)
frames = []
for site, start in (("A", "2025-01-10"), ("B", "2025-06-10")):
    true = rng.gamma(3.0, 7.0, 90)
    shared = rng.normal(0, 2.5, 90)
    frame = pd.DataFrame({
        "date": pd.date_range(start, periods=90).strftime("%Y-%m-%d"),
        "site": site,
        "ref": (true + rng.normal(0, 0.5, 90)).round(1),
    })
    for name in ("s1", "s2", "s3"):
        frame[name] = (1.5 + 1.26 * true + shared + rng.normal(0, 1.0, 90)).round(1)
    frames.append(frame)
data = Path(tempfile.mkdtemp()) / "daily.csv"
pd.concat(frames).to_csv(data, index=False, sep=";", decimal=",")

window = app.build_window()
window.geometry("1180x700+40+40")
window.open_file(str(data))
window.reference.selection_set(0)
window.tested.selection_set(1, 3)
window.site.set("site")
window.adjustment.set("both")
window.entries["rh_factor"][1].insert(0, "1,3")
window.run()


def grab():
    window.update()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    box = (x, y, x + window.winfo_width(), y + window.winfo_height())
    ImageGrab.grab(bbox=box).save(sys.argv[1])
    window.destroy()


window.attributes("-topmost", True)
window.after(1500, grab)
window.mainloop()
