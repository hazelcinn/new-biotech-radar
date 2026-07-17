import requests
from datetime import datetime, timedelta

def fetch(kw, lookback_days, domain):
    print(f"[{domain}] Searching bioRxiv for keyword: '{kw}'...")
    
    # 1. Calculate the date window
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # 2. Fetch recent preprints from the bioRxiv API
    # Note: bioRxiv API fetches by date range, then we filter by keyword
    url = f"https://biorxiv.org{start_str}/{end_str}/0/json"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Warning: bioRxiv API returned status code {response.status_code}")
            return []
            
        data = response.json()
        messages = data.get("messages", [])
        
        # Check if the API returned an explicit error message
        if messages and messages[0].get("status") != "ok":
            print(f"bioRxiv API message: {messages[0].get('status')}")
            return []
            
        collection = data.get("collection", [])
        results = []
        
        # 3. Filter papers matching the keyword in title or abstract
        kw_lower = kw.lower()
        for paper in collection:
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            
            if kw_lower in title or kw_lower in abstract:
                results.append({
                    "title": paper.get("title"),
                    "authors": paper.get("authors"),
                    "link": f"https://biorxiv.org{paper.get('doi')}",
                    "source": "bioRxiv",
                    "date": paper.get("date"),
                    "abstract": paper.get("abstract"),
                    "domain": domain,
                    "keyword": kw
                })
                
        print(f"Found {len(results)} matching papers on bioRxiv for '{kw}'")
        return results

    except Exception as e:
        print(f"Error fetching from bioRxiv: {e}")
        return []
