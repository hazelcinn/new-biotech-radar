import urllib.parse
import requests
import re
import json

# ORCID helpers and validators
_ORCID_HYPHEN_RE = re.compile(r'(\d{4}-\d{4}-\d{4}-[\dXx]{4})')
_ORCID_URL_RE = re.compile(r'https?://orcid\.org/(\d{4}-\d{4}-\d{4}-[\dXx]{4})', re.I)
_ORCID_DIGITS_RE = re.compile(r'(\d{16})')
_ORCID_HTML_RE = re.compile(r'https?://orcid\.org/(\d{4}-\d{4}-\d{4}-[\dXx]{4})', re.I)
_ORCID_META_RE = re.compile(r'ORCID[:\s]*([0-9Xx\-\s]{12,})', re.I)

def _orcid_normalize(candidate: str) -> str | None:
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
    m3 = _ORCID_DIGITS_RE.search(digits)
    if m3:
        d = m3.group(1)
        return f"{d[0:4]}-{d[4:8]}-{d[8:12]}-{d[12:16]}"
    return None

def _orcid_checksum_is_valid(orcid_hyphenated: str) -> bool:
    """ISO 7064 mod 11-2 validation for ORCID (hyphenated or not)."""
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

def _find_strings(obj):
    """Yield string leaf values from nested dict/list/tuple structures."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _find_strings(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _find_strings(v)

def _extract_orcid_from_html(html_text: str, debug=False) -> str:
    """Return the hyphenated ORCID (no URL prefix) if found and valid, else ''."""
    if not html_text:
        return ""
    # 1) explicit orcid.org URL
    m = _ORCID_HTML_RE.search(html_text)
    if m and _orcid_checksum_is_valid(m.group(1)):
        return m.group(1)
    # 2) meta tags
    meta_matches = re.findall(
        r'<meta[^>]+(?:name|property|itemprop)=["\']?([^"\'>]+)["\']?[^>]+content=["\']?([^"\'>]+)["\']?[^>]*>',
        html_text, flags=re.I
    )
    for name, content in meta_matches:
        if 'orcid' in name.lower() or 'orcid' in content.lower():
            norm = _orcid_normalize(content)
            if norm and _orcid_checksum_is_valid(norm):
                return norm
    # 3) JSON-LD blocks
    for script in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_text, flags=re.I|re.S):
        try:
            data = json.loads(script)
        except Exception:
            continue
        for leaf in _find_strings(data):
            norm = _orcid_normalize(leaf)
            if norm and _orcid_checksum_is_valid(norm):
                return norm
    # 4) ORCID-labelled text
    for m in re.finditer(r'ORCID(?:\s*iD)?[:\s]*([0-9Xx\-\s]{12,})', html_text, flags=re.I):
        norm = _orcid_normalize(m.group(1))
        if norm and _orcid_checksum_is_valid(norm):
            return norm
        if debug:
            print("[orcid-debug] found candidate but rejected:", m.group(1))
    # 5) fallback: hyphenated candidate anywhere (strict checksum)
    for m in _ORCID_HYPHEN_RE.finditer(html_text):
        cand = m.group(1)
        if _orcid_checksum_is_valid(cand):
            return cand
        if debug:
            print("[orcid-debug] hyphenated candidate rejected:", cand)
    return ""

def _get_orcid_url(person_data, fetch_fallback=False, grant_page_url=None, headers=None, debug=False) -> str:
    """
    Robust ORCID extractor. Returns canonical https://orcid.org/{id} or empty string.
    If fetch_fallback=True and not present in person_data, will fetch grant_page_url and scan HTML.
    """
    if isinstance(person_data, dict):
        # top-level keys
        for key in ("orcid", "orcidId", "Orcid", "ORCID", "orcid-id", "orcid_id"):
            val = person_data.get(key)
            if val:
                norm = _orcid_normalize(str(val))
                if norm and _orcid_checksum_is_valid(norm):
                    return f"https://orcid.org/{norm}"
                if debug:
                    print("[orcid-debug] top-level candidate rejected:", val)
        # authorId structures
        if "authorId" in person_data:
            aid = person_data["authorId"]
            if isinstance(aid, dict) and str(aid.get("type", "")).upper() == "ORCID":
                cand = aid.get("value") or aid.get("id") or ""
                norm = _orcid_normalize(str(cand))
                if norm and _orcid_checksum_is_valid(norm):
                    return f"https://orcid.org/{norm}"
                if debug:
                    print("[orcid-debug] authorId candidate rejected:", cand)
            elif isinstance(aid, str):
                norm = _orcid_normalize(aid)
                if norm and _orcid_checksum_is_valid(norm):
                    return f"https://orcid.org/{norm}"
                if debug:
                    print("[orcid-debug] authorId-string candidate rejected:", aid)
    # search nested values
    for s in _find_strings(person_data):
        norm = _orcid_normalize(s)
        if norm and _orcid_checksum_is_valid(norm):
            return f"https://orcid.org/{norm}"
        if debug and norm:
            print("[orcid-debug] nested candidate rejected:", s)
    # optional fetch fallback
    if fetch_fallback and grant_page_url:
        try:
            resp = requests.get(grant_page_url, headers=headers or {}, timeout=8)
            if resp.status_code == 200:
                found = _extract_orcid_from_html(resp.text, debug=debug)
                if found:
                    return f"https://orcid.org/{found}"
        except Exception as e:
            if debug:
                print("[orcid-debug] failed to fetch grant page for ORCID:", e)
    return ""

def _make_clickable_pi(pi_name: str, orcid_url: str) -> str:
    if not orcid_url:
        return pi_name
    return f'<a href="{orcid_url}" target="_blank" rel="noopener noreferrer">{pi_name}</a>'

# Cleaning helpers
def _clean_abstract(abstract_node) -> str:
    if not abstract_node:
        return ""
    if isinstance(abstract_node, list):
        parts = []
        for item in abstract_node:
            if isinstance(item, dict):
                val = item.get("value") or item.get("content") or item.get("text") or ""
                if val:
                    parts.append(str(val))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts).strip()
    if isinstance(abstract_node, dict):
        return str(
            abstract_node.get("value")
            or abstract_node.get("content")
            or abstract_node.get("text")
            or ""
        ).strip()
    return str(abstract_node).strip()

def _clean_affiliation(aff_node) -> str:
    if not aff_node:
        return ""
    if isinstance(aff_node, list):
        names = []
        for item in aff_node:
            cleaned = _clean_affiliation(item)
            if cleaned and cleaned != "N/A" and cleaned not in names:
                names.append(cleaned)
        return "; ".join(names).strip()
    if isinstance(aff_node, dict):
        # try likely keys, fall back to searching nested values for meaningful text
        for key in ("name", "Name", "institutionName", "institution", "title", "Title", "value", "text"):
            val = aff_node.get(key)
            if val and not isinstance(val, (dict, list)):
                return str(val).strip()
            if val and isinstance(val, (dict, list)):
                # recurse into nested structure
                nested = _clean_affiliation(val)
                if nested:
                    return nested
        # if still nothing, try concatenating string leaves
        leaves = [s for s in _find_strings(aff_node)]
        if leaves:
            return "; ".join({l.strip() for l in leaves if l and l.strip() != "N/A"})
        return ""
    return str(aff_node).strip()

def _clean_amount(amount_node, currency: str = "") -> str:
    if amount_node is None:
        return "N/A"
    if isinstance(amount_node, list):
        for item in amount_node:
            cleaned = _clean_amount(item, currency)
            if cleaned != "N/A":
                return cleaned
        return "N/A"
    raw_val = None
    extracted_curr = currency
    if isinstance(amount_node, dict):
        extracted_curr = (
            amount_node.get("currency")
            or amount_node.get("currencyCode")
            or amount_node.get("Currency")
            or currency
        )
        raw_val = (
            amount_node.get("value")
            or amount_node.get("amount")
            or amount_node.get("content")
            or amount_node.get("text")
            or amount_node.get("#text")
            or amount_node.get("formattedAmount")
            or amount_node.get("total")
        )
    else:
        raw_val = amount_node
    if raw_val is None or str(raw_val).strip().upper() in ("", "N/A", "NONE", "NULL"):
        return "N/A"
    raw_str = str(raw_val).strip()
    try:
        num_val = float(raw_str.replace(",", ""))
        if num_val.is_integer():
            raw_str = f"{int(num_val):,}"
        else:
            raw_str = f"{num_val:,.2f}"
    except (ValueError, TypeError):
        pass
    curr_symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
    curr_str = str(extracted_curr).strip()
    curr_display = curr_symbols.get(curr_str.upper(), curr_str)
    if curr_display and not any(symbol in raw_str for symbol in ["£", "$", "€", "EUR", "USD", "GBP"]):
        return f"{curr_display} {raw_str}".strip()
    return raw_str

def _extract_pi_info(item: dict, grant_data: dict) -> tuple[str, dict]:
    person_node = (
        item.get("person")
        or item.get("Person")
        or grant_data.get("person")
        or grant_data.get("Person")
        or item.get("investigator")
        or grant_data.get("investigator")
        or {}
    )
    person = {}
    if isinstance(person_node, list) and len(person_node) > 0:
        person = person_node[0] if isinstance(person_node[0], dict) else {}
    elif isinstance(person_node, dict):
        person = person_node
    given_name = (
        person.get("givenName")
        or person.get("GivenName")
        or person.get("firstName")
        or person.get("FirstName")
        or ""
    )
    family_name = (
        person.get("familyName")
        or person.get("FamilyName")
        or person.get("lastName")
        or person.get("LastName")
        or person.get("surname")
        or person.get("Surname")
        or ""
    )
    pi_name = f"{given_name} {family_name}".strip()
    if not pi_name and isinstance(person, dict):
        pi_name = person.get("fullName") or person.get("name") or person.get("Name") or ""
    pi_raw = str(pi_name).strip() if pi_name else "N/A"
    return pi_raw, person

def fetch_grants(keyword: str, lookback_days: int, domain: str) -> list:
    """Fetch grants from Europe PMC GRIST API (top 10)."""
    raw_items = []
    base_url = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantHarvesterBot/1.0",
        "Accept": "application/json"
    }
    clean_kw = keyword.strip()
    encoded_query = urllib.parse.quote(clean_kw)
    url = f"{base_url}{encoded_query}&format=json&resultType=core"
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return raw_items
        data = response.json()
        record_list = data.get("RecordList", {}) if isinstance(data, dict) else {}
        records = (
            record_list.get("Record", [])
            or record_list.get("grant", [])
            or data.get("Record", [])
        )
        if isinstance(records, dict):
            records = [records]
        for item in records[:10]:
            grant_data = item.get("grant", item.get("Grant", item))
            grant_id = grant_data.get("id") or grant_data.get("Id") or grant_data.get("grantId") or "N/A"
            title = grant_data.get("title") or grant_data.get("Title") or "Untitled Grant Project"
            abstract_raw = (
                grant_data.get("abstractText")
                or grant_data.get("abstract")
                or grant_data.get("ab")
                or grant_data.get("abstr")
                or grant_data.get("Ab")
                or grant_data.get("Abstr")
                or grant_data.get("Abstract")
                or grant_data.get("projectSummary")
                or grant_data.get("description")
                or item.get("abstractText")
                or item.get("abstract")
                or item.get("abs")
                or item.get("abstr")
                or item.get("description")
                or "No abstract description provided."
            )
            abstract = _clean_abstract(abstract_raw) or "No abstract description provided."
            funder_dict = grant_data.get("funder", grant_data.get("Funder", {}))
            if isinstance(funder_dict, dict):
                funder = funder_dict.get("name") or funder_dict.get("Name") or grant_data.get("grantedAuthority") or "Europe PMC / GRIST"
            else:
                funder = str(funder_dict)
            # PI info
            pi_raw, person = _extract_pi_info(item, grant_data)
            # Affiliation
            aff_raw = (
                person.get("affiliation")
                or person.get("Affiliation")
                or person.get("institution")
                or person.get("Institution")
                or grant_data.get("institution")
                or grant_data.get("Institution")
                or grant_data.get("affiliation")
                or grant_data.get("Affiliation")
                or grant_data.get("grantee")
                or item.get("institution")
                or item.get("Institution")
            )
            aff = _clean_affiliation(aff_raw) or "N/A"
            # Amount and currency
            amount_node = (
                grant_data.get("amount")
                or grant_data.get("awardAmount")
                or grant_data.get("AwardAmount")
                or grant_data.get("grantAmount")
                or grant_data.get("totalAwardAmount")
                or grant_data.get("fundAmount")
                or grant_data.get("Amount")
                or item.get("amount")
                or item.get("Amount")
                or item.get("awardAmount")
            )
            currency = (
                grant_data.get("currency")
                or grant_data.get("Currency")
                or item.get("currency")
                or ""
            )
            amount = _clean_amount(amount_node, currency)
            # Duration
            start_date = grant_data.get("startDate") or grant_data.get("StartDate") or grant_data.get("from") or ""
            end_date = grant_data.get("endDate") or grant_data.get("EndDate") or grant_data.get("to") or ""
            if start_date and end_date:
                duration = f"{start_date} to {end_date}"
            else:
                duration = grant_data.get("activeDate") or grant_data.get("date") or grant_data.get("duration") or grant_data.get("Duration") or grant_data.get("period") or "N/A"
            # Link
            grant_doi = grant_data.get("doi") or grant_data.get("Doi")
            if grant_doi:
                grant_link = f"https://doi.org/{grant_doi}"
            elif grant_id != "N/A":
                grant_link = f"https://europepmc.org/grantfinder/grantdetails?query=gid%3A%22{urllib.parse.quote(str(grant_id))}%22"
            else:
                grant_link = "https://europepmc.org/grantfinder"
            # ORCID extraction with fallback to page scraping
            orcid_url = _get_orcid_url(person, fetch_fallback=True, grant_page_url=grant_link, headers=headers, debug=False)
            pi_display = _make_clickable_pi(pi_raw, orcid_url)
            pi_md = f"[{pi_raw}]({orcid_url})" if orcid_url else pi_raw
            raw_items.append({
                "title": title,
                "project contact": pi_display,
                "project_contact_name": pi_raw,
                "project_contact_orcid": orcid_url,
                "project_contact_html": pi_display,
                "project_contact_md": pi_md,
                "affiliation": aff,
                "grant amount": amount,
                "grant duration": duration,
                "abstract": abstract,
                "source": funder,
                "keyword": keyword,
                "domain": domain,
                "link": grant_link
            })
    except Exception as e:
        print(f"[europepmc] Connection error during GRIST grant fetch for '{keyword}': {e}")
    return raw_items
