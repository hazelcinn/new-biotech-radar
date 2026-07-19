"""
Europe PMC Grist API — grant records from the Europe PMC Funders' Group
(mostly UK/EU medical research charities and councils: Wellcome Trust,
Cancer Research UK, MRC, BBSRC, NIHR, and others — a different funder set
than NIH RePORTER/NSF, so this is complementary, not overlapping).

Docs: https://europepmc.org/GristAPI
No API key required.

*** FIELD NAMES NOT FULLY VERIFIED ***
Europe PMC's field-reference page (GristAPI/dataFields) blocks automated
access, so the field names below (grantId, agencyName, etc.) are inferred
from the query-syntax docs, not confirmed against a live JSON response.
DEBUG_PRINT_RAW is on below — run this once locally, check the printed
raw JSON against what the parser extracts, and adjust the .get() keys in
_parse_record() if anything comes back empty that shouldn't.
"""
import requests
from urllib.parse import quote
from datetime import date, timedelta
from schema import make_item

BASE = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get"

# Set to True to print the first raw record's full JSON to the console,
# so you can check the parser below is reading the right keys. Turn off
# once confirmed, to keep logs clean.
DEBUG_PRINT_RAW = True


def _parse_record(r: dict, domain_hint: str) -> dict:
    grant_id = r.get("grantId") or r.get("gid") or ""
    title = r.get("title") or r.get("ti") or ""
    abstract = r.get("abstractText") or r.get("abstract") or ""
    agency = r.get("agencyName") or r.get("ga") or r.get("grantAgency") or ""
    institution = r.get("institution") or r.get("aff") or r.get("department") or ""
    start_date = r.get("startDate") or r.get("date") or ""

    return make_item(
        source=f"Europe PMC Grist ({agency})" if agency else "Europe PMC Grist",
        item_type="grant",
        title=title,
        url=f"https://europepmc.org/grantfinder?query=gid:{grant_id}" if grant_id else "",
        date=start_date,
        institution=institution,
        raw_text=abstract,
        domain_hint=domain_hint,
    )


def fetch(keyword: str, lookback_days: int, domain_hint: str = ""):
    # Search grant abstracts specifically, per the "abs:" field syntax.
    # Restricting to epmc_funders:yes keeps this to the actual Europe PMC
    # Funders' Group (see https://europepmc.org/Funders) rather than every
    # grant record Europe PMC has ever indexed.
    query = f'abs:"{keyword}" epmc_funders:yes'
    encoded_query = quote(query)

    # This API's URL syntax embeds the query directly after "query=" in the
    # path, with subsequent parameters joined by "&" but with NO leading
    # "?" — non-standard, so building the URL manually rather than via
    # requests' params= (which would add a "?" and break this API's format).
    url = f"{BASE}/query={encoded_query}&format=json&resultType=core"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[europepmc_grants] request failed for '{keyword}': {e}")
        return []
    except ValueError as e:
        print(f"[europepmc_grants] response wasn't valid JSON for '{keyword}': {e}")
        return []

    results = data.get("resultList", {}).get("result", [])

    if DEBUG_PRINT_RAW and results:
        print(f"[europepmc_grants] RAW FIRST RECORD for '{keyword}':")
        print(results[0])

    cutoff = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    items = []
    for r in results:
        item = _parse_record(r, domain_hint)
        # Filter locally by date since this API's date filtering syntax
        # (active_date) matches grants ACTIVE during a period, not grants
        # ADDED during a period — not the same thing we want for "what's new."
        if item["date"] and item["date"] < cutoff:
            continue
        items.append(item)

    print(f"[europepmc_grants] Found {len(items)} grants for '{keyword}' "
          f"(of {len(results)} returned before date filtering)")
    return items
