-- ====================================================================
-- RoleReady Initial Database Schema & Row-Level Security (RLS)
-- Author: Oussema Ferchichi (Backend Lead)
-- ====================================================================

-- 1. SESSIONS TABLE
CREATE TABLE IF NOT EXISTS public.sessions (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    target_role TEXT NOT NULL,
    experience_level TEXT NOT NULL DEFAULT 'mid',
    cv_text TEXT,
    job_text TEXT NOT NULL,
    cv_storage_path TEXT,
    strengths JSONB DEFAULT '[]'::jsonb,
    requirements_not_evidenced JSONB DEFAULT '[]'::jsonb,
    supporting_source_excerpts JSONB DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'created', -- 'created', 'analyzed', 'in_progress', 'completed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. QUESTIONS TABLE (7 questions per session)
CREATE TABLE IF NOT EXISTS public.questions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_order INT NOT NULL,
    text TEXT NOT NULL,
    target_skill TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'medium',
    reason_for_asking TEXT NOT NULL,
    reference_criteria TEXT NOT NULL,
    source_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. ANSWERS & EVALUATIONS TABLE
CREATE TABLE IF NOT EXISTS public.answers (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    original_transcript TEXT NOT NULL,
    corrected_transcript TEXT NOT NULL,
    rubric_version TEXT NOT NULL DEFAULT 'v1.0',
    correctness INT NOT NULL CHECK (correctness BETWEEN 1 AND 5),
    coverage INT NOT NULL CHECK (coverage BETWEEN 1 AND 5),
    relevance INT NOT NULL CHECK (relevance BETWEEN 1 AND 5),
    evidence_and_structure INT NOT NULL CHECK (evidence_and_structure BETWEEN 1 AND 5),
    overall_score NUMERIC(3, 2) NOT NULL CHECK (overall_score BETWEEN 1.0 AND 5.0),
    evidence JSONB DEFAULT '[]'::jsonb,
    feedback TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. FINAL REPORTS TABLE
CREATE TABLE IF NOT EXISTS public.reports (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES public.sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    average_score NUMERIC(3, 2) NOT NULL,
    priority_improvements JSONB NOT NULL DEFAULT '[]'::jsonb,
    cheat_sheet_content JSONB NOT NULL DEFAULT '{}'::jsonb,
    pdf_storage_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ====================================================================
-- ROW-LEVEL SECURITY (RLS) POLICIES
-- Ensures each candidate can only view, create, and delete their own data
-- ====================================================================

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- Sessions Policies
CREATE POLICY "Users can manage their own sessions"
ON public.sessions
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Questions Policies
CREATE POLICY "Users can view and manage their session questions"
ON public.questions
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Answers Policies
CREATE POLICY "Users can view and manage their session answers"
ON public.answers
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Reports Policies
CREATE POLICY "Users can view and manage their session reports"
ON public.reports
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- ====================================================================
-- STORAGE BUCKET INSTRUCTIONS (Run in Supabase Dashboard or SQL)
-- ====================================================================
-- insert into storage.buckets (id, name, public) 
-- values ('cv-uploads', 'cv-uploads', false)
-- on conflict do nothing;

-- create policy "Users can upload their own CV files"
-- on storage.objects for insert
-- with check (bucket_id = 'cv-uploads' and auth.uid()::text = (storage.foldername(name))[1]);

-- create policy "Users can read their own CV files"
-- on storage.objects for select
-- using (bucket_id = 'cv-uploads' and auth.uid()::text = (storage.foldername(name))[1]);
