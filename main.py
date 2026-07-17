"""
On-demand pipeline entrypoint.

Usage:
    python main.py

Requires:
    ANTHROPIC_API_KEY   - for the extraction step
    FWF_API_KEY          - optional, only needed for the FWF (Austria) source

Triggered manually (locally, or via the "Run workflow" button on the
GitHub Actions tab). Each run:
  1. Computes how far back to search based on when the pipeline last
     actually ran (see dedup.compute_lookback_days) — not a fixed
     schedule assumption, since runs are on-demand and may be irregular
  2. Harvests new items from all configured sources for each domain keyword
  3. Deduplicates against everything seen in previous runs (state/seen_items.json)
  4. Runs the two-lens LLM extraction on genuinely new items
  5. Writes markdown + CSV + HTML digests
"""
import os
import sys
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR
from sources import europepmc
from extract import extract_all

def main():
    print(f"[main] Harvesting across categories, {LOOKBACK_DAYS}-day lookback...")
    all_harvested_items = []
    
    # Clean up structure to ensure loop works perfectly
    for domain_name, keywords in DOMAINS.items():
        for kw in keywords:
            # Explicitly capture results from our working EuropePMC engine
            results = europepmc.fetch(kw, LOOKBACK_DAYS, domain_name)
            if results:
                all_harvested_items.extend(results)
                
    print(f"[main] Harvested {len(all_harvested_items)} total items.")
    
    if not all_harvested_items:
        print("[main] No papers found. Generating a standard placeholder page to keep pipeline alive.")
        # Fallback page so deployment never breaks or stays blank
        os.makedirs(DOCS_DIR, exist_ok=True)
        with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
            f.write("<html><body><h1>Biotech Radar Online: No new papers found in this window.</h1></body></html>")
        return 0

    # Feed the papers straight to your Claude compiler
    success = extract_all(all_harvested_items, OUTPUT_DIR, DOCS_DIR)
    if success:
        print("[main] Weekly digest compiled successfully!")
    else:
        print("[main] Failed compiling the dashboard via Claude.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
