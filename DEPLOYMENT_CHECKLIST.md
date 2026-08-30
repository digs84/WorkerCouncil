# Worker Council Assistant — Deployment Checklist

## 🚀 Complete Step-by-Step Deployment Guide

---

## Pre-Deployment Checklist (5 minutes)

### Prerequisites
- [ ] GitHub account (free, https://github.com/join)
- [ ] Render account (free, https://render.com, no credit card needed)
- [ ] At least one free LLM API key (Groq recommended for speed)
- [ ] Terminal/PowerShell access
- [ ] Git installed locally

### Which LLM Provider to Start With?
| Provider | Sign Up Time | Limit | Recommendation |
|----------|--------------|-------|-----------------|
| **Groq** | 2 min | 30 req/min | ✅ **Start here** (fastest) |
| **Gemini** | 3 min | Daily quota | ✅ Good backup |
| **OpenRouter** | 5 min | 20 req/min | ✅ Good for variety |

**Recommendation:** Get a Groq key first. If you hit limits later, add Gemini/OpenRouter.

---

## Phase 1: Get API Keys (10 minutes)

### Step 1.1: Groq API Key ⚡

**Time:** 2 minutes

```
1. Go to https://console.groq.com/keys
2. Sign up with email (or GitHub)
3. Verify email
4. Click "Create API Key" (or "Create an API key for groq-api")
5. Copy the key (looks like: "gsk_xxxxxxxxxxxxxx")
6. Keep it safe in a text editor (you'll paste it into Render later)
```

**Save this:** `GROQ_API_KEY=gsk_xxxxxxxxxxxxxx`

---

### Step 1.2 (Optional): Google Gemini API Key

**Time:** 3 minutes

```
1. Go to https://aistudio.google.com/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key (looks like: "AIzaSy...")
5. Keep it in your text editor
```

**Save this:** `GEMINI_API_KEY=AIzaSy_xxxxxxxxxxxxxx`

---

### Step 1.3 (Optional): OpenRouter API Key

**Time:** 5 minutes

```
1. Go to https://openrouter.ai/keys
2. Sign up with email
3. Verify email
4. Click "Create Key" under "API Keys"
5. Copy the key
6. Keep it in your text editor
```

**Save this:** `OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxx`

---

## Phase 2: Prepare GitHub Repository (5 minutes)

### Step 2.1: Clone or Initialize Local Repo

**If you already have this project locally:**

```bash
cd c:\Users\Asus\OneDrive\Desktop\NewAI\ Project\Architecture_Diagrams_Python_AI\Digvijay_New_Automation\Workercouncil
git status
```

**Expected output:** Should show the current status (if already a git repo).

---

### Step 2.2: Ensure All Files Are Committed

```bash
git add .
git commit -m "Worker Council Assistant - ready for deployment"
```

**If already committed:** You'll see `nothing to commit` message — that's fine.

---

### Step 2.3: Verify GitHub Remote Is Set

```bash
git remote -v
```

**Expected output:**
```
origin    https://github.com/<your-username>/worker-council-assistant.git (fetch)
origin    https://github.com/<your-username>/worker-council-assistant.git (push)
```

**If no remote:**
```bash
git remote add origin https://github.com/<your-username>/worker-council-assistant.git
git branch -M main
git push -u origin main
```

---

### Step 2.4: Push Latest Code to GitHub

```bash
git push
```

**Expected output:** Shows how many objects were pushed (or "Everything up-to-date").

---

## Phase 3: Deploy to Render (10 minutes)

### Step 3.1: Create Render Account

**Time:** 2 minutes

```
1. Go to https://render.com
2. Click "Sign Up" (top right)
3. Use GitHub login (easiest) OR email
4. Verify email
5. You're logged in!
```

---

### Step 3.2: Create a New Web Service

**Time:** 3 minutes

```
1. Click "New +" button (top left)
2. Select "Web Service" (or "Blueprint" if you see it)
3. Click "Connect to a repository"
4. Search for your GitHub repo name: "worker-council-assistant"
5. Click "Connect"
```

---

### Step 3.3: Configure the Service

**In the "Create a new Web Service" form:**

| Field | Value |
|-------|-------|
| **Name** | `worker-council-assistant` (or your preferred name) |
| **Environment** | `Docker` |
| **Region** | Frankfurt (closest to Germany) or US East (default) |
| **Branch** | `main` |
| **Dockerfile path** | `./Dockerfile` (should auto-detect) |
| **Build command** | Leave blank (Render reads Dockerfile) |
| **Start command** | Leave blank (Render reads Dockerfile) |

---

### Step 3.4: Add Environment Variables

**After clicking "Create Web Service", scroll down to "Environment" section:**

```
Click "Add Secret File" or "Add Environment Variable"
```

**Add these one by one:**

```
GROQ_API_KEY = gsk_xxxxxxxxxxxxx  (paste your key here)
GEMINI_API_KEY = AIzaSy_xxxxx     (optional)
OPENROUTER_API_KEY = sk-or-xxxxx  (optional)
LLM_HOP_ORDER = groq,gemini,openrouter
HOST = 0.0.0.0
PORT = 8000
```

**Then click "Create Web Service"**

---

### Step 3.5: Wait for Deployment

**Render will now:**
1. Build the Docker image (~2 minutes)
2. Install Python dependencies
3. Start the FastAPI server
4. Assign a public URL

**Watch the logs** (should appear in the dashboard):
```
=== Building Docker image ===
...
Successfully tagged worker-council-assistant:latest

=== Starting service ===
...
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Status will change to:** 🟢 **Live** (when ready)

---

### Step 3.6: Get Your Public URL

**In the Render dashboard:**
```
Find the "URL" field — looks like:
https://worker-council-assistant.onrender.com/
```

**This is your app!** Copy it.

---

## Phase 4: Test the Deployment (5 minutes)

### Step 4.1: Visit the App in Browser

```
1. Open the URL (https://worker-council-assistant.onrender.com/)
2. You should see the landing page with:
   - Large "§" logo
   - Green headline: "Ask the law." + "Get the exact section."
   - White body text
   - Example questions
3. Page should load within 30 seconds (Render free tier wakes on first request)
```

---

### Step 4.2: Test a Question

```
1. In the text box, type: "What is a Betriebsrat?"
2. Click "Ask"
3. Wait for answer (should come within 5 seconds)
4. Expected: Answer in English with § citations
5. Verify sources panel shows BetrVG + BDSG links
```

---

### Step 4.3: Test Bilingual Detection

```
1. Try a German question: "Was ist ein Betriebsrat?"
2. Expected: Answer in German with § citations
3. Language detection should work automatically
```

---

### Step 4.4: Test PWA Installation

```
1. On desktop: Click the install icon (top-left URL bar, if present)
   OR: Right-click → "Install app"
2. On mobile: Open in Safari/Chrome, look for "Add to Home Screen" prompt
3. App should appear on home screen / start menu
4. Open it — should work exactly like the web version
```

---

### Step 4.5: Check Service Worker & Offline

```
1. Open app in browser (desktop or mobile)
2. Go to Settings → Application → Service Workers
3. You should see "sw.js" registered
4. Close internet connection
5. Reload page or navigate in app
6. Cached questions should still appear
7. Asking new questions will fail gracefully (informative message)
```

---

## Phase 5: Share with Users (Immediate)

### Step 5.1: Create a Shareable Link

```
Copy your Render URL:
https://worker-council-assistant.onrender.com/

Share via:
- Email
- Slack / Teams
- QR code (use qr-server.com if needed)
- Intranet / wiki
- Print on posters for the office
```

---

### Step 5.2: Create a Quick User Guide

**Share this one-liner:**

```
1. Visit: https://worker-council-assistant.onrender.com/
2. Click "Install" to add to your home screen
3. Ask a question in German or English
4. Get an answer with law citations
5. Check "Sources" or "Recent" for history
```

---

### Step 5.3: Monitor First 24 Hours

| What to Watch | What's Normal | What's a Problem |
|---|---|---|
| **Response time** | 3–5 sec | > 30 sec consistently |
| **Error messages** | Rare (< 1 per 100 questions) | Every question fails |
| **Page load** | < 5 sec on reload | Never loads |
| **Offline mode** | Shows cached answers | Shows blank |
| **LLM hopping** | Rarely needed | Every question hops |

---

## Phase 6: Ongoing Maintenance (Once Per Month)

### Step 6.1: Check Logs (Optional but Recommended)

```
In Render dashboard → select your service → Logs tab

Look for:
✅ Lots of 200 responses (good)
⚠️ Occasional 429/503 (rate limits — normal, auto-recovery works)
❌ Repeated 500 errors (bad — investigate)
```

---

### Step 6.2: Update Law Data (Quarterly or As Needed)

**If German laws change (rare):**

```bash
cd scripts/
python fetch_betrvg.py
# This downloads latest law text from gesetze-im-internet.de

git add data/betrvg.json
git commit -m "Update law data: fetch latest from gov"
git push
# Render auto-redeployds on push
```

---

### Step 6.3: Rotate API Keys (Annually)

**If you're concerned about key security:**

```bash
1. Go to your LLM provider console (Groq, Gemini, etc.)
2. Rotate/create new API keys
3. Update Render environment variables
4. Test the app (should still work)
5. Revoke old keys
```

---

### Step 6.4: Monitor Costs (Realtime)

**LLM Provider Dashboards:**

| Provider | Cost Monitor |
|----------|--------------|
| Groq | https://console.groq.com/account/billing |
| Gemini | https://aistudio.google.com/ → Usage |
| OpenRouter | https://openrouter.ai/account/billing |

**Expected cost:** €0 (you should never be charged if using only free tiers)

---

## Phase 7: Scaling (If Usage Grows)

### Step 7.1: Monitor Render Resource Usage

**If you see:**
- ⚠️ Page load times > 10 sec consistently
- ⚠️ "Out of memory" errors
- ⚠️ 100+ concurrent users

**Action:**
```
Render dashboard → your service → "Upgrade" button
Choose a paid tier (starts at $7/month for Production)
```

---

### Step 7.2: Upgrade LLM Providers

**If you hit rate limits on free tiers:**

1. **Option A:** Add more free API keys (Groq + Gemini + OpenRouter combined = ~100 req/min)
2. **Option B:** Upgrade to paid tiers (see provider docs)
3. **Option C:** Deploy multiple instances (advanced; contact Render support)

---

## Troubleshooting During Deployment

### Problem: "Build failed"

**Check logs:**
```
Render dashboard → Logs tab → scroll up
```

**Common causes:**
- Docker syntax error (unlikely, we provide it)
- Python package missing (try rebuilding)
- Environment variable issue (check spelling)

**Fix:**
```bash
git push  # Force redeploy
# or: In Render dashboard, click "Manual Deploy" → "Deploy latest commit"
```

---

### Problem: "Deployment successful but page won't load"

**Checklist:**
1. [ ] URL correct? (https://worker-council-assistant.onrender.com/)
2. [ ] Wait 30 seconds (free Render tier wakes slowly)
3. [ ] Hard refresh (Ctrl+Shift+R on Windows/Linux, Cmd+Shift+R on Mac)
4. [ ] Check Render logs for startup errors
5. [ ] Check that API keys are set in Render environment

---

### Problem: "Questions are failing / 'All providers exhausted'"

**Check:**
1. [ ] At least one API key is set in Render environment
2. [ ] API key spelling is correct (copy-paste to verify)
3. [ ] API key is still valid (not expired, not revoked)
4. [ ] Provider rate limits (check Groq/Gemini/OpenRouter dashboards)

**Fix:**
```bash
# Add a second API key as fallback
# In Render: Add GEMINI_API_KEY or OPENROUTER_API_KEY
```

---

### Problem: "App loads but looks outdated / wrong colors"

**Fix: Hard refresh and clear cache**

```
Browser: Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
Then: Select "Cached files and images" and "Clear"
Then: Hard refresh (Ctrl+Shift+R)
```

**Or:**
```
App → Settings → Clear Site Data
Then reload
```

---

### Problem: "PWA install button doesn't appear"

**This is normal on some browsers.** Alternatives:
- **Chrome/Edge:** Icon in URL bar
- **Safari:** Share → Add to Home Screen
- **Firefox:** ⋮ menu → Install
- **Manual:** Users can always bookmark and add to home screen

---

## Post-Deployment Checklist

### Day 1: Go-Live
- [ ] App loads quickly (< 5 sec)
- [ ] Landing page displays correctly
- [ ] Can ask a test question
- [ ] Answer appears in < 10 sec
- [ ] Language detection works (German & English)
- [ ] PWA install works
- [ ] Service worker cached assets (open DevTools → Application)
- [ ] No 500 errors in logs

### Day 2–7: Stability
- [ ] No crash reports
- [ ] Users can install app successfully
- [ ] Recent questions load from device storage
- [ ] Source excerpts toggle works
- [ ] Copy answer button works
- [ ] Follow-up chips work
- [ ] Mobile experience is smooth

### Week 2: Optimization
- [ ] Document any common questions (FAQ)
- [ ] Monitor Render logs for patterns
- [ ] Gather user feedback (survey or feedback form)
- [ ] Update team on usage stats
- [ ] Plan feature requests (e.g., PDF export, more laws)

---

## Deployment Summary

| Phase | Duration | Effort | Cost |
|-------|----------|--------|------|
| **Get API keys** | 10 min | 1 person | €0 |
| **Prepare GitHub** | 5 min | 1 person | €0 |
| **Deploy to Render** | 10 min | 1 person | €0 |
| **Test** | 5 min | 1 person | €0 |
| **Share with users** | 2 min | 1 person | €0 |
| **TOTAL** | **32 min** | **1 person** | **€0** |

---

## Success Criteria

✅ **Deployment is successful when:**
- [ ] App loads at public Render URL
- [ ] Landing page displays with correct colors (green headline, white text)
- [ ] Can ask a test question and get an answer
- [ ] Answer includes § citations
- [ ] Language detection works (test German + English)
- [ ] PWA installs on at least one device
- [ ] No 500 errors in Render logs
- [ ] Response time is < 10 seconds

✅ **Launch is successful when:**
- [ ] URL is shared with target users
- [ ] First 5 users install the app
- [ ] First 10 questions are asked
- [ ] Users report satisfaction (informal feedback)
- [ ] No critical bugs reported
- [ ] Operating cost is €0

---

## Quick Reference: Render Dashboard

### Find Your Service
```
https://dashboard.render.com → select your service
```

### Key Sections
- **Logs** — Real-time output, see errors
- **Environment** — Manage API keys & config
- **Manual Deploy** — Trigger redeploy
- **Settings** → **Danger** — Delete service (if needed)

### Common Render URLs
```
Service URL:  https://<your-service-name>.onrender.com
Logs:         https://dashboard.render.com → Logs tab
API Status:   https://render.com/status (check if Render is having issues)
```

---

## Support Resources

### Official Docs
- **Render:** https://render.com/docs
- **Groq:** https://console.groq.com/docs
- **Gemini:** https://ai.google.dev/gemini-api/docs
- **OpenRouter:** https://openrouter.ai/docs/api_reference

### Project Docs
- **README.md** — Full project documentation
- **PROJECT_OVERVIEW.md** — Business overview
- **ARCHITECTURE_DIAGRAM.md** — System design (with Mermaid diagrams)
- **EXECUTIVE_PITCH.md** — Stakeholder presentation

### Common Errors & Solutions
- See **Troubleshooting During Deployment** section above
- Check **Known Issues** in README.md (if any)
- Open an issue on GitHub with logs and error details

---

## 🎉 Congratulations!

You've successfully deployed a production-grade, bilingual legal reference assistant that:
- ✅ Costs €0/month to operate
- ✅ Works offline on mobile & desktop
- ✅ Serves multiple concurrent users
- ✅ Grounds answers in official German law
- ✅ Auto-scales across LLM providers
- ✅ Requires zero ongoing maintenance

**Next Steps:**
1. Gather user feedback
2. Plan for additional German laws (AGG, ArbSchG, etc.)
3. Consider role-based customizations (HR vs. employees)
4. Monitor usage and celebrate the impact!

---

**Deployment Guide Version:** 1.0 | **Last Updated:** 2026-08-30 | **Status:** Production-Ready ✅
