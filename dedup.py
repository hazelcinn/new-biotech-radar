"""
Deduplication + adaptive lookback window.

State file schema (JSON):
{
  "last_run_date": "2026-07-17",   # ISO date of the previous successful run
  "seen": [{"url": ..., "title": ..., "source": ...}, ...]
}

Deduplication itself:
1. Exact URL match against previously seen items.
2. Fuzzy title similarity (difflib) against recently seen items, to catch
   the same project appearing as both a grant record and, months later,
   a publication with a near-identical title.

This is intentionally simple for v1. If false-duplicate or missed-duplicate
rates turn out to be a problem once real volume comes in, the natural
upgrade is embedding-based similarity instead of string matching.
"""
import json
import os
from datetime import date, timedelta
from difflib import SequenceMatcher

TITLE_SIMILARITY_THRESHOLD = 0.88

# Since runs are on-demand rather than scheduled, the lookback window
# adapts to how long it's actually been since the last run, instead of
# assuming a fixed weekly cadence. These bounds keep it sane:
MIN_LOOKBACK_DAYS = 9    # never search a window smaller than this
MAX_LOOKBACK_DAYS = 90   # cap it — very long gaps should prompt a manual review of the plan, not one giant catch-up query


def _default_state() -> dict:
    return {"last_run_date": None, "seen": []}


def load_state(state_file: str) -> dict:
    if not os.path.exists(state_file):
        return _default_state()
    with open(state_file, "r") as f:
        data = json.load(f)
    # backward-compat: if an old flat-list state file exists, wrap it
    if isinstance(data, list):
        return {"last_run_date": None, "seen": data}
    return data


def save_state(state_file: str, state: dict):
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def compute_lookback_days(state_file: str, configured_default: int) -> int:
    """
    Returns how many days back to search this run. On-demand runs may be
    days or weeks apart, so this looks at when the pipeline last actually
    ran (not a fixed schedule assumption) and searches back that far,
    clamped to [MIN_LOOKBACK_DAYS, MAX_LOOKBACK_DAYS].
    """
    state = load_state(state_file)
    last_run = state.get("last_run_date")
    if not last_run:
        return configured_default  # first-ever run

    days_since = (date.today() - date.fromisoformat(last_run)).days
    if days_since > MAX_LOOKBACK_DAYS:
        print(
            f"[dedup] Last run was {days_since} days ago — capping lookback at "
            f"{MAX_LOOKBACK_DAYS} days. Some items published in the gap may be "
            f"missed; consider running more frequently or widening MAX_LOOKBACK_DAYS "
            f"in dedup.py for a one-off catch-up run."
        )
        return MAX_LOOKBACK_DAYS
    return max(days_since, MIN_LOOKBACK_DAYS)


def _title_similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= TITLE_SIMILARITY_THRESHOLD


def deduplicate(new_items: list, state_file: str):
    """
    Returns (fresh_items, updated_state).
    fresh_items = items not seen before, safe to include in this run's digest.
    updated_state = full state dict (seen list + today's date), ready to save_state().
    """
    state = load_state(state_file)
    seen = state.get("seen", [])
    seen_urls = {s["url"] for s in seen if s.get("url")}
    seen_titles = [s["title"] for s in seen if s.get("title")]

    fresh = []
    for item in new_items:
        url = item.get("url", "")
        title = item.get("title", "")

        if url and url in seen_urls:
            continue
        if title and any(_title_similar(title, t) for t in seen_titles):
            continue

        fresh.append(item)
        seen_urls.add(url)
        seen_titles.append(title)

    updated_seen = seen + [
        {"url": i.get("url", ""), "title": i.get("title", ""), "source": i.get("source", "")}
        for i in fresh
    ]
    updated_state = {"last_run_date": date.today().isoformat(), "seen": updated_seen}
    return fresh, updated_state
