import os
import requests
import json
from config import KEYWORDS  # Importing your target keywords

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama

def generate_summary(prompt: str) -> str:
    if LLM_PROVIDER == "ollama":
        # Local Ollama endpoint
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": os.getenv("OLLAMA_MODEL", "llama3.2"), "prompt": prompt, "stream": False}
        )
        return response.json()["response"]

    elif LLM_PROVIDER == "anthropic":
        # Anthropic API
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text

    else:
        raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")


# =====================================================================
# EuropePMC Grant Retrieval & Processing Logic
# =====================================================================

def build_europepmc_query(keywords):
    """Formats keywords from config.py into a valid EuropePMC search query."""
    if isinstance(keywords, dict):
        # Flatten dictionary values if keywords are grouped in categories
        all_kw = [kw for sublist in keywords.values() for kw in sublist]
    elif isinstance(keywords, list):
        all_kw = keywords
    else:
        all_kw = [str(keywords)]

    query_terms = " OR ".join([f'"{kw}"' for kw in all_kw])
    return f"({query_terms}) HAS_GRANT:y"

def fetch_grants_from_europepmc(limit=25):
    """Queries EuropePMC REST API for grants matching the config keywords."""
    query = build_europepmc_query(KEYWORDS)
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
        "resultType": "core"
    }

    print(f"🔍 Searching EuropePMC with query: {query}...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        print(f"✅ Found {len(results)} grant records.")
        return results
    except Exception as e:
        print(f"❌ EuropePMC API Request failed: {e}")
        return []

def process_grants():
    grants = fetch_grants_from_europepmc()
    processed_results = []

    for grant in grants:
        title = grant.get("title", "No Title")
        abstract = grant.get("abstractText", "No Abstract Provided")
        grant_id = grant.get("id", "Unknown ID")

        # Build prompt for LLM evaluation
        prompt = f"""
        You are a biotech research analyst. Evaluate the following research grant based on these tracking keywords: {KEYWORDS}

        Grant Title: {title}
        Abstract: {abstract}

        Tasks:
        1. Summarize the core biotech/pharma technology in 2 sentences.
        2. Highlight which specific keywords apply.
        """

        print(f"\nProcessing Grant [{grant_id}]: {title[:60]}...")
        summary = generate_summary(prompt)

        processed_results.append({
            "id": grant_id,
            "title": title,
            "summary": summary
        })

    # Save output to docs/index.html / output files
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w") as f:
        f.write("<html><body><h1>Biotech Radar Digest</h1><ul>")
        for item in processed_results:
            f.write(f"<li><h3>{item['title']}</h3><p>{item['summary']}</p></li>")
        f.write("</ul></body></html>")

    print("\n🎉 Done! Written updated output to docs/index.html")

if __name__ == "__main__":
    process_grants()
