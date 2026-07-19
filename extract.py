import os
import json
from anthropic import Anthropic

def extract_all(raw_items, output_dir, docs_dir):
    print(f"[extract] Processing {len(raw_items)} harvested items for digest...")
    
    # 1. Initialize the Anthropic client using the GitHub secret
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[extract] Error: ANTHROPIC_API_KEY environment variable not found.")
        return False
        
    client = Anthropic(api_key=api_key)
    
    # 2. Format the raw paper data into text for Claude to read
    papers_text = ""
    for idx, item in enumerate(raw_items, 1):
        papers_text += f"\n--- Paper #{idx} ---\n"
        papers_text += f"Title: {item.get('title')}\n"
        papers_text += f"Source: {item.get('source')} | Keyword: {item.get('keyword')}\n"
        papers_text += f"Link: {item.get('link')}\n"
        papers_text += f"Abstract: {item.get('abstract')}\n"

    # 3. Create the prompt asking Claude to construct an elegant HTML dashboard
    prompt = f"""
    You are an expert biotech market intelligence analyst. 
    Analyze the following recent scientific papers and compile a beautifully styled, high-impact weekly summary.
    
    Generate ONLY a complete, valid HTML5 file that will serve as the dashboard. Include modern CSS inside <style> tags (use a dark or clean modern tech theme, nice typography, cards for articles, and tags for sources).
    
    Organize the papers logically by domain/theme. For each paper, include its title (linked to its original URL), source, and a punchy 2-sentence executive summary explaining why this finding matters to pharma/biotech.
    
    Papers data:
    {papers_text}
    """

    # 4. Call Claude (using the standard claude-3-5-sonnet model)
    try:
        print("[extract] Sending data to Anthropic Claude...")
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.2,
            system="You only output pure HTML code starting with <!DOCTYPE html>. Do not include markdown code blocks like ```html.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        html_content = message.content[0].text.strip()
        
        # 5. Ensure directories exist and save the live dashboard
        os.makedirs(docs_dir, exist_ok=True)
        html_path = os.path.join(docs_dir, "index.html")
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"[extract] Successfully wrote fresh dashboard to {html_path}")
        return True

    except Exception as e:
        print(f"[extract] Error during Claude extraction: {e}")
        return False
