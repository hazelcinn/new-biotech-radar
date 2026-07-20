import requests

def fetch(keyword, lookback_days, domain_name):
    print(f"[europepmc] Initiating live API lookup for: '{keyword}'...")
    
    query = f"{keyword}"
    url = f"https://ebi.ac.uk{query}&format=json&pageSize=50&resultType=core"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"[europepmc] Connection warning. Server code: {response.status_code}")
            return []
            
        data = response.json()
        results = data.get('resultList', {}).get('result', [])
        
        formatted_items = []
        for item in results:
            formatted_items.append({
                "title": item.get("title", "Untitled Document"),
                "source": "EuropePMC",
                "keyword": keyword,
                "abstract": item.get("abstractText", "") or item.get("description", "No descriptive text available."),
                "link": item.get("url", "https://europepmc.org")
            })
            
        print(f"[europepmc] Found {len(formatted_items)} raw matches for '{keyword}'")
        return formatted_items
    except Exception as e:
        print(f"[europepmc] Connection error during fetch: {e}")
        return []
