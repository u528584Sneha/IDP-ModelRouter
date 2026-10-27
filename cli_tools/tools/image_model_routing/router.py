"""
Image routing engine.

Ported (simplified, images-only) from llm-router-platform's
app/core/router_engine.py pipeline:

  1. Hard filter  -- drop any ModelCard without supports_vision=True
                     (mirrors app/services/constraints.py:
                      derive_required_features + ModelCard.has_feature).
                      All benchmark-sourced candidates have supports_vision=True
                      by construction (every benchmark leaderboard is vision-only),
                      so this branch is currently dead but kept for structural
                      consistency / future-proofing.
                      Also drops any candidate whose context_window can't fit
                      input_tokens + expected_output_tokens (with headroom), or
                      whose max_output_tokens is less than expected_output_tokens
                      -- mirrors constraints.py's context_window/max_output_tokens
                      hard gates. For a single document image these almost never
                      trigger today (benchmark context windows are 500K-1M+,
                      output needs are a few hundred to low thousands of tokens)
                      but are included for when inputs grow (multi-page docs,
                      larger --expected-output-tokens). A "-" in the benchmark
                      sheet's Context Window/Max Output Tokens columns means the
                      model has no fixed limit, not "value not measured" -- it
                      parses to None (see benchmarks.py::_parse_optional_number),
                      and None skips the corresponding check entirely, which is
                      the correct behavior for an unlimited capacity (never reject).
  2. Normalize     -- min-max scale quality/cost/latency across the surviving
                      candidates (cost and latency inverted, since lower is
                      better for both). Reliability is tracked per-candidate
                      but intentionally excluded from scoring for now (see
                      ModelCard.reliability docstring) -- there is no
                      production-history signal yet to make it meaningful.
  3. Score         -- weighted dot product against the active profile's
                      weight vector (mirrors RouterEngine._score). When
                      --complexity is supplied, the profile's quality weight
                      is first shifted up (hard docs) or down (easy docs) --
                      see _adapt_weights.
  4. Select        -- argmax score (mirrors RoutingStrategy.SCORE).

Quality, latency, cost, and capacity (context window / max output tokens) per
candidate come from a benchmark leaderboard selected by --doc-type (see
benchmarks.py) -- not a static registry. Cost is computed from the benchmark's
own per-model "Input Token Cost($)"/"Output Token Cost($)" rates (USD per 1M
tokens) applied to this request's actual input_tokens and expected_output_tokens
-- mirrors llm-router-platform's CostEstimator.predict formula exactly:
    cost = (input_tokens/1e6)*cost_input + (output_tokens/1e6)*cost_output
model_cards.py's override table can replace a benchmark row's cost rates if
needed, but is no longer required to get a real (non-placeholder) cost.

No bandit/cascade/shadow strategies are ported -- this tool only needs a
single best pick per invocation.
"""
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from helper.config_loader import get_config, load_config_for_file
from benchmarks import load_benchmark_rows
from model_cards import get_cost_override
from complexity import normalize_complexity, describe_complexity

_DEBUG = False

def _debug(*args, **kwargs):
    """Print debug output to stderr only when debug mode is enabled"""
    if _DEBUG:
        print(*args, file=sys.stderr, **kwargs)

def enable_debug_trace() -> None:
    global _DEBUG
    _DEBUG = True


load_config_for_file(__file__)
config = get_config(__file__, validation_level="tool")

# Reliability is intentionally NOT in OBJECTIVES -- see ModelCard.reliability
# docstring below. It is still carried on each candidate (as a placeholder)
# and reported in output, just never scored.
OBJECTIVES = ("quality", "cost", "latency")


@dataclass(frozen=True)
class ModelCard:
    """A per-request routing candidate, assembled from a benchmark leaderboard
    row (quality, latency, cost rates, capacity), optionally overridden by
    model_cards.py's cost table."""
    model_id: str
    provider: str
    supports_vision: bool
    quality: float                         # 0-1, from the benchmark leaderboard for --doc-type
    cost_per_1m_input_tokens_usd: float     # USD per 1M input tokens, from benchmark row or override
    cost_per_1m_output_tokens_usd: float    # USD per 1M output tokens, from benchmark row or override
    cost_is_placeholder: bool               # True only if neither the benchmark row nor an override supplied a cost
    latency_ms: float                       # from the benchmark leaderboard (seconds * 1000)
    context_window: Optional[int]           # from the benchmark leaderboard; None means no fixed limit ("-" in the sheet)
    max_output_tokens: Optional[int]        # from the benchmark leaderboard; None means no fixed limit ("-" in the sheet)
    reliability: float                      # placeholder only -- not used in scoring (see OBJECTIVES)
    notes: str = ""


def _build_candidates(doc_type: str) -> List[ModelCard]:
    """Build the per-request candidate pool from the --doc-type benchmark
    leaderboard, applying any model_cards.py cost override."""
    rows = load_benchmark_rows(doc_type)
    default_reliability = config.get_float("IMR_DEFAULT_RELIABILITY", 0.98)

    _debug(f"  Loading '{doc_type}' benchmark leaderboard: {len(rows)} models")

    cards = []
    for row in rows:
        override = get_cost_override(row["model_id"])
        if override:
            cost_in = override.cost_per_1m_input_tokens_usd
            cost_out = override.cost_per_1m_output_tokens_usd
            cost_source = "OVERRIDE"
        else:
            cost_in = row["cost_per_1m_input_tokens_usd"]
            cost_out = row["cost_per_1m_output_tokens_usd"]
            cost_source = "BENCHMARK"
        cost_is_placeholder = not override and cost_in == 0.0 and cost_out == 0.0

        _debug(f"    {row['model_id']:<30} | quality={row['quality']:.3f} | latency={row['latency_ms']:>6.0f}ms | cost({cost_source}): ${cost_in:.4f}/${cost_out:.4f} per 1M {'(placeholder)' if cost_is_placeholder else ''}")

        cards.append(ModelCard(
            model_id=row["model_id"],
            provider=row["provider"],
            supports_vision=True,
            quality=row["quality"],
            cost_per_1m_input_tokens_usd=cost_in,
            cost_per_1m_output_tokens_usd=cost_out,
            cost_is_placeholder=cost_is_placeholder,
            latency_ms=row["latency_ms"],
            context_window=row["context_window"],
            max_output_tokens=row["max_output_tokens"],
            reliability=default_reliability,
            notes=f"doc_type={doc_type}; benchmark_model_name={row['model_name_raw']}",
        ))
    return cards


def _estimate_cost(card: ModelCard, input_tokens: int, expected_output_tokens: int) -> float:
    """Predicted USD cost for this request on this model.
    Mirrors llm-router-platform's CostEstimator.predict exactly:
        cost = (input_tokens/1e6)*cost_input + (output_tokens/1e6)*cost_output
    """
    _debug(f"=== COST CALCULATION for {card.model_id} ===")
    _debug(f"Formula: cost = (input_tokens/1e6)×cost_input + (output_tokens/1e6)×cost_output")
    _debug(f"Input: tokens={input_tokens}, expected_output={expected_output_tokens}")
    _debug(f"Rates: cost_per_1m_input=${card.cost_per_1m_input_tokens_usd}, cost_per_1m_output=${card.cost_per_1m_output_tokens_usd}")

    in_cost = (input_tokens / 1_000_000.0) * card.cost_per_1m_input_tokens_usd
    _debug(f"Input cost: ({input_tokens}/1e6) × {card.cost_per_1m_input_tokens_usd} = ${in_cost:.6f}")

    out_cost = (expected_output_tokens / 1_000_000.0) * card.cost_per_1m_output_tokens_usd
    _debug(f"Output cost: ({expected_output_tokens}/1e6) × {card.cost_per_1m_output_tokens_usd} = ${out_cost:.6f}")

    total = round(in_cost + out_cost, 6)
    _debug(f"Total cost: ${in_cost:.6f} + ${out_cost:.6f} = ${total:.6f}")
    return total


class NoEligibleModelError(Exception):
    """Raised when zero models survive the hard eligibility filter."""


def get_weight_profile(profile_name: str) -> Dict[str, float]:
    """Weights in config are already final (sum to 1 across OBJECTIVES);
    any extra keys (e.g. reliability_reserved) are ignored here."""
    profiles = config.get_dict("IMR_WEIGHT_PROFILES", {})
    default_name = config.get("IMR_DEFAULT_PROFILE", "balanced")
    weights = profiles.get(profile_name) or profiles.get(default_name)
    if not weights:
        weights = {"quality": 0.4375, "cost": 0.3125, "latency": 0.25}
    return {o: weights.get(o, 0.0) for o in OBJECTIVES}


def _adapt_weights(weights: Dict[str, float], complexity_norm: Optional[float]) -> Dict[str, float]:
    """
    Shift the profile's quality weight by request complexity: harder documents
    weigh quality more, easier documents weigh cost/latency more.

    _predict_quality alone cannot change the chosen model in practice: benchmark
    qualities are tightly clustered, so for almost every complexity value all
    candidates degrade by the same affine shift, which min-max normalization
    cancels out. Shifting the weights is what lets complexity move the decision.

        w_q' = clamp(w_q + (complexity_norm - pivot) * strength, w_min, w_max)
        cost/latency split (1 - w_q') in their original ratio

    pivot/strength/min/max are hand-picked seed values exposed as config.
    complexity_norm is None when no --complexity was supplied, in which case
    the profile weights are returned unchanged.
    """
    if complexity_norm is None:
        _debug("=== COMPLEXITY WEIGHT SHIFT ===")
        _debug("No complexity provided, using profile weights unchanged")
        return dict(weights)

    pivot = config.get_float("IMR_COMPLEXITY_WEIGHT_PIVOT", 0.5)
    strength = config.get_float("IMR_COMPLEXITY_WEIGHT_STRENGTH", 0.5)
    w_min = config.get_float("IMR_COMPLEXITY_WEIGHT_MIN", 0.05)
    w_max = config.get_float("IMR_COMPLEXITY_WEIGHT_MAX", 0.95)

    _debug("=== COMPLEXITY WEIGHT SHIFT ===")
    _debug(f"Constants: pivot={pivot:.4f}, strength={strength:.4f}, clamp=[{w_min}, {w_max}]")

    shift = (complexity_norm - pivot) * strength
    _debug(f"Shift: ({complexity_norm:.4f} - {pivot:.4f}) × {strength:.4f} = {shift:+.4f}")

    w_q = min(w_max, max(w_min, weights["quality"] + shift))
    _debug(f"Quality weight: clamp({weights['quality']:.4f} + {shift:+.4f}) = {w_q:.4f}")

    rest = weights["cost"] + weights["latency"]
    if rest > 0:
        w_c = (1.0 - w_q) * weights["cost"] / rest
        w_l = (1.0 - w_q) * weights["latency"] / rest
    else:
        w_c = w_l = (1.0 - w_q) / 2.0
    _debug(f"Cost weight: (1 - {w_q:.4f}) × {weights['cost']:.4f} / {rest:.4f} = {w_c:.4f}")
    _debug(f"Latency weight: (1 - {w_q:.4f}) × {weights['latency']:.4f} / {rest:.4f} = {w_l:.4f}")
    return {"quality": w_q, "cost": w_c, "latency": w_l}


def _hard_filter(
    candidates: List[ModelCard],
    quality_floor: float,
    input_tokens: int,
    expected_output_tokens: int,
) -> Dict[str, List]:
    """Apply hard eligibility gates. Returns {eligible: [...], filtered_out: [...]}"""
    headroom_factor = config.get_float("IMR_CONTEXT_HEADROOM_FACTOR", 1.05)
    needed_context = (input_tokens + expected_output_tokens) * headroom_factor

    _debug("=== HARD FILTER (Eligibility Checks) ===")
    _debug(f"Quality floor: {quality_floor}")
    _debug(f"Input tokens: {input_tokens}, Expected output: {expected_output_tokens}")
    _debug(f"Context headroom factor: {headroom_factor}")
    _debug(f"Required context: ({input_tokens} + {expected_output_tokens}) × {headroom_factor} = {int(needed_context)}")
    _debug(f"Total candidates to filter: {len(candidates)}")
    _debug(f"Candidates: {[c.model_id for c in candidates]}\n")

    eligible = []
    filtered_out = []
    for card in candidates:
        _debug(f"Checking {card.model_id}:")

        # Check 1: Vision capability
        if not card.supports_vision:
            _debug(f"  [1] Vision support: {card.supports_vision} ✗ DROPPED")
            filtered_out.append({
                "model_id": card.model_id,
                "reason": "missing_feature:vision",
                "category": "capability_mismatch",
            })
            continue
        _debug(f"  [1] Vision support: {card.supports_vision} ✓")

        # Check 2: Quality floor
        if card.quality < quality_floor:
            _debug(f"  [2] Quality: {card.quality:.6f} < floor {quality_floor} ✗ DROPPED")
            filtered_out.append({
                "model_id": card.model_id,
                "reason": f"quality {card.quality} below floor {quality_floor}",
                "category": "quality_floor",
            })
            continue
        _debug(f"  [2] Quality: {card.quality:.6f} >= floor {quality_floor} ✓")

        # Check 3: Context window
        if card.context_window is not None:
            if card.context_window < needed_context:
                _debug(f"  [3] Context window: {card.context_window:,} < required {int(needed_context):,} ✗ DROPPED")
                filtered_out.append({
                    "model_id": card.model_id,
                    "reason": f"context window {card.context_window} < required {int(needed_context)}",
                    "category": "context_window_exceeded",
                })
                continue
            _debug(f"  [3] Context window: {card.context_window:,} >= required {int(needed_context):,} ✓")
        else:
            _debug(f"  [3] Context window: unlimited (None) ✓")

        # Check 4: Max output tokens
        if card.max_output_tokens is not None:
            if card.max_output_tokens < expected_output_tokens:
                _debug(f"  [4] Max output tokens: {card.max_output_tokens:,} < expected {expected_output_tokens:,} ✗ DROPPED")
                filtered_out.append({
                    "model_id": card.model_id,
                    "reason": f"max_output_tokens {card.max_output_tokens} < expected {expected_output_tokens}",
                    "category": "max_output_exceeded",
                })
                continue
            _debug(f"  [4] Max output tokens: {card.max_output_tokens:,} >= expected {expected_output_tokens:,} ✓")
        else:
            _debug(f"  [4] Max output tokens: unlimited (None) ✓")

        _debug(f"  ✓ ALL CHECKS PASSED - ELIGIBLE")
        eligible.append(card)

    _debug(f"\nFilter results: {len(eligible)} eligible, {len(filtered_out)} filtered out")
    _debug(f"Eligible: {[c.model_id for c in eligible]}")
    _debug(f"Filtered out: {[f['model_id'] for f in filtered_out]}")
    return {"eligible": eligible, "filtered_out": filtered_out}


def _predict_quality(card: ModelCard, complexity_norm: Optional[float]) -> float:
    """
    Degrade a model's static quality prior based on request complexity.

    Mirrors llm-router-platform's QualityPredictor.predict headroom/degradation
    heuristic. The pivot (0.55) and degradation factor (0.45) are hand-picked
    constants with no calibration/benchmark backing in the reference project
    either (confirmed: llm-router-platform's docs/VERIFICATION_REPORT.md
    explicitly flags both as unverified seed values) -- they are exposed here
    as config so they can be tuned later against real outcomes, not presented
    as derived truth. complexity_norm is None when no --complexity was
    supplied, in which case quality is returned unchanged (today's behavior).
    """
    if complexity_norm is None:
        _debug(f"=== QUALITY PREDICTION for {card.model_id} ===")
        _debug(f"No complexity provided, using base quality: {card.quality}")
        return card.quality

    _debug(f"=== QUALITY PREDICTION for {card.model_id} ===")
    _debug(f"Base quality from benchmark: {card.quality:.4f}")
    _debug(f"Normalized complexity score: {complexity_norm:.4f}")

    baseline = config.get_float("IMR_QUALITY_HEADROOM_BASELINE", 0.55)
    factor = config.get_float("IMR_QUALITY_DEGRADATION_FACTOR", 0.45)
    _debug(f"Constants: baseline_headroom={baseline:.4f}, degradation_factor={factor:.4f}")

    headroom = card.quality - baseline
    _debug(f"Headroom: {card.quality:.4f} - {baseline:.4f} = {headroom:.4f}")

    excess_complexity = complexity_norm - max(0.0, headroom)
    degradation = max(0.0, excess_complexity) * factor
    _debug(f"Excess complexity: max(0, {complexity_norm:.4f} - max(0, {headroom:.4f})) = {max(0.0, excess_complexity):.4f}")
    _debug(f"Degradation: {max(0.0, excess_complexity):.4f} × {factor:.4f} = {degradation:.4f}")

    predicted = card.quality - degradation
    _debug(f"Predicted quality: {card.quality:.4f} - {degradation:.4f} = {predicted:.4f}")
    return predicted


def _normalize(
    cards: List[ModelCard],
    predicted_quality: Dict[str, float],
    predicted_cost: Dict[str, float],
) -> Dict[str, Dict[str, float]]:
    """Min-max scale each objective across candidates; cost/latency inverted.
    Quality uses the (possibly complexity-degraded) predicted_quality map; cost
    uses the per-request predicted_cost map (input+output token cost for this
    request); latency stays the static benchmark value. Reliability is
    intentionally not normalized/scored here (see OBJECTIVES)."""
    raw = {
        "quality": {c.model_id: predicted_quality[c.model_id] for c in cards},
        "cost": {c.model_id: predicted_cost[c.model_id] for c in cards},
        "latency": {c.model_id: c.latency_ms for c in cards},
    }
    _debug("=== NORMALIZATION (Min-Max Scaling) ===")
    for obj, values in raw.items():
        _debug(f"{obj}: {{{', '.join(f'{k!r}: {v:.4f}' for k, v in values.items())}}}")

    normalized: Dict[str, Dict[str, float]] = {o: {} for o in OBJECTIVES}
    for objective in OBJECTIVES:
        values = list(raw[objective].values())
        lo, hi = min(values), max(values)
        invert = objective in ("cost", "latency")

        _debug(f"\nNormalizing '{objective}':")
        _debug(f"  Raw values: {{{', '.join(f'{k!r}: {v:.4f}' for k, v in raw[objective].items())}}}")
        _debug(f"  Min={lo:.4f}, Max={hi:.4f}, Invert={invert}")

        for model_id, value in raw[objective].items():
            if hi == lo:
                score = 1.0
                _debug(f"  {model_id}: all values equal, score=1.0")
            else:
                score = (value - lo) / (hi - lo)
                _debug(f"  {model_id}: ({value:.4f} - {lo:.4f}) / ({hi:.4f} - {lo:.4f}) = {score:.4f}")
                if invert:
                    score = 1.0 - score
                    _debug(f"    Inverted (lower is better): 1.0 - {score + (1.0 - score):.4f} = {score:.4f}")
            normalized[objective][model_id] = score

    _debug("\nNormalized scores:")
    for obj in OBJECTIVES:
        _debug(f"  {obj}: {normalized[obj]}")
    return normalized


def _score(model_id: str, normalized: Dict[str, Dict[str, float]], weights: Dict[str, float]) -> float:
    _debug(f"  Scoring {model_id}:")
    _debug(f"    Weights: {weights}")
    objectives_vals = {o: normalized[o][model_id] for o in OBJECTIVES}
    _debug(f"    Normalized scores: {objectives_vals}")

    terms = []
    for o in OBJECTIVES:
        term = weights[o] * normalized[o][model_id]
        terms.append(term)
        _debug(f"      {o}: {weights[o]:.3f} × {normalized[o][model_id]:.4f} = {term:.4f}")

    total = sum(terms)
    _debug(f"    TOTAL SCORE: {' + '.join(f'{t:.4f}' for t in terms)} = {total:.4f}")
    return total


def _select_top_models(candidates_scored: List[dict], n: int = 3) -> dict:
    """Pick the top-n ranked models, applying a provider-diversity rule to
    the 3rd pick: if rank-1 and rank-2 share a provider, rank-3 must come
    from a different provider (falling back to the plain next-highest score
    if no such candidate exists); otherwise rank-3 is picked purely by score
    (no provider constraint)."""
    top_n = min(n, len(candidates_scored))
    if top_n < 3:
        return {
            "models": candidates_scored[:top_n],
            "diversity_constraint_applied": False,
            "diversity_constraint_satisfied": True,
        }

    rank1, rank2 = candidates_scored[0], candidates_scored[1]
    rest = candidates_scored[2:]

    if rank1["provider"] != rank2["provider"]:
        return {
            "models": [rank1, rank2, rest[0]],
            "diversity_constraint_applied": False,
            "diversity_constraint_satisfied": True,
        }

    rank3 = next((c for c in rest if c["provider"] != rank1["provider"]), None)
    if rank3 is None:
        return {
            "models": [rank1, rank2, rest[0]],
            "diversity_constraint_applied": True,
            "diversity_constraint_satisfied": False,
        }
    return {
        "models": [rank1, rank2, rank3],
        "diversity_constraint_applied": True,
        "diversity_constraint_satisfied": True,
    }


def route(
    doc_type: str,
    input_tokens: int,
    required_feature: str = "vision",
    profile_name: Optional[str] = None,
    quality_floor: Optional[float] = None,
    candidates: Optional[List[ModelCard]] = None,
    complexity_raw: Optional[float] = None,
    expected_output_tokens: Optional[int] = None,
) -> dict:
    """
    Run the hard-filter -> normalize -> score -> select pipeline and
    return a RoutingDecision-shaped dict (chosen model + eligibility funnel).

    doc_type selects which benchmark leaderboard (bol/awb/accord/other) supplies
    the candidate pool's quality/latency/cost/capacity when `candidates` is not
    explicitly passed in (the latter is mainly for tests/programmatic use).

    input_tokens is this request's estimated input token count (e.g. from
    common.py::estimate_image_tokens). expected_output_tokens is a flat,
    caller-supplied (or config-defaulted) assumption about output length --
    mirrors llm-router-platform's RouteRequest.expected_output_tokens; it is
    NOT derived from input_tokens or model capacity.

    complexity_raw is an optional externally-supplied 0-20 complexity value
    (see --complexity). When omitted, quality is not degraded and behavior
    is identical to routing with no complexity concept at all. Complexity
    never affects eligibility (the hard filter below still keys on each
    card's static quality); it degrades predicted quality and shifts the
    profile weights toward quality (hard docs) or cost/latency (easy docs).
    """
    profile_name = profile_name or config.get("IMR_DEFAULT_PROFILE", "balanced")
    quality_floor = quality_floor if quality_floor is not None else config.get_float("IMR_QUALITY_FLOOR", 0.0)

    # Determine expected_output_tokens source and log it
    expected_output_tokens_source = "provided by user"
    default_expected_output = config.get_int("IMR_DEFAULT_EXPECTED_OUTPUT_TOKENS", 512)
    if expected_output_tokens is None:
        expected_output_tokens = default_expected_output
        expected_output_tokens_source = "config default"

    complexity_info = describe_complexity(complexity_raw)
    complexity_norm = complexity_info['normalized'] if complexity_info is not None else None

    _debug("╔════════════════════════════════════════════════════════════════════╗")
    _debug("║                    IMAGE MODEL ROUTING PIPELINE                    ║")
    _debug("╚════════════════════════════════════════════════════════════════════╝")
    _debug(f"\n[1] REQUEST PARAMETERS:")
    _debug(f"  Document type: {doc_type}")
    _debug(f"  Input tokens (estimated): {input_tokens}")
    _debug(f"  Expected output tokens: {expected_output_tokens}")
    _debug(f"    Source: {expected_output_tokens_source}")
    _debug(f"    Config key: IMR_DEFAULT_EXPECTED_OUTPUT_TOKENS = {default_expected_output}")
    _debug(f"  Weight profile: {profile_name}")
    _debug(f"  Quality floor: {quality_floor}")
    _debug(f"  Complexity: {complexity_raw} → normalized: {complexity_norm} ({complexity_info})")

    pool = candidates if candidates is not None else _build_candidates(doc_type)
    _debug(f"\n[2] CANDIDATE POOL LOADED: {len(pool)} models from '{doc_type}' benchmark")

    profile_weights = get_weight_profile(profile_name)
    _debug(f"\n[3] WEIGHT PROFILE APPLIED:")
    _debug(f"  Profile weights: {profile_weights}")
    weights = _adapt_weights(profile_weights, complexity_norm)
    _debug(f"  Effective weights: {weights}")

    _debug(f"\n[4] HARD FILTER (remove ineligible models)")
    filter_result = _hard_filter(pool, quality_floor, input_tokens, expected_output_tokens)
    eligible = filter_result["eligible"]

    if not eligible:
        raise NoEligibleModelError(
            f"No eligible vision-capable model found (required_feature={required_feature}, "
            f"quality_floor={quality_floor}, total_models={len(pool)})"
        )

    _debug(f"\n[5] PREDICT QUALITY (apply complexity degradation if provided)")
    predicted_quality = {}
    for c in eligible:
        predicted_quality[c.model_id] = _predict_quality(c, complexity_norm)

    _debug(f"\n[6] ESTIMATE COST (for this specific request)")
    predicted_cost = {}
    for c in eligible:
        predicted_cost[c.model_id] = _estimate_cost(c, input_tokens, expected_output_tokens)

    _debug(f"\n[7] NORMALIZE SCORES (min-max scaling 0-1, inverted for cost/latency)")
    normalized = _normalize(eligible, predicted_quality, predicted_cost)

    _debug(f"\n[8] CALCULATE FINAL SCORES (weighted dot product)")
    candidates_scored = []
    for card in eligible:
        score = _score(card.model_id, normalized, weights)
        candidates_scored.append({
            "model_id": card.model_id,
            "provider": card.provider,
            "score": round(score, 4),
            "objectives": {o: round(normalized[o][card.model_id], 4) for o in OBJECTIVES},
            "base_quality": round(card.quality, 4),
            "predicted_quality": round(predicted_quality[card.model_id], 4),
            "predicted_cost_usd": round(predicted_cost[card.model_id], 4),
            "cost_per_1m_input_tokens_usd": round(card.cost_per_1m_input_tokens_usd, 4),
            "cost_per_1m_output_tokens_usd": round(card.cost_per_1m_output_tokens_usd, 4),
            "cost_is_placeholder": card.cost_is_placeholder,
            "predicted_latency_ms": round(card.latency_ms, 4),
            "predicted_reliability": card.reliability,
            "context_window": card.context_window,
            "max_output_tokens": card.max_output_tokens,
        })

    candidates_scored.sort(key=lambda c: c["score"], reverse=True)
    _debug(f"\n[9] RANKING (sorted by score descending):")
    for i, c in enumerate(candidates_scored, 1):
        _debug(f"  {i}. {c['model_id']}: score={c['score']:.4f} (quality={c['objectives']['quality']:.4f}, cost={c['objectives']['cost']:.4f}, latency={c['objectives']['latency']:.4f})")

    chosen = candidates_scored[0]
    _debug(f"\n[10] SELECTION:")
    _debug(f"  ✓ CHOSEN: {chosen['model_id']} (score={chosen['score']:.4f})")

    top_models = _select_top_models(candidates_scored, n=3)

    return {
        "strategy": "score",
        "doc_type": doc_type,
        "profile": profile_name,
        "profile_weights": profile_weights,
        "effective_weights": {o: round(w, 4) for o, w in weights.items()},
        "quality_floor": quality_floor,
        "input_tokens": input_tokens,
        "expected_output_tokens": expected_output_tokens,
        "complexity": complexity_info,
        "total_models": len(pool),
        "eligible_count": len(eligible),
        "filtered_out": filter_result["filtered_out"],
        "eligible_ranked": candidates_scored,
        "chosen": chosen,
        "top_models": top_models,
    }
