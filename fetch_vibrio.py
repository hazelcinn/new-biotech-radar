import requests
import json

q = "VIBRIO SPECIES IN MARKET LEVEL SEAFOOD AND COASTAL WATERS IN PUERTO RICO"

resp = requests.post(
    "https://api.reporter.nih.gov/v2/projects/search",
    json={"criteria": {"keyword": q}, "offset": 0, "limit": 200},
    timeout=30,
)
data = resp.json()

candidates = data.get("results") or data.get("projects") or data.get("data") or data.get("items") or []
if isinstance(candidates, dict):
    for v in candidates.values():
        if isinstance(v, list):
            candidates = v
            break

matches = [
    p
    for p in candidates
    if "VIBRIO" in (p.get("projectTitle") or p.get("title") or "").upper()
]

keys = [
    "projectNumber",
    "project_number",
    "subProjectId",
    "sub_project_id",
    "projectId",
    "project_id",
    "id",
    "projectDetailId",
    "projectUrl",
    "title",
    "contactPiName",
    "contact_pi_name",
    "contactPIs",
]

out = []
for p in matches:
    d = {k: p.get(k) for k in keys}
    d["_raw_sample_keys"] = list(p.keys())[:80]
    out.append(d)

print(json.dumps(out, indent=2))
