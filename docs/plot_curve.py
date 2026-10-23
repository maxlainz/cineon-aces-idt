"""Regenerate docs/cineon_curve.svg from the generator's constants (needs matplotlib).

    python docs/plot_curve.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import cineon_idt as idt  # noqa: E402

GREY, COLORS = "#8b949e", {"LAD": "#e3b341", "Kodak": "#58a6ff"}
GREY_CODE = {"LAD": 445, "Kodak": 468}

code = np.linspace(96, 1023, 1024)
fig, ax = plt.subplots(figsize=(8, 4.2))
fig.patch.set_alpha(0)
ax.set_facecolor("none")
for name, (gain, _) in idt.VARIANTS.items():
    stops = np.log2(idt.cineon_to_linear(code / 1023, gain) / 0.18)
    ax.plot(code, stops, color=COLORS[name], lw=2, label=f"{name}: 18% grey at code {GREY_CODE[name]}")
    ax.plot(GREY_CODE[name], 0, "o", color=COLORS[name])
ax.axhline(0, color=GREY, lw=0.6, ls=":")
ax.annotate("ref. black 95\n→ linear 0", (185, -6.5), color=GREY, fontsize=10)
ax.annotate("ref. white 685\n→ linear 1.0 / 1.21", (470, 3.4), color=GREY, fontsize=10)
ax.annotate("1023\n→ linear 13.5 / 16.3", (740, 5.9), color=GREY, fontsize=10)
ax.set_xlabel("Cineon code value (10-bit)", color=GREY)
ax.set_ylabel("Stops relative to 18% grey", color=GREY)
ax.set_title("Cineon decode: code value → scene-linear, both variants", color=GREY, fontsize=12, loc="left")
ax.set_xlim(0, 1050)
ax.set_ylim(-7, 7.3)
ax.grid(color=GREY, alpha=0.25, lw=0.6)
ax.tick_params(colors=GREY, labelsize=11)
for s in ax.spines.values():
    s.set_visible(False)
ax.legend(loc="lower right", frameon=False, labelcolor=GREY, fontsize=10)
fig.tight_layout()
fig.savefig(ROOT / "docs" / "cineon_curve.svg")
fig.savefig("/private/tmp/claude-501/-Users-sala1macstudio-Documents-GitHub-MaxLainz-cineon-aces-idt/804218b5-2f0f-4f92-9cb2-0a96fab3b7a0/scratchpad/curve.png", dpi=110, facecolor="#0d1117")
