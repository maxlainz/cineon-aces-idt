# cineon-aces-idt

[![CI](https://github.com/maxlainz/cineon-aces-idt/actions/workflows/ci.yml/badge.svg)](https://github.com/maxlainz/cineon-aces-idt/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/maxlainz/cineon-aces-idt)](https://github.com/maxlainz/cineon-aces-idt/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An **ACES Input Transform for Cineon film scans** (Kodak convention) to **ACES2065-1**, shipped in two formats:

| File | Format | Use it in |
|---|---|---|
| [`Cineon_to_ACES2065-1.clf`](transforms/Cineon_to_ACES2065-1.clf) | Common LUT Format (CLF 3) | OpenColorIO 2.x, Nuke, Flame, any tool that reads CLF |
| [`IDT_Cineon_Kodak.dctl`](transforms/IDT/IDT_Cineon_Kodak.dctl) | ACES DCTL for DaVinci Resolve | Resolve's ACES color management, as one more Input Transform |

**[Download the latest release](https://github.com/maxlainz/cineon-aces-idt/releases/latest)**

## Why

ACES ships no Input Transform for Cineon scans. The closest one, ADX10, assumes scans calibrated to the Academy's printing density (APD) and inverts the negative with its own curves, so it doesn't match most "Cineon" scans that come out of a lab. This transform does the conventional Kodak decode instead, and lands it in ACES2065-1 the way any camera IDT would.

## What it does

Two steps: decode the Cineon log curve to scene-linear, then convert Rec.709 primaries to ACES AP0.

![Cineon decode curve: code value against stops relative to 18% grey](docs/cineon_curve.svg)

**1. Cineon decode** (Kodak convention: reference black 95, reference white 685, 0.002 density per code value, negative gamma 0.6):

```
lin = (10^((1023·v − 685)·0.002/0.6) − k) / (1 − k),   k = 10^((95 − 685)·0.002/0.6)
```

Code 95 maps to 0, code 685 to 1.0, 18% grey sits at about code 468, and code 1023 reaches linear 13.5 (about 6 stops above grey). In the CLF this is a single `Log` op in `logToLin` style, with `logSideSlope = 0.6/(0.002·1023)`, `logSideOffset = 685/1023`, `linSideOffset = k` and `linSideSlope = 1 − k`.

**2. Rec.709/D65 → AP0 matrix**, with **CAT02** chromatic adaptation to the ACES white point:

```
0.4395756842 0.3839125893 0.1765117265
0.0896003829 0.8147141542 0.0956854629
0.0174154827 0.1087343522 0.8738501650
```

It is derived from the published Rec.709 and ACES primaries, and targets AP0, which is what an IDT must produce.

## The two files

### CLF: `Cineon_to_ACES2065-1.clf`

The [Common LUT Format](https://docs.acescentral.com/specifications/clf/) is the Academy's open XML format for describing color transforms. Unlike a baked 3D LUT, a CLF stores the actual math, here one `Log` op and one `Matrix` op, so it is exact at every input value, keeps values above 1.0 and needs no shaper. Any tool built on OpenColorIO 2.x can read it.

**OpenColorIO**: add a color space to your config whose `to_scene_reference` is a `FileTransform` pointing at the file:

```yaml
  - !<ColorSpace>
    name: Cineon (Kodak)
    family: Input
    encoding: log
    to_scene_reference: !<FileTransform> {src: Cineon_to_ACES2065-1.clf}
```

Put the `.clf` in a folder listed in the config's `search_path`. This assumes your config's scene reference is ACES2065-1, as in the ACES reference configs.

**Nuke**: use an `OCIOFileTransform` node, set `file` to the `.clf` and direction to `forward`. Its output is linear ACES2065-1.

### DCTL: `IDT_Cineon_Kodak.dctl`

A DCTL is DaVinci Resolve's GPU shader format for color transforms. This one is a non-parametric **ACES DCTL** (`DEFINE_ACES_PARAM(IS_PARAMETRIC_ACES_TRANSFORM: 0)`): Resolve treats it as an ACES Input Transform and lists it next to the built-in ones, instead of as a LUT you apply on a node.

**Install**

1. Copy `IDT_Cineon_Kodak.dctl` into Resolve's `ACES Transforms/IDT` folder:
   - macOS: `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/ACES Transforms/IDT/`
   - Windows: `%AppData%\Blackmagic Design\DaVinci Resolve\Support\ACES Transforms\IDT\`
2. Restart Resolve. It only scans that folder at startup.

**Use**

1. Project Settings → Color Management → set Color science to **ACEScct** (or ACEScc).
2. Pick **IDT_Cineon_Kodak** as the ACES Input Transform, either:
   - for the whole project, in Project Settings → Color Management → ACES Input Transform, or
   - per clip, in the Media Pool: right-click the clip → ACES Input Transform.

Make sure the clips are read as **full range** (clip attributes → Data Level → Full), as Cineon/DPX scans normally are.

## Limitations (read these)

- **It is not colorimetric.** Printing density has no primaries. Treating it as Rec.709 is a convention, not a measurement, so color will be plausible, not exact.
- **The 0.6 gamma is a generic negative's.** Every stock has its own, and it differs per channel. Mid-tones line up; shadows and highlights only approximately.
- **Black at 95 assumes the scanner already removed the film base.** If it didn't, the offset needs adjusting per roll or per stock.
- **Below code 95 the output goes negative.** It is not clipped, on purpose, so no data is lost.

## Verification

`tools/cineon_idt.py` is the **single source of truth**: it defines the decode and the matrix and generates both files, which are never edited by hand. CI runs these tests on every push:

| Test | Checks |
|---|---|
| `test_anchors` | 95 → 0 and 685 → 1 |
| `test_neutral_axis_stays_neutral` | adapted D65 white comes out R = G = B in AP0 and AP1 |
| `test_generated_files_up_to_date` | `transforms/` matches the generator |
| `test_clf_matches_reference` | an independent CLF evaluator (per the CLF 3 spec) reproduces the reference on 20,000 samples |
| `test_dctl_matches_reference` | the DCTL's constants and arithmetic reproduce the reference |
| `test_ocio_applies_clf` | OpenColorIO loads and applies the CLF and matches the reference (relative error ≤ 3e-5, float32) |

The DCTL was also checked inside **DaVinci Resolve Studio 21.1.1**: it compiles, shows up as an ACES Input Transform, and a rendered 144-patch test chart (ACEScct project, no output transform, no gamut compression) matched the reference to within 7.8e-6, which is the rounding of the 16-bit output file.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python tools/cineon_idt.py           # regenerate transforms/
.venv/bin/python tools/cineon_idt.py --check   # fail if transforms/ is out of date
.venv/bin/pytest -v
```

To change the transform, edit the constants in `tools/cineon_idt.py`, regenerate, and commit the generator and the generated files together.

## License

[MIT](LICENSE)
