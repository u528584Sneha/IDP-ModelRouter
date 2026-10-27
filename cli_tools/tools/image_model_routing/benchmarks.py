"""
Benchmark leaderboard loader for the Image Model Routing tool.

Each document type (bol/awb/accord/other) has its own xlsx leaderboard under
Input/Frontier_Curve_Benchmark/, one row per model with accuracy, latency,
input/output token cost, and capacity (context window / max output tokens)
measured for that document type. These files are the SOURCE OF TRUTH for
which models exist and their quality/latency/cost/capacity for a given
--doc-type -- not a static registry.

The leaderboard's own "Cost" column (rupee-denominated, per-document-run) is
still NOT used for routing cost -- it's a different unit/currency than the
USD-per-1M-tokens rates in "Input Token Cost($)"/"Output Token Cost($)",
which mirror llm-router-platform's ModelCard.cost_input/cost_output split and
ARE what router.py uses to compute predicted cost (see router.py::_estimate_cost).
"""
import sys
import os
from pathlib import Path
from typing import List, Dict

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from helper.config_loader import get_config, load_config_for_file

load_config_for_file(__file__)
config = get_config(__file__, validation_level="tool")

_TOOL_DIR = Path(__file__).resolve().parent


def slugify_model_name(raw: str) -> str:
    """'Claude Opus 5.5' -> 'claude-opus-5.5'"""
    return raw.strip().lower().replace(" ", "-")


def _benchmark_dir() -> Path:
    rel = config.get("IMR_BENCHMARK_DIR", "Input/Frontier_Curve_Benchmark")
    return (_TOOL_DIR / rel).resolve()


def _benchmark_file_path(doc_type: str) -> Path:
    files = config.get_dict("IMR_BENCHMARK_FILES", {})
    filename = files.get(doc_type)
    if not filename:
        raise ValueError(f"No benchmark file configured for doc_type={doc_type!r}")
    path = _benchmark_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark file not found for doc_type={doc_type!r}: {path}")
    return path


def _find_column(headers: List, *keywords: str) -> int:
    """Return the index of the first header containing all keywords (case-insensitive)."""
    for idx, header in enumerate(headers):
        if header is None:
            continue
        text = str(header).strip().lower()
        if all(kw in text for kw in keywords):
            return idx
    raise ValueError(f"Could not find a column matching {keywords} in headers: {headers}")


def _parse_optional_number(value, cast):
    """Parse a numeric cell, treating missing/non-numeric placeholders (None, '-', '',
    etc.) as None rather than raising. For cost columns, None means "not provided"
    (router.py falls back to a flagged placeholder). For context_window/
    max_output_tokens specifically, "-" is the sheet's convention for "no limit"
    (the model has no fixed ceiling) -- None is still the right internal value for
    that case, since router.py's capacity hard filters treat None as "nothing to
    check against" and never reject on an unset field, which is exactly the
    behavior an unlimited capacity should have."""
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def load_benchmark_rows(doc_type: str) -> List[Dict]:
    """
    Read the benchmark leaderboard for doc_type and return one dict per model row:
    {'model_id': slug, 'model_name_raw': str, 'provider': str,
     'quality': accuracy/100.0, 'latency_ms': latency_s * 1000,
     'cost_per_1m_input_tokens_usd': float, 'cost_per_1m_output_tokens_usd': float,
     'context_window': int, 'max_output_tokens': int}.
    """
    path = _benchmark_file_path(doc_type)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]

    rows_iter = ws.iter_rows(values_only=True)
    headers = next(rows_iter, None)
    if not headers:
        raise ValueError(f"Benchmark file for doc_type={doc_type!r} has no header row: {path}")

    model_idx = _find_column(headers, "model")
    provider_idx = _find_column(headers, "model", "provider")
    accuracy_idx = _find_column(headers, "accuracy")
    latency_idx = _find_column(headers, "latency")
    input_cost_idx = _find_column(headers, "input", "token", "cost")
    output_cost_idx = _find_column(headers, "output", "token", "cost")
    context_window_idx = _find_column(headers, "context", "window")
    max_output_idx = _find_column(headers, "max", "output", "token")

    rows = []
    for row in rows_iter:
        if row is None or row[model_idx] is None:
            continue
        model_name_raw = str(row[model_idx]).strip()
        accuracy_pct = row[accuracy_idx]
        latency_s = row[latency_idx]
        if accuracy_pct is None or latency_s is None:
            continue
        rows.append({
            "model_id": slugify_model_name(model_name_raw),
            "model_name_raw": model_name_raw,
            "provider": str(row[provider_idx]).strip() if row[provider_idx] else "unknown",
            "quality": float(accuracy_pct) / 100.0,
            "latency_ms": float(latency_s) * 1000.0,
            "cost_per_1m_input_tokens_usd": _parse_optional_number(row[input_cost_idx], float) or 0.0,
            "cost_per_1m_output_tokens_usd": _parse_optional_number(row[output_cost_idx], float) or 0.0,
            "context_window": _parse_optional_number(row[context_window_idx], int),
            "max_output_tokens": _parse_optional_number(row[max_output_idx], int),
        })

    if not rows:
        raise ValueError(f"Benchmark file for doc_type={doc_type!r} has no usable data rows: {path}")

    return rows
