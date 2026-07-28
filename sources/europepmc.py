import urllib.parse
import requests

def _clean_abstract(abstract_node) -> str:
    """Extracts raw text strings from GRIST abstract lists or dictionary nodes."""
    if not abstract_node:
        return ""
    
    if isinstance(abstract_node, list):
        parts = []
        for item in abstract_node:
            if isinstance(item, dict):
                val = item.get("value") or item.get("content") or item.get("text") or ""
                if val:
                    parts.append(str(val))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts).strip()
    
    if isinstance(abstract_node, dict):
        return str(
            abstract_node.get("value") 
            or abstract_node.get("content") 
            or abstract_node.get("text") 
            or ""
        ).strip()
        
    return str(abstract_node).strip()
    
def _clean_affiliation(aff_node) -> str:
    """Extracts plain text institution/university names from GRIST affiliation data."""
    if not aff_node:
        return ""
    
    # Handle list of affiliations
    if isinstance(aff_node, list):
        names = []
        for item in aff_node:
            cleaned = _clean_affiliation(item)
            if cleaned and cleaned != "N/A" and cleaned not in names:
                names.append(cleaned)
        return "; ".join(names).strip()
    
    # Handle dictionary node
    if isinstance(aff_node, dict):
        return str(
            aff_node.get("name")
            or aff_node.get("Name")
            or aff_node.get("institutionName")
            or aff_node.get("title")
            or aff_node.get("Title")
            or aff_node.get("value")
            or aff_node.get("text")
            or ""
        )
        if isinstance(val, (dict, list)):
            return _clean_affiliation(val)
        return str(val).strip()
        
    return str(aff_node).strip()

def _clean_amount(amount_node, currency: str = "") -> str:
    """Extracts and formats grant amount and currency from GRIST response nodes."""
    if amount_node is None:
        return "N/A"

    # Handle list of amount objects
    if isinstance(amount_node, list):
        for item in amount_node:
            cleaned = _clean_amount(item, currency)
            if cleaned != "N/A":
                return cleaned
        return "N/A"

    raw_val = None
    extracted_curr = currency

    # Extract value and currency from dictionary
    if isinstance(amount_node, dict):
        extracted_curr = (
            amount_node.get("currency")
            or amount_node.get("currencyCode")
            or amount_node.get("Currency")
            or currency
        )
        raw_val = (
            amount_node.get("value")
            or amount_node.get("amount")
            or amount_node.get("content")
            or amount_node.get("text")
            or amount_node.get("#text")
            or amount_node.get("formattedAmount")
            or amount_node.get("total")
        )
    else:
        raw_val = amount_node

    if raw_val is None or str(raw_val).strip().upper() in ("", "N/A", "NONE", "NULL"):
        return "N/A"

    raw_str = str(raw_val).strip()

    # Format numeric values (e.g., 100000 -> 100,000)
    try:
        num_val = float(raw_str.replace(",", ""))
        if num_val.is_integer():
            raw_str = f"{int(num_val):,}"
        else:
            raw_str = f"{num_val:,.2f}"
    except (ValueError, TypeError):
        pass

    curr_symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
    curr_str = str(extracted_curr).strip()
    curr_display = curr_symbols.get(curr_str.upper(), curr_str)

    # Avoid duplicating symbol if raw string already contains one
    if curr_display and not any(symbol in raw_str for symbol in ["£", "$", "€", "EUR", "USD", "GBP"]):
        return f"{curr_display} {raw_str}".strip()

    return raw_str
    
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
    url = f"{base_url}{encoded_query}&format=json&resultType=core"

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
                
                abstract_raw = (
                    grant_data.get("abstractText") 
                    or grant_data.get("abstract")
                    or grant_data.get("ab")
                    or grant_data.get("abstr")
                    or grant_data.get("Ab")
                    or grant_data.get("Abstr") 
                    or grant_data.get("Abstract")
                    or grant_data.get("projectSummary")
                    or grant_data.get("description")
                    or item.get("abstractText")
                    or item.get("abstract")
                    or item.get("abs")
                    or item.get("abstr")
                    or item.get("description")
                    or "No abstract description provided."
                )
                # Unwraps list/dict structures into clean plain text
                abstract = _clean_abstract(abstract_raw) or "No abstract description provided."
                
                funder_dict = grant_data.get("funder", grant_data.get("Funder", {}))
                if isinstance(funder_dict, dict):
                    funder = funder_dict.get("name") or funder_dict.get("Name") or grant_data.get("grantedAuthority") or "Europe PMC / GRIST"
                else:
                    funder = str(funder_dict)

                person = item.get("person", item.get("Person", {}))
                given_name = person.get("givenName") or person.get("GivenName") or ""
                family_name = person.get("familyName") or person.get("FamilyName") or ""
                pi = f"{given_name} {family_name}".strip() or "N/A"
                
                # --- TEMPORARY DEBUG ---
                #import json
                #print("=== RAW ITEM ===")
                #if records.index(item) == 0:
                #    import copy
                #    grant_debug = copy.deepcopy(grant_data)
                #    if "Abstract" in grant_debug:
                #        grant_debug["Abstract"] = "<<TRUNCATED>>"
                #    print("=== GRANT KEYS ===", list(grant_data.keys()))
                #    print("=== GRANT (no abstract) ===")
                #    print(json.dumps(grant_debug, indent=2))
                #    print("=== PERSON KEYS ===", list(person.keys()) if isinstance(person, dict) else person)
                #    print("=== PERSON (full) ===")
                #    print(json.dumps(person, indent=2))
                #    print("=== END RAW ITEM ===")
                # --- END TEMPORARY DEBUG ---
                
                aff_raw = (
                    person.get("affiliation")
                    or person.get("Affiliation")
                    or person.get("institution")
                    or person.get("Institution")
                    or grant_data.get("institution")
                    or grant_data.get("Institution")
                    or grant_data.get("affiliation")
                    or grant_data.get("Affiliation")
                    or grant_data.get("grantee")
                    or item.get("institution")
                    or item.get("Institution")
                )
                
                aff = _clean_affiliation(aff_raw) or "N/A"
                
                # Extract grant amount and currency cleanly
                amount_node = (
                    grant_data.get("amount") 
                    or grant_data.get("awardAmount") 
                    or grant_data.get("AwardAmount") 
                    or grant_data.get("grantAmount") 
                    or grant_data.get("totalAwardAmount") 
                    or grant_data.get("fundAmount")
                    or grant_data.get("Amount")
                    or item.get("amount")
                    or item.get("Amount")
                    or item.get("awardAmount")
                )
                
                currency = (
                    grant_data.get("currency") 
                    or grant_data.get("Currency") 
                    or item.get("currency") 
                    or ""
                )
                
                amount = _clean_amount(amount_node, currency)
                    
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
                    "source": funder,
                    "keyword": keyword,
                    "domain": domain,
                    "link": grant_link
                })
                # --- TEMPORARY DEBUG ---
                # --- TEMPORARY DEBUG ---
                #import re
                #if amount != "N/A" and not re.search(r'[\d]', str(amount)):
                #    print(f"=== SUSPECT RECORD (keyword={keyword}) ===")
                #    print("affiliation:", repr(aff))
                #    print("amount:", repr(amount))
                #    print("amount_node (raw):", repr(amount_node))
                #    print("aff_raw (raw):", repr(aff_raw))
                #    print("grant_data keys:", list(grant_data.keys()))
                #    print("item keys:", list(item.keys()))
                # --- END TEMPORARY DEBUG ---
                # --- END TEMPORARY DEBUG ---
    except Exception as e:
        print(f"[europepmc] Connection error during GRIST grant fetch for '{keyword}': {e}")

    return raw_items
