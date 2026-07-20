import csv
import os
import xml.etree.ElementTree as ET
import requests
from config import BASIC_SEARCH_KEYWORDS, DOCS_DIR, OUTPUT_DIR

# Endpoint syntax per Europe PMC GRIST API documentation:
# https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query=kw:<keyword>
GRIST_BASE_URL = "https://www.ebi.ac.uk/europepmc/GristAPI/rest/get/query="


def extract_grist_data(keywords, limit_per_kw=5):
    """Fetches exact grant metadata directly from Europe PMC GRIST API (XML)."""
    records = []
    seen_ids = set()

    for kw in keywords:
        # Construct GRIST search query with keyword tag
        url = f"{GRIST_BASE_URL}kw:{kw}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Failed HTTP {response.status_code} for query: {kw}")
                continue

            # Parse XML response
            root = ET.fromstring(response.content)

            # GRIST records are nested under <Record> or <Grant> tags
            grants = root.findall(".//Record") or root.findall(".//Grant")

            count = 0
            for grant in grants:
                # Extract exact string values from XML nodes
                grant_id = getattr(grant.find("Id"), "text", "N/A")
                title = getattr(grant.find("Title"), "text", "Untitled")
                funder = getattr(
                    grant.find("GrantedAuthority"), "text", "Unknown"
                )
                abstract = getattr(grant.find("Abstract"), "text", "")

                # Skip duplicates
                key = grant_id if grant_id != "N/A" else title
                if key in seen_ids:
                    continue

                seen_ids.add(key)
                records.append(
                    {
                        "Keyword": kw,
                        "Grant ID": grant_id,
                        "Title": title,
                        "Funder": funder,
                        "Abstract": abstract[
                            :200
                        ]
                        + "..."  # Truncated for table formatting
                        if abstract
                        else "N/A",
                    }
                )

                count += 1
                if count >= limit_per_kw:
                    break

        except ET.ParseError:
            print(f"Could not parse XML payload for term: '{kw}'")
        except Exception as e:
            print(f"Error requesting GRIST API for '{kw}': {e}")

    return records


def export_to_csv(data, filename="grants_digest.csv"):
    """Saves exact retrieved data to CSV file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)

    if not data:
        print("No records found to export.")
        return

    fieldnames = ["Grant ID", "Title", "Funder", "Keyword", "Abstract"]
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"Saved {len(data)} raw records to: {filepath}")


if __name__ == "__main__":
    print(
        f"Pulling raw grant data across {len(BASIC_SEARCH_KEYWORDS)} keywords..."
    )
    grant_records = extract_grist_data(BASIC_SEARCH_KEYWORDS, limit_per_kw=3)

    if grant_records:
        # Display extracted facts directly as a table
        print("\n### Extracted GRIST API Grant Records\n")
        print("| Grant ID | Title | Funder | Matched Keyword |")
        print("| --- | --- | --- | --- |")
        for rec in grant_records:
            print(
                f"| {rec['Grant ID']} | {rec['Title'][:50]}... | {rec['Funder']} | {rec['Keyword']} |"
            )

        export_to_csv(grant_records)
    else:
        print("0 records returned.")
