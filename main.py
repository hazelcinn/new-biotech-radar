import os
import urllib.parse
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

# Get basic search terms from config.py
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_grist_grants(keywords, max_per_keyword=5):
    """
    Queries the official Europe PMC GRIST API using strict path-query syntax.
    Parses native GRIST JSON payload for grant awards (ID, Title, Funder, Abstract).
    """
    raw_items = []
    seen_ids = set()

    print(f"[harvest] Querying Europe PMC GRIST API across {len(keywords)} keyword(s)...")

    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    for kw in keywords:
        # Build GRIST query with keyword parameter (kw:)
        encoded_kw = urllib.parse.quote(f'kw:"{kw}"')
        url = f"{base_url}{encoded_kw}&format=json"

        try:
            response = requests.get(url, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()

            # GRIST response record list hierarchy
            record_list = data.get("RecordList", {})
            grants = record_list.get("grant", []) if isinstance(record_list, dict) else []

            # Handle single dict response if GRIST returns only 1 hit
            if isinstance(grants, dict):
                grants = [grants]

            print(f"[harvest] Keyword '{kw}': Found {len(grants)} grant(s).")

            count = 0
            for item in grants:
                # Extract GRIST fields
                grant_id = item.get("id") or item.get("code") or "N/A"
                title = item.get("title", "Untitled Grant Project")
                abstract = item.get("abstract", "No abstract text available.")
                funder = item.get("GrantedAuthority", "Europe PMC / GRIST")
                
                # Deduplicate records across overlapping terms
                unique_key = grant_id if grant_id != "N/A" else title
                if unique_key in seen_ids:
                    continue
                seen_ids.add(unique_key)

                # Direct link to Europe PMC Grant Finder entry
                grant_link = f"https://europepmc.org/grantfinder/grantid?id={grant_id}" if grant_id != "N/A" else "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title,
                    "abstract": abstract,
                    "source": funder,
                    "keyword": kw,
                    "link": grant_link
                })

                count += 1
                if count >= max_per_keyword:
                    break

        except Exception as e:
            print(f"[harvest] Error fetching GRIST data for '{kw}': {e}")

    print(f"[harvest] Total harvested GRIST grant records: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    # Step 1: Harvest actual grant records directly from GRIST API
    raw_items = fetch_grist_grants(BASIC_SEARCH_KEYWORDS, max_per_keyword=5)

    if not raw_items:
        print("⚠️ No grant records harvested. Verify internet access or check keywords in config.py.")
        return

    # Step 2: Pass harvested items to extract.py pipeline (Ollama + HTML dashboard)
    print("\n[pipeline] Handing harvested records to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
