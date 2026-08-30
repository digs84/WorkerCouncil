"""
Download and parse the Betriebsverfassungsgesetz (BetrVG) - the German law
that governs works/worker councils (Betriebsrat) - from the official
government law portal gesetze-im-internet.de, and write it out as a single
structured JSON file that the app's retrieval layer can search over.

Source: https://www.gesetze-im-internet.de/betrvg/
Download pattern used by this law portal for every law it publishes:
    https://www.gesetze-im-internet.de/<slug>/xml.zip
(This is the same pattern used by the community-maintained
https://github.com/bundestag/gesetze mirror, which re-downloads every German
federal law this same way.)

NOTE: gesetze-im-internet.de's own XML schema is a bit idiosyncratic (it
mixes legal metadata tags with embedded HTML-like markup for the running
text). This parser is written defensively: it does NOT hard-fail if a tag
it expects is missing, it recovers from minor malformed XML, and it falls
back to plain text-extraction (itertext) so that even if the exact tag
names drift over time, you still get usable section text out the other
end. If a future site redesign breaks this badly, the error message below
tells you exactly what to check.

Run:
    python scripts/fetch_betrvg.py
Output:
    data/betrvg.json
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import requests
from lxml import etree

LAW_SLUG = "betrvg"
SOURCE_URL = f"https://www.gesetze-im-internet.de/{LAW_SLUG}/xml.zip"
SOURCE_PAGE = f"https://www.gesetze-im-internet.de/{LAW_SLUG}/"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "betrvg.json"

HEADERS = {
    # A descriptive UA is good etiquette when hitting a small government
    # server; it identifies the traffic without pretending to be a browser.
    "User-Agent": "worker-council-app/1.0 (educational, non-commercial; "
                  "fetches public law text from gesetze-im-internet.de)"
}


def download_zip(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content


def extract_xml_bytes(zip_bytes: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_names:
            raise RuntimeError(
                f"No .xml file found inside the downloaded zip. "
                f"Contents were: {zf.namelist()}"
            )
        # BetrVG is a single-law zip, so there should be exactly one XML file.
        return zf.read(xml_names[0])


def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def text_of(el) -> str:
    """Join all descendant text nodes of an lxml element into one string."""
    if el is None:
        return ""
    return clean_text("".join(el.itertext()))


def parse_norms(xml_bytes: bytes, default_abbreviation: str = "BetrVG") -> list[dict]:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(xml_bytes, parser=parser)
    if root is None:
        raise RuntimeError(
            "lxml could not parse the downloaded XML at all, even in "
            "recovery mode. The file may be empty or the site may have "
            "returned an HTML error page instead of the zip."
        )

    norm_elements = root.findall(".//norm")
    if not norm_elements:
        # Schema drift fallback: try any element literally named 'norm'
        # anywhere, case-insensitively, via a broader XPath.
        norm_elements = root.xpath(
            "//*[translate(local-name(), 'NORM', 'norm')='norm']"
        )
    if not norm_elements:
        raise RuntimeError(
            "Could not find any <norm> elements in the parsed XML. "
            "gesetze-im-internet.de may have changed its export schema - "
            "open the extracted XML by hand and check the top-level tag "
            "structure, then adjust parse_norms() accordingly."
        )

    sections = []
    order = 0
    for norm in norm_elements:
        meta = norm.find(".//metadaten")
        jurabk = text_of(meta.find("jurabk")) if meta is not None else ""
        enbez = text_of(meta.find("enbez")) if meta is not None else ""
        titel = text_of(meta.find("titel")) if meta is not None else ""

        # Skip the law's own front-matter norm (title page / table of
        # contents entry), which has no "§" section designation.
        if not enbez or not enbez.strip().startswith("§"):
            continue

        textdaten = norm.find(".//textdaten")
        body_text = text_of(textdaten) if textdaten is not None else text_of(norm)

        # Remove the title text if it also leaked into the body join.
        if titel and body_text.startswith(titel):
            body_text = body_text[len(titel):].strip()

        order += 1
        sections.append(
            {
                "order": order,
                "section": enbez,          # e.g. "§ 1"
                "title_de": titel,         # German section heading
                "text_de": body_text,      # German section full text
                "law_abbreviation": jurabk or default_abbreviation,
                "source_url": SOURCE_PAGE,
            }
        )

    if not sections:
        raise RuntimeError(
            "Parsed the XML but extracted zero usable '§' sections. "
            "This usually means the <enbez>/<titel>/<textdaten> tag names "
            "have changed on the source site - inspect the raw XML and "
            "update parse_norms()."
        )

    return sections


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
        sections = parse_norms(xml_bytes)
    except (zipfile.BadZipFile, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "law": "Betriebsverfassungsgesetz (BetrVG)",
        "law_english": "Works Constitution Act (governs German worker/works councils)",
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
