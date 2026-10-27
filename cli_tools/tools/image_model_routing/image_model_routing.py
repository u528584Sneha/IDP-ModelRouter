#!/usr/bin/env python3
"""Image Model Routing - route an image input to the best vision-capable LLM"""
import argparse
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from helper.config_loader import get_config, load_config_for_file
from common import estimate_image_tokens, is_supported_image, supported_extensions
import common
import complexity
import router
from router import route, NoEligibleModelError

load_config_for_file(__file__)
_CFG = get_config(__file__, validation_level="tool")


def process(
    input_file: str,
    doc_type: str,
    profile: str | None,
    quality_floor: float | None,
    complexity: float | None,
    expected_output_tokens: int | None,
) -> dict:
    image_path = Path(input_file)
    if not image_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if not is_supported_image(input_file):
        supported = ", ".join(supported_extensions())
        raise ValueError(f"Unsupported image format: {image_path.suffix}. Supported: {supported}")

    if complexity is not None:
        lo = _CFG.get_float("IMR_COMPLEXITY_MIN", 0.0)
        hi = _CFG.get_float("IMR_COMPLEXITY_MAX", 20.0)
        if not (lo <= complexity <= hi):
            raise ValueError(f"--complexity must be between {lo} and {hi}, got {complexity}")

    if expected_output_tokens is not None and expected_output_tokens <= 0:
        raise ValueError(f"--expected-output-tokens must be positive, got {expected_output_tokens}")

    ext = image_path.suffix.lower().lstrip(".")
    data = image_path.read_bytes()
    estimated_tokens, dims = estimate_image_tokens(data, ext)

    decision = route(
        doc_type=doc_type,
        input_tokens=estimated_tokens,
        profile_name=profile,
        quality_floor=quality_floor,
        complexity_raw=complexity,
        expected_output_tokens=expected_output_tokens,
    )

    return {
        "input_file": str(image_path.resolve()),
        "image_dimensions": {"width": dims[0], "height": dims[1]} if dims else None,
        "estimated_input_tokens": estimated_tokens,
        "routing_decision": decision,
    }


def main():
    parser = argparse.ArgumentParser(description="Image Model Routing")
    parser.add_argument("--input-file", required=True, help="Path to the image file to route")
    parser.add_argument("--doc-type", required=True, choices=["bol", "awb", "accord", "other"],
                         help="Document type driving which benchmark leaderboard to use for "
                              "model quality/latency. Use 'other' for anything not BOL/AWB/Accord.")
    parser.add_argument("--profile", required=False, default=None,
                         help="Weight profile: balanced | quality_first | cost_first | latency_first")
    parser.add_argument("--quality-floor", required=False, type=float, default=None,
                         help="Minimum quality prior a model must meet to be eligible (0-1)")
    parser.add_argument("--output", default=None, help="Optional output JSON file path")
    parser.add_argument("--complexity", required=False, type=float, default=None,
                         help="External complexity score, 0-20 (0-5 low, 5-10 medium, "
                              "10-15 complex, 15-20 very_high). Omit to skip quality degradation.")
    parser.add_argument("--expected-output-tokens", required=False, type=int, default=None,
                         help="Assumed output token count used for cost estimation. "
                              "Omit to use IMR_DEFAULT_EXPECTED_OUTPUT_TOKENS from config "
                              "(default 512) -- this is a flat assumption, not derived from "
                              "input size or model capacity.")
    parser.add_argument("--debug", action="store_true",
                         help="Print icecream traces of each routing stage to stderr (does not affect stdout JSON)")
    args = parser.parse_args()

    if args.debug:
        common._DEBUG = True
        complexity._DEBUG = True
        router.enable_debug_trace()

    try:
        result = process(
            args.input_file,
            args.doc_type,
            args.profile,
            args.quality_floor,
            args.complexity,
            args.expected_output_tokens,
        )
        output = {"success": True, "result": result, "message": "Routing complete"}
        if args.output:
            with open(args.output, "w") as f:
                json.dump(output, f, indent=2)
        else:
            print(json.dumps(output, indent=2))
        sys.exit(0)
    except NoEligibleModelError as e:
        print(json.dumps({"success": False, "error": str(e), "error_code": "NO_ELIGIBLE_MODEL"}, indent=2), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
