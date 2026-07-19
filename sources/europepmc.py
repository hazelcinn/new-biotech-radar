cat > sources/europepmc.py << 'EOF'
"""
Europe PMC REST API — publications (and some grant metadata) worldwide.
Docs: https://europepmc.org/RestfulWebService
No API key required.
"""
import requests
from datetime import date, timedelta
from schema import make_item

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def fetch(keyword: str, lookback_days: int, domain_hint: str = ""):
    since = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    query = f'"{keyword}" AND FIRST_PDATE:[{since} TO {date.today().strftime("%Y-%m-%d")}]'
    params = {
        "query": query,
        "format": "json",
        "pageSize": 50,
        "resultType": "core",
    }
    try:
        resp = requests.get(BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[europepmc] request failed for '{keyword}': {e}")
        return []

    items = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid") or r.get("id")
        url = f"https://europepmc.org/article/{r.get('source','MED')}/{pmid}" if pmid else ""
        affiliations = ""
        author_list = r.get("authorList", {}).get("author", [])
        if author_list:
            affiliations = author_list[0].get("affiliation", "") or ""
        items.append(
            make_item(
                source="Europe PMC",
                item_type="preprint" if r.get("pubType", "").lower() == "preprint" else "publication",
                title=r.get("title", ""),
                url=url,
                date=r.get("firstPublicationDate", ""),
                institution=affiliations,
                raw_text=r.get("abstractText", ""),
                domain_hint=domain_hint,
            )
        )
    return items
EOF
python3 -m py_compile sources/europepmc.py && echo "SYNTAX OK"
