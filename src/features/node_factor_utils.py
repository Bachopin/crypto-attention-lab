"""Utilities for reusing node carry factors inside the attention pipeline.

The node carry factor was originally exposed via the API for diagnostics.
This helper module adds lightweight aggregation / transformation helpers so
that other modules (news weighting, diagnostics dashboards) can pull the
same statistics without duplicating logic.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.config.attention_channels import (
    ENABLE_NODE_WEIGHT_ADJUSTMENT,
    NODE_ADJUSTMENT_LOOKAHEAD,
    NODE_ADJUSTMENT_LOOKBACK_DAYS,
    NODE_ADJUSTMENT_MIN_EVENTS,
    NODE_ADJUSTMENT_SCALING,
)


def _sigmoid_rescale(value: float, scaling: float) -> float:
    """Map raw IR values into a bounded multiplier around 1.

    We keep the mapping intentionally simple/monotonic so that researchers
    can reason about the effect. tanh ensures extreme IR does not blow up
    weights, while `scaling` controls the spread (e.g. 0.2 => +/-20%).
    """

    # Cap IR to avoid exploding tanh inputs when DB gets noisy values.
    capped = float(np.clip(value, -5.0, 5.0))
    return 1.0 + np.tanh(capped) * scaling


@lru_cache(maxsize=128)
def get_node_weight_lookup(
    symbol: str,
    lookahead: str = NODE_ADJUSTMENT_LOOKAHEAD,
    lookback_days: int = NODE_ADJUSTMENT_LOOKBACK_DAYS,
    min_events: int = NODE_ADJUSTMENT_MIN_EVENTS,
    scaling: float = NODE_ADJUSTMENT_SCALING,
) -> Dict[str, float]:
    """Return node_id -> multiplier lookup derived from carry factors.

    The lookup is cached per `(symbol, lookahead, lookback_days, min_events)`
    tuple to avoid repeated DB scans inside feature generation.
    """

    if not ENABLE_NODE_WEIGHT_ADJUSTMENT:
        return {}

    from src.features.node_influence import load_node_carry_factors  # local import to dodge circulars

    df = load_node_carry_factors(symbol)
    if df.empty:
        return {}

    df = df[(df["lookahead"] == lookahead) & (df["lookback_days"] == lookback_days)]
    if df.empty:
        return {}

    df = df[df["n_events"] >= int(min_events)]
    if df.empty:
        return {}

    lookup: Dict[str, float] = {}
    for _, row in df.iterrows():
        node_id = str(row["node_id"])
        ir = float(row.get("ir", 0.0) or 0.0)
        lookup[node_id] = _sigmoid_rescale(ir, scaling)
    return lookup


def get_source_level_multiplier(node_id: str, lookup: Dict[str, float]) -> Optional[float]:
    """Convenience accessor with graceful fallback for missing node IDs."""

    if not lookup:
        return None
    return lookup.get(node_id)
