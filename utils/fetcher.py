"""
Fetches articles from PubMed (E-utilities) and enriches with Semantic Scholar
citation data. Computes composite relevance scores.
"""
import requests
import xml.etree.ElementTree as ET
import hashlib
import math
import time
from datetime import datetime
from typing import Optional

# ─── Topic Search Queries ─────────────────────────────────────────────────────
TOPICS = {
    "meniscus": {
        "label": "Knee Meniscus Pain",
        "queries": [
            "knee meniscus degenerative pain treatment",
            "meniscal degeneration conservative management",
            "degenerative meniscus tear physical therapy",
            "meniscal pathology knee pain rehabilitation",
        ],
        "keywords": ["meniscus", "meniscal", "menisci", "knee pain", "degenerative", "tear"],
    },
    "perimenopause": {
        "label": "Perimenopausal Training",
        "queries": [
            "exercise training perimenopausal women",
            "physical activity perimenopause musculoskeletal",
            "resistance training menopause transition women",
            "strength training perimenopausal women outcomes",
        ],
        "keywords": ["perimenopause", "perimenopausal", "menopause", "menopausal transition",
                     "exercise", "training", "women", "hormonal"],
    },
    "crossleg": {
        "label": "Cross-Leg Sitting Pain",
        "queries": [
            "cross legged sitting medial knee pain",
            "sitting posture hip medial knee pain",
            "tailor position knee hip pain mechanism",
            "squatting sitting knee pain hip pain physiotherapy",
        ],
        "keywords": ["cross-legged", "sitting posture", "medial knee", "hip pain",
                     "tailor", "squat", "floor sitting", "knee hip"],
    },
}

# ─── Journal Tiers ────────────────────────────────────────────────────────────
JOURNAL_TIERS = {
    1: [
        "british journal of sports medicine",
        "american journal of sports medicine",
        "sports medicine",
        "journal of orthopaedic & sports physical therapy",
        "journal of orthopaedic and sports physical therapy",
        "jospt",
    ],
    2: [
        "journal of physiotherapy",
        "physical therapy",
        "clinical rehabilitation",
        "osteoarthritis and cartilage",
        "menopause",
        "journal of bone and joint surgery",
        "knee surgery sports traumatology arthroscopy",
        "arthroscopy",
        "physiotherapy",
    ],
    3: [
        "physical therapy in sport",
        "journal of sport rehabilitation",
        "international journal of sports physical therapy",
        "musculoskeletal science and practice",
        "pm&r",
        "disability and rehabilitation",
        "scandinavian journal of medicine & science in sports",
    ],
}
TIER_SCORES = {1: 100, 2: 70, 3: 40, 4: 20}

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def get_journal_tier(journal_name: str) -> int:
    if not journal_name:
        return 4
    jl = journal_name.lower().strip()
    for tier, journals in JOURNAL_TIERS.items():
        if any(j in jl for j in journals):
            return tier
    return 4


def pubmed_search(query: str, max_results: int = 30) -> list:
    try:
        resp = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params={
            "db": "pubmed",
            "term": query + "[Title/Abstract]",
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "datetype": "pdat",
            "mindate": "2015",
            "maxdate": str(datetime.now().year),
        }, timeout=15)
        resp.raise_for_status()
        return resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"PubMed search error: {e}")
        return []


def pubmed_fetch_details(pmids: list) -> list:
    if not pmids:
        return []
    try:
        resp = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params={
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }, timeout=30)
        resp.raise_for_status()
        return parse_pubmed_xml(resp.text)
    except Exception as e:
        print(f"PubMed fetch error: {e}")
        return []


def parse_pubmed_xml(xml_text: str) -> list:
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for article_node in root.findall(".//PubmedArticle"):
        try:
            med = article_node.find("MedlineCitation")
            art = med.find("Article")

            pmid = med.findtext("PMID", "")
            title = (art.findtext("ArticleTitle", "") or "").strip()

            abstract_parts = art.findall(".//AbstractText")
            abstract = " ".join(
                (p.get("Label", "") + ": " + (p.text or "") if p.get("Label") else (p.text or ""))
                for p in abstract_parts
            ).strip()

            journal = art.findtext("Journal/Title", "") or art.findtext("Journal/ISOAbbreviation", "") or ""

            doi = ""
            for id_node in article_node.findall(".//ArticleId"):
                if id_node.get("IdType") == "doi":
                    doi = id_node.text or ""

            is_oa = any(
                id_node.get("IdType") == "pmc"
                for id_node in article_node.findall(".//ArticleId")
            )

            author_list = art.find("AuthorList")
            authors = ""
            if author_list is not None:
                names = []
                for a in author_list.findall("Author")[:3]:
                    last = a.findtext("LastName", "")
                    fore = a.findtext("ForeName", "")
                    if last:
                        names.append(f"{last} {fore[:1]}." if fore else last)
                if len(author_list.findall("Author")) > 3:
                    names.append("et al.")
                authors = ", ".join(names)

            year_node = art.find(".//PubDate/Year")
            pub_year = int(year_node.text) if year_node is not None and year_node.text else 2020

            month_raw = art.findtext(".//PubDate/Month", "01") or "01"
            month = MONTH_MAP.get(month_raw[:3].lower(), "01") if not month_raw.isdigit() else month_raw.zfill(2)
            pub_date = f"{pub_year}-{month}"

            articles.append({
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": journal,
                "pub_year": pub_year,
                "pub_date": pub_date,
                "doi": doi,
                "abstract": abstract,
                "is_open_access": is_oa,
            })
        except Exception as e:
            print(f"Parse error: {e}")
            continue

    return articles


def get_semantic_scholar_citations(doi: str = "", title: str = "") -> Optional[dict]:
    try:
        if doi:
            resp = requests.get(
                f"{SEMANTIC_SCHOLAR_BASE}/paper/DOI:{doi}",
                params={"fields": "citationCount,year,openAccessPdf"},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        if title:
            resp = requests.get(
                f"{SEMANTIC_SCHOLAR_BASE}/paper/search",
                params={"query": title[:100], "fields": "citationCount,year,openAccessPdf", "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                hits = resp.json().get("data", [])
                if hits:
                    return hits[0]
    except Exception:
        pass
    return None


def compute_topic_score(title: str, abstract: str, topic_key: str) -> float:
    keywords = TOPICS[topic_key]["keywords"]
    text = (title + " " + abstract).lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return min(100.0, (hits / max(len(keywords), 1)) * 150)


def compute_composite_score(pub_year, citations_per_year, journal_tier, topic_score, is_open_access) -> float:
    age = max(0, datetime.now().year - pub_year)
    recency = max(0, 100 * (0.84 ** age))
    cit_score = min(100, math.log1p(citations_per_year) / math.log1p(10) * 100)
    prestige = TIER_SCORES.get(journal_tier, 20)
    oa = 100 if is_open_access else 0
    return round(0.30 * recency + 0.35 * cit_score + 0.20 * prestige + 0.10 * topic_score + 0.05 * oa, 2)


def make_id(pmid: str, topic: str) -> str:
    return hashlib.md5(f"{pmid}_{topic}".encode()).hexdigest()[:16]


def run_fetch() -> dict:
    from utils.database import upsert_articles, log_fetch

    all_records = []

    for topic_key, topic_info in TOPICS.items():
        seen_pmids: set = set()

        for query in topic_info["queries"]:
            pmids = pubmed_search(query, max_results=25)
            new_pmids = [p for p in pmids if p not in seen_pmids]
            seen_pmids.update(new_pmids)
            if not new_pmids:
                continue

            articles = pubmed_fetch_details(new_pmids)

            for art in articles:
                art["topic"] = topic_key
                art["id"] = make_id(art["pmid"], topic_key)

                ss = get_semantic_scholar_citations(doi=art.get("doi", ""), title=art["title"])
                citations = 0
                if ss:
                    citations = ss.get("citationCount") or 0
                    if ss.get("openAccessPdf"):
                        art["is_open_access"] = True

                age = max(1, datetime.now().year - art["pub_year"])
                art["citation_count"] = citations
                art["citations_per_year"] = round(citations / age, 2)
                art["journal_tier"] = get_journal_tier(art["journal"])
                art["topic_score"] = compute_topic_score(art["title"], art["abstract"], topic_key)
                art["composite_score"] = compute_composite_score(
                    art["pub_year"], art["citations_per_year"],
                    art["journal_tier"], art["topic_score"], art["is_open_access"]
                )
                art["fetched_at"] = datetime.now()
                all_records.append(art)
                time.sleep(0.12)

            time.sleep(0.35)

    new_count = upsert_articles(all_records)
    log_fetch(len(all_records), new_count)
    return {"success": True, "new_articles": new_count, "total_fetched": len(all_records)}
