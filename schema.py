"""
Every source module returns a list of dicts matching this shape, so the
rest of the pipeline (dedup, extraction, digest) never needs to know which
API something came from.
"""

def make_item(
    source: str,
    item_type: str,       # "publication" | "preprint" | "grant" | "patent"
    title: str,
    url: str,
    date: str,             # ISO format YYYY-MM-DD, best available
    country: str = "",
    institution: str = "",
    raw_text: str = "",    # abstract / objective / description text
    domain_hint: str = "", # which config.DOMAINS keyword bucket matched
):
    return {
        "source": source,
        "item_type": item_type,
        "title": title.strip() if title else "",
        "url": url,
        "date": date,
        "country": country,
        "institution": institution,
        "raw_text": (raw_text or "").strip(),
        "domain_hint": domain_hint,
        # filled in later by extract.py
        "extracted": None,
    }
