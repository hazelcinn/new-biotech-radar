import os
import json
import requests
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama

# Extract basic search terms from config
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def generate_summary(prompt: str) -> str:
    """Handles LLM calls seamlessly across Ollama and Anthropic."""
    if LLM_PROVIDER == "ollama":
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
                "prompt": prompt,
                "stream": False,
            },
        )
        return response.json()["response"]

    elif LLM_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    else:
        raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")


# =====================================================================
# EuropePMC Grant Retrieval & Processing Logic
# =====================================================================


def build_europepmc_query(keywords):
    """Formats the basic search terms into a EuropePMC REST query string."""
    if not keywords:
        raise ValueError("No keywords found in DOMAINS['Basic Search']")

    # Target Title, Abstract, or Grant text specifically
    # Using field tags ensures EuropePMC searches the relevant metadata
    query_parts = []
    for kw in keywords:
        query_parts.append(f'TITLE:"{kw}" OR ABSTRACT:"{kw}"')
    
    combined_keywords = " OR ".join(query_parts)
    
    # HAS_GRANT:y filters for records associated with a grant
    return f"({combined_keywords}) AND HAS_GRANT:y"    

def fetch_grants_from_europepmc(limit=25):
    """Queries EuropePMC REST API for grants matching the basic search keywords."""
    query = build_europepmc_query(BASIC_SEARCH_KEYWORDS)
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
        "resultType": "core",
    }

    print(
        f"🔍 Querying EuropePMC with {len(BASIC_SEARCH_KEYWORDS)} Basic Search keywords..."
    )
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        print(f"✅ Found {len(results)} matching grant records.")
        return results
    except Exception as e:
        print(f"❌ EuropePMC API Request failed: {e}")
        return []


def process_grants():
    """Main processing loop."""
    grants = fetch_grants_from_europepmc()
    processed_results = []

    for grant in grants:
        title = grant.get("title", "No Title")
        abstract = grant.get("abstractText", "No Abstract Provided")
        grant_id = grant.get("id", "Unknown ID")

        # Build prompt for LLM evaluation
        prompt = f"""
        You are a biotech research analyst. Evaluate the following research grant based on these core technology tracking keywords: {BASIC_SEARCH_KEYWORDS}

        Grant Title: {title}
        Abstract: {abstract}

        Tasks:
        1. Summarize the key technology or methodology in 2 concise sentences.
        2. Identify which basic search keywords (e.g., 'delivery system', 'automation', 'assay') directly apply.
        """

        print(f"\nProcessing Grant [{grant_id}]: {title[:60]}...")
        summary = generate_summary(prompt)

        processed_results.append(
            {"id": grant_id, "title": title, "summary": summary}
        )

    # Ensure output directories exist using your config values
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save output to docs/index.html
    html_path = os.path.join(DOCS_DIR, "index.html")
    with open(html_path, "w") as f:
        f.write(
            "<!DOCTYPE html>\n<html><head><title>Biotech Radar Digest</title>"
        )
        f.write(
            "<style>body{font-family:sans-serif; margin:40px; line-height:1.6;} li{margin-bottom:20px;}</style></head><body>"
        )
        f.write("<h1>Pharma Tech Radar Digest</h1><ul>")
        for item in processed_results:
            f.write(
                f"<li><h3>{item['title']}</h3><p>{item['summary']}</p></li>"
            )
        f.write("</ul></body></html>")

    print(f"\n🎉 Processed {len(processed_results)} grants!")
    print(f"📄 Written updated dashboard to {html_path}")


if __name__ == "__main__":
    process_grants()
