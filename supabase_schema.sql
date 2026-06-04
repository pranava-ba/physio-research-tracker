-- Run this in Supabase → SQL Editor → New query → Run
-- Creates both tables explicitly in the public schema.

CREATE TABLE IF NOT EXISTS public.articles (
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

CREATE TABLE IF NOT EXISTS public.fetch_log (
    id               SERIAL PRIMARY KEY,
    fetched_at       TIMESTAMPTZ DEFAULT NOW(),
    articles_fetched INTEGER,
    new_articles     INTEGER
);
