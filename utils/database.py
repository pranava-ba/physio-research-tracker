"""
Supabase (Postgres) persistence layer.
"""
import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import json


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def check_connection():
    sb = get_supabase()
    errors = []
    for table in ["articles", "fetch_log"]:
        try:
            sb.table(table).select("*").limit(1).execute()
        except Exception as e:
            errors.append(f"**`{table}`**: {e}")
    if errors:
        st.error(
            "### ❌ Supabase table access failed\n\n" + "\n\n".join(errors) +
            "\n\n**Fix:** Run `supabase_schema.sql` then `fix_rls.sql` in Supabase SQL Editor."
        )
        st.stop()
    # custom_topics table is optional — don't hard-fail if missing
    return True


# ─── Custom Topics ────────────────────────────────────────────────────────────

def get_custom_topics() -> list:
    """Returns list of custom topic dicts from Supabase."""
    sb = get_supabase()
    try:
        resp = sb.table("custom_topics").select("*").order("created_at").execute()
        return resp.data or []
    except Exception:
        return []


def save_custom_topic(label: str, keyword: str, queries: list, keywords: list) -> bool:
    import hashlib
    sb = get_supabase()
    topic_id = "custom_" + hashlib.md5(keyword.lower().encode()).hexdigest()[:10]
    try:
        sb.table("custom_topics").upsert({
            "id": topic_id,
            "label": label,
            "keyword": keyword,
            "queries": json.dumps(queries),
            "keywords_csv": ",".join(keywords),
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        st.error(f"Could not save custom topic: {e}")
        return False


def delete_custom_topic(topic_id: str):
    sb = get_supabase()
    try:
        sb.table("custom_topics").delete().eq("id", topic_id).execute()
    except Exception as e:
        st.error(f"Could not delete topic: {e}")


# ─── Articles ─────────────────────────────────────────────────────────────────

def upsert_articles(records: list) -> int:
    if not records:
        return 0
    sb = get_supabase()
    try:
        existing_resp = sb.table("articles").select("id").execute()
        existing_ids = {row["id"] for row in (existing_resp.data or [])}
    except Exception as e:
        st.error(f"Could not read existing IDs: {e}")
        raise

    new_records = [r for r in records if r["id"] not in existing_ids]
    if not new_records:
        return 0

    for i in range(0, len(new_records), 100):
        batch = new_records[i:i + 100]
        for rec in batch:
            if isinstance(rec.get("fetched_at"), datetime):
                rec["fetched_at"] = rec["fetched_at"].isoformat()
            rec["pub_year"]           = int(rec.get("pub_year") or 2000)
            rec["citation_count"]     = int(rec.get("citation_count") or 0)
            rec["journal_tier"]       = int(rec.get("journal_tier") or 4)
            rec["citations_per_year"] = float(rec.get("citations_per_year") or 0)
            rec["topic_score"]        = float(rec.get("topic_score") or 0)
            rec["composite_score"]    = float(rec.get("composite_score") or 0)
            rec["is_open_access"]     = bool(rec.get("is_open_access", False))
            rec["is_read"]            = False
            for col in ["id", "pmid", "title", "authors", "journal",
                        "pub_date", "doi", "abstract", "topic"]:
                rec[col] = str(rec.get(col) or "")
        try:
            sb.table("articles").upsert(batch).execute()
        except Exception as e:
            st.error(f"Upsert failed (batch {i//100+1}): {e}")
            raise

    return len(new_records)


def get_articles(
    topics=None,           # list of topic keys, or None for all
    read_status=None,
    open_access_only=False,
    journals=None,         # list of journal name fragments, or None for all
    year_min=2015,
    sort_by="Composite Score ↓",
    keyword_search=None,   # free-text search against title+abstract
) -> pd.DataFrame:
    sb = get_supabase()
    query = sb.table("articles").select("*")

    # Topic filter — if multiple, fetch all and filter in Python
    if topics and len(topics) == 1:
        query = query.eq("topic", topics[0])

    if read_status is True:
        query = query.eq("is_read", True)
    elif read_status is False:
        query = query.eq("is_read", False)
    if open_access_only:
        query = query.eq("is_open_access", True)

    # Journal: single ilike only; multi-journal filter done in Python
    if journals and len(journals) == 1:
        query = query.ilike("journal", f"%{journals[0]}%")

    query = query.gte("pub_year", year_min)

    sort_map = {
        "Composite Score ↓":   ("composite_score",    False),
        "Date (Newest First)":  ("pub_year",           False),
        "Citation Velocity ↓":  ("citations_per_year", False),
        "Journal Prestige ↓":   ("journal_tier",       True),
    }
    col, asc = sort_map.get(sort_by, ("composite_score", False))
    query = query.order(col, desc=not asc).limit(1000)

    try:
        resp = query.execute()
    except Exception as e:
        st.error(f"Failed to fetch articles: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df

    # Multi-topic filter in Python
    if topics and len(topics) > 1:
        df = df[df["topic"].isin(topics)]

    # Multi-journal filter in Python
    if journals and len(journals) > 1:
        mask = df["journal"].str.contains("|".join(journals), case=False, na=False)
        df = df[mask]

    # Keyword search across title + abstract
    if keyword_search and keyword_search.strip():
        kw = keyword_search.strip().lower()
        mask = (
            df["title"].str.lower().str.contains(kw, na=False) |
            df["abstract"].str.lower().str.contains(kw, na=False)
        )
        df = df[mask]

    return df.reset_index(drop=True)


def toggle_read(article_id: str, current: bool):
    sb = get_supabase()
    try:
        sb.table("articles").update({"is_read": not current}).eq("id", article_id).execute()
    except Exception as e:
        st.error(f"Could not update read status: {e}")


def log_fetch(articles_fetched: int, new_articles: int):
    sb = get_supabase()
    try:
        sb.table("fetch_log").insert({
            "articles_fetched": articles_fetched,
            "new_articles": new_articles,
        }).execute()
    except Exception as e:
        print(f"log_fetch error (non-fatal): {e}")


def get_stats() -> dict:
    sb = get_supabase()
    try:
        total  = sb.table("articles").select("id", count="exact").execute().count or 0
        unread = sb.table("articles").select("id", count="exact").eq("is_read", False).execute().count or 0
        oa     = sb.table("articles").select("id", count="exact").eq("is_open_access", True).execute().count or 0
        log_resp = sb.table("fetch_log").select("fetched_at").order("fetched_at", desc=True).limit(1).execute()
        last_dt = None
        if log_resp.data:
            last_dt = datetime.fromisoformat(log_resp.data[0]["fetched_at"].replace("Z", "+00:00"))
        last_fetch = last_dt.strftime("%d %b %H:%M") if last_dt else None
        next_fetch = (last_dt + timedelta(days=7)).strftime("%d %b") if last_dt else None
    except Exception as e:
        st.warning(f"Stats unavailable: {e}")
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
