# sources/nih_reporter.py
import urllib.parse
import requests
import re
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse, quote

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

def _looks_like_reporter_projnum(s: str) -> bool:
    if not s:
        return False
    s = str(s).strip()
    # typical NIH project numbers include letters and digits (e.g., R01CA123456-01A1)
    if re.search(r'[A-Za-z]', s) and re.search(r'\d', s):
        return True
    if '-' in s and re.match(r'^[A-Za-z0-9\-\_]+$', s):
        return True
    return False

def _normalize_person_name(name: str) -> str:
    """
    Convert "Last, First [Middle]" to "First [Middle] Last".
    Leaves names already in "First Last" form unchanged.
    """
    if not name:
        return ""
    s = name.strip()
    if ',' in s:
        parts = [p.strip() for p in s.split(',') if p.strip()]
        if len(parts) >= 2:
            last = parts[0]
            rest = " ".join(parts[1:])
            return f"{rest} {last}"
    return s

def _date_only(dt) -> str:
    if not dt:
        return ""
    s = str(dt).strip()
    s = s.rstrip(" |;,-")
    if "T" in s:
        s = s.split("T", 1)[0]
    elif " " in s and re.match(r'^\d{4}-\d{2}-\d{2}\s', s):
        s = s.split(" ", 1)[0]
    if len(s) > 10 and re.match(r'^\d{4}', s):
        s = s[:10]
    return s

def _format_nih_affiliation(aff_node: dict, title_case: bool = False) -> dict:
    if not aff_node or not isinstance(aff_node, dict):
        return {
            "affiliation": "",
            "org_name": "",
            "city": "",
            "state": "",
            "country": "",
            "zipcode": "",
            "duns": [],
            "ueis": [],
            "primary_duns": None,
            "primary_uei": None,
        }
    org_name = (
        aff_node.get("org_name")
        or aff_node.get("orgName")
        or aff_node.get("organization")
        or aff_node.get("name")
        or ""
    ) or ""
    city = (aff_node.get("org_city") or aff_node.get("city") or "").strip()
    state = (aff_node.get("org_state") or aff_node.get("org_state_name") or aff_node.get("state") or "").strip()
    country = (aff_node.get("org_country") or aff_node.get("country") or aff_node.get("org_fips") or "").strip()
    zipcode = (aff_node.get("org_zipcode") or aff_node.get("zipcode") or "").strip()

    duns = aff_node.get("org_duns") or aff_node.get("org_duns_list") or []
    if isinstance(duns, str):
        duns = [duns]
    ueis = aff_node.get("org_ueis") or aff_node.get("org_uei") or []
    if isinstance(ueis, str):
        ueis = [ueis]

    primary_duns = aff_node.get("primary_duns") or aff_node.get("primary_duns") or aff_node.get("primary_duns", None)
    primary_uei = aff_node.get("primary_uei") or aff_node.get("primary_uei") or aff_node.get("primary_uei", None)

    if country and len(country) == 2 and country.isalpha():
        if country.upper() in ("US", "USA"):
            country_display = "United States"
        else:
            country_display = country.upper()
    else:
        country_display = country

    def _maybe_title(s: str) -> str:
        return s.title() if title_case and s else s

    org_name_display = _maybe_title(org_name)
    city_display = _maybe_title(city)
    state_display = state
    country_display = _maybe_title(country_display)

    parts = []
    if org_name_display:
        parts.append(org_name_display)
    loc_parts = []
    if city_display:
        loc_parts.append(city_display)
    if state_display:
        loc_parts.append(state_display)
    if country_display:
        loc_parts.append(country_display)
    if loc_parts:
        parts.append(", ".join(loc_parts))

    affiliation = ", ".join(parts) if parts else org_name_display or ""

    return {
        "affiliation": affiliation,
        "org_name": org_name,
        "city": city,
        "state": state,
        "country": country_display or "",
        "zipcode": zipcode,
        "duns": duns if isinstance(duns, list) else list(duns),
        "ueis": ueis if isinstance(ueis, list) else list(ueis),
        "primary_duns": primary_duns,
        "primary_uei": primary_uei,
    }

_NIH_INSTITUTE_MAP = {
    "NCI": "National Cancer Institute",
    "NIAID": "National Institute of Allergy and Infectious Diseases",
    "NIMH": "National Institute of Mental Health",
    "NINDS": "National Institute of Neurological Disorders and Stroke",
    "NIEHS": "National Institute of Environmental Health Sciences",
    "NIDDK": "National Institute of Diabetes and Digestive and Kidney Diseases",
    "NICHD": "Eunice Kennedy Shriver National Institute of Child Health and Human Development",
    "NIGMS": "National Institute of General Medical Sciences",
    "NIA": "National Institute on Aging",
    "NIDA": "National Institute on Drug Abuse",
}

def _extract_funder_from_proj(proj: dict, debug: bool = False) -> str:
    if not isinstance(proj, dict):
        return "NIH RePORTER"

    for key in (
        "fundingAgency", "funding_agency", "funder", "awardOrg", "award_organization",
        "agency", "agencyName", "agency_name", "awardingIC", "awarding_ic", "awardingICName",
        "fundingIC", "funding_ic", "fundingICName", "org", "orgName", "org_name"
    ):
        val = proj.get(key)
        if not val:
            continue
        if isinstance(val, dict):
            for sub in ("name", "displayName", "agency", "agencyName", "funder"):
                name = val.get(sub)
                if name:
                    return str(name).strip()
        elif isinstance(val, str) and val.strip():
            s = val.strip()
            if s.upper() in _NIH_INSTITUTE_MAP:
                return _NIH_INSTITUTE_MAP[s.upper()]
            return s

    awarding = proj.get("awardingIC") or proj.get("awardIC") or proj.get("award_ics") or proj.get("awardICs")
    if awarding:
        if isinstance(awarding, str):
            if awarding.upper() in _NIH_INSTITUTE_MAP:
                return _NIH_INSTITUTE_MAP[awarding.upper()]
            return awarding
        if isinstance(awarding, dict):
            code = awarding.get("code") or awarding.get("acronym") or awarding.get("id")
            name = awarding.get("name") or awarding.get("displayName")
            if name:
                return name
            if code and str(code).upper() in _NIH_INSTITUTE_MAP:
                return _NIH_INSTITUTE_MAP[str(code).upper()]
            if code:
                return str(code)

    funding = proj.get("funding") or proj.get("award") or proj.get("awards")
    if isinstance(funding, dict):
        for sub in ("agency", "funder", "org", "awardOrg", "awardingIC", "awardingICName"):
            v = funding.get(sub)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                name = v.get("name") or v.get("displayName")
                if name:
                    return name

    for k, v in proj.items():
        if isinstance(k, str) and any(tok in k.lower() for tok in ("funder", "funding", "award", "agency", "institute", "ic")):
            if isinstance(v, str) and v.strip():
                s = v.strip()
                if s.upper() in _NIH_INSTITUTE_MAP:
                    return _NIH_INSTITUTE_MAP[s.upper()]
                return s
            if isinstance(v, dict):
                n = v.get("name") or v.get("displayName")
                if n:
                    return n

    if debug:
        sample_keys = {k: type(v).__name__ for k, v in list(proj.items())[:40]}
        print("[nih debug] no funder found; top-level keys (sample):", sample_keys)

    return "NIH RePORTER"


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

def _extract_numeric_id_from_url(url):
    if not url:
        return None
    try:
        p = urlparse(str(url))
        m = re.search(r"/project-details/(\d+)(?:/|$)", p.path or "")
        if m:
            return m.group(1)
        last = (p.path or "").rstrip("/").split("/")[-1]
        if last.isdigit():
            return last
    except Exception:
        return None
    return None

def build_source_and_link(proj: dict, title: str = "", keyword: str = "", debug: bool = False):
    """
    Given a single RePORTER project dict `proj`, compute a stable source_id and a canonical grant_link.
    Returns tuple: (source_id, grant_link, numeric_id, detail_url, proj_num_candidate, internal_id, proj_num, sub_proj)
    Paste this helper at module scope (only once) and call it inside your per-project loop.
    """
    # normalized getters
    proj_num = (
        proj.get("projectNumber")
        or proj.get("project_number")
        or proj.get("project_num")
        or proj.get("core_project_num")
        or ""
    )
    proj_num = str(proj_num).strip() if proj_num else ""

    sub_proj = (
        proj.get("subProjectId")
        or proj.get("sub_project_id")
        or proj.get("subproject_id")
        or None
    )
    sub_proj = str(sub_proj).strip() if sub_proj else None

    # Prefer explicit numeric id fields
    numeric_id = None
    for key in ("projectDetailId", "projectDetailID", "projectId", "project_id", "id", "appl_id"):
        val = proj.get(key)
        if val:
            s = str(val).strip()
            if s.isdigit():
                numeric_id = s
                break

    # Prefer explicit RePORTER project_detail_url field (snake_case) or camelCase
    primary_detail = proj.get("project_detail_url") or proj.get("projectDetailUrl")
    primary_detail = str(primary_detail).strip() if primary_detail else None

    # fallback detail_url (other URL-like fields)
    detail_url = (
        primary_detail
        or proj.get("projectUrl")
        or proj.get("project_url")
        or proj.get("url")
        or proj.get("link")
        or ""
    )
    detail_url = str(detail_url).strip() if detail_url else ""

    # Extract numeric id from URLs if not already found
    def _extract_numeric_id_from_url_local(url):
        if not url:
            return None
        try:
            p = urlparse(str(url))
            m = re.search(r"/project-details/(\d+)(?:/|$)", p.path or "")
            if m:
                return m.group(1)
            last = (p.path or "").rstrip("/").split("/")[-1]
            if last.isdigit():
                return last
        except Exception:
            return None
        return None

    if not numeric_id and primary_detail:
        numeric_id = _extract_numeric_id_from_url_local(primary_detail)
    if not numeric_id and detail_url:
        numeric_id = _extract_numeric_id_from_url_local(detail_url)

    # internal id fallback
    internal_id = str(proj.get("projectId") or proj.get("project_id") or proj.get("id") or "").strip()

    # Build proj_num_candidate (project-number-based link candidate)
    proj_num_candidate = None
    if proj_num:
        if "-" in proj_num:
            proj_num_candidate = proj_num
        else:
            if sub_proj:
                proj_num_candidate = f"{proj_num}-{sub_proj}"
            else:
                proj_num_candidate = proj_num

    # Build stable source_id (keep subprojects distinct)
    if proj_num and sub_proj:
        source_id = f"{proj_num}::{sub_proj}"
    elif proj_num:
        source_id = proj_num
    elif numeric_id:
        source_id = f"RID::{numeric_id}"
    elif internal_id:
        source_id = internal_id
    else:
        org = proj.get("organization") or proj.get("organizationName") or proj.get("orgName") or ""
        source_id = (title or "")[:120] + "|" + str(org)[:60]

    # Build canonical grant_link: priority described in docstring
    grant_link = None

    # 1) Prefer explicit project_detail_url if it's a reporter.nih.gov URL with a non-root path
    if primary_detail and "reporter.nih.gov" in primary_detail:
        try:
            p = urlparse(primary_detail)
            if p.path and p.path.strip() not in ("/", ""):
                grant_link = urlunparse((p.scheme or "https", p.netloc, p.path, "", "", ""))
        except Exception:
            grant_link = primary_detail

    # 2) numeric_id authoritative
    if not grant_link and numeric_id:
        grant_link = f"https://reporter.nih.gov/project-details/{quote(numeric_id)}"

    # 3) fallback: any other reporter URL returned by the API (canonicalized)
    if not grant_link and detail_url and "reporter.nih.gov" in detail_url:
        try:
            p = urlparse(detail_url)
            if p.path and p.path.strip() not in ("/", ""):
                grant_link = urlunparse((p.scheme or "https", p.netloc, p.path, "", "", ""))
        except Exception:
            grant_link = detail_url

    # 4) proj_num_candidate -> project-details/<proj_num_candidate> 
    if not grant_link and proj_num_candidate:
        # If a module-level helper _looks_like_reporter_projnum exists, prefer it; else do a lightweight check.
        try:
            looks_ok = _looks_like_reporter_projnum(proj_num_candidate)  # uses your existing helper if present
        except NameError:
            looks_ok = bool(re.search(r'[A-Za-z]', proj_num_candidate) and re.search(r'\d', proj_num_candidate)) or ("-" in proj_num_candidate)
        if looks_ok:
            grant_link = f"https://reporter.nih.gov/project-details/{quote(proj_num_candidate)}"

    # 5) final fallback -> reporter search
    if not grant_link:
        search_term = proj_num_candidate or title or keyword or ""
        grant_link = f"https://reporter.nih.gov/search/results?query={quote(search_term)}"

    if debug:
        print("[NIH DEBUG] title:", title)
        print("[NIH DEBUG] source_id:", source_id)
        print("[NIH DEBUG] numeric_id:", numeric_id)
        print("[NIH DEBUG] primary_detail:", primary_detail)
        print("[NIH DEBUG] detail_url:", detail_url)
        print("[NIH DEBUG] proj_num_candidate:", proj_num_candidate)
        print("[NIH DEBUG] internal_id:", internal_id)
        print("[NIH DEBUG] grant_link:", grant_link)

    return source_id, grant_link, numeric_id, detail_url, proj_num_candidate, internal_id, proj_num, sub_proj

# Usage example (inside your per-project loop):
# source_id, grant_link, numeric_id, detail_url, proj_num_candidate, internal_id = build_source_and_link(proj, title, keyword, debug)

def fetch_nih_reporter(
    keyword: str,
    lookback_days: int,
    domain: str,
    limit: int = 10,
    summary_mode: str = "truncate",
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
    seen_ids = set()
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

        # REPLACE the old block with this single call (keeps variables used later) URL PULL
        source_id, grant_link, numeric_id, detail_url, proj_num_candidate, internal_id, proj_num, sub_proj = build_source_and_link(
            proj, title=title, keyword=keyword, debug=debug
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

        # --- abstract_display according to summary_mode
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
                    abstract_display = _simple_sentence_summary(abstract, max_sentences=summary_sentences)
                    if not abstract_display:
                        abstract_display = _truncate_text(abstract, truncate_chars)
            elif summary_mode == "sentences":
                abstract_display = _simple_sentence_summary(abstract, max_sentences=summary_sentences)
            else:
                abstract_display = _truncate_text(abstract, truncate_chars)

        # --- funder/source
        funder_name = _extract_funder_from_proj(proj, debug=debug)
        # guard: avoid returning pure numeric IDs as funder
        if isinstance(funder_name, str) and funder_name.strip().isdigit():
            funder_name = "NIH RePORTER"

        # --- PI extraction (single path)
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
        pi_raw = (pi_name or "").strip()
        if not pi_raw:
            pi_raw = "N/A"
        else:
            pi_raw = _normalize_person_name(pi_raw)

        # --- ORCID detection
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
                        found_orcid = False
                        for entry in val:
                            if isinstance(entry, dict):
                                if str(entry.get("type", "")).upper() == "ORCID":
                                    cand = _orcid_normalize(str(entry.get("value") or entry.get("id") or ""))
                                    if cand and _orcid_checksum_is_valid(cand):
                                        orcid_url = f"https://orcid.org/{cand}"
                                        found_orcid = True
                                        break
                                else:
                                    for s in _find_strings(entry):
                                        cand = _orcid_normalize(s)
                                        if cand and _orcid_checksum_is_valid(cand):
                                            orcid_url = f"https://orcid.org/{cand}"
                                            found_orcid = True
                                            break
                            elif isinstance(entry, str):
                                cand = _orcid_normalize(entry)
                                if cand and _orcid_checksum_is_valid(cand):
                                    orcid_url = f"https://orcid.org/{cand}"
                                    found_orcid = True
                                    break
                        if found_orcid:
                            break
        if not orcid_url:
            dump = json.dumps(proj) if isinstance(proj, dict) else str(proj)
            m = _orcid_normalize(dump)
            if m and _orcid_checksum_is_valid(m):
                orcid_url = f"https://orcid.org/{m}"

        pi_display = _make_clickable_pi(pi_raw, orcid_url)

        # --- affiliation (single extraction)
        aff_node = (
            proj.get("org") or proj.get("affiliation") or proj.get("organization") or proj.get("org_info") or proj.get("org_name") or {}
        )
        aff_info = _format_nih_affiliation(aff_node if isinstance(aff_node, dict) else {}, title_case=True)
        affiliation = aff_info["affiliation"] or "N/A"

        # --- amount (single)
        amount_val = proj.get("awardAmount") or proj.get("award_amount") or proj.get("award") or proj.get("total_cost") or None
        amount = "N/A"
        if amount_val is not None:
            try:
                num = float(amount_val)
                amount = f"${int(num):,}" if num.is_integer() else f"${num:,.2f}"
            except Exception:
                amount = str(amount_val)

        # --- duration (single)
        raw_start = proj.get("projectStartDate") or proj.get("project_start_date") or proj.get("startDate") or proj.get("start") or ""
        raw_end = proj.get("projectEndDate") or proj.get("project_end_date") or proj.get("endDate") or proj.get("end") or ""
        start_date = _date_only(raw_start)
        end_date = _date_only(raw_end)
        if start_date and end_date:
            duration = f"{start_date} to {end_date}"
        else:
            # if RePORTER sometimes returns a single-year int, turn it into a string
            duration = proj.get("projectPeriodText") or proj.get("fiscal_year") or proj.get("fy") or proj.get("year") or proj.get("projectYear") or "N/A"
            duration = str(duration)

        # --- build robust grant_link (single, canonical)
        detail_url = proj.get("projectUrl") or proj.get("project_url") or proj.get("url") or proj.get("link") or ""
        detail_url = str(detail_url).strip() if detail_url else ""
        # Prefer an explicit detail URL when available (canonical), otherwise
        # build a precise project-number candidate. If proj_num looks like a
        # parent (no '-NN' suffix) but a sub-project id is present, append it
        # so we construct the specific subproject identifier RePORTER recognizes.
        proj_num_candidate = None

        if not proj_num_candidate and proj_num:
            proj_num = str(proj_num).strip()
            # If proj_num already looks like a full reporter number (contains '-'),
            # use it as-is.
            if "-" in proj_num:
                proj_num_candidate = proj_num
            else:
                # If a sub-project identifier exists, append it as a suffix.
                # Common reporter format: <projectBase>-<suffix> e.g. 2S06GM008159-13
                if sub_proj:
                    proj_num_candidate = f"{proj_num}-{sub_proj}"
                else:
                    proj_num_candidate = proj_num
        
        # prefer a non-root reporter detail URL (but strip fragment/query)
        grant_link = None
        if detail_url:
            try:
                parsed = urllib.parse.urlparse(detail_url)
                if ("reporter.nih.gov" in (parsed.netloc or "")) and parsed.path and parsed.path.strip() not in ("/", ""):
                    # canonicalize to remove fragment/query
                    grant_link = urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, "", "", ""))
            except Exception:
                grant_link = None

        if not grant_link:
            if proj_num_candidate and _looks_like_reporter_projnum(proj_num_candidate):
                grant_link = f"https://reporter.nih.gov/project-details/{urllib.parse.quote(proj_num_candidate)}"
            else:
                search_term = proj_num_candidate or title or keyword
                grant_link = f"https://reporter.nih.gov/search/results?query={urllib.parse.quote(search_term)}"

        if debug:
            print("[nih debug] title:", title)
            print("[nih debug] source_id:", source_id, "proj_num:", proj_num, "internal_id:", internal_id)
            print("[nih debug] link chosen:", grant_link)

        # REPLACE the existing results_out.append({...}) inside fetch_nih_reporter's per-project loop
        # (i.e. the block near the end of the for proj in candidates[:limit]: loop)
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
            "source": funder_name,
            "source_id": source_id,
            "keyword": keyword,
            "domain": domain,
            # Visible link used in the digest/UI
            "link": grant_link,
            # NEW: preserve RePORTER-provided canonical fields so merges can prefer them
            "reporter_project_detail_url": detail_url or "",  # populated from project_detail_url / projectUrl etc.
            "reporter_numeric_id": numeric_id or "",          # populated from projectDetailId / appl_id / url-extraction
        })
    return results_out

# Backwards-compatible alias expected by older code
fetch = fetch_nih_reporter
