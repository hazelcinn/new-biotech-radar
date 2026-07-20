import os
import json
import ollama

def extract_all(raw_items, output_dir, docs_dir):
    print(f"[extract] Processing {len(raw_items)} harvested items for digest locally using Ollama...")
    
    MODEL_NAME = "llama3.2:3b"
    analyzed_papers = []

    for idx, item in enumerate(raw_items, 1):
        print(f"[extract] Analyzing paper {idx}/{len(raw_items)}: {item.get('title')[:50]}...")
        
        # Pulling the keywords and funding/source data from the harvested item
        keywords_list = item.get('keyword', 'N/A')
        funding_source = item.get('source', 'Unknown Source')
        
        paper_info = f"""
        Title: {item.get('title')}
        Source/Funding: {funding_source}
        Keywords: {keywords_list}
        Abstract: {item.get('abstract')}
        """
        
        prompt = f"""
        You are an expert biotech market intelligence analyst. 
        Read this paper data and write a punchy, 2-sentence executive summary explaining why this finding matters to pharma/biotech.
        Output ONLY the 2-sentence summary. Do not add intro text, conversational filler, or formatting.
        
        Paper data:
        {paper_info}
        """
        
        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2}
            )
            
            summary = response['message']['content'].strip()
            
            # 1. Save keywords and funding source alongside the summary
            analyzed_papers.append({
                "title": item.get('title'),
                "link": item.get('link'),
                "source": funding_source,
                "keywords": keywords_list,
                "summary": summary
            })
            
        except Exception as e:
            print(f"[extract] Error analyzing paper #{idx}: {e}")
            analyzed_papers.append({
                "title": item.get('title'),
                "link": item.get('link'),
                "source": funding_source,
                "keywords": keywords_list,
                "summary": "Summary unavailable due to local processing error."
            })

    print("[extract] Building the HTML dashboard layout...")
    
    cards_html = ""
    for paper in analyzed_papers:
        # 2. Injecting the Funding Source and Keywords explicitly into the HTML template cards
        cards_html += f"""
        <div class="card">
            <h2><a href="{paper['link']}" target="_blank">{paper['title']}</a></h2>
            <div class="meta">
                <span class="tag funding">💰 Funding/Source: {paper['source']}</span>
                <span class="tag keyword">🔑 Keywords: {paper['keywords']}</span>
            </div>
            <p class="summary">{paper['summary']}</p>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Biotech Market Intelligence Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        h1 {{
            color: #38bdf8;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
        }}
        .card {{
            background-color: #1e293b;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .card h2 a {{
            color: #f8fafc;
            text-decoration: none;
        }}
        .card h2 a:hover {{
            color: #38bdf8;
            text-decoration: underline;
        }}
        .meta {{
            margin: 12px 0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .tag {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
        }}
        .funding {{ background-color: #1e3a8a; color: #dbeafe; border: 1px solid #3b82f6; }}
        .keyword {{ background-color: #064e3b; color: #d1fae5; border: 1px solid #10b981; }}
        .summary {{
            line-height: 1.6;
            color: #cbd5e1;
            margin-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weekly Biotech Summary Dashboard</h1>
        <div class="feed">
            {cards_html}
        </div>
    </div>
</body>
</html>"""

    try:
        os.makedirs(docs_dir, exist_ok=True)
        html_path = os.path.join(docs_dir, "index.html")
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"[extract] Successfully wrote fresh local dashboard with funding and keywords to {html_path}")
        return True

    except Exception as e:
        print(f"[extract] Error saving HTML file: {e}")
        return False
