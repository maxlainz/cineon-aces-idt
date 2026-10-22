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


def test_anchors():
    # Reference black (95) -> 0, reference white (685) -> 1.
    assert idt.cineon_to_linear(95 / 1023) == pytest.approx(0.0, abs=1e-12)
    assert idt.cineon_to_linear(685 / 1023) == pytest.approx(1.0, abs=1e-12)


def test_neutral_axis_stays_neutral():
    # D65 white adapted to the ACES white must give R=G=B in both AP0 and AP1.
    for m in (idt.MATRIX_AP0, idt.MATRIX_AP1):
        np.testing.assert_allclose(m @ np.ones(3), np.ones(3), atol=1e-6)


def test_generated_files_up_to_date():
    assert idt.main(["--check"]) == 0


def _eval_clf(path, rgb):
    """Minimal, independent CLF evaluator following the CLF 3 specification."""
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


def test_clf_matches_reference():
    got = _eval_clf(idt.CLF_PATH, SAMPLES)
    np.testing.assert_allclose(got, idt.cineon_to_aces2065(SAMPLES), rtol=1e-8, atol=1e-9)


def _eval_dctl(path, rgb):
    """Read the DCTL constants and reproduce its arithmetic."""
    src = path.read_text()
    c = {k: float(v) for k, v in re.findall(r"const float (\w+)\s*=\s*([-\d.]+)f;", src)}
    rows = re.findall(r"const float \w+ = ([-\d.]+)f \* r \+ ([-\d.]+)f \* g \+ ([-\d.]+)f \* b;", src)
    m = np.array(rows, dtype=np.float64)
    assert m.shape == (3, 3)
    lin = (10.0 ** ((np.asarray(rgb) - c["logSideOffset"]) / c["logSideSlope"]) - c["linSideOffset"]) / c["linSideSlope"]
    return lin @ m.T


def test_dctl_matches_reference():
    assert "IS_PARAMETRIC_ACES_TRANSFORM: 0" in idt.DCTL_PATH.read_text()
    got = _eval_dctl(idt.DCTL_PATH, SAMPLES)
    np.testing.assert_allclose(got, idt.cineon_to_aces2065(SAMPLES), rtol=1e-8, atol=1e-9)


def test_ocio_applies_clf():
    ocio = pytest.importorskip("PyOpenColorIO")
    cfg = ocio.Config.CreateRaw()
    proc = cfg.getProcessor(ocio.FileTransform(str(idt.CLF_PATH))).getDefaultCPUProcessor()
    img = SAMPLES.astype(np.float32).copy()
    proc.applyRGB(img)
    np.testing.assert_allclose(img, idt.cineon_to_aces2065(SAMPLES), rtol=2e-5, atol=2e-6)
