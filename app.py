import streamlit as st
import pandas as pd
from datetime import datetime
from utils.database import (
    get_articles, toggle_read, get_stats, check_connection,
    get_custom_topics, save_custom_topic, delete_custom_topic,
)
from utils.fetcher import (
    run_fetch, fetch_custom_topic_now, build_queries_for_keyword, TOPICS,
)
from utils.scheduler import check_and_run_scheduled_fetch
import time
import re

st.set_page_config(
    page_title="PhysioResearch Tracker",
    page_icon="🦴",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');
html, body, [data-testid="stAppViewContainer"] { font-family: 'Outfit', sans-serif !important; }
h1 { font-family: 'DM Serif Display', serif !important; }
[data-testid="stSidebar"] { background-color: #0f1117 !important; }
[data-testid="metric-container"] {
    background: #1e2233; border: 1px solid #2a2f3e;
    border-radius: 10px; padding: 14px 18px !important;
}
.stButton > button { font-family: 'Outfit', sans-serif !important; font-weight: 500 !important; border-radius: 8px !important; }
[data-testid="stExpander"] { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────

BUILTIN_TOPIC_LABELS = {
    "meniscus":      "🦵 Knee Meniscus Pain",
    "perimenopause": "🏃‍♀️ Perimenopausal Training",
    "crossleg":      "🧘 Cross-Leg Sitting Pain",
}

JOURNAL_LIST = [
    "British Journal of Sports Medicine",
    "Journal of Orthopaedic & Sports Physical Therapy",
    "Journal of Physiotherapy",
    "Sports Medicine",
    "American Journal of Sports Medicine",
    "Physical Therapy",
    "Clinical Rehabilitation",
    "Osteoarthritis and Cartilage",
    "Menopause",
    "Arthroscopy",
    "Knee Surgery Sports Traumatology Arthroscopy",
    "Physical Therapy in Sport",
    "Journal of Sport Rehabilitation",
    "Disability and Rehabilitation",
]

SORT_OPTIONS = [
    "Composite Score ↓",
    "Date (Newest First)",
    "Citation Velocity ↓",
    "Journal Prestige ↓",
]

SECTION_ORDER = ["BACKGROUND", "OBJECTIVE", "METHODS", "RESULTS", "CONCLUSIONS", "CONCLUSION"]
SECTION_ICONS = {
    "BACKGROUND":  "📋",
    "OBJECTIVE":   "🎯",
    "METHODS":     "🔬",
    "RESULTS":     "📊",
    "CONCLUSIONS": "💡",
    "CONCLUSION":  "💡",
}


def parse_abstract(abstract: str) -> dict | None:
    """
    Try to parse a structured abstract (BACKGROUND: ... METHODS: ... etc.)
    Returns dict of {SECTION: text} if structured, else None.
    """
    pattern = r'\b(BACKGROUND|OBJECTIVE|METHODS?|RESULTS?|CONCLUSIONS?|PURPOSE|DESIGN|SETTING|PARTICIPANTS?|INTERVENTIONS?|MAIN OUTCOMES?)\s*:\s*'
    parts   = re.split(pattern, abstract, flags=re.IGNORECASE)
    if len(parts) < 3:
        return None
    sections = {}
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].strip().upper().rstrip("S") + ("S" if parts[i].strip().upper() in
              ["RESULTS", "CONCLUSIONS", "METHODS", "PARTICIPANTS", "INTERVENTIONS"] else "")
        key = parts[i].strip().upper()
        val = parts[i + 1].strip()
        if val:
            sections[key] = val
    return sections if len(sections) >= 2 else None


def render_abstract(abstract: str):
    """Render abstract in a clean, readable format inside an expander."""
    if not abstract:
        return
    with st.expander("📄 Abstract", expanded=False):
        sections = parse_abstract(abstract)
        if sections:
            # Structured abstract — render each section clearly
            for section in SECTION_ORDER:
                if section in sections:
                    icon = SECTION_ICONS.get(section, "•")
                    st.markdown(f"**{icon} {section.title()}**")
                    st.markdown(
                        f"<p style='font-size:0.85rem;color:#cbd5e1;line-height:1.65;margin:0 0 12px 0'>{sections[section]}</p>",
                        unsafe_allow_html=True,
                    )
            # Any sections not in our order list
            for key, val in sections.items():
                if key not in SECTION_ORDER:
                    st.markdown(f"**{key.title()}**")
                    st.markdown(
                        f"<p style='font-size:0.85rem;color:#cbd5e1;line-height:1.65;margin:0 0 12px 0'>{val}</p>",
                        unsafe_allow_html=True,
                    )
        else:
            # Unstructured — show first 2 sentences as preview, rest behind toggle
            sentences  = re.split(r'(?<=[.!?])\s+', abstract.strip())
            preview    = " ".join(sentences[:2])
            remainder  = " ".join(sentences[2:]) if len(sentences) > 2 else ""
            st.markdown(
                f"<p style='font-size:0.85rem;color:#cbd5e1;line-height:1.65;margin:0'>{preview}</p>",
                unsafe_allow_html=True,
            )
            if remainder:
                with st.expander("Read full abstract", expanded=False):
                    st.markdown(
                        f"<p style='font-size:0.85rem;color:#94a3b8;line-height:1.65'>{remainder}</p>",
                        unsafe_allow_html=True,
                    )


# ─── Init ─────────────────────────────────────────────────────────────────────
check_connection()
check_and_run_scheduled_fetch()

# Load custom topics once per session
if "custom_topics" not in st.session_state:
    st.session_state.custom_topics = get_custom_topics()

custom_topics     = st.session_state.custom_topics
custom_topic_map  = {ct["id"]: ct["label"] for ct in custom_topics}
all_topic_labels  = {**BUILTIN_TOPIC_LABELS, **custom_topic_map}

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
            st.success(f"✓ {result['new_articles']} new · {result['total_fetched']} fetched")
            time.sleep(1.2)
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

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 Filters")

    # ── Topic multi-select ──
    topic_display   = list(all_topic_labels.values())
    topic_key_index = {v: k for k, v in all_topic_labels.items()}
    selected_topic_labels = st.multiselect(
        "Topics", topic_display, placeholder="All topics"
    )
    selected_topics = [topic_key_index[l] for l in selected_topic_labels] or None

    # ── Read status ──
    read_filter = st.selectbox("Read Status", ["All", "Unread Only", "Read Only"])

    # ── Open access ──
    oa_only = st.checkbox("🔓 Open Access Only")

    # ── Journal multi-select ──
    selected_journals = st.multiselect(
        "Journals", JOURNAL_LIST, placeholder="All journals"
    )
    journals_val = selected_journals if selected_journals else None

    # ── Year ──
    year_min = st.slider("Published After", 2015, datetime.now().year, 2019)

    # ── Sort ──
    sort_by = st.selectbox("Sort By", SORT_OPTIONS)

    # ── Keyword search ──
    st.divider()
    st.markdown("#### 🔍 Keyword Search")
    keyword_search = st.text_input(
        "Search title & abstract",
        placeholder="e.g. rotator cuff, ACL, sarcopenia…",
        help="Filters the current results in real time. Does not fetch new articles.",
    )

    # ─── Add Custom Topic ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### ➕ Add Permanent Topic")
    with st.expander("New topic", expanded=False):
        new_label   = st.text_input("Display name", placeholder="e.g. Rotator Cuff Tears")
        new_keyword = st.text_input("Search keyword", placeholder="e.g. rotator cuff tear physiotherapy")
        new_kw_list = st.text_input(
            "Highlight keywords (comma-separated)",
            placeholder="rotator cuff, shoulder, impingement",
            help="Used for topic-match scoring. Include synonyms.",
        )
        col_add, col_info = st.columns([1, 1])
        with col_add:
            add_btn = st.button("Add & Fetch", use_container_width=True, type="primary")
        with col_info:
            st.caption("Fetches from PubMed and saves permanently for all users.")

        if add_btn:
            if not new_label.strip() or not new_keyword.strip():
                st.warning("Please fill in both the display name and search keyword.")
            else:
                keywords_list = [k.strip() for k in new_kw_list.split(",") if k.strip()] or [new_keyword.strip()]
                queries       = build_queries_for_keyword(new_keyword)
                import hashlib
                topic_id = "custom_" + hashlib.md5(new_keyword.lower().encode()).hexdigest()[:10]

                saved = save_custom_topic(new_label.strip(), new_keyword.strip(), queries, keywords_list)
                if saved:
                    with st.spinner(f"Fetching articles for '{new_label}'…"):
                        result = fetch_custom_topic_now(topic_id, queries, keywords_list)
                    st.success(f"✓ Added '{new_label}' · {result['new_articles']} new articles")
                    # Refresh custom topics in session
                    st.session_state.custom_topics = get_custom_topics()
                    time.sleep(1)
                    st.rerun()

    # ─── Manage Custom Topics ─────────────────────────────────────────────────
    if custom_topics:
        st.divider()
        st.markdown("#### 🗂 Custom Topics")
        for ct in custom_topics:
            col_name, col_del = st.columns([3, 1])
            col_name.markdown(f"**{ct['label']}**")
            if col_del.button("✕", key=f"del_{ct['id']}", help="Delete this topic"):
                delete_custom_topic(ct["id"])
                st.session_state.custom_topics = get_custom_topics()
                st.rerun()

    # ─── Scoring info ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("📊 Scoring & Info"):
        st.markdown("""
**Score formula:**

| Factor | Weight |
|--------|--------|
| Citation velocity | **35%** |
| Recency | **30%** |
| Journal prestige | **20%** |
| Topic match | **10%** |
| Open access | **5%** |

**Sources:** PubMed + Semantic Scholar

**Paywalled articles are included.** 🔒 = paywalled, 🔓 = free full text.

**Read/unread** state is shared across all users.
        """)

# ─── Article Query ────────────────────────────────────────────────────────────
read_map = {"All": None, "Unread Only": False, "Read Only": True}
df = get_articles(
    topics=selected_topics,
    read_status=read_map[read_filter],
    open_access_only=oa_only,
    journals=journals_val,
    year_min=year_min,
    sort_by=sort_by,
    keyword_search=keyword_search or None,
)

# ─── Toolbar ──────────────────────────────────────────────────────────────────
col_count, col_export = st.columns([4, 1])
with col_count:
    st.markdown(f"**{len(df)} articles** match your filters")
with col_export:
    if not df.empty:
        st.download_button(
            "⬇ Export CSV",
            data=df.drop(columns=["id"], errors="ignore").to_csv(index=False).encode("utf-8"),
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
        is_read   = bool(row.get("is_read", False))
        score     = float(row.get("composite_score", 0))
        citations = int(row.get("citation_count", 0) or 0)
        cit_vel   = float(row.get("citations_per_year", 0) or 0)
        doi       = str(row.get("doi", "") or "")
        topic_key = str(row.get("topic", ""))
        is_oa     = bool(row.get("is_open_access", False))
        pub_year  = str(row.get("pub_year", ""))
        journal   = str(row.get("journal", "") or "")
        title     = str(row.get("title", "") or "(No title)")
        authors   = str(row.get("authors", "") or "")
        abstract  = str(row.get("abstract", "") or "")
        topic_label = all_topic_labels.get(topic_key, topic_key)

        with st.container(border=True):
            # Row 1: topic · journal · access · year · score
            b1, b2, b3, b4, b_score = st.columns([2, 3, 1.2, 0.8, 1])
            b1.markdown(f"**{topic_label}**")
            b2.caption(journal[:60] + ("…" if len(journal) > 60 else ""))
            b3.markdown("🔓 Free" if is_oa else "🔒 Paywalled")
            b4.markdown(f"`{pub_year}`")
            b_score.markdown(
                f"<span style='background:linear-gradient(135deg,#4f9cf9,#a78bfa);"
                f"color:white;padding:3px 10px;border-radius:20px;"
                f"font-size:0.8rem;font-weight:600'>★ {score:.0f}</span>",
                unsafe_allow_html=True,
            )

            # Row 2: title
            title_colour = "#6b7280" if is_read else "#f1f5f9"
            st.markdown(
                f"<p style='font-size:1.05rem;font-weight:600;margin:4px 0 2px 0;color:{title_colour}'>{title}</p>",
                unsafe_allow_html=True,
            )

            # Row 3: authors · citations · DOI
            meta_parts = []
            if authors:
                meta_parts.append(authors)
            meta_parts.append(f"{citations} citations · {cit_vel:.1f}/yr")
            if doi:
                meta_parts.append(f"[↗ Full text / DOI](https://doi.org/{doi})")
            st.caption("  ·  ".join(meta_parts))

            # Row 4: abstract (structured or truncated)
            render_abstract(abstract)

            # Row 5: read toggle
            btn_col, _ = st.columns([1, 5])
            with btn_col:
                btn_label = "✓ Mark Unread" if is_read else "Mark as Read"
                if st.button(btn_label, key=f"toggle_{row['id']}", use_container_width=True):
                    toggle_read(row["id"], is_read)
                    st.rerun()
