import os
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

# Retrieve search terms from config.py
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_actual_grants(keywords, max_per_keyword=5):
    """
    Queries Europe PMC REST API specifically for Grant Award Projects (SRC:GRANT).
    Excludes research publications/papers completely.
    """
    raw_items = []
    seen_grant_ids = set()

    print(f"[harvest] Querying Europe PMC Grant Database across {len(keywords)} keyword(s)...")

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    for kw in keywords:
        # SRC:GRANT restricts results EXCLUSIVELY to funded grant project records
        query = f'SRC:GRANT AND "{kw}"'
        params = {
            "query": query,
            "format": "json",
            "pageSize": max_per_keyword,
            "resultType": "core"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()
            results = data.get("resultList", {}).get("result", [])

            # Fallback retry with unquoted keyword if exact phrase yielded 0 grants
            if not results:
                print(f"[harvest] 0 grants for '{query}', retrying broader term...")
                params["query"] = f'SRC:GRANT AND {kw}'
                response = requests.get(url, params=params, headers=headers, timeout=12)
                if response.status_code == 200:
                    results = response.json().get("resultList", {}).get("result", [])

            print(f"[harvest] Keyword '{kw}': Found {len(results)} actual grant record(s).")

            for item in results:
                grant_id = item.get("id") or item.get("title")
                
                # Deduplicate records across keywords
                if grant_id in seen_grant_ids:
                    continue
                seen_grant_ids.add(grant_id)

                # Extract Funder Agency and PI from grant record metadata
                grants = item.get("grantsList", {}).get("grant", [])
                funder = grants[0].get("agency") if grants else "Europe PMC Grant Finder"
                award_number = grants[0].get("grantId") if grants else item.get("id", "N/A")
                
                pi_name = item.get("authorString", "Unlisted PI")

                # Direct link to Europe PMC Grant Finder entry
                grant_link = f"https://europepmc.org/grantfinder/grantid?id={award_number}" if award_number != "N/A" else "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": item.get("title", "Untitled Grant Award"),
                    "abstract": item.get("abstractText", "No grant description or abstract available."),
                    "source": f"{funder} (Grant ID: {award_number} | PI: {pi_name})",
                    "keyword": kw,
                    "link": grant_link
                })

        except Exception as e:
            print(f"[harvest] Connection error fetching grant for '{kw}': {e}")

    print(f"[harvest] Total harvested actual grant awards: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    # Step 1: Harvest actual grant awards
    raw_items = fetch_actual_grants(BASIC_SEARCH_KEYWORDS, max_per_keyword=5)

    if not raw_items:
        print("⚠️ No grant records were harvested. Check network access or search terms.")
        return

    # Step 2: Send harvested grant awards to extract.py
    print("\n[pipeline] Handing harvested grant awards to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
