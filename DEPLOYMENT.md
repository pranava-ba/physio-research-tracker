# PhysioResearch Tracker — Deployment Guide

Complete step-by-step instructions to go from zero to a live shareable URL.
Estimated time: **15–20 minutes**.

---

## What You're Setting Up

```
Your Browser
    └── Streamlit Cloud (hosts the app, free)
            └── Supabase (stores articles + read state, free)
                    └── PubMed + Semantic Scholar (fetched on demand)
```

---

## Step 1 — Create a Supabase Project

1. Go to **https://supabase.com** and sign up for a free account.
2. Click **"New project"**.
   - Give it a name: `physio-tracker`
   - Set a database password (save it somewhere — you won't need it again but keep it safe)
   - Choose a region close to you (e.g. **Singapore** or **Mumbai**)
3. Wait ~1 minute for the project to spin up.

### Create the database tables

4. In your Supabase project, go to **SQL Editor** (left sidebar).
5. Click **"New query"**.
6. Open the file `supabase_schema.sql` from this project, copy its entire contents, paste into the editor, and click **Run**.
7. You should see: `Success. No rows returned.`

### Get your credentials

8. Go to **Project Settings → API** (gear icon in sidebar).
9. Copy two values:
   - **Project URL** — looks like `https://abcdefgh.supabase.co`
   - **anon / public key** — a long string starting with `eyJ...`

Keep these handy for Steps 3 and 4.

---

## Step 2 — Push the Code to GitHub

1. Go to **https://github.com** and sign in (or create a free account).
2. Click **"New repository"**.
   - Name: `physio-research-tracker`
   - Set to **Public** (required for free Streamlit Cloud)
   - Do NOT initialise with README
3. Click **"Create repository"**.

### Upload the files

You can do this directly in the browser — no Git CLI needed.

4. In your new empty repo, click **"uploading an existing file"** (the link in the middle of the page).
5. Drag and drop **all files from the `physio_cloud` folder**. The structure must look exactly like this in GitHub:

```
physio-research-tracker/
├── app.py
├── requirements.txt
├── supabase_schema.sql
├── .gitignore
├── .streamlit/
│   └── secrets.toml          ← IMPORTANT: see note below
└── utils/
    ├── __init__.py
    ├── database.py
    ├── fetcher.py
    └── scheduler.py
```

> ⚠️ **IMPORTANT — secrets.toml:**
> The `.streamlit/secrets.toml` file contains placeholder text only.
> **Do NOT put your real Supabase credentials in this file before uploading to GitHub.**
> You will add the real credentials directly in Streamlit Cloud (Step 4).
> The `.gitignore` already excludes this file from being tracked if you use Git CLI.
> If uploading via browser, upload the template version — it's harmless.

6. Scroll down, write a commit message like `initial upload`, and click **"Commit changes"**.

---

## Step 3 — Deploy on Streamlit Cloud

1. Go to **https://share.streamlit.io** and sign in with your GitHub account.
2. Click **"New app"**.
3. Fill in:
   - **Repository:** `your-github-username/physio-research-tracker`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Advanced settings"** — you'll add secrets here next.

---

## Step 4 — Add Secrets to Streamlit Cloud

In the **Advanced settings → Secrets** text box, paste:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "your-anon-public-key-here"
```

Replace with your **actual** values from Step 1.

5. Click **"Deploy!"**

Streamlit will install dependencies and launch the app. This takes ~1–2 minutes the first time.

---

## Step 5 — First Launch

Once deployed, the app will open in your browser.

- On first load, the **weekly scheduler detects no prior fetch** and automatically starts a background fetch from PubMed.
- This takes **2–4 minutes** to complete in the background.
- You can also click **⟳ Refresh Now** to run it manually and watch the progress.

After the first fetch, you'll have ~300 articles across all three topics.

---

## Step 6 — Share with Your Client

Your app URL will look like:
```
https://your-github-username-physio-research-tracker-app-xxxx.streamlit.app
```

Copy this URL and send it to your client. Anyone with the link can:
- Browse and filter articles
- Read abstracts
- Mark articles as read/unread (shared state)
- Export filtered results to CSV

---

## Running Locally (Optional)

If you want to test on your Windows machine before deploying:

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` with your real credentials:
```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "your-anon-public-key-here"
```

Then run:
```bash
streamlit run app.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App shows "No articles" | Click ⟳ Refresh Now and wait 3–4 min |
| `supabase.exceptions.APIError` | Check your SUPABASE_URL and SUPABASE_KEY in secrets |
| Tables not found error | Re-run `supabase_schema.sql` in Supabase SQL Editor |
| Streamlit Cloud build fails | Check `requirements.txt` is in the repo root |
| Articles not updating weekly | Streamlit Cloud sleeps inactive apps — open the app to wake it, which triggers the scheduler |

---

## Updating the App Later

To add features or fix bugs:
1. Edit the files locally
2. Upload the changed files to GitHub (or use Git CLI: `git add . && git commit -m "update" && git push`)
3. Streamlit Cloud auto-redeploys within ~30 seconds

---

## File Reference

| File | Purpose |
|------|---------|
| `app.py` | Main UI — Streamlit layout, filters, article cards |
| `utils/database.py` | Supabase read/write — articles, stats, fetch log |
| `utils/fetcher.py` | PubMed + Semantic Scholar API calls + scoring |
| `utils/scheduler.py` | 7-day auto-fetch trigger on app load |
| `requirements.txt` | Python dependencies for Streamlit Cloud |
| `supabase_schema.sql` | One-time SQL to create tables in Supabase |
| `.streamlit/secrets.toml` | Credentials template (replace with real values) |
