# sources/nih_reporter.py
import urllib.parse
import requests
import re
import json
from typing import List, Dict, Any, Optional

# ORCID helpers
_ORCID_HYPHEN_RE = re.compile(r'(\d{4}-\d{4}-\d{4}-[\dXx]{4})')
_ORCID_URL_RE = re.compile(r'https?://orcid\.org/(\d{4}-\d{4}-\d{4}-[\dXx]{4})', re.I)

def _orcid_normalize(candidate: str) -> Optional[str]:
    if not candidate:
        return None
    s = candidate.strip()
    m = _ORCID_URL_RE.search(s)
    if m:
        return m.group(1)
    m2 = _ORCID_HYPHEN_RE.search(s)
    if m2:
        return m2.group(1)
    digits = re.sub(r'\D', '', s)
    if len(digits) == 16:
        return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"
    return None

def _orcid_checksum_is_valid(orcid_hyphenated: str) -> bool:
    if not orcid_hyphenated:
        return False
    digits = re.sub(r'[^0-9Xx]', '', orcid_hyphenated)
    if len(digits) != 16:
        return False
    total = 0
    for ch in digits[:-1]:
        if not ch.isdigit():
            return False
        total = (total + int(ch)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    check_char = 'X' if result == 10 else str(result)
    return check_char == digits[-1].upper()

# Simple text helpers
def _truncate_text(text: str, length: int = 200) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= length:
        return t
    cut = t[:length].rsplit(" ", 1)[0]
    return cut + "…"

def _simple_sentence_summary(text: str, max_sentences: int = 5) -> str:
    if not text:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s and len(s.strip()) > 0]
    if not sentences:
        return _truncate_text(text, 200)
    return " ".join(sentences[:max_sentences])

def _clean_simple_text(node) -> str:
    if not node:
        return ""
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, list):
        parts = []
        for v in node:
            parts.append(_clean_simple_text(v))
        return " ".join([p for p in parts if p]).strip()
    if isinstance(node, dict):
        for k in ("abstractText", "abstract", "project_abstract", "abstract_text", "description", "projectDescription", "summary"):
            if k in node and node[k]:
                return _clean_simple_text(node[k])
        leaves = []
        def _g(o):
            if isinstance(o, str):
                leaves.append(o.strip())
            elif isinstance(o, dict):
                for vv in o.values():
                    _g(vv)
            elif isinstance(o, list):
                for vv in o:
                    _g(vv)
        _g(node)
        return " ".join([l for l in leaves if l]).strip()
    return str(node).strip()

def _find_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _find_strings(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _find_strings(v)

def _make_clickable_pi(pi_name: str, orcid_url: str) -> str:
    if not orcid_url:
        return pi_name
    return f'<a href="{orcid_url}" target="_blank" rel="noopener noreferrer">{pi_name}</a>'

# Ollama summarization helper (defensive)
def _ollama_summarize(
    text: str,
    n_sentences: int = 5,
    ollama_url: str = "http://localhost:11434",
    model: str = "llama2",
    max_tokens: int = 256,
    temperature: float = 0.2,
    timeout: int = 15,
) -> Optional[str]:
    if not text:
        return ""
    prompt = (
        f"Summarize the following abstract into {n_sentences} concise sentences. "
        "Keep it factual and omit speculative claims.\n\n"
        f"Abstract:\n{text.strip()}\n\nSummary:"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    try:
        resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
    except Exception:
        return None
    try:
        j = resp.json()
    except Exception:
        j = None
    if j:
        if isinstance(j, dict):
            if "text" in j and isinstance(j["text"], str):
                return j["text"].strip()
            if "result" in j and isinstance(j["result"], str):
                return j["result"].strip()
            if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
                c = j["choices"][0]
                if isinstance(c, dict):
                    for key in ("text", "content", "message"):
                        if key in c and isinstance(c[key], str):
                            return c[key].strip()
                    if "message" in c and isinstance(c["message"], dict) and "content" in c["message"]:
                        return str(c["message"]["content"]).strip()
    if resp.status_code == 200 and resp.text:
        return resp.text.strip()
    return None

def fetch_nih_reporter(
    keyword: str,
    lookback_days: int,
    domain: str,
    limit: int = 10,
    summary_mode: str = "truncate",   # "truncate" | "sentences" | "ollama"
    truncate_chars: int = 200,
    summary_sentences: int = 5,
    use_ollama: bool = False,
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "llama2",
    ollama_max_tokens: int = 256,
    ollama_temperature: float = 0.2,
    ollama_timeout: int = 15,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    results_out: List[Dict[str, Any]] = []
    endpoint = "https://api.reporter.nih.gov/v2/projects/search"
    headers = {
        "User-Agent": "GrantHarvester/1.0 (+https://your.project/)",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {
        "criteria": {
            "keyword": [keyword]
        },
        "offset": 0,
        "limit": limit
    }
    try:
        resp = requests.post(endpoint, json=body, headers=headers, timeout=15)
    except Exception as e:
        if debug:
            print("[nih] request failed:", e)
        return results_out
    if resp.status_code != 200:
        if debug:
            print("[nih] non-200 response:", resp.status_code, resp.text[:400])
        return results_out
    try:
        data = resp.json()
    except Exception as e:
        if debug:
            print("[nih] json decode failed:", e)
        return results_out
    candidates = data.get("results") or data.get("projects") or data.get("data") or data.get("items") or []
    if isinstance(candidates, dict):
        for v in candidates.values():
            if isinstance(v, list):
                candidates = v
                break

    for proj in candidates[:limit]:
        title = (
            proj.get("projectTitle")
            or proj.get("project_title")
            or proj.get("title")
            or proj.get("projectTitleDisplay")
            or ""
        ).strip()
        project_num = (
            proj.get("projectNumber")
            or proj.get("project_number")
            or proj.get("projectId")
            or proj.get("project_id")
            or proj.get("id")
            or ""
        )
        abstract_raw = (
            proj.get("abstractText")
            or proj.get("abstract")
            or proj.get("projectAbstract")
            or proj.get("abstract_text")
            or proj.get("project_description")
            or proj.get("description")
            or proj.get("summary")
            or proj.get("projectSummary")
            or None
        )
        if abstract_raw is None and isinstance(proj, dict):
            for k, v in proj.items():
                if isinstance(k, str) and ("abstract" in k.lower() or "project" in k.lower() or "summary" in k.lower()):
                    abstract_raw = v
                    break
        abstract = _clean_simple_text(abstract_raw) if abstract_raw is not None else ""

        # build abstract_display using summary_mode and Ollama option
        if not abstract:
            abstract_display = "No abstract available."
        else:
            if summary_mode == "ollama" and use_ollama:
                summary = _ollama_summarize(
                    abstract,
                    n_sentences=summary_sentences,
                    ollama_url=ollama_url,
                    model=ollama_model,
                    max_tokens=ollama_max_tokens,
                    temperature=ollama_temperature,
                    timeout=ollama_timeout,
                )
                if summary:
                    abstract_display = summary
                else:
                    # fallback chain
                    abstract_display = _simple_sentence_summary(abstract, max_sentences=summary_sentences)
                    if not abstract_display:
                        abstract_display = _truncate_text(abstract, truncate_chars)
            elif summary_mode == "sentences":
                abstract_display = _simple_sentence_summary(abstract, max_sentences=summary_sentences)
            else:
                abstract_display = _truncate_text(abstract, truncate_chars)

        # PI extraction (varied shapes)
        pi_name = ""
        person_obj = {}
        if proj.get("contact_pi_name"):
            pi_name = proj.get("contact_pi_name")
        elif proj.get("contactPiName"):
            pi_name = proj.get("contactPiName")
        elif proj.get("contactPIs"):
            cp = proj.get("contactPIs")
            if isinstance(cp, list) and cp:
                pi_name = cp[0].get("contact_pi_name") or cp[0].get("name") or ""
                person_obj = cp[0]
            elif isinstance(cp, dict):
                pi_name = cp.get("name") or cp.get("contact_pi_name") or ""
                person_obj = cp
        elif proj.get("piNames"):
            pn = proj.get("piNames")
            if isinstance(pn, list) and pn:
                pi_name = pn[0] if isinstance(pn[0], str) else (pn[0].get("name") if isinstance(pn[0], dict) else "")
        elif proj.get("principal_investigator"):
            pi_name = proj.get("principal_investigator")
        else:
            for k in ("principalInvestigators", "principal_investigators", "principalInvestigator", "pi"):
                v = proj.get(k)
                if isinstance(v, list) and v:
                    first = v[0]
                    if isinstance(first, dict):
                        pi_name = first.get("fullName") or first.get("name") or first.get("displayName") or ""
                        person_obj = first
                    elif isinstance(first, str):
                        pi_name = first
                    break
                elif isinstance(v, dict):
                    pi_name = v.get("fullName") or v.get("name") or ""
                    person_obj = v
                    break
        pi_raw = (pi_name or "").strip() or "N/A"

        # ORCID detection
        orcid_url = ""
        if isinstance(person_obj, dict):
            for key in ("orcid", "orcidId", "Orcid", "ORCID", "pi_orcid"):
                val = person_obj.get(key)
                if val:
                    cand = _orcid_normalize(str(val))
                    if cand and _orcid_checksum_is_valid(cand):
                        orcid_url = f"https://orcid.org/{cand}"
                        break
        if not orcid_url and isinstance(proj, dict):
            for k in ("pi_ids", "piIds", "piIdentifiers", "projectPIs"):
                if k in proj and proj[k]:
                    val = proj[k]
                    if isinstance(val, str):
                        cand = _orcid_normalize(val)
                        if cand and _orcid_checksum_is_valid(cand):
                            orcid_url = f"https://orcid.org/{cand}"
                            break
                    elif isinstance(val, list):
                        found = False
                        for entry in val:
                            if isinstance(entry, dict):
                                if str(entry.get("type", "")).upper() == "ORCID":
                                    cand = _orcid_normalize(str(entry.get("value") or entry.get("id") or ""))
                                    if cand and _orcid_checksum_is_valid(cand):
                                        orcid_url = f"https://orcid.org/{cand}"
                                        found = True
                                        break
                                else:
                                    for s in _find_strings(entry):
                                        cand = _orcid_normalize(s)
                                        if cand and _orcid_checksum_is_valid(cand):
                                            orcid_url = f"https://orcid.org/{cand}"
                                            found = True
                                            break
                            elif isinstance(entry, str):
                                cand = _orcid_normalize(entry)
                                if cand and _orcid_checksum_is_valid(cand):
                                    orcid_url = f"https://orcid.org/{cand}"
                                    found = True
                                    break
                        if found:
                            break
        if not orcid_url:
            dump = json.dumps(proj) if isinstance(proj, dict) else str(proj)
            m = _orcid_normalize(dump)
            if m and _orcid_checksum_is_valid(m):
                orcid_url = f"https://orcid.org/{m}"

        pi_display = _make_clickable_pi(pi_raw, orcid_url)

        org = (
            proj.get("orgName")
            or proj.get("org_name")
            or proj.get("organization")
            or proj.get("applicantOrganization")
            or proj.get("org")
            or ""
        )
        affiliation = org or "N/A"

        amount_val = proj.get("awardAmount") or proj.get("award_amount") or proj.get("award") or proj.get("total_cost") or None
        amount = "N/A"
        if amount_val is not None:
            try:
                num = float(amount_val)
                amount = f"${int(num):,}" if num.is_integer() else f"${num:,.2f}"
            except Exception:
                amount = str(amount_val)

        start_date = proj.get("projectStartDate") or proj.get("project_start_date") or proj.get("startDate") or proj.get("start")
        end_date = proj.get("projectEndDate") or proj.get("project_end_date") or proj.get("endDate") or proj.get("end")
        if start_date and end_date:
            duration = f"{start_date} to {end_date}"
        else:
            duration = proj.get("projectPeriodText") or proj.get("fiscal_year") or proj.get("fy") or "N/A"

        if project_num:
            grant_link = f"https://reporter.nih.gov/project-details/{urllib.parse.quote(str(project_num))}"
        else:
            grant_link = f"https://reporter.nih.gov/search/results?query={urllib.parse.quote(title or keyword)}"

        results_out.append({
            "title": title or "Untitled Project",
            "project contact": pi_display,
            "project_contact_name": pi_raw,
            "project_contact_orcid": orcid_url,
            "project_contact_html": pi_display,
            "project_contact_md": f"[{pi_raw}]({orcid_url})" if orcid_url else pi_raw,
            "affiliation": affiliation,
            "grant amount": amount,
            "grant duration": duration,
            "abstract": abstract_display,
            "abstract_full": abstract,
            "source": "NIH RePORTER",
            "keyword": keyword,
            "domain": domain,
            "link": grant_link
        })

    return results_out
    def fetch(keyword: str, lookback_days: int, domain: str, **kwargs):
        return fetch_nih_reporter(keyword, lookback_days, domain, **kwargs)
