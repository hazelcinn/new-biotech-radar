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
                grant_data = item.get("grant", item.get("Grant", item))
                
                grant_id = grant_data.get("id") or grant_data.get("Id") or grant_data.get("grantId") or "N/A"
                title = grant_data.get("title") or grant_data.get("Title") or "Untitled Grant Project"
                
                # Abstract is frequently keyed under 'abstractText' or 'abstract' in the Grist API
                abstract = grant_data.get("abstractText") or grant_data.get("abstract") or grant_data.get("Abstract") or "No abstract description provided."
                
                funder_dict = grant_data.get("funder", grant_data.get("Funder", {}))
                if isinstance(funder_dict, dict):
                    funder = funder_dict.get("name") or funder_dict.get("Name") or grant_data.get("grantedAuthority") or "Europe PMC / GRIST"
                else:
                    funder = str(funder_dict)

                person = item.get("person", item.get("Person", {}))
                given_name = person.get("givenName") or person.get("GivenName") or ""
                family_name = person.get("familyName") or person.get("FamilyName") or ""
                pi = f"{given_name} {family_name}".strip() or "N/A"
                
                aff = person.get("affiliation") or person.get("Affiliation") or grant_data.get("affiliation") or "N/A"
                
                # Extract raw amount value
                raw_amount = grant_data.get("awardAmount") or grant_data.get("amount") or grant_data.get("AwardAmount") or grant_data.get("totalAwardAmount") or grant_data.get("fundAmount")
                # Extract currency symbol/code (often stored as 'currency' or nested in the amount object)
                currency = grant_data.get("currency") or grant_data.get("Currency") or ""
                if isinstance(raw_amount, dict):
                    currency = raw_amount.get("currency", currency)
                    raw_amount = raw_amount.get("value") or raw_amount.get("amount") or "N/A"
                # Format amount with currency symbol or code if available
                if raw_amount and str(raw_amount) != "N/A":
                    # Clean symbol mapping if needed, or default to the code/symbol provided
                    curr_symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
                    curr_display = curr_symbols.get(currency.upper(), currency)
                    amount = f"{curr_display} {raw_amount}".strip() if curr_display else str(raw_amount)
                else:
                    amount = "N/A"
                    
                # Date Duration mapping using active dates, start/end dates, or period keys
                start_date = grant_data.get("startDate") or grant_data.get("StartDate") or grant_data.get("from") or ""
                end_date = grant_data.get("endDate") or grant_data.get("EndDate") or grant_data.get("to") or ""
                
                if start_date and end_date:
                    duration = f"{start_date} to {end_date}"
                else:
                    duration = grant_data.get("activeDate") or grant_data.get("date") or grant_data.get("duration") or grant_data.get("Duration") or grant_data.get("period") or "N/A"

                grant_doi = grant_data.get("doi") or grant_data.get("Doi")
                if grant_doi:
                    grant_link = f"https://doi.org/{grant_doi}"
                elif grant_id != "N/A":
                    grant_link = f"https://europepmc.org/grantfinder/grantdetails?query=gid%3A%22{urllib.parse.quote(str(grant_id))}%22"
                else:
                    grant_link = "https://europepmc.org/grantfinder"

                raw_items.append({
                    "title": title,
                    "project contact": pi,
                    "affiliation": aff,
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
