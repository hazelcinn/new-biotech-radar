import requests


def extract_all(fresh_items, output_dir=None, docs_dir=None):
    """
    Processes fresh harvested items locally using Ollama and returns 
    enhanced extracted items with summaries for the digest generators.
    """
    print(f"[extract] Processing {len(fresh_items)} harvested items for digest locally using Ollama...")
    
    extracted_items = []
    
    for i, item in enumerate(fresh_items, 1):
        title = item.get("title", "Untitled")
        print(f"[extract] Analyzing paper {i}/{len(fresh_items)}: {title[:50]}...")
        
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

        item["summary"] = summary
        extracted_items.append(item)

    print(f"[extract] Successfully processed {len(extracted_items)} items.")
    return extracted_items
