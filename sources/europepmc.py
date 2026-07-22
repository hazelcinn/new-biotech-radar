import urllib.parse
import requests

#def fetch(keyword: str, lookback_days: int, domain: str) -> list:
#    """Fetches standard research papers from Europe PMC, limited to top 10."""
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
#        "pageSize": 1,  # Capped at top 10 per keyword
#        "resultType": "core"
#    }
#
#    try:
#        response = requests.get(url, params=params, headers=headers, timeout=12)
#        if response.status_code == 200:
#            data = response.json()
#            results = data.get("resultList", {}).get("result", [])
#            for item in results[:10]:
#                raw_items.append({
#                    "title": item.get("title", "Untitled Research"),
#                    "abstract": item.get("abstractText", "No abstract available."),
#                    "source": item.get("journalTitle", "Europe PMC"),
#                    "keyword": keyword,
#                    "domain": domain,
#                    "link": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id')}" if item.get("id") else "#"
#                })
#    except Exception as e:
#        print(f"[europepmc] Connection error during paper fetch for '{keyword}': {e}")
#
#    return raw_items


def fetch_grants(keyword: str, lookback_days: int, domain: str) -> list:
    """
    Fetches actual grant records using the official Europe PMC GRIST REST API,
    limited to the top 10 per keyword.
    """
    raw_items = []
    
    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }

    clean_kw = keyword.strip()
    encoded_query = urllib.parse.quote(clean_kw)
    url = f"{base_url}{encoded_query}&format=json"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            
            record_list = data.get("RecordList", {}) if isinstance(data, dict) else {}
            records = (
                record_list.get("Record", [])
                or record_list.get("grant", [])
                or data.get("Record", [])
            )

            if isinstance(records, dict):
                records = [records]
                
            # Slice to only take the top 10 records per keyword
            for item in records[:10]:
                # Navigate into the nested 'Grant' dictionary
                grant_data = item.get("Grant", item)
                
                grant_id = grant_data.get("Id") or grant_data.get("id") or "N/A"
                title = grant_data.get("Title") or grant_data.get("title") or "Untitled Grant Project"
                abstract = grant_data.get("Abstract") or grant_data.get("abstract") or "No abstract description provided."
                
                # Navigate into the nested 'Funder' dictionary
                funder_dict = grant_data.get("Funder", {})
                funder = funder_dict.get("Name") or grant_data.get("GrantedAuthority") or "Europe PMC / GRIST"

                # Extract person / PI details safely
                person = item.get("Person", {})
                given_name = person.get("GivenName", "")
                family_name = person.get("FamilyName", "")
                pi = f"{given_name} {family_name}".strip() or "N/A"
                aff = person.get("Affiliation") or person.get("affiliation") or "N/A"
                
                # Category / subject if available
                cat = grant_data.get("Subject") or grant_data.get("category") or "N/A"
                amount = grant_data.get("AwardAmount") or grant_data.get("amount") or "N/A"
                start_date = grant_data.get("StartDate", "")
                end_date = grant_data.get("EndDate", "")
                duration = f"{start_date} to {end_date}" if start_date and end_date else grant_data.get("Duration", "N/A")
                grant_doi = grant_data.get("Doi") or grant_data.get("doi")                
                if grant_doi:
                    grant_link = f"https://doi.org/{grant_doi}"
                elif grant_id != "N/A":
                    # Correct direct detail view path
                    grant_link = f"https://europepmc.org/grantfinder/grantdetails?query=gid%3A%22{urllib.parse.quote(grant_id)}%22"
                else:
                    grant_link = "https://europepmc.org/grantfinder"
                    
                raw_items.append({
                    "title": title,
                    "project contact": pi,
                    "affiliation": aff,
                    "subject": cat,
                    "grant amount": amount,
                    "grant duration": duration,
                    "abstract": abstract,
                    "source": f"{funder} (Grant ID: {grant_id})",
                    "keyword": keyword,
                    "domain": domain,
                    "link": grant_link
                })
    except Exception as e:
        print(f"[europepmc] Connection error during GRIST grant fetch for '{keyword}': {e}")

    return raw_items
