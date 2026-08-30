// Netlify build-time script: downloads + parses every law in LAWS from
// gesetze-im-internet.de, then bakes the merged result directly into the
// deployed edge functions (Netlify Edge Functions have no bundled-file or
// JSON-import support and no writable/shared disk at runtime, so the data
// has to be embedded as a JS literal at build time instead of read from
// disk like the Python/FastAPI version does).
//
// This is a JS port of scripts/fetch_betrvg.py + scripts/fetch_bdsg.py's
// defensive XML parsing (find <norm> elements, pull jurabk/enbez/titel/
// textdaten, flatten all descendant text like lxml's itertext()) using
// @xmldom/xmldom instead of lxml, since this runs in Node during the
// Netlify build rather than in Python.
//
// Run: node scripts/fetch-laws.mjs

import { writeFile, readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import AdmZip from "adm-zip";
import { DOMParser } from "@xmldom/xmldom";

const REPO_ROOT = path.resolve(import.meta.dirname, "..");

const LAWS = [
  {
    slug: "betrvg",
    defaultAbbreviation: "BetrVG",
    lawName: "Betriebsverfassungsgesetz (BetrVG)",
    lawEnglish: "Works Constitution Act (governs German worker/works councils)",
    dataFile: "betrvg.json",
  },
  {
    slug: "bdsg_2018",
    defaultAbbreviation: "BDSG",
    lawName: "Bundesdatenschutzgesetz (BDSG)",
    lawEnglish: "Federal Data Protection Act (supplements the EU GDPR in Germany)",
    dataFile: "bdsg.json",
  },
];

const HEADERS = {
  "User-Agent":
    "worker-council-app/1.0 (educational, non-commercial; fetches public law text from gesetze-im-internet.de)",
};

function cleanText(s) {
  return (s || "").replace(/\s+/g, " ").trim();
}

// Recursively concatenate all descendant TEXT_NODE values - equivalent to
// lxml's `"".join(el.itertext())`.
function textOf(node) {
  if (!node) return "";
  let out = "";
  const walk = (n) => {
    if (n.nodeType === 3 /* TEXT_NODE */) {
      out += n.nodeValue;
    } else if (n.childNodes) {
      for (let i = 0; i < n.childNodes.length; i++) walk(n.childNodes[i]);
    }
  };
  walk(node);
  return cleanText(out);
}

function localName(node) {
  if (!node.tagName) return "";
  const parts = node.tagName.split(":");
  return parts[parts.length - 1].toLowerCase();
}

// Depth-first collection of every descendant element whose local name
// (namespace prefix stripped, case-insensitive) matches `name`.
function findAllByTagName(root, name) {
  const results = [];
  const walk = (n) => {
    if (n.nodeType === 1 /* ELEMENT_NODE */ && localName(n) === name) {
      results.push(n);
    }
    if (n.childNodes) {
      for (let i = 0; i < n.childNodes.length; i++) walk(n.childNodes[i]);
    }
  };
  walk(root);
  return results;
}

function findFirstByTagName(root, name) {
  const matches = findAllByTagName(root, name);
  return matches.length ? matches[0] : null;
}

function parseNorms(xmlText, defaultAbbreviation) {
  const doc = new DOMParser({
    // Swallow non-fatal parser warnings/errors instead of throwing, so
    // minor XML quirks degrade gracefully like the Python parser's
    // recover=True mode.
    errorHandler: { warning: () => {}, error: () => {}, fatalError: (e) => { throw e; } },
  }).parseFromString(xmlText, "text/xml");

  const normElements = findAllByTagName(doc.documentElement, "norm");
  if (!normElements.length) {
    throw new Error(
      "Could not find any <norm> elements in the parsed XML. " +
        "gesetze-im-internet.de may have changed its export schema."
    );
  }

  const sections = [];
  let order = 0;
  for (const norm of normElements) {
    const meta = findFirstByTagName(norm, "metadaten");
    const jurabk = meta ? textOf(findFirstByTagName(meta, "jurabk")) : "";
    const enbez = meta ? textOf(findFirstByTagName(meta, "enbez")) : "";
    const titel = meta ? textOf(findFirstByTagName(meta, "titel")) : "";

    // Skip the law's own front-matter norm (title page / table of
    // contents entry), which has no "§" section designation.
    if (!enbez || !enbez.trim().startsWith("§")) continue;

    const textdaten = findFirstByTagName(norm, "textdaten");
    let bodyText = textdaten ? textOf(textdaten) : textOf(norm);

    // Remove the title text if it also leaked into the body join.
    if (titel && bodyText.startsWith(titel)) {
      bodyText = bodyText.slice(titel.length).trim();
    }

    order += 1;
    sections.push({
      order,
      section: enbez,
      title_de: titel,
      text_de: bodyText,
      law_abbreviation: jurabk || defaultAbbreviation,
    });
  }

  if (!sections.length) {
    throw new Error(
      "Parsed the XML but extracted zero usable '§' sections - the " +
        "<enbez>/<titel>/<textdaten> tag names may have changed."
    );
  }
  return sections;
}

async function fetchLaw(law) {
  const sourcePage = `https://www.gesetze-im-internet.de/${law.slug}/`;
  const zipUrl = `${sourcePage}xml.zip`;
  console.log(`Downloading ${zipUrl} ...`);

  const resp = await fetch(zipUrl, { headers: HEADERS });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} fetching ${zipUrl}`);
  }
  const buffer = Buffer.from(await resp.arrayBuffer());

  const zip = new AdmZip(buffer);
  const xmlEntry = zip.getEntries().find((e) => e.entryName.toLowerCase().endsWith(".xml"));
  if (!xmlEntry) {
    throw new Error(`No .xml file found inside ${zipUrl}`);
  }
  const xmlText = xmlEntry.getData().toString("utf-8");

  const sections = parseNorms(xmlText, law.defaultAbbreviation).map((s) => ({
    ...s,
    // Force the exact abbreviation from LAW_REGISTRY rather than trusting
    // the government XML's own <jurabk> (which for BDSG is "BDSG 2018",
    // not "BDSG") - see scripts/fetch_bdsg.py for the same fix in the
    // Python version. Section identity elsewhere depends on this being
    // an exact, stable match.
    law_abbreviation: law.defaultAbbreviation,
    source_url: sourcePage,
  }));

  console.log(`  Parsed ${sections.length} sections for ${law.defaultAbbreviation}`);
  return sections;
}

function replacePlaceholder(template, placeholder, value) {
  const quoted = `"${placeholder}"`;
  if (!template.includes(quoted)) {
    throw new Error(`Placeholder ${quoted} not found in template`);
  }
  return template.split(quoted).join(value);
}

async function main() {
  const perLawSections = {};
  const failures = [];

  for (const law of LAWS) {
    try {
      perLawSections[law.defaultAbbreviation] = await fetchLaw(law);
    } catch (err) {
      console.error(`WARNING: could not fetch/parse ${law.defaultAbbreviation}: ${err.message}`);
      failures.push(law.defaultAbbreviation);
    }
  }

  const loadedAbbreviations = Object.keys(perLawSections);
  if (loadedAbbreviations.length === 0) {
    console.error("ERROR: every configured law failed to fetch - aborting build.");
    process.exit(1);
  }
  if (failures.length) {
    console.warn(
      `Continuing with partial data - failed law(s): ${failures.join(", ")}. ` +
        "The deployed app will only answer using whichever law(s) did load."
    );
  }

  // Write data/<file>.json for each law that loaded, mirroring the Python
  // scripts' output - not read by the edge functions (which get their
  // copy baked into the generated files below), but useful for local
  // inspection/debugging and kept for parity with the Python version.
  const dataDir = path.join(REPO_ROOT, "data");
  await mkdir(dataDir, { recursive: true });
  for (const law of LAWS) {
    const sections = perLawSections[law.defaultAbbreviation];
    if (!sections) continue;
    const payload = {
      law: law.lawName,
      law_english: law.lawEnglish,
      source: `https://www.gesetze-im-internet.de/${law.slug}/`,
      section_count: sections.length,
      sections,
    };
    await writeFile(path.join(dataDir, law.dataFile), JSON.stringify(payload, null, 2), "utf-8");
    console.log(`Wrote ${sections.length} sections to data/${law.dataFile}`);
  }

  const allSections = loadedAbbreviations.flatMap((abbr) => perLawSections[abbr]);
  const sectionCounts = Object.fromEntries(
    loadedAbbreviations.map((abbr) => [abbr, perLawSections[abbr].length])
  );

  const templatesDir = path.join(REPO_ROOT, "netlify-build", "templates");
  const outDir = path.join(REPO_ROOT, "netlify", "edge-functions");
  await mkdir(outDir, { recursive: true });

  // api-chat.js: needs the full section text for every loaded law.
  {
    let out = await readFile(path.join(templatesDir, "api-chat.template.js"), "utf-8");
    out = replacePlaceholder(out, "__LAW_DATA_JSON__", JSON.stringify(allSections));
    await writeFile(path.join(outDir, "api-chat.js"), out, "utf-8");
    console.log("Generated netlify/edge-functions/api-chat.js");
  }

  // api-sources.js: only needs per-law counts, not the full text.
  {
    let out = await readFile(path.join(templatesDir, "api-sources.template.js"), "utf-8");
    out = replacePlaceholder(out, "__SECTION_COUNTS_JSON__", JSON.stringify(sectionCounts));
    await writeFile(path.join(outDir, "api-sources.js"), out, "utf-8");
    console.log("Generated netlify/edge-functions/api-sources.js");
  }

  // api-health.js: just needs to know whether any law loaded.
  {
    let out = await readFile(path.join(templatesDir, "api-health.template.js"), "utf-8");
    out = replacePlaceholder(out, "__LAW_LOADED__", String(loadedAbbreviations.length > 0));
    await writeFile(path.join(outDir, "api-health.js"), out, "utf-8");
    console.log("Generated netlify/edge-functions/api-health.js");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
