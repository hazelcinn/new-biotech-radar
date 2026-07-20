<<<<<<< Updated upstream
import os
import requests

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

    # Add future providers here (e.g., groq, openai, deepseek)
    else:
        raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")
=======
"""
On-demand pipeline entrypoint.
"""
import os
import sys
import glob
import re
from config import DOMAINS, LOOKBACK_DAYS, STATE_FILE, OUTPUT_DIR, DOCS_DIR
from sources import europepmc
from extract import extract_all

def get_next_digest_number(digests_dir):
    """Finds the highest number in the digests folder and adds 1."""
    os.makedirs(digests_dir, exist_ok=True)
    existing_files = glob.glob(os.path.join(digests_dir, "digest_*.html"))
    
    highest_num = 0
    for filepath in existing_files:
        filename = os.path.basename(filepath)
        # Looks for the digits inside 'digest_X.html'
        match = re.search(r'digest_(\d+)\.html', filename)
        if match:
            num = int(match.group(1))
            if num > highest_num:
                highest_num = num
                
    return highest_num + 1

def main():
    print(f"[main] Harvesting across categories, {LOOKBACK_DAYS}-day lookback...")
    all_harvested_items = []
    
    # Run the harvesting loop across all your configured keywords
    for domain_name, keywords in DOMAINS.items():
        for kw in keywords:
            results = europepmc.fetch(clean_kw, LOOKBACK_DAYS, domain_name)
            if results:
                all_harvested_items.extend(results)
                
    print(f"[main] Harvested {len(all_harvested_items)} total items.")
    
    if not all_harvested_items:
        print("[main] No papers found. Generating a standard placeholder page.")
        os.makedirs(DOCS_DIR, exist_ok=True)
        with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
            f.write("<html><body><h1>Biotech Radar Online: No new papers found in this window.</h1></body></html>")
        return 0

    # Determine the unique sequential file name (e.g., digest_1.html, digest_2.html)
    digests_dir = os.path.join(DOCS_DIR, "digests")
    next_num = get_next_digest_number(digests_dir)
    unique_filename = f"digest_{next_num}.html"

    # Pass the data and our unique file name down to the compiler script
    success = extract_all(all_harvested_items, OUTPUT_DIR, DOCS_DIR, unique_filename)
    if success:
        print(f"[main] Success! Digest sequence #{next_num} compiled successfully.")
    else:
        print("[main] Failed compiling the dashboard.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
>>>>>>> Stashed changes
