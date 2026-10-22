# cineon-aces-idt

[![CI](https://github.com/maxlainz/cineon-aces-idt/actions/workflows/ci.yml/badge.svg)](https://github.com/maxlainz/cineon-aces-idt/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/maxlainz/cineon-aces-idt)](https://github.com/maxlainz/cineon-aces-idt/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Bring Cineon film scans into an ACES pipeline the same way you bring in camera footage: pick an Input Transform and grade.**

ACES has Input Transforms for almost every digital camera, but none for the Cineon DPX scans most labs deliver. The closest built-in option, ADX10, expects scans calibrated to the Academy's own printing-density standard, so on a regular lab scan it usually looks wrong. This project fills that gap with an Input Transform for standard Kodak-style Cineon scans, for DaVinci Resolve and for anything that runs OpenColorIO (Nuke, Flame and others).

**[⬇ Download the latest release](https://github.com/maxlainz/cineon-aces-idt/releases/latest)**

| File | Use it in |
|---|---|
| `IDT_Cineon_Kodak.dctl` | **DaVinci Resolve**: appears in the ACES Input Transform list next to the built-in cameras |
| `Cineon_to_ACES2065-1.clf` | **Nuke, Flame, OpenColorIO configs**, or any tool that reads CLF |

## Is it for my footage?

**Use it** for 10-bit Cineon/DPX log scans from a film scanner set up the usual way, where the film base sits at code value 95 (the default on most lab scanners).

**Don't use it** for:
- Scans the lab calls **ADX** or **APD**. Use Resolve's built-in **ADX10** / **ADX16** Input Transform instead.
- Scans that are already linear (for example EXRs) or already converted to video (Rec.709).
- Scans where the film base was **not** removed. The transform expects the base at code 95; if it sits higher, blacks come out lifted.

## Install and use

### DaVinci Resolve

1. Download `IDT_Cineon_Kodak.dctl` from the [latest release](https://github.com/maxlainz/cineon-aces-idt/releases/latest).
2. Copy it into the `ACES Transforms/IDT` folder:
   - **macOS**: `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/ACES Transforms/IDT/`
   - **Windows**: `%AppData%\Blackmagic Design\DaVinci Resolve\Support\ACES Transforms\IDT\`
3. **Restart Resolve.** It only looks in that folder at startup.
4. In **Project Settings → Color Management**, set Color science to **ACEScct**.
5. Choose **IDT_Cineon_Kodak** as the Input Transform:
   - for the whole project, under **ACES Input Transform** in the same settings page, or
   - for some clips only: select them in the Media Pool, right-click → **ACES Input Transform → IDT_Cineon_Kodak**.
6. Check the clips are read as full range: right-click → **Clip Attributes → Data Level → Full**. DPX scans normally are.

Your scans now behave like any other ACES source. Pick your Output Transform (Rec.709, P3, …) as usual.

### Nuke

Add an **OCIOFileTransform** node right after the Read node, point **file** at `Cineon_to_ACES2065-1.clf`, and leave direction on **forward**. Tick **raw data** on the Read node so nothing else touches the scan. The output is linear ACES2065-1.

### OpenColorIO config (Flame, Nuke, Blender, Houdini, …)

For pipeline and color engineers: add a color space to your config, with the `.clf` in a folder from the config's `search_path`. This assumes the config's scene reference is ACES2065-1, as in the official ACES configs.

```yaml
  - !<ColorSpace>
    name: Cineon (Kodak)
    family: Input
    encoding: log
    to_scene_reference: !<FileTransform> {src: Cineon_to_ACES2065-1.clf}
```

## What it does

![Pipeline: Cineon scan, Kodak decode to scene-linear Rec.709, 3×3 matrix with CAT02 to ACES2065-1](docs/pipeline.svg)

It does two things, in this order:

1. **Turns the log scan into linear light** using the standard Kodak Cineon conversion, the same one behind "Cineon log to linear" nodes in Nuke and other compositors. The film base (code 95) becomes black, code 685 becomes diffuse white, and 18% grey lands at about code 468. It assumes the contrast of a generic negative (gamma 0.6); real stocks differ slightly, and per channel.
2. **Converts the colors into ACES.** Film scans don't come with defined color primaries the way cameras do, so the transform treats them as Rec.709, the usual convention, and converts that to ACES with a proper white-point adaptation. The result is a plausible, neutral starting point, not a measured match to the film.

![Cineon decode curve: code value against stops relative to 18% grey](docs/cineon_curve.svg)

The curve shows how much room there is: everything from the film base up to code 1023 is kept, which is about **6 stops above middle grey**. Nothing is clipped at either end, so highlight and shadow detail are all there to grade with.

## Technical details

For color engineers who want to check the numbers.

**Decode** (Kodak Cineon: reference black 95, reference white 685, 0.002 density per code value, negative gamma 0.6), with `v` the code value normalised to 0–1:

```
lin = (10^((1023·v − 685)·0.002/0.6) − k) / (1 − k),   k = 10^((95 − 685)·0.002/0.6)
```

In the CLF this is a single `Log` op (`logToLin`) with `logSideSlope = 0.6/(0.002·1023)`, `logSideOffset = 685/1023`, `linSideOffset = k`, `linSideSlope = 1 − k`. The DCTL uses the same constants.

**Matrix**: linear Rec.709/D65 → ACES2065-1 (AP0), CAT02 adaptation to the ACES white, derived from the published primaries:

```
0.4395756842 0.3839125893 0.1765117265
0.0896003829 0.8147141542 0.0956854629
0.0174154827 0.1087343522 0.8738501650
```

**About the files.** The `.clf` uses the Academy's [Common LUT Format](https://docs.acescentral.com/specifications/clf/), which stores the math itself rather than a sampled LUT, so it is exact at every value and needs no shaper. The `.dctl` is a non-parametric ACES DCTL (`DEFINE_ACES_PARAM(IS_PARAMETRIC_ACES_TRANSFORM: 0)`), which is what makes Resolve list it as an Input Transform instead of a node LUT.

**Verification.** Both files are generated from one Python reference, [`tools/cineon_idt.py`](tools/cineon_idt.py), and CI checks on every change that:
- code 95 decodes to 0 and code 685 to 1;
- a neutral input stays neutral (R = G = B) in ACES;
- the CLF, read by an independent evaluator and by OpenColorIO, matches the reference on 20,000 random samples;
- the DCTL's constants and arithmetic match the reference;
- the committed files match the generator.

The DCTL was also tested in **DaVinci Resolve Studio 21.1.1**. A 144-patch chart rendered through it matched the reference to within 0.0000078, which is the rounding of the 16-bit output file.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python tools/cineon_idt.py           # regenerate transforms/
.venv/bin/python tools/cineon_idt.py --check   # fail if transforms/ is out of date
.venv/bin/pytest -v
```

To change the transform, edit the constants in `tools/cineon_idt.py`, regenerate, and commit the generator and the generated files together.

## License

[MIT](LICENSE). Free to use, modify and redistribute, including commercially.
