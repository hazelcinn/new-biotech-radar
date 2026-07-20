import os
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

# Get basic search keywords from config.py
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_europepmc_records(keywords, max_per_keyword=3):
    """
    Queries Europe PMC REST API for research papers/grants matching config keywords.
    Formats data into the schema expected by extract.py.
    """
    raw_items = []
    seen_ids = set()

    print(f"[harvest] Querying Europe PMC across {len(keywords)} keywords...")

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    for kw in keywords:
        # Search for keyword with grant funding filter
        query = f'"{kw}" HAS_GRANT:y'
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

            for item in results:
                pmc_id = item.get("id") or item.get("pmid") or item.get("title")
                
                # Avoid duplicate records across overlapping keywords
                if pmc_id in seen_ids:
                    continue
                seen_ids.add(pmc_id)

                # Extract Grant/Funding Agency if available
                grants = item.get("grantsList", {}).get("grant", [])
                funding_agency = grants[0].get("agency", "Europe PMC / Funded") if grants else "Europe PMC"

                # Construct paper article link
                article_source = item.get("source", "MED")
                link = f"https://europepmc.org/article/{article_source}/{item.get('id')}" if item.get("id") else "#"

                raw_items.append({
                    "title": item.get("title", "Untitled Research"),
                    "abstract": item.get("abstractText", "No abstract available."),
                    "source": funding_agency,
                    "keyword": kw,
                    "link": link
                })

        except Exception as e:
            print(f"[harvest] Error fetching keyword '{kw}': {e}")

    print(f"[harvest] Successfully harvested {len(raw_items)} items.")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Check config.py.")
        return

    # Step 1: Harvest papers from Europe PMC
    raw_items = fetch_europepmc_records(BASIC_SEARCH_KEYWORDS, max_per_keyword=3)

    if not raw_items:
        print("⚠️ No items were harvested. Check your network connection.")
        return

    # Step 2: Pass items to your extract.py Ollama pipeline
    print("\n[pipeline] Handing harvested items over to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
