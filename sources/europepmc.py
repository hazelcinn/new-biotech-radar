import requests
import urllib.parse

def fetch_grants(keyword: str, lookback_days: int, domain: str) -> list:
    """
    Fetches grants exclusively from Europe PMC's GristAPI using fetch_grants.
    """
    raw_items = []
    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    clean_kw = keyword.strip()
    query_str = f'kw:"{clean_kw}"'
    encoded_query = urllib.parse.quote(query_str)
    url = f"{base_url}{encoded_query}&format=json"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            
            response_box = data.get("response", data)
            result_list = response_box.get("resultList", response_box.get("RecordList", data.get("RecordList", {})))
            records = (
                result_list.get("result", [])
                or result_list.get("Record", [])
                or result_list.get("grant", [])
                or data.get("Record", [])
            )

            if isinstance(records, dict):
                records = [records]

            for item in records[:1]:
                grant_id = item.get("id") or item.get("Id") or item.get("grantId") or ""
                
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
