// Smoke tests for the generated netlify/edge-functions/api-chat.js, using
// Node's built-in test runner. Mocks the `Netlify` global and `fetch` so
// this runs with no real Netlify/Deno environment and no network access -
// no API keys needed. Run with: npm test (after `npm run fetch-laws`, so
// the generated file exists).
//
// These mirror app/main.py's own tests in spirit, but there's no shared
// test harness between the two runtimes (Python vs this JS port) - see
// README.md's "Part 1b" for why this port exists and how it differs.

import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

globalThis.Netlify = { env: { get: (key) => process.env[key] } };

async function importHandler() {
  const url = `file://${REPO_ROOT}/netlify/edge-functions/api-chat.js`.replace(/\\/g, "/");
  // Cache-bust so each test file re-imports fresh module state (the
  // generated file has no per-request state, but this keeps tests
  // independent if that ever changes).
  const mod = await import(`${url}?t=${Date.now()}-${Math.random()}`);
  return mod.default;
}

function withEnv(overrides, fn) {
  return async () => {
    const saved = { ...process.env };
    for (const k of ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "LLM_HOP_ORDER"]) {
      delete process.env[k];
    }
    Object.assign(process.env, overrides);
    const savedFetch = globalThis.fetch;
    try {
      await fn();
    } finally {
      globalThis.fetch = savedFetch;
      process.env = saved;
    }
  };
}

async function postQuestion(handler, question) {
  const req = new Request("https://example.netlify.app/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const resp = await handler(req);
  return { status: resp.status, data: await resp.json() };
}

test(
  "no providers configured -> degrades gracefully with lexical-search sections",
  withEnv({}, async () => {
    const handler = await importHandler();
    const { status, data } = await postQuestion(handler, "Can a works council member be dismissed?");
    assert.equal(status, 200);
    assert.equal(data.degraded, true);
    assert.equal(data.language, "en");
    assert.ok(data.cited_sections.length > 0);
    assert.ok(data.cited_sections.some((s) => s.law_abbreviation === "BetrVG"));
    assert.deepEqual(data.follow_up_questions, []);
  })
);

test(
  "mocked provider success -> full happy path with follow-ups",
  withEnv({ GROQ_API_KEY: "fake-key-for-test" }, async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls++;
      const content =
        "This is a test answer.\n\n###FOLLOWUP_QUESTIONS_JSON###\n" +
        JSON.stringify(["Follow-up A?", "Follow-up B?"]);
      return new Response(JSON.stringify({ choices: [{ message: { content } }] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    const handler = await importHandler();
    const { status, data } = await postQuestion(handler, "What are the co-determination rights on working hours?");
    assert.equal(status, 200);
    assert.equal(data.degraded, false);
    assert.equal(data.provider_used, "groq");
    assert.ok(data.answer.startsWith("This is a test answer."));
    assert.ok(!data.answer.includes("FOLLOWUP_QUESTIONS_JSON"));
    assert.equal(data.follow_up_questions.length, 2);
    assert.ok(data.cited_sections.some((s) => s.law_abbreviation === "BetrVG" && s.section === "§ 87"));
    assert.equal(calls, 1, "exactly one LLM call - no separate selector step");
  })
);

test(
  "German question -> German language and disclaimer",
  withEnv({}, async () => {
    const handler = await importHandler();
    const { data } = await postQuestion(handler, "Kann ein Betriebsratsmitglied gekündigt werden?");
    assert.equal(data.language, "de");
    assert.ok(data.answer.includes("Rechtsberatung"));
  })
);

test(
  "BDSG-flavored question resolves at least one BDSG section via lexical fallback",
  withEnv({}, async () => {
    const handler = await importHandler();
    const { data } = await postQuestion(
      handler,
      "What are my rights regarding deletion of personal data and the data protection officer?"
    );
    assert.ok(data.cited_sections.some((s) => s.law_abbreviation === "BDSG"));
  })
);

test(
  "empty question -> 400",
  withEnv({}, async () => {
    const handler = await importHandler();
    const { status, data } = await postQuestion(handler, "   ");
    assert.equal(status, 400);
    assert.match(data.detail, /empty/);
  })
);

test(
  "every hop hanging -> degrades within a safe time budget instead of hanging forever",
  withEnv({ GROQ_API_KEY: "fake", GEMINI_API_KEY: "fake" }, async () => {
    globalThis.fetch = async (url, opts) =>
      new Promise((_resolve, reject) => {
        opts.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    const handler = await importHandler();
    const start = Date.now();
    const { status, data } = await postQuestion(handler, "Test question about works councils");
    const elapsed = Date.now() - start;
    assert.equal(status, 200);
    assert.equal(data.degraded, true);
    assert.ok(data.cited_sections.length > 0);
    assert.ok(elapsed < 36000, `expected < 36s, took ${elapsed}ms`);
  })
);
