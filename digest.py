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
        domain = item.get("domain", "Uncategorized")
        by_domain.setdefault(domain, []).append(item)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Biotechnology Radar — Weekly Digest ({date.today().isoformat()})\n\n")
        f.write(f"{len(items)} new items this week.\n\n")

        for domain, domain_items in sorted(by_domain.items(), key=lambda kv: -len(kv[1])):
            f.write(f"## {domain} ({len(domain_items)})\n\n")
            for item in domain_items:
                title = item.get("title", "Untitled")
                pi = item.get("project contact", "N/A")
                aff = item.get("affiliation", "N/A")
                abstract = item.get("abstract", "No abstract available.")
                source = item.get("source", "N/A")
                keyword = item.get("keyword", "N/A")
                subject = item.get("subject", "N/A")
                link = item.get("link", "#")

                # 1. Unlinked Title
                f.write(f"### {title}\n")
                f.write(f"- **Project Contact:** {pi}\n")
                f.write(f"- **Affiliation:** {aff}\n")
                f.write(f"- **Subject:** {subject}\n")
                f.write(f"- **Source:** {source} | **Keyword:** {keyword}\n")
                f.write(f"- **Abstract:** {abstract}\n")
                f.write(f"- [🔗 View Original Source]({link})\n\n")
    return path

def write_csv(items: list, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"digest_{date.today().isoformat()}.csv")

    fieldnames = [
        "title", "project contact", "affiliation", "subject", "source",
        "keyword", "domain", "abstract", "link",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({
                "title": item.get("title", ""),
                "project contact": item.get("project contact", ""),
                "affiliation": item.get("affiliation", ""),
                "subject": item.get("subject", ""),
                "source": item.get("source", ""),
                "keyword": item.get("keyword", ""),
                "domain": item.get("domain", ""),
                "abstract": item.get("abstract", ""),
                "link": item.get("link", ""),
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
        keyword = item.get("keyword", "")
        title = item.get("title", "Untitled")
        amount = item.get("affiliation", "N/A")
        duration = item.get("grant duration", "N/A")
        pi = item.get("project contact", "N/A")
        aff = item.get("affiliation", "N/A")
        subject = item.get("subject", "N/A")
        abstract = item.get("abstract", "No abstract available.")
        source = item.get("source", "Source")
        link = item.get("link", "#")

        html_content += f"""
        <div class="item">
            <!-- 1. Unlinked Title -->
            <h3>{title}</h3>
            <div class="meta">
                <strong>Keyword:</strong> {keyword} | 
                <strong>Source:</strong> {source} | 
                <strong>Subject:</strong> {subject} | 
                <strong>Grant Amount:</strong> {amount} | 
                <strong>Grant Duration:</strong> {duration} | 
                
            </div>
            <p><strong>Project Contact (PI):</strong> {pi}</p>
            <p><strong>Affiliation:</strong> {aff}</p>
            <p><strong>Abstract:</strong> {abstract}</p>
            <!-- Separate View Original Source Link -->
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
