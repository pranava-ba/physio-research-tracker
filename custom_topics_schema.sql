-- Run this in Supabase → SQL Editor → New query → Run
-- Adds the custom_topics table for user-defined permanent topics.

CREATE TABLE IF NOT EXISTS public.custom_topics (
    id           VARCHAR PRIMARY KEY,
    label        VARCHAR NOT NULL,
    keyword      VARCHAR NOT NULL,
    queries      TEXT NOT NULL,       -- JSON array of search queries
    keywords_csv TEXT NOT NULL,       -- comma-separated keyword list
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.custom_topics DISABLE ROW LEVEL SECURITY;
GRANT ALL ON public.custom_topics TO anon;
