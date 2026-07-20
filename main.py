import os
import requests
from config import DOMAINS, OUTPUT_DIR, DOCS_DIR
from extract import extract_all

# Retrieve keywords from config.py
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def fetch_grist_grant_records(keywords, max_per_keyword=5):
    """
    Queries Europe PMC GRIST REST API for funded grant records based on search terms.
    Parses GRIST-specific data fields (Grant ID, Funder, PI, Institution, Abstract).
    """
    raw_items = []
    seen_grant_ids = set()

    print(f"[harvest] Querying Europe PMC GRIST API across {len(keywords)} keyword(s)...")

    # Legacy GRIST REST URL syntax format:
    url = f"https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query={kw}&format=json&pageSize={max_per_keyword}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0"
    }

    for kw in keywords:
        # GRIST search query syntax
        query_str = f'"{kw}"'
        params = {
            "query": query_str,
            "format": "json",
            "pageSize": max_per_keyword,
            "page": 1
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"[harvest] HTTP {response.status_code} for keyword: '{kw}'")
                continue

            data = response.json()
            
            # GRIST response payload path for grant records
            grant_list = (
                data.get("recordList", {}).get("grant", [])
                or data.get("responseWrapper", {}).get("userGrantList", {}).get("grant", [])
                or data.get("grantList", {}).get("grant", [])
            )

            # Standardize single dictionary response into list if necessary
            if isinstance(grant_list, dict):
                grant_list = [grant_list]

            # Fallback retry with unquoted search if phrase yielded no results
            if not grant_list:
                print(f"[harvest] 0 GRIST grants for phrase '{query_str}', trying '{kw}'...")
                params["query"] = kw
                response = requests.get(url, params=params, headers=headers, timeout=12)
                if response.status_code == 200:
                    data = response.json()
                    grant_list = (
                        data.get("recordList", {}).get("grant", [])
                        or data.get("responseWrapper", {}).get("userGrantList", {}).get("grant", [])
                        or data.get("grantList", {}).get("grant", [])
                    )
                    if isinstance(grant_list, dict):
                        grant_list = [grant_list]

            print(f"[harvest] Keyword '{kw}': Found {len(grant_list)} grant record(s).")

            for item in grant_list:
                # Extract GRIST Data Fields
                grant_id = item.get("id") or item.get("grantId") or item.get("code")
                title = item.get("title") or item.get("projectTitle", "Untitled Grant")
                
                # Deduplicate records by Grant ID
                unique_key = grant_id if grant_id else title
                if unique_key in seen_grant_ids:
                    continue
                seen_grant_ids.add(unique_key)

                # Extract Funder/Agency
                funder_info = item.get("funder") or item.get("fundingAgency") or {}
                funder_name = funder_info.get("name") if isinstance(funder_info, dict) else str(funder_info or "Europe PMC Funder")

                # Extract Grant Holder / Principal Investigator (PI)
                holder_info = item.get("grantHolder") or item.get("person") or {}
                pi_name = (
                    f"{holder_info.get('firstName', '')} {holder_info.get('lastName', '')}".strip()
                    if isinstance(holder_info, dict)
                    else str(holder_info or "Unlisted PI")
                )

                # Extract Institution & ROR ID
                inst_info = item.get("institution") or item.get("institutionName") or {}
                inst_name = inst_info.get("name") if isinstance(inst_info, dict) else str(inst_info or "Unlisted Institution")
                ror_id = inst_info.get("rorId", "") if isinstance(inst_info, dict) else ""

                # Extract Dates & Abstract
                abstract_text = item.get("abstract") or item.get("abstractText") or "No grant description available."
                start_date = item.get("startDate", "N/A")
                end_date = item.get("endDate", "N/A")

                # Construct Grant Finder link
                grant_link = f"https://europepmc.org/grantfinder/grantid?id={grant_id}" if grant_id else "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title,
                    "abstract": abstract_text,
                    "source": funder_name,
                    "grant_id": grant_id or "N/A",
                    "principal_investigator": pi_name or "N/A",
                    "institution": inst_name,
                    "ror_id": ror_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "keyword": kw,
                    "link": grant_link
                })

        except Exception as e:
            print(f"[harvest] Error parsing GRIST data for '{kw}': {e}")

    print(f"[harvest] Total harvested grant records: {len(raw_items)}")
    return raw_items


def main():
    if not BASIC_SEARCH_KEYWORDS:
        print("❌ No keywords found in DOMAINS['Basic Search']. Please check config.py.")
        return

    # Step 1: Harvest grants using Europe PMC GRIST API
    raw_items = fetch_grist_grant_records(BASIC_SEARCH_KEYWORDS, max_per_keyword=5)

    if not raw_items:
        print("⚠️ No grant records were harvested. Verify internet access or check search terms.")
        return

    # Step 2: Pass harvested records to extract.py pipeline
    print("\n[pipeline] Handing harvested GRIST records to extract.py...")
    success = extract_all(raw_items, OUTPUT_DIR, DOCS_DIR)

    if success:
        print("\n🎉 Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline encountered an issue during extraction.")


if __name__ == "__main__":
    main()
