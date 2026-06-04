-- Run this in Supabase → SQL Editor → New query → Run
-- Disables RLS and grants full anon access.

ALTER TABLE public.articles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.fetch_log DISABLE ROW LEVEL SECURITY;

GRANT ALL ON public.articles  TO anon;
GRANT ALL ON public.fetch_log TO anon;
GRANT USAGE, SELECT ON SEQUENCE public.fetch_log_id_seq TO anon;
