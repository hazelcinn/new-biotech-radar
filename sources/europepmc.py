import urllib.parse
import requests

# def fetch(keyword: str, lookback_days: int, domain: str) -> list:
#    """Fetches standard research papers from Europe PMC, limited to top 1."""
#    raw_items = []
#    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
#    
#    headers = {
#        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
#        "Accept": "application/json"
#    }
#    
#    params = {
#        "query": f'"{keyword}" HAS_ABSTRACT:y',
#        "format": "json",
#        "pageSize": 1,  # Capped at top 1 per keyword
#        "resultType": "core"
#    }
#
#    try:
#        response = requests.get(url, params=params, headers=headers, timeout=12)
#        if response.status_code == 200:
#            data = response.json()
#            results = data.get("resultList", {}).get("result", [])
#            for item in results:
#                title = item.get("title", "Untitled Grant").strip()
#                abstract = item.get("abstractText", "No grant abstract available.").strip()
#                source_agency = item.get("grantsList", [{}])[0].get("agency", "Europe PMC Funder")
#                grant_id = item.get("grantsList", [{}])[0].get("grantId", "")
#                
#                if grant_id:
#                    link = f"https://europepmc.org/grantfinder/grantid?id={urllib.parse.quote(grant_id)}"
#                else:
#                    item_id = item.get("id")
#                    link = f"https://europepmc.org/article/MED/{item_id}" if item_id else "https://europepmc.org/grantfinder"
#                    
#                raw_items.append({
#                    "title": title,
#                    "abstract": abstract,
#                    "source": f"Grant: {source_agency} ({grant_id})" if grant_id else f"Grant: {source_agency}",
#                    "keyword": keyword,
#                    "domain": domain,
#                    "link": link
#                })
#    except Exception as e:
#        print(f"[europepmc] Connection error during paper fetch for '{keyword}': {e}")
#
#    return raw_items

def fetch_grants(keyword: str, lookback_days: int, domain: str) -> list:
    """
    Fetches actual grant records using the official Europe PMC GRIST REST API,
    limited to the top 1 per keyword.
    """
    raw_items = []
    
    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    clean_kw = keyword.strip()
    query_str = f'kw:{clean_kw}"'
    encoded_query = urllib.parse.quote(clean_kw)
    url = f"{base_url}{encoded_query}&format=json"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()

            response_box = data.get("response", data)
            record_list = response_box.get("resultsList", response_box.get("RecordList", data.get("RecordList", {})))
            records = (
                result_list.get("result", [])
                or result_list.get("Record",[])
                or result_list.get("grant", [])
                or data.get("Record", [])
            )

            if isinstance(records, dict):
                records = [records]

            # Slice to only take the top 1 records per keyword
            for item in records[:1]:
                grant_id = item.get("id") or item.get("Id") or item.get("grantId") or ""
                
                # Extract grant title fields
                title = (
                    item.get("projectTitle")
                    or item.get("Title")
                    or item.get("title")
                    or item.get("ProjectTitle")
                )
                
                if not title or not title.strip():
                    if grant_id:
                        title = f"Grant Award: {keyword.capitalize()} ({grant_id})"
                    else:
                        continue

                abstract = (
                    item.get("abstractText")
                    or item.get("Abstract")
                    or item.get("abstract")
                    or "No grant abstract provided."
                )
                
                funder = item.get("agency") or item.get("GrantedAuthority") or item.get("funder") or "Europe PMC Funder"

                # Construct direct deep link to the individual grant
                if grant_id:
                    link = f"https://europepmc.org/grantfinder/grantid?id={urllib.parse.quote(str(grant_id))}"
                else:
                    link = "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title.strip(),
                    "abstract": abstract.strip(),
                    "source": f"{funder} (Grant ID: {grant_id})" if grant_id else f"{funder}",
                    "keyword": keyword,
                    "domain": domain,
                    "link": link
                })
    except Exception as e:
        print(f"[europepmc] Grist API connection error for '{keyword}': {e}")

    return raw_items
