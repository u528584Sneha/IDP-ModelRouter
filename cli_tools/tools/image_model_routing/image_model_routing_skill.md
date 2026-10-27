---
tool_name: "image_model_routing"
version: "1.0.0"
description: "Routes an image to the best vision-capable LLM using a per-doc-type benchmark leaderboard for quality/latency, scored on quality/cost/latency"
owner_team: "halo-platform"
category: "LLM Routing"
---

# Input/Output Contract

## input_schema
| Argument | Type | Required | Description |
|---|---|---|---|
| `--input-file` | Path | Yes | Path to the image file to route (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff`, `.tif`) |
| `--doc-type` | String | **Yes** | `bol` \| `awb` \| `accord` \| `other`. Selects which benchmark leaderboard (`Input/Frontier_Curve_Benchmark/*.xlsx`) supplies the candidate models' quality/latency for this run. Use `other` for anything not BOL/AWB/Accord (routes to `Combined.xlsx`). |
| `--profile` | String | No | Weight profile: `balanced` (default), `quality_first`, `cost_first`, `latency_first` |
| `--quality-floor` | Float | No | Minimum quality prior (0-1) a model must meet to stay eligible. Default `0.0` |
| `--complexity` | Float | No | External complexity score, **0-20** (0-5 low, 5-10 medium, 10-15 complex, 15-20 very_high). Not computed by this tool -- supplied by the caller/upstream process. Omit to skip quality degradation entirely (today's behavior). |
| `--expected-output-tokens` | Integer | No | Assumed output token count used for cost estimation. Defaults to `IMR_DEFAULT_EXPECTED_OUTPUT_TOKENS` (512) -- a flat assumption, not derived from input size or model capacity (matches `llm-router-platform`'s `RouteRequest.expected_output_tokens` pattern). |
| `--output` | Path | No | Write JSON result to this file instead of stdout |
| `--debug` | Flag | No | Print an `icecream`-formatted trace of every routing stage (filter/normalize/score/select/complexity) to stderr. Never touches stdout JSON. |

## output_schema
```json
{
  "success": true,
  "result": {
    "input_file": "string",
    "image_dimensions": {"width": 0, "height": 0},
    "estimated_input_tokens": 0,
    "routing_decision": {
      "strategy": "score",
      "doc_type": "bol|awb|accord|other",
      "profile": "balanced",
      "profile_weights": {"quality": 0.0, "cost": 0.0, "latency": 0.0},
      "effective_weights": {"quality": 0.0, "cost": 0.0, "latency": 0.0},
      "quality_floor": 0.0,
      "input_tokens": 0,
      "expected_output_tokens": 0,
      "complexity": {"raw": 0.0, "normalized": 0.0, "tier": "low|medium|complex|very_high"} | null,
      "total_models": 0,
      "eligible_count": 0,
      "filtered_out": [{"model_id": "string", "reason": "string", "category": "capability_mismatch|quality_floor|context_window_exceeded|max_output_exceeded"}],
      "eligible_ranked": [{"model_id": "string", "provider": "string", "score": 0.0, "objectives": {"quality": 0.0, "cost": 0.0, "latency": 0.0}, "base_quality": 0.0, "predicted_quality": 0.0, "predicted_cost_usd": 0.0, "cost_per_1m_input_tokens_usd": 0.0, "cost_per_1m_output_tokens_usd": 0.0, "cost_is_placeholder": false, "predicted_latency_ms": 0.0, "predicted_reliability": 0.0, "context_window": 0, "max_output_tokens": 0}],
      "chosen": {"model_id": "string", "provider": "string", "score": 0.0, "base_quality": 0.0, "predicted_quality": 0.0, "predicted_cost_usd": 0.0, "cost_is_placeholder": false},
      "top_models": {"models": ["<top 3 entries, same shape as eligible_ranked>"], "diversity_constraint_applied": false, "diversity_constraint_satisfied": true}
    }
  },
  "message": "Routing complete"
}
```

# Error Handling

## error_codes
| Condition | stderr payload | exit code |
|---|---|---|
| `--doc-type` missing or not one of `bol/awb/accord/other` | argparse usage message (plain text, not JSON) | 2 |
| Benchmark file for `--doc-type` missing/unreadable/malformed | `{"success": false, "error": "Benchmark file not found for doc_type=...: <path>"}` or similar | 1 |
| Input file missing | `{"success": false, "error": "Input file not found: <path>"}` | 1 |
| Unsupported extension | `{"success": false, "error": "Unsupported image format: <ext>. Supported: ..."}` | 1 |
| No vision-capable model survives the hard filter (e.g. `--quality-floor` set too high, or every model's `context_window`/`max_output_tokens` is too small for this request) | `{"success": false, "error": "No eligible vision-capable model found...", "error_code": "NO_ELIGIBLE_MODEL"}` | 1 |
| `--complexity` outside `[0, 20]` | `{"success": false, "error": "--complexity must be between 0.0 and 20.0, got <value>"}` | 1 |
| `--expected-output-tokens` not positive | `{"success": false, "error": "--expected-output-tokens must be positive, got <value>"}` | 1 |

Any other unexpected exception is caught and reported as `{"success": false, "error": "<message>"}` to stderr with exit code 1. The tool never prints plain-text status lines.

## Reference Information

### Supported Use Cases
- Picking which vision-capable LLM should process a scanned document image before OCR/entity-extraction tools run.
- Choosing a model under different cost/latency/quality tradeoffs (e.g. `cost_first` for high-volume batch jobs, `quality_first` for low-volume high-stakes documents).
- Auditing why a model was excluded from consideration (`filtered_out` + `eligible_ranked` give a full funnel).
- Picking a top-3 panel of models for ensemble/fallback use (`top_models`): the 1st and 2nd picks are always the top 2 by score; the 3rd pick must come from a different provider than the 1st/2nd *only if* those two already share a provider (`diversity_constraint_applied`/`diversity_constraint_satisfied` report whether the rule fired and whether it could be satisfied).

### When to Use / When NOT to Use
**Use this tool when:**
- You have an image file and need to decide *which* vision-capable LLM to call next, before invoking it.
- You want a transparent, auditable scoring breakdown (not just a single model name).

**Do NOT use this tool when:**
- You already know which model to call (skip straight to the extraction/classification tool).
- Routing a non-image document (PDF, DOCX) — convert to images first (see `image_pre_processing`) or route by document type instead.
- You need the actual LLM response — this tool only *selects* a model, it never calls one.

### Workflow Position
**Typical order:**
1. `image_pre_processing` (optional — convert PDF pages to images / enhance quality)
2. **→ `image_model_routing`** ← You are here
3. `entity_extraction` / `document_domain_classification` (call the `chosen.model_id` from this tool's output)

### Examples

**Basic:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.png \
  --doc-type bol
```

**With a cost-sensitive profile:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type awb \
  --profile cost_first \
  --output routing_result.json
```

**Unrecognized document type:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type other
```

**Advanced — enforce a quality floor:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type accord \
  --profile quality_first \
  --quality-floor 0.85
```

**With external complexity:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type bol \
  --profile balanced \
  --complexity 12
```

**With an explicit output-length assumption (affects cost estimate):**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type awb \
  --profile cost_first \
  --expected-output-tokens 2000
```

**Error case — no model meets the floor:**
```bash
python tools/image_model_routing/image_model_routing.py \
  --input-file scan.jpg \
  --doc-type bol \
  --quality-floor 2.0
# stderr:
# {"success": false, "error": "No eligible vision-capable model found (...)", "error_code": "NO_ELIGIBLE_MODEL"}
# exit code 1
```

**Error case — missing/invalid `--doc-type`:**
```bash
python tools/image_model_routing/image_model_routing.py --input-file scan.jpg
# stderr (plain text, argparse):
# image_model_routing.py: error: the following arguments are required: --doc-type
# exit code 2
```

## Developer Notes

### Complexity-aware quality adjustment (`--complexity`)
When `--complexity` is supplied, each candidate's static `quality` prior is degraded before scoring:
```
complexity_norm = normalize(raw_0_20)              # rescaled to [0, 1]
headroom        = base_quality - IMR_QUALITY_HEADROOM_BASELINE   # default baseline 0.55
degradation     = max(0, complexity_norm - max(0, headroom)) * IMR_QUALITY_DEGRADATION_FACTOR  # default factor 0.45
predicted_quality = base_quality - degradation
```
This mirrors `llm-router-platform`'s `QualityPredictor.predict` heuristic. **Important caveat, carried over deliberately:** the baseline (0.55) and degradation factor (0.45) are hand-picked constants with no calibration or benchmark backing in the reference project either -- its own `docs/VERIFICATION_REPORT.md` explicitly flags both as unverified seed values. They are exposed as `IMR_QUALITY_HEADROOM_BASELINE`/`IMR_QUALITY_DEGRADATION_FACTOR` in `config.json` so they can be tuned against real outcomes later, not presented as derived truth.

A model with more headroom (higher base quality) degrades later and less than a model with less headroom — but a higher-quality model's `predicted_quality` can never fall below a lower-quality model's. Complexity therefore does not reorder quality; it widens or narrows the *quality gap* between candidates, which can change the overall weighted-score winner when a cheaper/faster model's cost or latency savings are no longer enough to offset a now-larger quality deficit.

On its own, this degradation almost never changes the chosen model with the current benchmarks. Benchmark qualities sit within ~1-2 points of each other, so for nearly every complexity value all candidates are in the same regime: either none degrade, or all degrade by the same affine shift (`1.45·q − 0.45·c_norm − 0.2475`). Min-max normalization cancels that shift exactly. The only "mixed" window, where complexity sits between candidates' headroom values, is ~0.3 raw-complexity wide (e.g. 6.28–6.54 for AWB). With exactly 2 eligible candidates, degradation can never matter.

### Complexity-adjusted weights
To make complexity actually move the decision, `router.py::_adapt_weights` also shifts the profile's quality weight before scoring. Harder documents weigh quality more; easier documents weigh cost/latency more:
```
shift   = (complexity_norm - IMR_COMPLEXITY_WEIGHT_PIVOT) * IMR_COMPLEXITY_WEIGHT_STRENGTH   # defaults 0.5, 0.5
w_q'    = clamp(w_q + shift, IMR_COMPLEXITY_WEIGHT_MIN, IMR_COMPLEXITY_WEIGHT_MAX)          # defaults 0.05, 0.95
w_cost' = (1 - w_q') * w_cost / (w_cost + w_latency)
w_lat'  = (1 - w_q') * w_latency / (w_cost + w_latency)
```
- Raw complexity 10 (norm 0.5) leaves the profile unchanged. The weights always sum to 1, and the base profile's cost:latency ratio is kept.
- The output reports both `profile_weights` (the configured profile) and `effective_weights` (the weights actually used for scoring).
- Example (AWB, `balanced`, sample image): complexity 0–4.2 → `claude-haiku-5.5`, 4.3–9.9 → `claude-sonnet-5.5`, 10–20 → `grok-4.7`. If one model is best on every objective (e.g. BoL → `claude-haiku-5.5`), it still wins at every complexity.
- Pivot, strength and clamp values are hand-picked seed values, the same as the degradation constants. Tune them against real outcomes.
- Complexity never affects eligibility. The hard filter (`supports_vision`, `--quality-floor`) still keys on each card's static `quality`, never the degraded value.
- `--complexity` is optional. Omitting it reproduces the no-complexity behavior exactly (`base_quality == predicted_quality` and `effective_weights == profile_weights`).

### Benchmark-driven candidates (`--doc-type`)
Quality, latency, cost, and capacity are no longer a static hand-maintained registry — they come from a per-document-type benchmark leaderboard under `../../../Input/Frontier_Curve_Benchmark/` (relative to this tool's directory: `BoL.xlsx`, `AWB.xlsx`, `Accord.xlsx`, `Combined.xlsx` for `other`), loaded fresh on every run via `benchmarks.py::load_benchmark_rows()`. Each row becomes a routing candidate:
- `model_id` = slugified `Model` column (e.g. `"Claude Opus 5.5"` → `claude-opus-5.5`)
- `quality` = `Scaled Accuracy (%)` (or `Accuracy (%)` in `Combined.xlsx`) / 100
- `latency_ms` = `Latency (s)` × 1000
- `cost_per_1m_input_tokens_usd` / `cost_per_1m_output_tokens_usd` = `Input Token Cost($)` / `Output Token Cost($)` columns, read as-is (USD per 1M tokens)
- `context_window` / `max_output_tokens` = `Context Window` / `Max Output Tokens` columns. A `"-"` means the model has **no fixed limit** (not "value not measured"); it parses to `None`, which simply skips the corresponding hard-filter check for that model — the correct behavior for a model with unlimited capacity
- `supports_vision` = always `True` (every row in every benchmark file is a multimodal/vision benchmark)

**If the benchmark file's models or numbers change, routing changes on the very next run** — there is no caching, and `model_cards.py` no longer controls which models exist.

### Cost estimation: input + output token pricing
Cost is computed per-request using the model's own benchmark-row rates (or an override from `model_cards.py`, see below) and this request's actual token counts — mirroring `llm-router-platform`'s `CostEstimator.predict` exactly:
```
predicted_cost_usd = (input_tokens / 1e6) * cost_per_1m_input_tokens_usd
                    + (expected_output_tokens / 1e6) * cost_per_1m_output_tokens_usd
```
- `input_tokens` = `estimated_input_tokens` from image dimension sniffing (`common.py`).
- `expected_output_tokens` = `--expected-output-tokens` if supplied, else `IMR_DEFAULT_EXPECTED_OUTPUT_TOKENS` (default `512`). This is a **flat assumption, never derived** from input size, document type, or any model's capacity — same approach as the reference project (`RouteRequest.expected_output_tokens`), which also never scales this value dynamically.

The benchmark leaderboard's own `Cost (₹)` column (rupee-denominated, per-document-run) is intentionally **never** used for this — it's a different unit/currency than the USD-per-1M-token rates the formula above needs.

`model_cards.py`'s `MODEL_COST_OVERRIDES` table (keyed by the same slugified `model_id`) can replace a benchmark row's cost rates if needed (e.g. to correct a number without editing the spreadsheet) — if present, it wins over the benchmark row. `"cost_is_placeholder"` in the output is `true` only when neither the benchmark row nor an override supplies a non-zero rate, so a caller can tell real cost-based ranking from a placeholder-driven one.

### Capacity hard filters (`context_window`, `max_output_tokens`)
Mirrors `llm-router-platform`'s `constraints.py` hard gates exactly: a candidate is **excluded** (not just scored lower) if its declared capacity can't fit this request --
- `context_window_exceeded`: `card.context_window < (input_tokens + expected_output_tokens) * IMR_CONTEXT_HEADROOM_FACTOR` (default headroom factor `1.05`, i.e. 5% buffer).
- `max_output_exceeded`: `card.max_output_tokens < expected_output_tokens`.

Both checks are skipped (never reject) when the benchmark row's corresponding field is `None` — i.e. the sheet says `"-"` (no fixed limit) for that model. For a single document image these filters almost never trigger in practice today — benchmark context windows run 500K-1M+ tokens and `estimated_input_tokens` for one image is a few hundred to low thousands — but they're included as a cheap safety net for when inputs grow (multi-page documents, a caller setting a large `--expected-output-tokens`).

**Reliability** is tracked per-candidate (`IMR_DEFAULT_RELIABILITY`, default `0.98`) and reported in output, but is **not currently used in scoring** (`OBJECTIVES` only contains `quality`, `cost`, `latency`) — there's no production-history signal yet to make a reliability score meaningful, so profile weights no longer include a `reliability` term.

### Debugging the routing pipeline
Pass `--debug` to trace every stage (candidate construction, `_hard_filter`, `_predict_quality`, `_estimate_cost`, `_normalize`, `_score`, select) via `icecream`:
```bash
pip install icecream openpyxl   # one-time, see requirements.txt
python tools/image_model_routing/image_model_routing.py --input-file scan.png --doc-type bol --profile cost_first --debug
```
This prints a `router| ...` trace to stderr showing: which benchmark rows were loaded and whether each got its cost rates from the benchmark row or a `model_cards.py` override; which models were dropped and why (capability, quality floor, context window, or output capacity); the per-model input+output cost calculation; the raw and min-max-normalized objective values; each candidate's weighted score breakdown; and the final ranking. stdout JSON is unaffected since `ic()` always writes to stderr and is disabled by default (`router.py` calls `ic.disable()` at import time; `--debug` calls `router.enable_debug_trace()`). For step-through inspection instead, set a breakpoint at the top of `_build_candidates`/`_hard_filter`/`_estimate_cost`/`_normalize`/`_score` in `router.py` and use VS Code's debugger -- the pipeline is a short, deterministic, single-pass sequence of pure functions, which is exactly what a conventional debugger (rather than Python Tutor or Cyberbrain) handles best.

- Eligibility is a hard capability gate (`ModelCard.supports_vision`), not a content classifier — ported from `llm-router-platform`'s `app/services/constraints.py` + `config/models.yaml`. Since every benchmark-sourced candidate is vision-capable by construction, this branch is currently dead code, kept for structural consistency / future-proofing.
- Scoring is a min-max-normalized weighted dot product over `quality`, `cost` (inverted), `latency` (inverted) — ported from `app/core/router_engine.py` (`_normalize`/`_score`), strategy `SCORE` only (no bandit/cascade/shadow). `reliability` is excluded from this (see above).
- Token estimation sniffs real PNG/JPEG dimensions directly from file headers (no Pillow dependency) and applies an OpenAI-tile-style formula (`base + tiles * per_tile`), matching `app/services/attachments.py`. Non-PNG/JPEG formats (e.g. `.tif`) fall back to a conservative default token estimate since no header parser is implemented for them.
- This tool only selects a model; it does not call any provider API or require any provider credentials.
