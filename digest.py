"""
Builds the weekly digest in three formats:
- markdown, for quick reading directly in the GitHub repo
- CSV, for filtering/sorting once volume builds up
- HTML, written to docs/ for GitHub Pages, formatted simply so Medium's
  "Import a story" tool converts it cleanly into an editable draft
"""
import os
import csv
import html
from datetime import datetime, date

STAGE_LABELS = {
    "basic_research": "Basic research",
    "funded_not_published": "Funded, not yet published",
    "published_research": "Published research",
    "preprint": "Preprint",
    "commercial_early": "Early commercial",
    "commercial_mature": "Mature commercial",
    "unknown": "Unknown stage",
}


def _domain_label(domain_hint: str) -> str:
    return domain_hint.replace("_", " ").title() if domain_hint else "Uncategorized"


def write_markdown(items: list, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"digest_{date.today().isoformat()}.md")

    # group by domain
    by_domain = {}
    for item in items:
        domain = item.get("domain_hint", "")
        by_domain.setdefault(domain, []).append(item)

    with open(path, "w") as f:
        f.write(f"# Pharma Technology Radar — Weekly Digest ({date.today().isoformat()})\n\n")
        f.write(f"{len(items)} new items this week.\n\n")

        for domain, domain_items in sorted(by_domain.items(), key=lambda kv: -len(kv[1])):
            f.write(f"## {_domain_label(domain)} ({len(domain_items)})\n\n")
            for item in domain_items:
                ext = item.get("extracted") or {}
                if ext.get("relevant") is False:
                    continue
                tech_name = ext.get("technology_name") or item["title"]
                stage = STAGE_LABELS.get(ext.get("development_stage", "unknown"), "Unknown stage")
                f.write(f"### {tech_name}\n")
                f.write(f"- **Source:** {item['source']} ({item.get('item_type','')}) — {stage}\n")
                if item.get("institution"):
                    loc = item.get("institution", "")
                    if item.get("country"):
                        loc += f" ({item['country']})"
                    f.write(f"- **Institution:** {loc}\n")
                if item.get("date"):
                    f.write(f"- **Date:** {item['date']}\n")
                if ext.get("plain_description"):
                    f.write(f"- **What it is:** {ext['plain_description']}\n")
                if ext.get("pharma_relevance"):
                    f.write(f"- **Pharma relevance:** {ext['pharma_relevance']}\n")
                if item.get("url"):
                    f.write(f"- **Link:** {item['url']}\n")
                f.write("\n")
    return path


def write_csv(items: list, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"digest_{date.today().isoformat()}.csv")

    fieldnames = [
        "technology_name", "domain", "development_stage", "source", "item_type",
        "institution", "country", "date", "plain_description", "pharma_relevance", "url",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            ext = item.get("extracted") or {}
            if ext.get("relevant") is False:
                continue
            writer.writerow({
                "technology_name": ext.get("technology_name") or item["title"],
                "domain": _domain_label(item.get("domain_hint", "")),
                "development_stage": STAGE_LABELS.get(ext.get("development_stage", "unknown"), "Unknown"),
                "source": item["source"],
                "item_type": item.get("item_type", ""),
                "institution": item.get("institution", ""),
                "country": item.get("country", ""),
                "date": item.get("date", ""),
                "plain_description": ext.get("plain_description", ""),
                "pharma_relevance": ext.get("pharma_relevance", ""),
                "url": item.get("url", ""),
            })
    return path


def write_html(extracted_items, docs_dir="docs"):
    """Writes the extracted items into a timestamped HTML digest inside docs/digests/."""
    digests_dir = os.path.join(docs_dir, "digests")
    os.makedirs(digests_dir, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}.html"
    filepath = os.path.join(digests_dir, filename)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Biotech Radar Digest - {date_str}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #fdfbf7; }}
        h1 {{ color: #1a365d; border-bottom: 2px solid #cbd5e1; padding-bottom: 10px; }}
        .item {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .item h3 {{ margin-top: 0; color: #2b6cb0; }}
        .meta {{ font-size: 0.85rem; color: #64748b; margin-bottom: 10px; }}
        a {{ color: #2563eb; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Biotech Radar Digest: {date_str}</h1>
    <p><a href="../index.html">← Back to Archive Index</a></p>
    <hr style="margin: 20px 0; border:0; border-top:1px solid #e2e8f0;">
"""

    for item in extracted_items:
        title = item.get("title", "Untitled")
        summary = item.get("summary", "No summary available.")
        source = item.get("source", "Source")
        link = item.get("link", "#")
        keyword = item.get("keyword", "")

        html_content += f"""
        <div class="item">
            <h3><a href="{link}" target="_blank">{title}</a></h3>
            <div class="meta"><strong>Keyword:</strong> {keyword} | <strong>Source:</strong> {source}</div>
            <p><strong>Summary:</strong> {summary}</p>
            <p><a href="{link}" target="_blank">🔗 View Original Source</a></p>
        </div>
        """

    html_content += """
</body>
</html>
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"[digest] HTML successfully written to: {filepath}")
    return filepath


def write_pages_index(docs_dir="docs"):
    """Scans docs/digests/ and updates docs/index.html with an archive list."""
    os.makedirs(docs_dir, exist_ok=True)
    digests_dir = os.path.join(docs_dir, "digests")
    
    os.makedirs(digests_dir, exist_ok=True)
    files = sorted([f for f in os.listdir(digests_dir) if f.endswith(".html")], reverse=True)
    
    index_path = os.path.join(docs_dir, "index.html")
    
    index_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Biotech Radar Archive</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #fdfbf7; }}
        h1 {{ color: #1a365d; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 10px; font-size: 1.1rem; }}
        a {{ color: #2563eb; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Biotech Radar Archive</h1>
    <p>Explore past intelligence reports and research digests:</p>
    <ul>
"""

    if not files:
        index_content += "<li>No digests generated yet.</li>"
    else:
        for file in files:
            date_name = file.replace(".html", "")
            index_content += f'<li><a href="digests/{file}">Digest Report – {date_name}</a></li>\n'

    index_content += """
    </ul>
</body>
</html>
"""

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_content)
        
    print(f"[digest] Index successfully updated: {index_path}")
    return index_path
