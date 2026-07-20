import os
import requests
import xml.etree.ElementTree as ET
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama

# Extract basic search keywords from config
BASIC_SEARCH_KEYWORDS = DOMAINS.get("Basic Search", [])


def generate_summary(prompt: str) -> str:
    """Handles LLM calls across Ollama and Anthropic."""
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
# EuropePMC GRIST API Fetching & Parsing (XML Engine)
# =====================================================================


def fetch_grants_from_grist(limit_per_keyword=5):
    """
    Queries the official EuropePMC GRIST REST API and parses the returned XML.
    Endpoint spec: https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query=kw:<keyword>
    """
    all_grants = []
    seen_grant_ids = set()

    print(f"🔍 Querying EuropePMC GRIST API across {len(BASIC_SEARCH_KEYWORDS)} keywords...")

    for kw in BASIC_SEARCH_KEYWORDS:
        url = f"https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query=kw:{kw}"

        try:
            response = requests.get(url, timeout=12)
            if response.status_code != 200:
                print(f"⚠️ GRIST returned status code {response.status_code} for keyword '{kw}'")
                continue

            # Parse XML root <RecordList>
            root = ET.fromstring(response.text)
            records = root.findall(".//Record")

            count_added = 0
            for rec in records:
                # Extract GRIST XML elements
                grant_id_elem = rec.find("Id")
                title_elem = rec.find("Title")
                abstract_elem = rec.find("Abstract")
                funder_elem = rec.find("GrantedAuthority")

                grant_id = grant_id_elem.text if grant_id_elem is not None else "N/A"
                title = title_elem.text if title_elem is not None else "Untitled Grant"
                abstract = abstract_elem.text if abstract_elem is not None else "No Abstract Provided"
                funder = funder_elem.text if funder_elem is not None else "Unknown Funder"

                # Deduplicate across keywords
                unique_key = grant_id if grant_id != "N/A" else title
                if unique_key not in seen_grant_ids:
                    seen_grant_ids.add(unique_key)
                    all_grants.append({
                        "id": grant_id,
                        "title": title,
                        "abstract": abstract,
                        "funder": funder
                    })
                    count_added += 1

                if count_added >= limit_per_keyword:
                    break

        except ET.ParseError as pe:
            print(f"⚠️ XML Parse Error for keyword '{kw}': {pe}")
        except Exception as e:
            print(f"⚠️ Failed fetching GRIST records for keyword '{kw}': {e}")

    print(f"✅ Successfully retrieved {len(all_grants)} unique grant records from GRIST.")
    return all_grants


def process_grants():
    """Main execution loop."""
    grants = fetch_grants_from_grist()

    if not grants:
        print("⚠️ No grants retrieved. Check your network connection or keyword parameters.")
        return

    processed_results = []

    for grant in grants:
        title = grant["title"]
        abstract = grant["abstract"]
        funder = grant["funder"]
        grant_id = grant["id"]

        prompt = f"""
        You are a biotech research analyst. Evaluate the following funded grant project:

        Grant Title: {title}
        Funder: {funder}
        Abstract: {abstract}

        Tasks:
        1. Summarize the core technology or research scope in 2 concise sentences.
        2. Highlight its potential relevance to pharmaceutical or biotech innovation.
        """

        print(f"\nProcessing Grant [{grant_id}]: {title[:60]}...")
        summary = generate_summary(prompt)

        processed_results.append({
            "id": grant_id,
            "title": title,
            "funder": funder,
            "summary": summary
        })

    # Ensure target output directories exist
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Write dashboard output
    html_path = os.path.join(DOCS_DIR, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<html><head><meta charset='utf-8'><title>Biotech Radar Digest</title>")
        f.write("<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin:40px; line-height:1.6; background:#f4f6f8;} .grant-card{margin-bottom:20px; padding:20px; border-left:5px solid #0066cc; background:#fff; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.1);}</style></head><body>")
        f.write("<h1>Pharma Tech Radar Digest (GRIST Grants)</h1>")
        for item in processed_results:
            f.write(f"<div class='grant-card'><h3>{item['title']}</h3>")
            f.write(f"<p><strong>Funder:</strong> {item['funder']} | <strong>Grant ID:</strong> {item['id']}</p>")
            f.write(f"<p>{item['summary']}</p></div>")
        f.write("</body></html>")

    print(f"\n🎉 Processed {len(processed_results)} grants!")
    print(f"📄 Updated dashboard written to {html_path}")


if __name__ == "__main__":
    process_grants()
