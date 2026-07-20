import requests

def extract_all(fresh_items, output_dir=None, docs_dir=None):
    """
    Processes fresh harvested items locally using Ollama and retains metadata links.
    """
    print(f"[extract] Processing {len(fresh_items)} harvested items for digest locally using Ollama...")
    
    extracted_items = []
    
    for i, item in enumerate(fresh_items, 1):
        title = item.get("title", "Untitled")
        print(f"[extract] Analyzing item {i}/{len(fresh_items)}: {title[:50]}...")
        
        summary = "Summary unavailable due to local processing error."
        try:
            res = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": f"Provide a concise 2-sentence executive summary of this grant or research item:\n\nTitle: {title}\nAbstract: {item.get('abstract', '')}",
                    "stream": False
                },
                timeout=30
            )
            if res.status_code == 200:
                summary = res.json().get("response", summary).strip()
        except Exception as e:
            print(f"[extract] Warning: Ollama connection failed ({e}). Using fallback text.")

        # Ensure all key fields—including the source link—are preserved
        extracted_items.append({
            "title": title,
            "abstract": item.get("abstract", "No abstract available."),
            "source": item.get("source", "Unknown Source"),
            "keyword": item.get("keyword", ""),
            "domain": item.get("domain", ""),
            "link": item.get("link", "#"),
            "summary": summary
        })

    print(f"[extract] Successfully processed {len(extracted_items)} items with links included.")
    return extracted_items
