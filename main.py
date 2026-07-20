import os
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

# Retrieve keywords from config.py
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_europepmc_records(keywords, max_per_keyword=3):
    """
    Queries Europe PMC REST API for research papers matching config keywords.
    Formats data into the dictionary schema expected by extract.py.
    """
    raw_items = []
    seen_ids = set()

    print(f"[harvest] Querying Europe PMC across {len(keywords)} keyword(s)...")

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    for kw in keywords:
        # Search query: broad search for keyword with abstract available
        query = f'"{kw}" HAS_ABSTRACT:y'
        params = {
            "query": query,
            "format": "json",
            "pageSize": max_per_keyword,
            "resultType": "core",
            "sort": "P_PD_DATE desc"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()
            results = data.get("resultList", {}).get("result", [])

            # Fallback query if exact phrase + filter yielded 0 results
            if not results:
                print(f"[harvest] 0 results for '{query}', trying broader term '{kw}'...")
                params["query"] = kw
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    results = response.json().get("resultList", {}).get("result", [])

            print(f"[harvest] Keyword '{kw}': Found {len(results)} items.")

            for item in results:
                pmc_id = item.get("id") or item.get("pmid") or item.get("title")
                
                # Prevent duplicates across overlapping keyword searches
                if pmc_id in seen_ids:
                    continue
                seen_ids.add(pmc_id)

                # Extract Grant or Publisher information
                grants = item.get("grantsList", {}).get("grant", [])
                funding_agency = grants[0].get("agency") if grants else item.get("journalTitle", "Europe PMC")

                # Build public article link
                article_source = item.get("source", "MED")
                link = f"https://europepmc.org/article/{article_source}/{item.get('id')}" if item.get("id") else "#"

                raw_items.append({
                    "title": item.get("title", "Untitled Research"),
                    "abstract": item.get("abstractText", "No abstract text available."),
                    "source": funding_agency,
                    "keyword": kw,
                    "link": link
                })

        except Exception as e:
            print(f"[harvest] Connection error fetching '{kw}': {e}")

    print(f"[harvest] Total harvested records: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    # Step 1: Harvest papers from Europe PMC
    raw_items = fetch_europepmc_records(BASIC_SEARCH_KEYWORDS, max_per_keyword=3)

    if not raw_items:
        print("⚠️ No items were harvested. Verify internet access or check search terms in config.py.")
        return

    # Step 2: Pass harvested items to extract.py pipeline
    print("\n[pipeline] Handing harvested records to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
