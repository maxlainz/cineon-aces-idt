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
# Code where each variant puts 18% grey (inverse of the decode), and its linear value at 685 and 1023.
GREY_CODE = {n: round(idt.REF_WHITE + np.log10(0.18 / g * (1 - idt.BLACK_OFFSET) + idt.BLACK_OFFSET)
                      * idt.NEG_GAMMA / idt.DENSITY_PER_CODE) for n, (g, _) in idt.VARIANTS.items()}
AT_WHITE = " / ".join(str(round(float(idt.cineon_to_linear(685 / 1023, g)), 2)) for g, _ in idt.VARIANTS.values())
AT_MAX = " / ".join(str(round(float(idt.cineon_to_linear(1.0, g)), 1)) for g, _ in idt.VARIANTS.values())

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
ax.annotate(f"ref. white 685\n→ linear {AT_WHITE}", (470, 3.4), color=GREY, fontsize=10)
ax.annotate(f"1023\n→ linear {AT_MAX}", (740, 5.9), color=GREY, fontsize=10)
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
