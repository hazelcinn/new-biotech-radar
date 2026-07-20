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
# EuropePMC GRIST Grant Retrieval & Processing Logic
# =====================================================================


def fetch_grants_from_grist(limit_per_keyword=5):
    """
    Queries the EuropePMC GRIST API directly for grant award metadata.
    """
    all_grants = []
    seen_grant_ids = set()

    print(f"🔍 Searching EuropePMC GRIST API across {len(BASIC_SEARCH_KEYWORDS)} keywords...")

    for kw in BASIC_SEARCH_KEYWORDS:
        # GRIST API endpoint query format
        url = f"https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query=kw:{kw}&format=json"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            data = response.json()
            records = data.get("RecordList", {}).get("Record", [])

            # Handle case where API returns a single record object instead of a list
            if isinstance(records, dict):
                records = [records]

            count_added = 0
            for rec in records:
                # Deduplicate records across keywords using Grant ID or Title
                grant_id = rec.get("Id") or rec.get("Title")
                if grant_id and grant_id not in seen_grant_ids:
                    seen_grant_ids.add(grant_id)
                    all_grants.append(rec)
                    count_added += 1

                if count_added >= limit_per_keyword:
                    break

        except Exception as e:
            print(f"⚠️ Failed fetching GRIST records for keyword '{kw}': {e}")

    print(f"✅ Retrieved {len(all_grants)} unique grant records from GRIST API.")
    return all_grants


def process_grants():
    """Main processing loop."""
    grants = fetch_grants_from_grist()

    if not grants:
        print("⚠️ No grants retrieved. Check internet connection or keyword settings.")
        return

    processed_results = []

    for grant in grants:
        title = grant.get("Title", "Untitled Grant")
        abstract = grant.get("Abstract", "No Abstract Provided")
        funder = grant.get("GrantedAuthority", "Unknown Funder")
        grant_id = grant.get("Id", "N/A")

        # Build prompt for LLM evaluation
        prompt = f"""
        You are a biotech research analyst. Evaluate the following funded grant project:

        Grant Title: {title}
        Funder: {funder}
        Abstract: {abstract}

        Tasks:
        1. Summarize the core technology or research scope in 2 concise sentences.
        2. Explain its relevance to pharma/biotech innovation.
        """

        print(f"\nProcessing Grant [{grant_id}]: {title[:60]}...")
        summary = generate_summary(prompt)

        processed_results.append({
            "id": grant_id,
            "title": title,
            "funder": funder,
            "summary": summary
        })

    # Ensure output directories exist using your config values
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save output to docs/index.html
    html_path = os.path.join(DOCS_DIR, "index.html")
    with open(html_path, "w") as f:
        f.write("<!DOCTYPE html>\n<html><head><title>Biotech Radar Digest</title>")
        f.write("<style>body{font-family:sans-serif; margin:40px; line-height:1.6;} .grant-card{margin-bottom:25px; padding:15px; border-left:4px solid #0066cc; background:#f9f9f9;}</style></head><body>")
        f.write("<h1>Pharma Tech Radar Digest (GRIST Grants)</h1>")
        for item in processed_results:
            f.write(f"<div class='grant-card'><h3>{item['title']}</h3>")
            f.write(f"<p><strong>Funder:</strong> {item['funder']} | <strong>Grant ID:</strong> {item['id']}</p>")
            f.write(f"<p>{item['summary']}</p></div>")
        f.write("</body></html>")

    print(f"\n🎉 Processed {len(processed_results)} grants!")
    print(f"📄 Written updated dashboard to {html_path}")


if __name__ == "__main__":
    process_grants()
