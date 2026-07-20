import os
import urllib.parse
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_grist_grants(keywords, max_per_keyword=5):
    """
    Queries Europe PMC GRIST API using direct query format.
    Safely extracts Title, Abstract, Funder, and Grant ID.
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
        clean_kw = kw.strip()
        encoded_query = urllib.parse.quote(clean_kw)
        url = f"{base_url}{encoded_query}&format=json"

        try:
            response = requests.get(url, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()

            # Navigate GRIST JSON hierarchy
            record_list = data.get("RecordList", {}) if isinstance(data, dict) else {}
            records = (
                record_list.get("Record", [])
                or record_list.get("grant", [])
                or data.get("Record", [])
            )

            if isinstance(records, dict):
                records = [records]

            added_for_this_kw = 0
            for item in records:
                # Extract GRIST fields with deep fallbacks
                grant_id = str(item.get("Id") or item.get("id") or "").strip()
                title = str(item.get("Title") or item.get("title") or "Untitled Grant Project").strip()
                abstract = str(item.get("Abstract") or item.get("abstract") or "No abstract description provided.").strip()
                funder = str(item.get("GrantedAuthority") or item.get("funder") or "Europe PMC / GRIST").strip()

                # Deduplicate based on unique Grant ID or Title
                unique_key = grant_id if grant_id else title
                if not unique_key or unique_key in seen_ids:
                    continue
                seen_ids.add(unique_key)

                grant_link = f"https://europepmc.org/grantfinder/grantid?id={grant_id}" if grant_id else "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title,
                    "abstract": abstract,
                    "source": funder,
                    "keyword": kw,
                    "link": grant_link
                })

                added_for_this_kw += 1
                if added_for_this_kw >= max_per_keyword:
                    break

            print(f"[harvest] Keyword '{kw}': Extracted {added_for_this_kw} unique grant(s).")

        except Exception as e:
            print(f"[harvest] Error fetching GRIST data for '{kw}': {e}")

    print(f"[harvest] Total harvested GRIST grant records: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    raw_items = fetch_grist_grants(BASIC_SEARCH_KEYWORDS, max_per_keyword=3)

    if not raw_items:
        print("⚠️ No grant records harvested. Check internet connection or keywords in config.py.")
        return

    print("\n[pipeline] Handing harvested records to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
