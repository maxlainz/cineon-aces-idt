import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import cineon_idt as idt  # noqa: E402

pytest.importorskip("imageio")
import resolve_check as rc  # noqa: E402


@pytest.mark.parametrize("name", list(idt.VARIANTS))
def test_chart_round_trip(name):
    # Simulate Resolve: apply the reference to the chart, quantise to 16 bits, compare.
    codes, img = rc.make_chart()
    lin = idt.cineon_to_aces2065(img / 65535.0, idt.VARIANTS[name][0])
    assert lin.min() >= 0 and lin.max() <= 1, "chart codes must keep the render inside 0..1"
    render = np.rint(lin * 65535.0).astype(np.uint16)
    assert rc.compare(render, codes, name) < 2e-5
    # The wrong variant is clearly detected (0.27 stops apart).
    other = next(n for n in idt.VARIANTS if n != name)
    assert rc.compare(render, codes, other) > 1e-2
