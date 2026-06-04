"""
Supabase (Postgres) persistence layer.
All credentials come from st.secrets / environment variables.
"""
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ─── Schema (run once in Supabase SQL editor) ─────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id                VARCHAR PRIMARY KEY,
    pmid              VARCHAR,
    title             TEXT,
    authors           VARCHAR,
    journal           VARCHAR,
    pub_year          INTEGER,
    pub_date          VARCHAR,
    doi               VARCHAR,
    abstract          TEXT,
    topic             VARCHAR,
    is_open_access    BOOLEAN DEFAULT FALSE,
    citation_count    INTEGER DEFAULT 0,
    citations_per_year FLOAT DEFAULT 0,
    journal_tier      INTEGER DEFAULT 3,
    topic_score       FLOAT DEFAULT 0,
    composite_score   FLOAT DEFAULT 0,
    is_read           BOOLEAN DEFAULT FALSE,
    fetched_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id               SERIAL PRIMARY KEY,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    articles_fetched INTEGER,
    new_articles     INTEGER
);
"""


def upsert_articles(records: list[dict]) -> int:
    if not records:
        return 0
    sb = get_supabase()

    # Get existing IDs
    existing_resp = sb.table("articles").select("id").execute()
    existing_ids = {row["id"] for row in (existing_resp.data or [])}

    new_records = [r for r in records if r["id"] not in existing_ids]
    if not new_records:
        return 0

    # Supabase upsert in batches of 100
    for i in range(0, len(new_records), 100):
        batch = new_records[i:i+100]
        # Convert datetime to string for JSON serialisation
        for rec in batch:
            if isinstance(rec.get("fetched_at"), datetime):
                rec["fetched_at"] = rec["fetched_at"].isoformat()
            # Ensure correct types
            rec["pub_year"] = int(rec.get("pub_year") or 2000)
            rec["citation_count"] = int(rec.get("citation_count") or 0)
            rec["journal_tier"] = int(rec.get("journal_tier") or 4)
            rec["citations_per_year"] = float(rec.get("citations_per_year") or 0)
            rec["topic_score"] = float(rec.get("topic_score") or 0)
            rec["composite_score"] = float(rec.get("composite_score") or 0)
            rec["is_open_access"] = bool(rec.get("is_open_access", False))
            rec["is_read"] = False
            for col in ["id", "pmid", "title", "authors", "journal",
                        "pub_date", "doi", "abstract", "topic"]:
                rec[col] = str(rec.get(col) or "")

        sb.table("articles").upsert(batch).execute()

    return len(new_records)


def get_articles(
    topic=None,
    read_status=None,
    open_access_only=False,
    journal=None,
    year_min=2015,
    sort_by="Composite Score ↓"
) -> pd.DataFrame:
    sb = get_supabase()
    query = sb.table("articles").select("*")

    if topic:
        query = query.eq("topic", topic)
    if read_status is True:
        query = query.eq("is_read", True)
    elif read_status is False:
        query = query.eq("is_read", False)
    if open_access_only:
        query = query.eq("is_open_access", True)
    if journal:
        query = query.ilike("journal", f"%{journal}%")
    query = query.gte("pub_year", year_min)

    # Sorting
    sort_map = {
        "Composite Score ↓":  ("composite_score", False),
        "Date (Newest First)": ("pub_year", False),
        "Citation Velocity ↓": ("citations_per_year", False),
        "Journal Prestige ↓":  ("journal_tier", True),
    }
    col, asc = sort_map.get(sort_by, ("composite_score", False))
    query = query.order(col, desc=not asc)

    resp = query.limit(500).execute()
    data = resp.data or []
    return pd.DataFrame(data) if data else pd.DataFrame()


def toggle_read(article_id: str, current: bool):
    sb = get_supabase()
    sb.table("articles").update({"is_read": not current}).eq("id", article_id).execute()


def log_fetch(articles_fetched: int, new_articles: int):
    sb = get_supabase()
    sb.table("fetch_log").insert({
        "articles_fetched": articles_fetched,
        "new_articles": new_articles
    }).execute()


def get_stats() -> dict:
    sb = get_supabase()
    try:
        total = sb.table("articles").select("id", count="exact").execute().count or 0
        unread = sb.table("articles").select("id", count="exact").eq("is_read", False).execute().count or 0
        oa = sb.table("articles").select("id", count="exact").eq("is_open_access", True).execute().count or 0
        log_resp = sb.table("fetch_log").select("fetched_at").order("fetched_at", desc=True).limit(1).execute()
        last_dt = None
        if log_resp.data:
            last_dt = datetime.fromisoformat(log_resp.data[0]["fetched_at"].replace("Z", "+00:00"))
        last_fetch = last_dt.strftime("%d %b %H:%M") if last_dt else None
        next_fetch = (last_dt + timedelta(days=7)).strftime("%d %b") if last_dt else None
    except Exception as e:
        print(f"Stats error: {e}")
        total, unread, oa, last_fetch, next_fetch = 0, 0, 0, None, None
    return {"total": total, "unread": unread, "open_access": oa,
            "last_fetch": last_fetch, "next_fetch": next_fetch}


def get_last_fetch_time():
    sb = get_supabase()
    try:
        resp = sb.table("fetch_log").select("fetched_at").order("fetched_at", desc=True).limit(1).execute()
        if resp.data:
            return datetime.fromisoformat(resp.data[0]["fetched_at"].replace("Z", "+00:00"))
    except Exception:
        pass
    return None
