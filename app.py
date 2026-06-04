import streamlit as st
import pandas as pd
from datetime import datetime
from utils.database import get_articles, toggle_read, get_stats
from utils.fetcher import run_fetch
from utils.scheduler import check_and_run_scheduled_fetch
import time

st.set_page_config(
    page_title="PhysioResearch Tracker",
    page_icon="🦴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global styles (layout + typography only, no card HTML) ───────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Outfit', sans-serif !important;
}
h1 { font-family: 'DM Serif Display', serif !important; }

/* Sidebar */
[data-testid="stSidebar"] { background-color: #0f1117 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #1e2233;
    border: 1px solid #2a2f3e;
    border-radius: 10px;
    padding: 14px 18px !important;
}

/* Buttons */
.stButton > button {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
}

/* Expander */
[data-testid="stExpander"] { border-radius: 10px !important; }

div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
</style>
""", unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────
TOPIC_OPTIONS = {
    "All Topics": None,
    "🦵 Knee Meniscus Pain": "meniscus",
    "🏃‍♀️ Perimenopausal Training": "perimenopause",
    "🧘 Cross-Leg Sitting Pain": "crossleg",
}
TOPIC_LABELS = {
    "meniscus":      "🦵 Knee Meniscus",
    "perimenopause": "🏃‍♀️ Perimenopause",
    "crossleg":      "🧘 Cross-Leg Pain",
}
JOURNAL_OPTIONS = [
    "All Journals",
    "British Journal of Sports Medicine",
    "Journal of Orthopaedic & Sports Physical Therapy",
    "Journal of Physiotherapy",
    "Sports Medicine",
    "American Journal of Sports Medicine",
    "Physical Therapy",
    "Clinical Rehabilitation",
    "Osteoarthritis and Cartilage",
    "Menopause",
]
SORT_OPTIONS = [
    "Composite Score ↓",
    "Date (Newest First)",
    "Citation Velocity ↓",
    "Journal Prestige ↓",
]

# ─── Init ─────────────────────────────────────────────────────────────────────
if "initialized" not in st.session_state:
    st.session_state.initialized = True

check_and_run_scheduled_fetch()

# ─── Header ───────────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("🦴 PhysioResearch Tracker")
    st.caption("Evidence-based clinical research · PubMed + Semantic Scholar · Auto-updates weekly")

with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⟳ Refresh Now", use_container_width=True, type="primary"):
        with st.spinner("Fetching from PubMed & Semantic Scholar… (~2–4 min)"):
            result = run_fetch()
        if result["success"]:
            st.success(f"✓ {result['new_articles']} new articles added ({result['total_fetched']} fetched total)")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"Fetch failed: {result.get('error', 'Unknown error')}")

st.divider()

# ─── Stats ────────────────────────────────────────────────────────────────────
stats = get_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📄 Total Articles", stats["total"])
c2.metric("📬 Unread", stats["unread"])
c3.metric("🔓 Open Access", stats["open_access"])
c4.metric("🕐 Last Fetch", stats["last_fetch"] or "Never")
c5.metric("📅 Next Auto-Fetch", stats["next_fetch"] or "—")

st.divider()

# ─── Sidebar Filters ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 Filters")

    topic_label = st.selectbox("Topic", list(TOPIC_OPTIONS.keys()))
    selected_topic = TOPIC_OPTIONS[topic_label]

    read_filter = st.selectbox("Read Status", ["All", "Unread Only", "Read Only"])

    oa_only = st.checkbox("🔓 Open Access Only")

    selected_journal = st.selectbox("Journal", JOURNAL_OPTIONS)
    journal_val = None if selected_journal == "All Journals" else selected_journal

    year_min = st.slider("Published After", 2015, datetime.now().year, 2019)

    sort_by = st.selectbox("Sort By", SORT_OPTIONS)

    st.divider()

    st.markdown("#### 📊 Scoring Breakdown")
    st.markdown("""
| Factor | Weight |
|--------|--------|
| Citation velocity | **35%** |
| Recency | **30%** |
| Journal prestige | **20%** |
| Topic match | **10%** |
| Open access | **5%** |
""")

    st.divider()
    with st.expander("ℹ️ About"):
        st.markdown("""
**Sources:** PubMed E-utilities + Semantic Scholar

**Journals tracked (Tier 1):**
- BJSM, AJSM, Sports Medicine, JOSPT

**Paywalled articles** are included — you'll see metadata + abstract for all papers. The 🔓 badge marks those freely readable in full.

**Read/unread** state is shared — marking something read is visible to everyone using this app.
        """)

# ─── Article Query ────────────────────────────────────────────────────────────
read_map = {"All": None, "Unread Only": False, "Read Only": True}
df = get_articles(
    topic=selected_topic,
    read_status=read_map[read_filter],
    open_access_only=oa_only,
    journal=journal_val,
    year_min=year_min,
    sort_by=sort_by,
)

# ─── Toolbar ──────────────────────────────────────────────────────────────────
col_count, col_export = st.columns([4, 1])
with col_count:
    st.markdown(f"**{len(df)} articles** match your filters")
with col_export:
    if not df.empty:
        export_df = df.drop(columns=["id"], errors="ignore")
        st.download_button(
            "⬇ Export CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=f"physio_research_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("")

# ─── Article Cards ────────────────────────────────────────────────────────────
if df.empty:
    st.info("No articles found. Adjust your filters or click **⟳ Refresh Now** to fetch articles.", icon="🔍")
else:
    for _, row in df.iterrows():
        is_read = bool(row.get("is_read", False))
        score = float(row.get("composite_score", 0))
        citations = int(row.get("citation_count", 0) or 0)
        cit_vel = float(row.get("citations_per_year", 0) or 0)
        doi = str(row.get("doi", "") or "")
        topic_key = str(row.get("topic", ""))
        is_oa = bool(row.get("is_open_access", False))
        pub_year = str(row.get("pub_year", ""))
        journal = str(row.get("journal", "") or "")
        title = str(row.get("title", "") or "(No title)")
        authors = str(row.get("authors", "") or "")
        abstract = str(row.get("abstract", "") or "")

        with st.container(border=True):
            # Row 1: badges + score
            b1, b2, b3, b4, b_score = st.columns([2, 2.5, 1.2, 1, 1])
            b1.markdown(f"**{TOPIC_LABELS.get(topic_key, topic_key)}**")
            b2.caption(journal[:55] + ("…" if len(journal) > 55 else ""))
            b3.markdown("🔓 Open Access" if is_oa else "🔒 Paywalled")
            b4.markdown(f"`{pub_year}`")
            b_score.markdown(
                f"<span style='background:linear-gradient(135deg,#4f9cf9,#a78bfa);"
                f"color:white;padding:3px 10px;border-radius:20px;"
                f"font-size:0.8rem;font-weight:600'>★ {score:.0f}</span>",
                unsafe_allow_html=True,
            )

            # Row 2: title (greyed if read)
            title_style = "color:#6b7280;" if is_read else ""
            st.markdown(
                f"<p style='font-size:1.05rem;font-weight:600;margin:4px 0 2px 0;{title_style}'>{title}</p>",
                unsafe_allow_html=True,
            )

            # Row 3: authors + citation info + DOI link
            meta_parts = []
            if authors:
                meta_parts.append(authors)
            meta_parts.append(f"{citations} citations ({cit_vel:.1f}/yr)")
            if doi:
                meta_parts.append(f"[↗ doi.org/{doi[:30]}{'…' if len(doi)>30 else ''}](https://doi.org/{doi})")
            st.caption("  ·  ".join(meta_parts))

            # Row 4: abstract (collapsed by default)
            if abstract:
                with st.expander("Abstract", expanded=False):
                    st.write(abstract)

            # Row 5: read toggle
            btn_col, _ = st.columns([1, 5])
            with btn_col:
                btn_label = "✓ Mark Unread" if is_read else "Mark as Read"
                if st.button(btn_label, key=f"toggle_{row['id']}", use_container_width=True):
                    toggle_read(row["id"], is_read)
                    st.rerun()
