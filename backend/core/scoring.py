"""
core/scoring.py
================
Single source of truth for signal weights and tier thresholds (spec
Section 5). Both routes/ingest.py (assigns a weight at write-time) and
core/correlation_engine.py (sums weights + decides tiers) import from
here so the numbers can't drift out of sync between the two.
"""

# (signal_type, label) -> point value.
SIGNAL_WEIGHTS = {
    ("search_query", "scam"): 1,
    ("url_visit", "unconfirmed"): 2,
    ("search_query", "concealment"): 2,
    ("chat_text", "personal_info_request"): 3,
    ("chat_text", "platform_switch_request"): 3,
}

# Fallback weights for a (signal_type, label) pair that isn't in the table
# above verbatim — e.g. a concealment phrase caught in page_text rather
# than search_query, or a grooming label the keyword list still returns
# generally. Keeps every risky label worth *something* even if it isn't
# one of the five signals the spec calls out explicitly.
DEFAULT_LABEL_WEIGHTS = {
    "scam": 1,
    "unconfirmed": 2,
    "concealment": 2,
    "grooming": 3,
    "personal_info_request": 3,
    "platform_switch_request": 3,
}

# Tier thresholds on the summed score within a rolling window.
TIER_1_MIN = 1
TIER_2_MIN = 3
TIER_3_MIN = 6


def get_weight(signal_type: str, label: str) -> int:
    """
    Look up the point value for a given (signal_type, label) pair.
    "safe" (or no label) is always worth 0. Falls back to a
    label-only lookup, then to 0 if the label is entirely unrecognized.
    """
    if not label or label == "safe":
        return 0

    if (signal_type, label) in SIGNAL_WEIGHTS:
        return SIGNAL_WEIGHTS[(signal_type, label)]

    return DEFAULT_LABEL_WEIGHTS.get(label, 0)


def get_weighted_score(signal_type: str, label: str, multiplier: float = 1.0) -> int:
    """
    Same as get_weight, but scaled by a per-child multiplier (Section
    7.1's false-positive feedback loop). Rounded to the nearest int since
    Event.weight and the tier thresholds are both integers.
    """
    base = get_weight(signal_type, label)
    return round(base * multiplier)


def tier_for_score(score: int) -> int | None:
    """
    Map a summed score to a tier per the spec's table. Returns None for
    a score of 0 (nothing worth acting on at all).
    """
    if score >= TIER_3_MIN:
        return 3
    if score >= TIER_2_MIN:
        return 2
    if score >= TIER_1_MIN:
        return 1
    return None
