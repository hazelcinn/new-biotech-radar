"""
Builds the weekly digest in three formats:
- markdown, for quick reading directly in the GitHub repo
- CSV, for filtering/sorting once volume builds up
- HTML, written to docs/ for GitHub Pages, formatted simply so Medium's
  "Import a story" tool converts it cleanly into an editable draft
"""
import csv
import os
import html
from datetime import date

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


def write_html(items: list, docs_dir: str) -> str:
    """
    Writes a single, simply-structured HTML page for this week's digest into
    docs_dir/digests/. Deliberately avoids CSS, layout divs, and styling —
    Medium's import tool works best with plain semantic HTML (h1/h2/h3, p,
    ul/li, a) and strips most styling anyway, so keeping it minimal reduces
    import artifacts.
    """
    digests_dir = os.path.join(docs_dir, "digests")
    os.makedirs(digests_dir, exist_ok=True)
    today = date.today().isoformat()
    path = os.path.join(digests_dir, f"{today}.html")

    by_domain = {}
    for item in items:
        ext = item.get("extracted") or {}
        if ext.get("relevant") is False:
            continue
        domain = item.get("domain_hint", "")
        by_domain.setdefault(domain, []).append(item)

    total = sum(len(v) for v in by_domain.values())

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append(f"<title>Pharma Technology Radar — {today}</title>")
    parts.append("</head><body>")
    parts.append(f"<h1>Pharma Technology Radar — Weekly Digest ({today})</h1>")
    parts.append(f"<p>{total} new items this week.</p>")

    for domain, domain_items in sorted(by_domain.items(), key=lambda kv: -len(kv[1])):
        parts.append(f"<h2>{html.escape(_domain_label(domain))} ({len(domain_items)})</h2>")
        for item in domain_items:
            ext = item.get("extracted") or {}
            tech_name = ext.get("technology_name") or item["title"]
            stage = STAGE_LABELS.get(ext.get("development_stage", "unknown"), "Unknown stage")

            parts.append(f"<h3>{html.escape(tech_name)}</h3>")
            parts.append("<ul>")
            meta_line = f"{html.escape(item['source'])} ({html.escape(item.get('item_type',''))}) — {html.escape(stage)}"
            parts.append(f"<li><strong>Source:</strong> {meta_line}</li>")
            if item.get("institution"):
                loc = item.get("institution", "")
                if item.get("country"):
                    loc += f" ({item['country']})"
                parts.append(f"<li><strong>Institution:</strong> {html.escape(loc)}</li>")
            if item.get("date"):
                parts.append(f"<li><strong>Date:</strong> {html.escape(item['date'])}</li>")
            parts.append("</ul>")
            if ext.get("plain_description"):
                parts.append(f"<p><strong>What it is:</strong> {html.escape(ext['plain_description'])}</p>")
            if ext.get("pharma_relevance"):
                parts.append(f"<p><strong>Pharma relevance:</strong> {html.escape(ext['pharma_relevance'])}</p>")
            if item.get("url"):
                safe_url = html.escape(item["url"], quote=True)
                parts.append(f'<p><a href="{safe_url}">Original source</a></p>')

    parts.append("</body></html>")

    with open(path, "w") as f:
        f.write("\n".join(parts))
    return path


def write_pages_index(docs_dir: str) -> str:
    """
    Rebuilds docs/index.html each run: a simple list of every digest that
    exists in docs/digests/, newest first, so you always have one stable
    URL (yourusername.github.io/repo-name/) to check for the latest links.
    """
    digests_dir = os.path.join(docs_dir, "digests")
    os.makedirs(digests_dir, exist_ok=True)
    files = sorted(
        (f for f in os.listdir(digests_dir) if f.endswith(".html")),
        reverse=True,
    )

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>Pharma Technology Radar — Digest Archive</title>",
        "</head><body>",
        "<h1>Pharma Technology Radar — Digest Archive</h1>",
        "<ul>",
    ]
    for f in files:
        label = f.replace(".html", "")
        parts.append(f'<li><a href="digests/{f}">{html.escape(label)}</a></li>')
    parts.append("</ul></body></html>")

    path = os.path.join(docs_dir, "index.html")
    with open(path, "w") as fh:
        fh.write("\n".join(parts))
    return path
