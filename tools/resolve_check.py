"""Reproducible check of the DCTL inside DaVinci Resolve.

1. python tools/resolve_check.py chart chart.tiff
   Writes a 16-bit TIFF test chart (12x12 patches of Cineon codes) and chart.json with the codes.
2. In Resolve: ACEScct project, ACES Input Transform = the variant under test, Output Transform =
   "No Output Transform", gamut compression off. Import chart.tiff, render it as 16-bit TIFF,
   same resolution. The render then holds linear ACES2065-1 clipped to 0..1.
3. python tools/resolve_check.py compare render.tiff chart.json --variant LAD
   Prints the max error against the reference; exits 1 if it exceeds 1e-4.

Codes stay in 95..660 so every output lands in 0..1 and survives the integer render.
"""
import argparse
import json
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cineon_idt as idt  # noqa: E402

GRID, PATCH = 12, 80
CODE_MIN, CODE_MAX = 95, 660


def make_chart(seed=1234):
    """(codes[GRID, GRID, 3] as the 16-bit values written, 16-bit RGB image)."""
    codes = np.random.default_rng(seed).integers(CODE_MIN, CODE_MAX + 1, (GRID, GRID, 3))
    codes[0, 0] = 445  # LAD grey in the first patch, easy to eyeball
    codes = np.rint(codes / 1023.0 * 65535.0).astype(np.uint16)  # what the file holds, so the reference is exact
    return codes, np.repeat(np.repeat(codes, PATCH, axis=0), PATCH, axis=1)


def patch_means(img):
    """Mean of the central half of each patch, for any resolution with the same aspect."""
    h, w = img.shape[0] // GRID, img.shape[1] // GRID
    cells = img[: h * GRID, : w * GRID].reshape(GRID, h, GRID, w, -1)
    return cells[:, h // 4: -(h // 4) or None, :, w // 4: -(w // 4) or None].mean(axis=(1, 3))


def compare(render, codes, variant):
    got = patch_means(np.asarray(render, dtype=np.float64) / 65535.0)
    want = idt.cineon_to_aces2065(codes / 65535.0, idt.VARIANTS[variant][0])
    return np.abs(got - want).max()


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chart"); c.add_argument("tiff")
    k = sub.add_parser("compare"); k.add_argument("render"); k.add_argument("json")
    k.add_argument("--variant", choices=list(idt.VARIANTS), default="LAD")
    k.add_argument("--tolerance", type=float, default=1e-4)
    a = ap.parse_args(argv)
    if a.cmd == "chart":
        codes, img = make_chart()
        iio.imwrite(a.tiff, img)
        Path(a.tiff).with_suffix(".json").write_text(json.dumps(codes.tolist()))
        print("wrote", a.tiff, "and", Path(a.tiff).with_suffix(".json"))
        return 0
    render = iio.imread(a.render)
    if render.dtype != np.uint16:
        sys.exit(f"expected a 16-bit render, got {render.dtype}")
    err = compare(render[..., :3], np.array(json.loads(Path(a.json).read_text())), a.variant)
    print(f"{a.variant}: max error {err:.2e} (tolerance {a.tolerance:.0e})")
    return 0 if err <= a.tolerance else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
