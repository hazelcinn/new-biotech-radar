import requests
from datetime import datetime, timedelta
import urllib.parse

def fetch(kw, lookback_days, domain):
    print(f"[{domain}] Querying EuropePMC for keyword: '{kw}'...")
    
    # 1. Calculate the date constraint
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # 2. Build the query string cleanly
    raw_query = f'("{kw}") AND (FIRST_PUB_DATE:[{start_str} TO {end_str}])'
    
    # 3. Use standard params dictionary so requests handles the URL encoding automatically
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": raw_query,
        "format": "json",
        "pageSize": "25",
        "resultType": "core"
    }
    
    try:
        # Pass params=params to ensure the URL encodes spaces and quotes correctly
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"Warning: EuropePMC API returned status code {response.status_code}")
            return []
            
        # Debugging step: if the text doesn't look like JSON, print a preview
        if not response.text.strip().startswith("{"):
            print(f"Server returned non-JSON text preview: {response.text[:200]}")
            return []
            
        data = response.json()
        result_list = data.get("resultList", {}).get("result", [])
        
        results = []
        for paper in result_list:
            pmcid = paper.get("pmcid")
            doi = paper.get("doi")
            link = f"https://doi.org{doi}" if doi else f"https://europepmc.org{pmcid}" if pmcid else f"https://europepmc.org{paper.get('id')}"
            
            results.append({
                "title": paper.get("title"),
                "authors": paper.get("authorString", "Unknown Authors"),
                "link": link,
                "source": "EuropePMC",
                "date": paper.get("firstPublicationDate", paper.get("pubYear")),
                "abstract": paper.get("abstractText", "No abstract available."),
                "domain": domain,
                "keyword": kw
            })
            
        print(f"Found {len(results)} highly matching papers on EuropePMC for '{kw}'")
        return results

    except Exception as e:
        print(f"Error fetching from EuropePMC: {e}")
        return []
