"""
Weekly auto-fetch scheduler for Streamlit Cloud.
Uses a threading flag to avoid duplicate fetches within a session.
"""
import threading
import streamlit as st
from datetime import datetime, timedelta, timezone

_fetch_lock = threading.Lock()


def check_and_run_scheduled_fetch():
    """Called on every app load. Silently triggers background fetch if overdue."""
    # Only trigger once per session
    if st.session_state.get("_scheduler_checked"):
        return
    st.session_state["_scheduler_checked"] = True

    from utils.database import get_last_fetch_time
    last = get_last_fetch_time()

    should_fetch = (last is None) or (
        datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)
        >= timedelta(days=7)
    )

    if should_fetch:
        _trigger_background_fetch()


def _trigger_background_fetch():
    if not _fetch_lock.acquire(blocking=False):
        return  # already running

    def _run():
        try:
            from utils.fetcher import run_fetch
            run_fetch()
        except Exception as e:
            print(f"[Scheduler] Background fetch error: {e}")
        finally:
            _fetch_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
