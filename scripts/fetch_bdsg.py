"""
Download and parse the Bundesdatenschutzgesetz (BDSG) - Germany's Federal
Data Protection Act, which supplements the EU GDPR domestically - from the
official government law portal gesetze-im-internet.de, and write it out as
a single structured JSON file that the app's retrieval layer can search
over.

Source: https://www.gesetze-im-internet.de/bdsg_2018/

NOTE: the EU GDPR itself (Datenschutz-Grundverordnung) is an EU regulation
published on EUR-Lex, not on gesetze-im-internet.de, and is not covered by
this script. The BDSG is Germany's national implementing/supplementing
law and uses the exact same XML export schema as every other law on this
portal, so it reuses the same parsing approach as scripts/fetch_betrvg.py
- see that file's module docstring for details on the parser's defensive
design.

Run:
    python scripts/fetch_bdsg.py
Output:
    data/bdsg.json
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_betrvg import download_zip, extract_xml_bytes, parse_norms  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402
import requests  # noqa: E402

LAW_SLUG = "bdsg_2018"
SOURCE_URL = f"https://www.gesetze-im-internet.de/{LAW_SLUG}/xml.zip"
SOURCE_PAGE = f"https://www.gesetze-im-internet.de/{LAW_SLUG}/"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "bdsg.json"


def main() -> int:
    print(f"Downloading {SOURCE_URL} ...")
    try:
        zip_bytes = download_zip(SOURCE_URL)
    except requests.RequestException as exc:
        print(
            f"ERROR: could not download the law from gesetze-im-internet.de.\n"
            f"  {exc}\n"
            f"Check your internet connection, and that the URL is still valid:\n"
            f"  {SOURCE_URL}\n"
            f"(If the URL has changed, browse {SOURCE_PAGE} by hand and look "
            f"for the current XML/zip download link.)",
            file=sys.stderr,
        )
        return 1

    try:
        xml_bytes = extract_xml_bytes(zip_bytes)
        sections = parse_norms(xml_bytes, default_abbreviation="BDSG")
    except (zipfile.BadZipFile, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # parse_norms() (imported from fetch_betrvg) stamps each section's
    # source_url from that module's own SOURCE_PAGE constant, and its
    # law_abbreviation from the XML's own <jurabk> metadata (which for this
    # law is "BDSG 2018", not "BDSG") - fix both up here so every section
    # matches app.config.LAW_REGISTRY's "BDSG" abbreviation exactly. That
    # exact match matters: app/retrieval.py disambiguates sections by
    # (law_abbreviation, section) pairs, and the frontend groups cited
    # sections by this same field.
    for s in sections:
        s["source_url"] = SOURCE_PAGE
        s["law_abbreviation"] = "BDSG"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "law": "Bundesdatenschutzgesetz (BDSG)",
        "law_english": "Federal Data Protection Act (supplements the EU GDPR in Germany)",
        "source": SOURCE_PAGE,
        "section_count": len(sections),
        "sections": sections,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {len(sections)} sections to {OUTPUT_PATH}")
    print("Spot-check a few entries:")
    for s in sections[:3]:
        preview = s["text_de"][:120].replace("\n", " ")
        print(f"  {s['section']} - {s['title_de']!r} :: {preview}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
