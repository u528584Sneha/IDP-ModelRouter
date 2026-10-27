"""
Optional cost overrides for benchmark-sourced models.

Quality, latency, cost, and capacity (context window / max output tokens)
now come from the benchmark xlsx leaderboards (benchmarks.py), keyed by
--doc-type -- every benchmark row carries its own "Input Token Cost($)" and
"Output Token Cost($)" (USD per 1M tokens), so this table is no longer
required to get a real (non-placeholder) cost.

This table remains as an optional escape hatch: if a model_id has an entry
here, it WINS over the benchmark row's cost (e.g. to correct a benchmark
value without editing the spreadsheet). Entries are keyed by the same
slugified model ids benchmarks.slugify_model_name produces, e.g.
"Claude Opus 5.5" -> "claude-opus-5.5".

Reliability is not currently used in scoring (see router.py OBJECTIVES) --
no reliability field is tracked here for that reason.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CostOverride:
    cost_per_1m_input_tokens_usd: float
    cost_per_1m_output_tokens_usd: float


MODEL_COST_OVERRIDES: Dict[str, CostOverride] = {
    # Override a benchmark row's cost here if needed, e.g.:
    # "claude-opus-5.5": CostOverride(cost_per_1m_input_tokens_usd=3.0, cost_per_1m_output_tokens_usd=15.0),
}


def get_cost_override(model_id: str) -> Optional[CostOverride]:
    return MODEL_COST_OVERRIDES.get(model_id)
