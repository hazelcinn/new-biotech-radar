import os
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])

def fetch_grist_grants(keywords, max_per_keyword=5):
    """
    Queries Europe PMC Search API specifically for Grant records.
    Uses the official EBI REST base URL to prevent HTTP 403 blocks.
    """
    raw_items = []
    seen_ids = set()

    print(f"[harvest] Querying Europe PMC Grant DB across {len(keywords)} keyword(s)...")

    # Official EBI Europe PMC endpoint
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PythonGrantHarvester/1.0",
        "Accept": "application/json"
    }

    for kw in keywords:
        # Querying specifically for Grant objects or grant metadata
        query = f'"{kw}" TYPE:GRANT'
        params = {
            "query": query,
            "format": "json",
            "pageSize": max_per_keyword,
            "resultType": "core"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=12)

            if response.status_code == 403:
                # Fallback to broader grant search if TYPE filter is blocked
                params["query"] = f'"{kw}"'
                response = requests.get(url, params=params, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()
            results = data.get("resultList", {}).get("result", [])

            # Fallback if phrase query yielded 0 results
            if not results:
                print(f"[harvest] 0 results for '{query}', trying broader term '{kw}'...")
                params["query"] = kw
                response = requests.get(url, params=params, headers=headers, timeout=12)
                if response.status_code == 200:
                    results = response.json().get("resultList", {}).get("result", [])

            print(f"[harvest] Keyword '{kw}': Found {len(results)} items.")

            for item in results:
                grant_id = item.get("id") or item.get("pmid") or item.get("title")
                
                if grant_id in seen_ids:
                    continue
                seen_ids.add(grant_id)

                # Extract Grant / Funding Metadata
                grants = item.get("grantsList", {}).get("grant", [])
                funder = grants[0].get("agency") if grants else item.get("journalTitle", "Europe PMC Grant DB")
                award_id = grants[0].get("grantId") if grants else "N/A"

                raw_items.append({
                    "title": item.get("title", "Untitled Grant"),
                    "abstract": item.get("abstractText", "No description or abstract available."),
                    "source": funder,
                    "grant_id": award_id,
                    "keyword": kw,
                    "link": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id')}" if item.get("id") else "#"
                })

        except Exception as e:
            print(f"[harvest] Connection error fetching '{kw}': {e}")

    print(f"[harvest] Total harvested grant records: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    raw_items = fetch_grist_grants(BASIC_SEARCH_KEYWORDS, max_per_keyword=5)

    if not raw_items:
        print("⚠️ No items were harvested. Check internet access or keywords.")
        return

    print("\n[pipeline] Handing harvested records to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
