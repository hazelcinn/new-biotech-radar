import requests
import json
import sys

queries = [
    "VIBRIO",
    "PUERTO RICO",
    "SEAFOOD",
    "VIBRIO PUERTO RICO",
    "VIBRIO SEAFOOD",
    "261201500036I-0-26100009-2",   # example composite proj num you showed earlier
    "3841636",                      # reporter numeric id you mentioned
]

API = "https://api.reporter.nih.gov/v2/projects/search"
limit = 200

def run_query(q):
    payload = {"criteria": {"keyword": q}, "offset": 0, "limit": limit}
    try:
        r = requests.post(API, json=payload, timeout=30)
    except Exception as e:
        print(f"ERROR: request for '{q}' failed: {e}")
        return None
    print("="*80)
    print(f"Query: {q!r}  -> status: {r.status_code}")
    if r.status_code != 200:
        print("Response text:", r.text[:1000])
        return None
    try:
        data = r.json()
    except Exception as e:
        print("ERROR decoding JSON:", e)
        print("Response text:", r.text[:1000])
        return None
    candidates = data.get("results") or data.get("projects") or data.get("data") or data.get("items") or []
    if isinstance(candidates, dict):
        # try to find a list inside
        for v in candidates.values():
            if isinstance(v, list):
                candidates = v
                break
    print("Total candidates returned:", len(candidates))
    if not candidates:
        return candidates
    # print up to 5 samples
    for i, p in enumerate(candidates[:5], 1):
        title = p.get("projectTitle") or p.get("title") or ""
        print(f"\n-- sample #{i}")
        print(" title:", title)
        print(" projectNumber:", p.get("projectNumber") or p.get("project_number"))
        print(" subProjectId:", p.get("subProjectId") or p.get("sub_project_id"))
        print(" projectDetailId:", p.get("projectDetailId"))
        print(" projectId / id:", p.get("projectId") or p.get("project_id") or p.get("id"))
        print(" projectUrl:", p.get("projectUrl") or p.get("url") or p.get("link"))
        # show first 60 keys to inspect what fields exist
        print(" raw keys:", list(p.keys())[:60])
    return candidates

def main():
    aggregated = {}
    for q in queries:
        res = run_query(q)
        aggregated[q] = len(res) if isinstance(res, list) else None
    print("\nSummary counts:")
    print(json.dumps(aggregated, indent=2))

if __name__ == "__main__":
    main()
