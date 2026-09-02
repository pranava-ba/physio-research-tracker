<div align="center">

<pre>
██████╗ ██╗  ██╗██╗   ██╗███████╗██╗ ██████╗ 
██╔══██╗██║  ██║╚██╗ ██╔╝██╔════╝██║██╔═══██╗
██████╔╝███████║ ╚████╔╝ ███████╗██║██║   ██║
██╔═══╝ ██╔══██║  ╚██╔╝  ╚════██║██║██║   ██║
██║     ██║  ██║   ██║   ███████║██║╚██████╔╝
╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝ ╚═════╝ 
</pre>

**PhysioResearch Tracker**

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres-3FCF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![License](https://img.shields.io/badge/License-MIT-8B949E?style=flat-square)](LICENSE)

<br/>

*A weekly research radar for physiotherapy — auto-pulls new PubMed &amp; Semantic Scholar papers on your topics and keeps track of what you've read.*

</div>

<br/>

---

## Installation

<details>
<summary><strong>🐍 Run from Source</strong></summary>
<br/>

Requires Python 3.10+ and a free [Supabase](https://supabase.com) project.

```bash
git clone https://github.com/pranava-ba/physio-research-tracker.git
cd physio-research-tracker
pip install -r requirements.txt
streamlit run app.py
```

Create `.streamlit/secrets.toml` with your Supabase credentials before running:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "your-anon-public-key"
```

The app opens at `http://localhost:8501`.

</details>

<details>
<summary><strong>☁️ Deploy your own (Streamlit Cloud, free)</strong></summary>
<br/>

The full 15-minute, zero-to-live-URL walkthrough is in **[DEPLOYMENT.md](DEPLOYMENT.md)** — create a Supabase project, run `supabase_schema.sql`, push to GitHub, and deploy on [Streamlit Community Cloud](https://share.streamlit.io) with `SUPABASE_URL` / `SUPABASE_KEY` added as secrets.

</details>

---

## Quick Start

| Step | Action |
|------|--------|
| 1 | Create a free Supabase project and run `supabase_schema.sql` in its SQL editor |
| 2 | Put `SUPABASE_URL` and `SUPABASE_KEY` in `.streamlit/secrets.toml` (or Streamlit Cloud secrets) |
| 3 | `streamlit run app.py` — the app opens at `http://localhost:8501` |
| 4 | On first load it auto-fetches ~300 papers in the background; hit **⟳ Refresh Now** anytime |

---

## Features

<details>
<summary><strong>📡 Automated fetching</strong></summary>
<br/>

- Pulls new papers from **PubMed** (NCBI E-utilities) and **Semantic Scholar**.
- A built-in **7-day scheduler** runs on app load — no cron, no server to babysit.
- Keyword-based relevance scoring keeps each topic's results on-target.
- One background fetch seeds ~300 articles across the default topics.

</details>

<details>
<summary><strong>🗂️ Topics &amp; reading workflow</strong></summary>
<br/>

- Ships with curated physiotherapy topics (e.g. degenerative **knee-meniscus pain**, **perimenopausal training**) plus **custom topics** you define at runtime.
- Mark articles **read / unread** — state is shared across everyone using the link.
- Filter and search by topic, then **export the filtered set to CSV**.

</details>

<details>
<summary><strong>☁️ Stack</strong></summary>
<br/>

| Layer | Tech |
|-------|------|
| UI | Streamlit (dark theme, DM Serif / Outfit) |
| Storage | Supabase (Postgres) — articles, read-state, fetch log |
| Sources | PubMed E-utilities · Semantic Scholar API |
| Hosting | Streamlit Community Cloud (free tier) |

</details>

---

## Data Notes

> Articles are fetched live from PubMed and Semantic Scholar — be considerate of their public rate limits. Credentials live only in Streamlit secrets; **never commit `secrets.toml`**. Streamlit Cloud sleeps inactive apps — opening the app wakes it, which is also what triggers the weekly fetch.

---

<div align="center">

**PhysioResearch Tracker** · built by Pranava Baascaran · © 2026

</div>
