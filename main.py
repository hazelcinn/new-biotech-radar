import sys
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR

from sources import europepmc, biorxiv, semantic_scholar, nih_reporter, nsf, ukri_gtr, cordis, fwf
from dedup import deduplicate, save_state, compute_lookback_days
from extract import extract_all
from digest import write_markdown, write_csv, write_html, write_pages_index

# ADD TO main.py at module scope (near other helpers, before harvest_all)
def _reporter_link_score(item: dict) -> int:
    """
    Scoring: higher means more authoritative reporter link.
      3: contains '/project-details/' (authoritative detail page)
      2: reporter_numeric_id present (numeric id available)
      1: reporter.nih.gov link present but not /project-details/
      0: nothing reporter-specific
    """
    url = (item.get("reporter_project_detail_url") or "") or (item.get("link") or "")
    if url and "/project-details/" in url:
        return 3
    if item.get("reporter_numeric_id"):
        return 2
    if url and "reporter.nih.gov" in url:
        return 1
    return 0

def merge_into_all_items(all_items: list, new_item: dict, debug: bool = False):
    """
    Merge new_item into all_items keyed by source_id.
    Prefer items with better reporter link authority. Merge missing fields from the lower-scored item.
    """
    sid = new_item.get("source_id")
    if not sid:
        # No source_id: append defensively
        if debug:
            print("[merge] new item has no source_id; appending")
        all_items.append(new_item)
        return

    for i, existing in enumerate(all_items):
        if existing.get("source_id") == sid:
            new_score = _reporter_link_score(new_item)
            exist_score = _reporter_link_score(existing)
            if debug:
                print(f"[merge] source_id={sid} exist_score={exist_score} new_score={new_score}")
            if new_score > exist_score:
                # new_item is more authoritative: replace, but keep non-empty fields from existing
                merged = new_item.copy()
                for k, v in existing.items():
                    if (k not in merged or not merged.get(k)) and v:
                        merged[k] = v
                all_items[i] = merged
                if debug:
                    print(f"[merge] replaced existing item for source_id={sid} with higher-scored new_item")
            else:
                # existing is better or equal: keep existing but merge missing fields from new_item
                for k, v in new_item.items():
                    if (k not in existing or not existing.get(k)) and v:
                        existing[k] = v
                all_items[i] = existing
                if debug:
                    print(f"[merge] kept existing item for source_id={sid}; merged missing fields from new_item")
            return

    # no existing match -> append
    if debug:
        print(f"[merge] no existing item for source_id={sid}; appending new_item")
    all_items.append(new_item)

def harvest_all(lookback_days: int):
    all_items = []
    all_keywords = [(kw, domain) for domain, kws in DOMAINS.items() for kw in kws]

    print(f"[main] Harvesting across {len(all_keywords)} keyword queries, "
          f"{lookback_days}-day lookback...")

    for kw, domain in all_keywords:
#        all_items.extend(europepmc.fetch(kw, lookback_days, domain))
        all_items.extend(europepmc.fetch_grants(kw, lookback_days, domain))
#        all_items.extend(semantic_scholar.fetch(kw, lookback_days, domain))
        # REPLACE the old extend call in harvest_all with this merge loop
        new_items = nih_reporter.fetch_nih_reporter(kw, lookback_days, domain)
        for ni in new_items:
            # pass debug=True to get merge diagnostic prints if you need them
            merge_into_all_items(all_items, ni, debug=False)
#        all_items.extend(nsf.fetch(kw, lookback_days, domain))
#        all_items.extend(ukri_gtr.fetch(kw, lookback_days, domain))
#        all_items.extend(cordis.fetch(kw, lookback_days, domain))
#        all_items.extend(fwf.fetch(kw, lookback_days, domain))

    # bioRxiv/medRxiv is date-range based, not per-keyword — pull once
#    flat_keywords = [kw for kw, _ in all_keywords]
#    domain_hints = {kw: domain for kw, domain in all_keywords}
#    all_items.extend(biorxiv.fetch(flat_keywords, lookback_days, domain_hints))

    print(f"[main] Harvested {len(all_items)} raw items (pre-dedup).")
    return all_items


def main():
    lookback_days = compute_lookback_days(STATE_FILE, LOOKBACK_DAYS)
    raw_items = harvest_all(lookback_days)

#    fresh_items, updated_state = deduplicate(raw_items, STATE_FILE)
#    print(f"[main] {len(fresh_items)} new items after deduplication.")
#
#    if not fresh_items:
#        print("[main] Nothing new since last run. Saving state, no digest written.")
#        save_state(STATE_FILE, updated_state)
#        return

    # Updated to pass output/docs paths matching your local Ollama pipeline structure
#    extracted_items = extract_all(fresh_items, OUTPUT_DIR, DOCS_DIR)
    extracted_items = raw_items

    if not extracted_items:
        print("[main] Extraction returned no items.")
#        save_state(STATE_FILE, updated_state)
        return

    md_path = write_markdown(extracted_items, OUTPUT_DIR)
    csv_path = write_csv(extracted_items, OUTPUT_DIR)
    html_path = write_html(extracted_items, DOCS_DIR)
    index_path = write_pages_index(DOCS_DIR)

#    save_state(STATE_FILE, updated_state)

    print(
        "[main] Digest written:\n"
        f"  {md_path}\n"
        f"  {csv_path}\n"
        f"  {html_path}  (published via GitHub Pages)\n"
        f"  {index_path}  (archive index, also published)"
    )


if __name__ == "__main__":
    sys.exit(main())
