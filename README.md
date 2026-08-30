# Worker Council Assist (Germany)

An installable app for German works/worker councils (**Betriebsrat**)
and employees that answers questions — in German or English — grounded
in the official text of two German federal laws, published by the German
government at [gesetze-im-internet.de](https://www.gesetze-im-internet.de/):

- **Betriebsverfassungsgesetz (BetrVG)** — the Works Constitution Act
  (works council rights, elections, co-determination, ...)
- **Bundesdatenschutzgesetz (BDSG)** — the Federal Data Protection Act,
  which supplements the EU GDPR domestically (data subject rights,
  employee data processing, data protection officers, ...). Note: this
  covers the *German* implementing law, not the EU GDPR regulation text
  itself, which isn't published on gesetze-im-internet.de — see
  "Extending to other laws" below.

Ask in German, get a German answer with the § (and law) cited; ask in
English, get an English answer. It ships with a **Recent** panel (your
own past questions, kept only on your device) and a **Sources** panel
(which laws it covers and links to the official text) — the app is built
so more laws (AGG, ArbSchG, MuSchG, ...) can be added later as config,
not a rewrite (see "Extending to other laws" below).

It's a **Progressive Web App (PWA)**: one deployment gives you a normal
web address that people install on their phone (Android or iPhone) or
computer (Windows/Mac/Linux) like a native app — icon on the home
screen/start menu, opens full-screen, no app store required. It runs on
**free-tier LLM APIs** that it automatically hops between when one is
rate-limited, so running it should cost **€0** in AI usage.

**This is general information, not legal advice.** Always confirm
anything important with your works council, your data protection
officer, your union, or a lawyer specializing in German labour or data
protection law (Arbeitsrecht / Datenschutzrecht).

---

## The two roles in this project

- **You (the person setting this up)** deploy the backend **once**. It's
  the only place the free API keys live, and it serves both the API and
  the installable app from a single public URL.
- **Everyone else (the works council / employees)** just visits that URL
  and installs it. They never see or need an API key — zero setup on
  their end.

---

## Part 1 — Deploy the shared backend (do this once)

The backend needs somewhere to run continuously with your API keys kept
secret server-side. **[Render](https://render.com)'s free web-service
tier** is the best fit for this as of 2026: no credit card required,
750 free instance-hours/month (enough to run one service continuously),
and it deploys straight from a GitHub repo using the `Dockerfile` and
`render.yaml` already in this project. The only trade-off is that a free
Render service falls asleep after 15 minutes with no traffic and takes
~30-60 seconds to wake up on the next request — fine for an internal
tool that isn't hit constantly. (Fly.io no longer offers a real free
tier as of 2026, and Railway's free credit is too small to run a service
continuously — Render is the practical no-cost option.)

### Steps

1. **Get your free API key(s) first** (you only need one to start; add
   more later for extra free capacity):

   | Provider | Get a key | Notes |
   |---|---|---|
   | Groq | https://console.groq.com/keys | Fast; free-tier RPM/RPD/TPM limits — https://console.groq.com/docs/rate-limits |
   | Google Gemini | https://aistudio.google.com/apikey | Free daily request quota — https://ai.google.dev/gemini-api/docs/rate-limits |
   | OpenRouter | https://openrouter.ai/keys | Free `:free`-suffixed models, 20 req/min / 50 req/day — https://openrouter.ai/docs/api_reference/limits |

2. **Put this project on GitHub** (Render deploys from a git repo):

   ```bash
   cd worker-council-app
   git init
   git add .
   git commit -m "Worker council assistant"
   ```

   Create a new empty repo on [github.com/new](https://github.com/new),
   then:

   ```bash
   git remote add origin https://github.com/<your-username>/worker-council-app.git
   git branch -M main
   git push -u origin main
   ```

3. **Create the Render service:**
   - Sign up / log in at [render.com](https://render.com) (free, no card).
   - Click **New +** → **Blueprint**, and point it at your GitHub repo.
     Render reads `render.yaml` automatically and sets up a Docker web
     service called `worker-council-assistant` on the free plan.
     (No Blueprint option in your Render UI? Use **New +** → **Web
     Service** instead, select the repo, and it will auto-detect the
     `Dockerfile`.)
   - When prompted for environment variables, paste in the API key(s)
     from step 1 (`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
     — leave any you don't have blank).
   - Click **Deploy**. First deploy takes a few minutes (it builds the
     Docker image, then downloads and parses the BetrVG text on startup —
     watch the deploy logs for the "Wrote N sections..." confirmation
     line from `scripts/fetch_betrvg.py`).

4. **You now have a public URL**, e.g.
   `https://worker-council-assistant.onrender.com`. Open it — you should
   see the chat UI and a status line confirming which AI providers are
   configured. That URL is the app.

### Updating later

Push new commits to `main` and Render redeploys automatically. To add or
change an API key, edit the environment variables in the Render
dashboard (Settings → Environment) — no code change needed, and
`LLM_HOP_ORDER` there also lets you reorder/swap models without a
redeploy of code.

---

## Part 1b — Alternative: deploy on Netlify

Netlify has no Python runtime, so it can't run the FastAPI backend in
`app/` directly. This repo also ships a **JS port** of that backend as
[Netlify Edge Functions](https://docs.netlify.com/build/edge-functions/overview/)
in `netlify/edge-functions/` (generated - see below), so the whole app,
frontend and API both, can live on Netlify as a single site if you'd
rather use it than Render.

**Two deliberate differences from the Render/Python version**, both
because Netlify Edge Functions must send response headers within ~40
seconds, whereas real Groq/Gemini calls have been observed taking up to
~25-30s on their own (model "thinking" overhead):

1. **No LLM-based section selector.** The Python version makes two
   sequential LLM calls per question (pick relevant §§, then answer).
   The Netlify version always uses fast local lexical/glossary matching
   (`app/retrieval.py`'s degraded-mode fallback, ported to JS) to pick
   sections, so only one LLM call (the answer) has to fit the time
   budget. This is quicker and needs no extra AI calls, but is less
   precise for oddly-phrased or multi-concept questions than the
   LLM-based selector - the answering model is instructed to say so
   plainly rather than guess when the retrieved excerpts don't cover the
   question.
2. Each provider hop gets a longer per-hop timeout (up to 25s) since
   there's no selector call competing for the budget. If every hop still
   doesn't answer in time, the request degrades to the same raw-text
   fallback the Python version uses when every provider is exhausted,
   instead of Netlify killing the request with no answer at all.

The law text itself is downloaded and parsed the same way as the Render
path, just once per build (see `scripts/fetch-laws.mjs`, a Node port of
`scripts/fetch_betrvg.py` / `scripts/fetch_bdsg.py`), and baked directly
into the generated edge functions - Edge Functions have no bundled-file
or JSON-import support and no shared runtime disk to read a data file
from at request time.

### Steps

1. Get your free API key(s) - same as step 1 in Part 1 above.
2. Push this project to GitHub - same as step 2 in Part 1 above.
3. Sign up / log in at [netlify.com](https://netlify.com) (free, no
   card). **Add new site** → **Import an existing project** → pick your
   GitHub repo. Netlify reads `netlify.toml` automatically (build
   command `npm install && npm run fetch-laws`, publish directory
   `public`).
4. Before the first deploy, go to **Site configuration → Environment
   variables** and add your API key(s) (`GROQ_API_KEY`, `GEMINI_API_KEY`,
   `OPENROUTER_API_KEY` - leave any you don't have blank). **Set the
   scope to include Functions** - variables scoped only to the build
   won't be visible to the edge functions at request time.
5. Deploy. Watch the build log for the "Wrote N sections..." lines from
   `scripts/fetch-laws.mjs` to confirm both laws downloaded.
6. You get a URL like `https://your-site-name.netlify.app` - that's the
   app, same as the Render URL in Part 1.

### Updating later

Push new commits and Netlify redeploys automatically, re-running
`scripts/fetch-laws.mjs` (so the law text and generated edge functions
are always rebuilt fresh, never stale). To change an API key, edit it
under Site configuration → Environment variables - no code change or
redeploy trigger needed, it takes effect on the next request.

### Editing the Netlify backend's logic

`netlify/edge-functions/*.js` are **generated files** (gitignored, not
the source of truth) - edit the templates in `netlify-build/templates/`
instead and run `npm run fetch-laws` to regenerate, or just push and let
Netlify's build do it. This keeps the law-text-embedding step (which
only a build script can do - see above) and the actual request-handling
logic in one place per function, instead of a separate templating layer
on top of hand-maintained files.

---

## Part 2 — For everyone else: install the app

Once you have the URL from Part 1, share it with your works council /
colleagues. No account, no download from an app store, no setup:

- **Android (Chrome):** open the link → tap the **Install** banner (or
  Chrome's menu → **Install app**). It appears on the home screen and
  opens full-screen like any other app.
- **iPhone/iPad (Safari):** open the link → tap the **Share** icon →
  **Add to Home Screen**. (Apple doesn't let Safari trigger this
  automatically, so the app shows a banner with these exact steps if you
  open it on an iPhone.)
- **Windows/Mac/Linux (Chrome or Edge):** open the link → click the
  **Install** icon in the address bar, or the in-page **Install**
  banner. It installs as a standalone desktop app with its own window
  and start-menu/dock icon.

After installing, the app shell (the interface) loads instantly even on
a slow connection, since a service worker caches it; only the actual AI
answers need a live connection.

---

## How it works

1. `scripts/fetch_betrvg.py` and `scripts/fetch_bdsg.py` each download one
   law's official XML from `gesetze-im-internet.de/<slug>/xml.zip` and
   parse it into `data/betrvg.json` / `data/bdsg.json` — one entry per §
   section (German text, as published). Both run automatically on every
   container startup (see `Dockerfile`), since free hosting tiers don't
   guarantee persistent disk; each is independent, so if one law's fetch
   fails the app still starts and answers using whichever law(s) did load.
2. When someone asks a question (in German or English), the backend:
   - asks an LLM to pick the relevant sections (law + § number) from a
     compact table of contents covering every configured law,
   - pulls the full German text of those sections,
   - asks an LLM to answer **in the same language the question was
     asked in**, grounded in that text, citing the law and § number.
   Section numbers repeat across laws (both BetrVG and BDSG have a "§ 1"),
   so `app/retrieval.py` always identifies a section by its
   (law abbreviation, § number) pair, never by § number alone.
   `app/i18n.py` does a cheap local language check (umlauts/ß + a
   stopword score) just to pick the matching disclaimer text and a
   couple of fixed fallback messages — the actual answer's language is
   handled by the LLM itself, per the instruction in its system prompt.
3. Both LLM calls go through `app/llm_router.py`, which tries providers
   in this order and **automatically hops to the next one** if a
   provider is rate-limited, out of quota, or errors out:

   **Groq → Google Gemini → OpenRouter (free `:free` models)**

   If every provider is temporarily exhausted, the app doesn't fail — it
   falls back to plain keyword search and shows the raw law text for the
   matching §§ instead of an AI-generated answer.
4. The frontend (`app/static/index.html` + `manifest.json` + `sw.js`) is
   a standard installable PWA: a web app manifest describes the icon/
   name/colors, and a service worker caches the interface so it installs
   and opens like a native app on Android, iOS, and desktop. The
   **Recent** panel is pure client-side (questions are kept in
   `localStorage` on that device only — never sent anywhere but the
   chat API). The **Sources** panel and the **Holds** pills in the header
   both come from `GET /api/sources`, which reports on every law in
   `app/config.py`'s `LAW_REGISTRY` (BetrVG and BDSG today).

---

## Local development (optional)

You don't need this to deploy or use the app — it's only for testing
changes before pushing.

```bash
cd worker-council-app
./run.sh
```

`run.sh` creates a virtualenv, installs dependencies, downloads the
BetrVG and BDSG text on first run, copies `.env.example` to `.env` if
missing, and starts the server at http://127.0.0.1:8000. Edit `.env` and
add at least one API key before asking questions.

Or with Docker, matching exactly what Render will run:

```bash
docker build -t worker-council-app .
docker run -p 8000:8000 --env-file .env worker-council-app
```

To test the Netlify (Edge Functions) version locally instead, via the
[Netlify CLI](https://docs.netlify.com/cli/get-started/):

```bash
npm install
npm install -g netlify-cli
netlify dev
```

`netlify dev` runs `netlify.toml`'s build command (which downloads and
embeds the law text - see Part 1b above) and serves the site with the
edge functions live at http://localhost:8888. Environment variables for
this local run come from `netlify env:set` / the Netlify CLI's own login
context, not from `.env` (that file is only read by the Python version).

Then open http://127.0.0.1:8000 (Python) or http://localhost:8888
(Netlify CLI). Note: installing a PWA generally
requires HTTPS, so "Install" banners may not appear over plain
`http://127.0.0.1` in every browser — that's expected locally and works
fine once deployed to Render's HTTPS URL.

---

## Important notes

- **The scraper works against the live site** — confirmed against the
  real `gesetze-im-internet.de` XML export for both BetrVG (148 sections)
  and BDSG (86 sections). It uses the same well-documented, stable URL
  pattern and export schema the site uses for every German federal law
  (the same pattern the community-maintained
  [bundestag/gesetze](https://github.com/bundestag/gesetze) mirror uses),
  and is written defensively so minor schema drift degrades gracefully
  rather than crashing. Check your first deploy log for the "Wrote N
  sections..." line from `scripts/fetch_betrvg.py` / `scripts/fetch_bdsg.py`
  to confirm it worked — if the government site changes its export format
  in the future, the scripts' error messages point you at exactly what to
  check.
- **Model names drift.** Free-tier model IDs on Groq/Gemini/OpenRouter
  change over time. If you start seeing "model not found" errors, check
  each provider's current model list and either edit the defaults in
  `app/config.py` or set `LLM_HOP_ORDER` as an env var on Render
  (format: `provider:model,provider:model,...`) — no redeploy of code
  needed.
- **Shared rate limits.** Because everyone hits the same backend, the
  free-tier request limits are shared across all users, not
  per-person. For occasional works-council questions this is normally
  plenty; if usage is heavy, add more provider keys (each one is another
  hop with its own quota) or upgrade Render's plan.
- **Translation quality.** Answers are generated on the fly by whichever
  free model answered, not pre-translated by a human — always cross-check
  anything important against the cited § of the original German text or
  with your works council/a lawyer.
- **Extending to other laws** (e.g. the AGG or ArbSchG). BetrVG and BDSG
  are both configured today, and `app/retrieval.py` already merges
  sections across every law in `LAW_REGISTRY` and disambiguates them by
  (law abbreviation, § number) pairs, since § numbers repeat across laws.
  The same download pattern (`{slug}/xml.zip`) works for any law on
  gesetze-im-internet.de. To add another:
  1. Copy `scripts/fetch_bdsg.py` to e.g. `scripts/fetch_agg.py`, change
     `LAW_SLUG`, `OUTPUT_PATH`, and the `default_abbreviation` passed to
     `parse_norms()`.
  2. Add an entry to `LAW_REGISTRY` in `app/config.py` (abbreviation,
     names, source URL, data filename) — the `abbreviation` must exactly
     match the `law_abbreviation` the fetch script stamps onto each
     section (don't rely on the government XML's own `<jurabk>` value,
     which can carry a year suffix like BDSG's "BDSG 2018" — see the
     comment in `scripts/fetch_bdsg.py`).
  3. Add the new fetch script to `Dockerfile`'s startup `CMD` and to
     `run.sh`'s first-run checks, alongside the existing ones.

  Once that's done, `/api/sources`, the **Holds** pills, the **Sources**
  panel, and the selector/answerer LLM prompts all pick up the new law
  automatically — no other code changes needed.

---

## Project layout

```
worker-council-app/
├── app/
│   ├── main.py              FastAPI app: /api/chat, /api/health, /api/sources, PWA routes, serves the UI
│   ├── llm_router.py         Multi-provider free-LLM fallback/hopping logic
│   ├── retrieval.py           Search over the parsed law data + law status for /api/sources
│   ├── i18n.py                 German/English detection, disclaimers, fixed fallback strings
│   ├── config.py                 Provider registry, hop-order config, LAW_REGISTRY
│   └── static/
│       ├── index.html            Chat UI: header, Holds row, Recent/Sources panels, hero, chat, ask bar
│       ├── manifest.json          PWA metadata (name, icons, dark theme colors)
│       ├── sw.js                    Service worker (app-shell caching)
│       ├── favicon.ico
│       └── icons/                    192/512/maskable/apple-touch icons + logo-mark.png
├── scripts/
│   ├── fetch_betrvg.py      Downloads + parses BetrVG -> data/betrvg.json
│   ├── fetch_bdsg.py         Downloads + parses BDSG -> data/bdsg.json
│   └── fetch-laws.mjs         Netlify build step: Node port of the two scripts above,
│                               also bakes the result into netlify/edge-functions/
├── tests/                    Python unit tests (mocked HTTP, no API keys needed)
├── data/betrvg.json          Generated at container/build time (not checked in)
├── data/bdsg.json             Generated at container/build time (not checked in)
├── Dockerfile                 Used for both local Docker runs and Render deploy
├── render.yaml                  Render Blueprint (auto-config for one-click deploy)
├── netlify.toml                  Netlify build/publish config (see README "Part 1b")
├── netlify-build/
│   ├── templates/                  Source-of-truth templates for the generated edge functions
│   └── test/                        Node test runner tests for the generated edge functions
├── netlify/edge-functions/         Generated by scripts/fetch-laws.mjs (gitignored)
├── public/                          Static frontend Netlify serves (mirrors app/static/)
├── package.json
├── .env.example
├── requirements.txt
└── run.sh
```

## Running the tests

Python (the Render/FastAPI version):

```bash
pip install pytest
python -m pytest tests/ -v
```

These test the hop/fallback logic (rate-limit → next provider → all
exhausted → graceful error) and the retrieval logic against a small
synthetic law dataset — no real API keys or network access required.

JS (the Netlify Edge Functions port):

```bash
npm install
npm run fetch-laws   # generates netlify/edge-functions/*.js first
npm test
```

Mocks `fetch` and the `Netlify` global, so no real API keys or a live
Netlify/Deno environment are needed either.
