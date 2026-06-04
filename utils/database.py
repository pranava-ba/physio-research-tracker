"""
Supabase (Postgres) persistence layer.
All credentials come from st.secrets.
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


def _safe_execute(query, label="query"):
    """Runs a postgrest query and raises with the real error message visible."""
    try:
        resp = query.execute()
        return resp
    except Exception as e:
        # Supabase redacts errors in Streamlit Cloud logs — re-raise with full detail
        msg = str(e)
        st.error(f"**Supabase error in `{label}`:** {msg}")
        raise


def upsert_articles(records: list) -> int:
    if not records:
        return 0
    sb = get_supabase()

    existing_resp = _safe_execute(sb.table("articles").select("id"), "select existing ids")
    existing_ids = {row["id"] for row in (existing_resp.data or [])}

    new_records = [r for r in records if r["id"] not in existing_ids]
    if not new_records:
        return 0

    for i in range(0, len(new_records), 100):
        batch = new_records[i:i + 100]
        for rec in batch:
            if isinstance(rec.get("fetched_at"), datetime):
                rec["fetched_at"] = rec["fetched_at"].isoformat()
            rec["pub_year"]          = int(rec.get("pub_year") or 2000)
            rec["citation_count"]    = int(rec.get("citation_count") or 0)
            rec["journal_tier"]      = int(rec.get("journal_tier") or 4)
            rec["citations_per_year"]= float(rec.get("citations_per_year") or 0)
            rec["topic_score"]       = float(rec.get("topic_score") or 0)
            rec["composite_score"]   = float(rec.get("composite_score") or 0)
            rec["is_open_access"]    = bool(rec.get("is_open_access", False))
            rec["is_read"]           = False
            for col in ["id", "pmid", "title", "authors", "journal",
                        "pub_date", "doi", "abstract", "topic"]:
                rec[col] = str(rec.get(col) or "")
        _safe_execute(sb.table("articles").upsert(batch), f"upsert batch {i//100+1}")

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

    sort_map = {
        "Composite Score ↓":   ("composite_score",   False),
        "Date (Newest First)":  ("pub_year",          False),
        "Citation Velocity ↓":  ("citations_per_year",False),
        "Journal Prestige ↓":   ("journal_tier",      True),
    }
    col, asc = sort_map.get(sort_by, ("composite_score", False))
    query = query.order(col, desc=not asc).limit(500)

    resp = _safe_execute(query, "get_articles")
    data = resp.data or []
    return pd.DataFrame(data) if data else pd.DataFrame()


def toggle_read(article_id: str, current: bool):
    sb = get_supabase()
    _safe_execute(
        sb.table("articles").update({"is_read": not current}).eq("id", article_id),
        "toggle_read"
    )


def log_fetch(articles_fetched: int, new_articles: int):
    sb = get_supabase()
    _safe_execute(
        sb.table("fetch_log").insert({
            "articles_fetched": articles_fetched,
            "new_articles": new_articles
        }),
        "log_fetch"
    )


def get_stats() -> dict:
    sb = get_supabase()
    try:
        total  = sb.table("articles").select("id", count="exact").execute().count or 0
        unread = sb.table("articles").select("id", count="exact").eq("is_read", False).execute().count or 0
        oa     = sb.table("articles").select("id", count="exact").eq("is_open_access", True).execute().count or 0
        log_resp = sb.table("fetch_log").select("fetched_at").order("fetched_at", desc=True).limit(1).execute()
        last_dt = None
        if log_resp.data:
            raw = log_resp.data[0]["fetched_at"]
            last_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        last_fetch = last_dt.strftime("%d %b %H:%M") if last_dt else None
        next_fetch = (last_dt + timedelta(days=7)).strftime("%d %b") if last_dt else None
    except Exception as e:
        st.warning(f"Stats error (non-fatal): {e}")
        total, unread, oa, last_fetch, next_fetch = 0, 0, 0, None, None
    return {"total": total, "unread": unread, "open_access": oa,
            "last_fetch": last_fetch, "next_fetch": next_fetch}


def get_last_fetch_time():
    sb = get_supabase()
    try:
        resp = sb.table("fetch_log").select("fetched_at").order("fetched_at", desc=True).limit(1).execute()
        if resp.data:
            raw = resp.data[0]["fetched_at"]
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    return None
