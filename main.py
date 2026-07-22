import sys
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR

from sources import europepmc, nih_reporter, nsf, ukri_gtr, cordis, fwf
from extract import extract_all
from digest import write_markdown, write_csv, write_html, write_pages_index


def harvest_all(lookback_days: int):
    all_items = []
    all_keywords = [(kw, domain) for domain, kws in DOMAINS.items() for kw in kws]

    print(f"[main] Harvesting grants across {len(all_keywords)} keyword queries, "
          f"{lookback_days}-day lookback...")

    for kw, domain in all_keywords:
        # ONLY pull grants - no articles or preprints
        all_items.extend(europepmc.fetch_grants(kw, lookback_days, domain))
        all_items.extend(nih_reporter.fetch(kw, lookback_days, domain))
        all_items.extend(nsf.fetch(kw, lookback_days, domain))
        all_items.extend(ukri_gtr.fetch(kw, lookback_days, domain))
        all_items.extend(cordis.fetch(kw, lookback_days, domain))
        all_items.extend(fwf.fetch(kw, lookback_days, domain))

    print(f"[main] Harvested {len(all_items)} raw grant items.")
    return all_items


def main():
    lookback_days = LOOKBACK_DAYS
    raw_items = harvest_all(lookback_days)

    if not raw_items:
        print("[main] No grants harvested.")
        return

    # Bypass deduplication entirely so items always process as new
    extracted_items = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if not extracted_items:
        print("[main] Extraction returned no items.")
        return

    md_path = write_markdown(extracted_items, OUTPUT_DIR)
    csv_path = write_csv(extracted_items, OUTPUT_DIR)
    html_path = write_html(extracted_items, DOCS_DIR)
    index_path = write_pages_index(DOCS_DIR)

    print(
        "[main] Digest written:\n"
        f"  {md_path}\n"
        f"  {csv_path}\n"
        f"  {html_path}  (published via GitHub Pages)\n"
        f"  {index_path}  (archive index, also published)"
    )


if __name__ == "__main__":
    sys.exit(main())
