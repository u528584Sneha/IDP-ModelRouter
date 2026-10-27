"""
External complexity input for the Image Model Routing tool.

Complexity is NOT computed from the image here -- it is supplied by the
caller as a raw 0-20 value (see --complexity in image_model_routing.py),
already produced by an upstream process. This module only rescales that
raw value to the [0, 1] range the degradation formula in router.py expects,
and attaches a human-readable tier label for reporting purposes only --
the tier never affects the math, only the raw/normalized value does.

Tier bands (half-open on the low end, closed at the configured max):
  [MIN, LOW_MAX)            -> low
  [LOW_MAX, MEDIUM_MAX)     -> medium
  [MEDIUM_MAX, COMPLEX_MAX) -> complex
  [COMPLEX_MAX, MAX]        -> very_high
"""
import sys
import os
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from helper.config_loader import get_config, load_config_for_file

load_config_for_file(__file__)
config = get_config(__file__, validation_level="tool")

_DEBUG = False

def _debug(*args, **kwargs):
    """Print debug output to stderr only when debug mode is enabled"""
    if _DEBUG:
        print(*args, file=sys.stderr, **kwargs)


def _bounds() -> tuple:
    return config.get_float("IMR_COMPLEXITY_MIN", 0.0), config.get_float("IMR_COMPLEXITY_MAX", 20.0)


def normalize_complexity(raw: float) -> float:
    """Clamp raw to [min, max] then rescale to [0.0, 1.0]."""
    lo, hi = _bounds()
    clamped = max(lo, min(hi, raw))

    _debug("=== COMPLEXITY NORMALIZATION ===")
    _debug(f"Raw complexity: {raw}")
    _debug(f"Config range: [{lo}, {hi}]")

    if raw != clamped:
        _debug(f"Clamped: max({lo}, min({hi}, {raw})) = {clamped}")
    else:
        _debug(f"Within range: {clamped}")

    if hi == lo:
        _debug(f"Formula: normalized = 0.0 (min == max)")
        return 0.0

    normalized = (clamped - lo) / (hi - lo)
    _debug(f"Formula: normalized = (clamped - min) / (max - min)")
    _debug(f"  = ({clamped} - {lo}) / ({hi} - {lo})")
    _debug(f"  = {clamped - lo} / {hi - lo}")
    _debug(f"  = {normalized:.4f}")
    return normalized


def complexity_tier(raw: float) -> str:
    """Map a raw complexity value to a display-only tier label."""
    lo, hi = _bounds()
    clamped = max(lo, min(hi, raw))
    low_max = config.get_float("IMR_COMPLEXITY_TIER_LOW_MAX", 5.0)
    medium_max = config.get_float("IMR_COMPLEXITY_TIER_MEDIUM_MAX", 10.0)
    complex_max = config.get_float("IMR_COMPLEXITY_TIER_COMPLEX_MAX", 15.0)
    if clamped < low_max:
        return "low"
    if clamped < medium_max:
        return "medium"
    if clamped < complex_max:
        return "complex"
    return "very_high"


def describe_complexity(raw: Optional[float]) -> Optional[dict]:
    """Return {'raw', 'normalized', 'tier'} for the given raw complexity value,
    or None if no complexity was supplied."""
    if raw is None:
        _debug("=== COMPLEXITY NORMALIZATION ===")
        _debug("No complexity provided (--complexity not specified)")
        return None

    normalized = round(normalize_complexity(raw), 4)
    tier = complexity_tier(raw)

    _debug(f"Tier classification: {tier}")
    _debug(f"  low: [0, 5)")
    _debug(f"  medium: [5, 10)")
    _debug(f"  complex: [10, 15)")
    _debug(f"  very_high: [15, 20]")
    _debug(f"  → {raw} falls in '{tier}' tier")

    return {
        "raw": raw,
        "normalized": normalized,
        "tier": tier,
    }
