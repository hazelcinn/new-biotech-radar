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
import re
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
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= TITLE_SIMILARITY_THRESHOLD

def _normalized_title_key(title: str) -> str:
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[^a-z0-9 ]', '', s)
    return s

def _parse_suffix_number_from_source_id(source_id: str) -> int:
    if not source_id:
        return 0
    m = re.search(r'-(\d+)(?:[A-Za-z0-9]*)?$', source_id)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 0
    return 0

def _parse_year_from_duration(duration_field) -> int:
    if not duration_field:
        return 0
    s = str(duration_field)
    m = re.search(r'(\d{4})(?:\D|$)', s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 0
    return 0

def _is_reporter_projnum(sid: str) -> bool:
    # conservative heuristic: must contain letters and digits, not be purely numeric,
    # and have reasonable length to avoid tiny internal ids like "2"
    if not sid:
        return False
    s = str(sid).strip()
    if s.isdigit():
        return False
    if len(s) < 8:
        return False
    if not (re.search(r'[A-Za-z]', s) and re.search(r'\d', s)):
        return False
    if not re.match(r'^[A-Za-z0-9\-\_:\.]+$', s):
        return False
    return True

def _score_item(it: dict) -> int:
    sc = 0
    sid = (it.get("source_id") or it.get("sourceId") or "") or ""
    if _is_reporter_projnum(sid):
        sc += 100000
    sc += _parse_suffix_number_from_source_id(sid) * 1000
    sc += _parse_year_from_duration(it.get("grant duration") or it.get("duration") or "")
    amt = it.get("grant amount") or it.get("amount") or ""
    try:
        num = (
            float(str(amt).replace("$", "").replace(",", ""))
            if isinstance(amt, (int, float)) or any(ch.isdigit() for ch in str(amt))
            else 0.0
        )
    except Exception:
        num = 0.0
    sc += int(num)
    return sc

state = load_state(state_file)
seen = state.get("seen", [])
seen_urls = {s["url"] for s in seen if s.get("url")}
seen_titles = [s["title"] for s in seen if s.get("title")]

# Build a set of seen keys that includes source+source_id when available,
# otherwise falls back to URL/title. This avoids collapsing distinct
# subprojects that share a parent project number.
seen_keys = set()
for s in seen:
    sid = s.get("source_id") or s.get("sourceId") or None
    if sid:
        seen_keys.add(f"{s.get('source') or ''}|{sid}")
    else:
        seen_keys.add(s.get("url") or s.get("title") or "")

fresh = []
for item in new_items:
    url = item.get("url", "")
    title = item.get("title", "")

    if url and url in seen_urls:
        continue
    if title and any(_title_similar(title, t) for t in seen_titles):
        continue

    source_id = item.get("source_id") or item.get("sourceId") or None
    if source_id:
        key = f"{item.get('source') or ''}|{source_id}"
    else:
        key = item.get("link") or (item.get("title", "") + "|" + item.get("project_contact_name", ""))

    if key in seen_keys:
        continue

    fresh.append(item)
    if url:
        seen_urls.add(url)
    if title:
        seen_titles.append(title)
    seen_keys.add(key)

# --- collapse multiple matching titles into a single best item for the manifest
grouped = {}
for it in fresh:
    key = _normalized_title_key(it.get("title", ""))
    grouped.setdefault(key, []).append(it)

selected = []
for group in grouped.values():
    if len(group) == 1:
        selected.append(group[0])
    else:
        best = max(group, key=_score_item)
        selected.append(best)

fresh = selected

updated_seen = seen + [
    {
        "url": i.get("url", ""),
        "title": i.get("title", ""),
        "source": i.get("source", ""),
        "source_id": i.get("source_id", "") or i.get("sourceId", ""),
    }
    for i in fresh
]
updated_state = {"last_run_date": date.today().isoformat(), "seen": updated_seen}
return fresh, updated_state
