import requests
from datetime import datetime, timedelta

def fetch(kw, lookback_days, domain):
    print(f"[{domain}] Querying EuropePMC for keyword: '{kw}'...")
    
    # 1. Calculate the date constraint
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    start_year = start_date.strftime("%Y")
    
    # 2. Build a highly specific Lucene search query for EuropePMC
    # Looks for terms in title, abstract, or keywords, filtered by date
    query = f'("{kw}") AND (FIRST_PUB_DATE:[{start_date.strftime("%Y-%m-%d")} TO {end_date.strftime("%Y-%m-%d")}])'
    
    url = "https://ebi.ac.uk"
    params = {
        "query": query,
        "format": "json",
        "pageSize": 25,  # Top 25 most relevant matches
        "resultType": "core" # Ensures we get the abstracts back
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            print(f"Warning: EuropePMC API returned status code {response.status_code}")
            return []
            
        data = response.json()
        result_list = data.get("resultList", {}).get("result", [])
        
        results = []
        for paper in result_list:
            # Safely grab links (prefer electronic journal link, fallback to EuropePMC)
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
