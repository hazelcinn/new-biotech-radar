import sys
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR

from sources import europepmc, biorxiv, semantic_scholar, nih_reporter, nsf, ukri_gtr, cordis, fwf
from dedup import deduplicate, save_state, compute_lookback_days
from extract import extract_all
from digest import write_markdown, write_csv, write_html, write_pages_index


def harvest_all(lookback_days: int):
    all_items = []
    all_keywords = [(kw, domain) for domain, kws in DOMAINS.items() for kw in kws]

    print(f"[main] Harvesting across {len(all_keywords)} keyword queries, "
          f"{lookback_days}-day lookback...")

    for kw, domain in all_keywords:
#        all_items.extend(europepmc.fetch(kw, lookback_days, domain))
        all_items.extend(europepmc.fetch_grants(kw, lookback_days, domain))
        all_items.extend(semantic_scholar.fetch(kw, lookback_days, domain))
        all_items.extend(nih_reporter.fetch(kw, lookback_days, domain))
        all_items.extend(nsf.fetch(kw, lookback_days, domain))
        all_items.extend(ukri_gtr.fetch(kw, lookback_days, domain))
        all_items.extend(cordis.fetch(kw, lookback_days, domain))
        all_items.extend(fwf.fetch(kw, lookback_days, domain))

    # bioRxiv/medRxiv is date-range based, not per-keyword — pull once
    flat_keywords = [kw for kw, _ in all_keywords]
    domain_hints = {kw: domain for kw, domain in all_keywords}
    all_items.extend(biorxiv.fetch(flat_keywords, lookback_days, domain_hints))

    print(f"[main] Harvested {len(all_items)} raw items (pre-dedup).")
    return all_items


def main():
    lookback_days = compute_lookback_days(STATE_FILE, LOOKBACK_DAYS)
    raw_items = harvest_all(lookback_days)

    fresh_items, updated_state = deduplicate(raw_items, STATE_FILE)
    print(f"[main] {len(fresh_items)} new items after deduplication.")

    if not fresh_items:
        print("[main] Nothing new since last run. Saving state, no digest written.")
        save_state(STATE_FILE, updated_state)
        return

    # Updated to pass output/docs paths matching your local Ollama pipeline structure
    extracted_items = extract_all(fresh_items, OUTPUT_DIR, DOCS_DIR)

    if not extracted_items:
        print("[main] Extraction returned no items.")
        save_state(STATE_FILE, updated_state)
        return

    md_path = write_markdown(extracted_items, OUTPUT_DIR)
    csv_path = write_csv(extracted_items, OUTPUT_DIR)
    html_path = write_html(extracted_items, DOCS_DIR)
    index_path = write_pages_index(DOCS_DIR)

    save_state(STATE_FILE, updated_state)

    print(
        "[main] Digest written:\n"
        f"  {md_path}\n"
        f"  {csv_path}\n"
        f"  {html_path}  (published via GitHub Pages)\n"
        f"  {index_path}  (archive index, also published)"
    )


if __name__ == "__main__":
    sys.exit(main())
