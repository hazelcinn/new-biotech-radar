import requests
import json

q = "VIBRIO"
resp = requests.post(
    "https://api.reporter.nih.gov/v2/projects/search",
    json={"criteria": {"keyword": q}, "offset": 0, "limit": 500},
    timeout=30,
)
resp.raise_for_status()
data = resp.json()

candidates = data.get("results") or data.get("projects") or data.get("data") or data.get("items") or []
if isinstance(candidates, dict):
    for v in candidates.values():
        if isinstance(v, list):
            candidates = v
            break

out = []
for p in candidates:
    title = (p.get("projectTitle") or p.get("title") or "")
    if "VIBRIO" not in title.upper() and "VIBRIO" not in str(p.get("projectNumber") or "").upper():
        continue
    out.append({
        "title": title,
        "projectNumber": p.get("projectNumber"),
        "subProjectId": p.get("subProjectId") or p.get("sub_project_id"),
        "projectDetailId": p.get("projectDetailId"),
        "projectId_or_id": p.get("projectId") or p.get("project_id") or p.get("id"),
        "projectUrl": p.get("projectUrl"),
    })

print(json.dumps(out, indent=2))
