import urllib.parse
import requests

def fetch(keyword: str, lookback_days: int, domain: str) -> list:
    """Fetches standard research papers from Europe PMC."""
    raw_items = []
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }
    
    params = {
        "query": f'"{keyword}" HAS_ABSTRACT:y',
        "format": "json",
        "pageSize": 25,
        "resultType": "core"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            results = data.get("resultList", {}).get("result", [])
            for item in results:
                raw_items.append({
                    "title": item.get("title", "Untitled Research"),
                    "abstract": item.get("abstractText", "No abstract available."),
                    "source": item.get("journalTitle", "Europe PMC"),
                    "keyword": keyword,
                    "domain": domain,
                    "link": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id')}" if item.get("id") else "#"
                })
    except Exception as e:
        print(f"[europepmc] Connection error during paper fetch for '{keyword}': {e}")

    return raw_items


def fetch_grants(keyword: str, lookback_days: int, domain: str) -> list:
    """
    Fetches actual grant records using the official Europe PMC GRIST REST API:
    https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query=<KEYWORD>&format=json
    """
    raw_items = []
    
    # Strictly separated base URL path per GRIST specifications
    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    # URL-encode the keyword securely for path insertion
    encoded_query = urllib.parse.quote(keyword.strip())
    url = f"{base_url}{encoded_query}&format=json"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            
            # GRIST API returns records under RecordList -> Record (or fallback structures)
            record_list = data.get("RecordList", {}) if isinstance(data, dict) else {}
            records = (
                record_list.get("Record", [])
                or record_list.get("grant", [])
                or data.get("Record", [])
            )

            if isinstance(records, dict):
                records = [records]

            for item in records:
                # Map GRIST-specific capitalized data fields
                grant_id = item.get("Id") or item.get("id") or "N/A"
                title = item.get("Title") or item.get("title") or "Untitled Grant Project"
                abstract = item.get("Abstract") or item.get("abstract") or "No abstract description provided."
                funder = item.get("GrantedAuthority") or item.get("funder") or "Europe PMC / GRIST"

                grant_link = f"https://europepmc.org/grantfinder/grantid?id={grant_id}" if grant_id != "N/A" else "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title,
                    "abstract": abstract,
                    "source": f"{funder} (Grant ID: {grant_id})",
                    "keyword": keyword,
                    "domain": domain,
                    "link": grant_link
                })
    except Exception as e:
        print(f"[europepmc] Connection error during GRIST grant fetch for '{keyword}': {e}")

    return raw_items
