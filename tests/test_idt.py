import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import cineon_idt as idt  # noqa: E402

RNG = np.random.default_rng(1234)
SAMPLES = RNG.uniform(0.0, 1.0, (20000, 3))
VARIANTS = pytest.mark.parametrize("name", list(idt.VARIANTS))


def test_anchors():
    # Reference black (95) -> 0 in every variant; Kodak: 685 -> 1; LAD: 445 -> 0.18.
    for gain, _ in idt.VARIANTS.values():
        assert idt.cineon_to_linear(95 / 1023, gain) == pytest.approx(0.0, abs=1e-12)
    assert idt.cineon_to_linear(685 / 1023, idt.VARIANTS["Kodak"][0]) == pytest.approx(1.0, abs=1e-12)
    np.testing.assert_allclose(idt.cineon_to_aces2065(np.full(3, 445 / 1023), idt.VARIANTS["LAD"][0]), 0.18, atol=1e-9)


def test_neutral_axis_stays_neutral():
    # D65 white adapted to the ACES white must give R=G=B in both AP0 and AP1.
    for m in (idt.MATRIX_AP0, idt.MATRIX_AP1):
        np.testing.assert_allclose(m @ np.ones(3), np.ones(3), atol=1e-6)


def test_decode_matches_colour_science():
    colour = pytest.importorskip("colour")
    # colour's defaults are the same Kodak convention: 95/685, 0.002 D/code, gamma 0.6.
    np.testing.assert_allclose(colour.models.log_decoding_Cineon(SAMPLES), idt.cineon_to_linear(SAMPLES), rtol=1e-9, atol=1e-12)


def test_matrix_matches_colour_science():
    colour = pytest.importorskip("colour")
    m = colour.matrix_RGB_to_RGB(colour.RGB_COLOURSPACES["sRGB"], colour.RGB_COLOURSPACES["ACES2065-1"],
                                 chromatic_adaptation_transform="CAT02")
    # colour derives its whites with more decimals than the 4-digit xy used here: agreement is ~6e-5.
    np.testing.assert_allclose(m, idt.MATRIX_AP0, atol=1e-4)


def test_generated_files_up_to_date():
    assert idt.main(["--check"]) == 0


def _eval_clf(path, rgb):
    """Minimal CLF evaluator following the CLF 3 specification (OCIO is the independent check)."""
    root = ET.parse(path).getroot()
    x = np.asarray(rgb, dtype=np.float64)
    for node in root:
        if node.tag == "Log":
            assert node.get("style") == "logToLin"
            p = {k: float(v) for k, v in node.find("LogParams").attrib.items()}
            x = (p["base"] ** ((x - p["logSideOffset"]) / p["logSideSlope"]) - p["linSideOffset"]) / p["linSideSlope"]
        elif node.tag == "Matrix":
            m = np.array(node.find("Array").text.split(), dtype=np.float64).reshape(3, 3)
            x = x @ m.T
    return x


@VARIANTS
def test_clf_matches_reference(name):
    got = _eval_clf(idt.clf_path(name), SAMPLES)
    np.testing.assert_allclose(got, idt.cineon_to_aces2065(SAMPLES, idt.VARIANTS[name][0]), rtol=1e-8, atol=1e-9)


def _eval_dctl(path, rgb):
    """Read the DCTL constants and reproduce its arithmetic."""
    src = path.read_text()
    c = {k: float(v) for k, v in re.findall(r"const float (\w+)\s*=\s*([-\d.]+)f;", src)}
    rows = re.findall(r"const float \w+ = ([-\d.]+)f \* r \+ ([-\d.]+)f \* g \+ ([-\d.]+)f \* b;", src)
    m = np.array(rows, dtype=np.float64)
    assert m.shape == (3, 3)
    lin = (10.0 ** ((np.asarray(rgb) - c["logSideOffset"]) / c["logSideSlope"]) - c["linSideOffset"]) / c["linSideSlope"]
    return lin @ m.T


@VARIANTS
def test_dctl_matches_reference(name):
    assert "IS_PARAMETRIC_ACES_TRANSFORM: 0" in idt.dctl_path(name).read_text()
    got = _eval_dctl(idt.dctl_path(name), SAMPLES)
    np.testing.assert_allclose(got, idt.cineon_to_aces2065(SAMPLES, idt.VARIANTS[name][0]), rtol=1e-8, atol=1e-9)


@VARIANTS
def test_ocio_applies_clf(name):
    ocio = pytest.importorskip("PyOpenColorIO")
    cfg = ocio.Config.CreateRaw()
    proc = cfg.getProcessor(ocio.FileTransform(str(idt.clf_path(name)))).getDefaultCPUProcessor()
    img = SAMPLES.astype(np.float32).copy()
    proc.applyRGB(img)
    np.testing.assert_allclose(img, idt.cineon_to_aces2065(SAMPLES, idt.VARIANTS[name][0]), rtol=2e-5, atol=2e-6)
