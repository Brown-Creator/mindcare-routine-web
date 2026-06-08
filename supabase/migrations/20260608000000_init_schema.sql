-- ==========================================
-- MindCare Routine Database Schema & RLS Setup
-- Migration: 20260608000000_init_schema.sql
-- ==========================================

-- 1. Profiles Table
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nickname VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    CONSTRAINT unique_user_profile UNIQUE (user_id)
);

-- 2. Consents Table
CREATE TABLE public.consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agreed_age_19 BOOLEAN DEFAULT FALSE NOT NULL,
    agreed_terms BOOLEAN DEFAULT FALSE NOT NULL,
    agreed_privacy BOOLEAN DEFAULT FALSE NOT NULL,
    agreed_sensitive_data BOOLEAN DEFAULT FALSE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 3. Mood Entries Table
CREATE TABLE public.mood_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    mood INTEGER CHECK (mood >= 1 AND mood <= 10) NOT NULL,
    stress INTEGER CHECK (stress >= 1 AND stress <= 10) NOT NULL,
    sleep INTEGER CHECK (sleep >= 1 AND sleep <= 10) NOT NULL,
    energy INTEGER CHECK (energy >= 1 AND energy <= 10) NOT NULL,
    emotions TEXT[] NOT NULL,
    note TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 4. Thought Records Table
CREATE TABLE public.thought_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    situation TEXT NOT NULL,
    automatic_thought TEXT NOT NULL,
    emotions TEXT NOT NULL,
    evidence_for TEXT NOT NULL,
    evidence_against TEXT NOT NULL,
    alternative_thought TEXT NOT NULL,
    next_action TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 5. Behavioral Activation Sessions Table
CREATE TABLE public.activation_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id VARCHAR(50) NOT NULL,
    task_title VARCHAR(100) NOT NULL,
    mood_before INTEGER CHECK (mood_before >= 1 AND mood_before <= 10) NOT NULL,
    mood_after INTEGER CHECK (mood_after >= 1 AND mood_after <= 10) NOT NULL,
    completed BOOLEAN DEFAULT TRUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 6. Mindfulness Sessions Table
CREATE TABLE public.mindfulness_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    exercise_id VARCHAR(50) NOT NULL,
    exercise_title VARCHAR(100) NOT NULL,
    duration_minutes INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 7. Journal Entries Table
CREATE TABLE public.journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prompt_id VARCHAR(50) NOT NULL,
    prompt_text TEXT NOT NULL,
    answers JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 8. Screening Results Table
CREATE TABLE public.screening_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type VARCHAR(20) CHECK (type IN ('PHQ-9', 'GAD-7')) NOT NULL,
    answers INTEGER[] NOT NULL,
    total_score INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 9. Safety Events Table (최소 로깅 원칙)
CREATE TABLE public.safety_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    trigger_type VARCHAR(50) CHECK (trigger_type IN ('KEYWORD', 'PHQ9_ITEM9')) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 10. Audit Logs Table (개인정보 관리 감사)
CREATE TABLE public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ==========================================
-- Enable Row Level Security (RLS) on all tables
-- ==========================================
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mood_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thought_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activation_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mindfulness_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.screening_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.safety_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- ==========================================
-- Create RLS Policies
-- ==========================================

-- 1. Profiles: Own profile read/write
CREATE POLICY "Users can manage their own profiles" ON public.user_profiles
    FOR ALL USING (auth.uid() = user_id);

-- 2. Consents: Own consent read/write
CREATE POLICY "Users can manage their own consents" ON public.consents
    FOR ALL USING (auth.uid() = user_id);

-- 3. Mood Entries: Own mood read/write
CREATE POLICY "Users can manage their own mood entries" ON public.mood_entries
    FOR ALL USING (auth.uid() = user_id);

-- 4. Thought Records: Own records read/write
CREATE POLICY "Users can manage their own thought records" ON public.thought_records
    FOR ALL USING (auth.uid() = user_id);

-- 5. Activation Tasks: Own tasks read/write
CREATE POLICY "Users can manage their own activation tasks" ON public.activation_tasks
    FOR ALL USING (auth.uid() = user_id);

-- 6. Mindfulness Sessions: Own sessions read/write
CREATE POLICY "Users can manage their own mindfulness sessions" ON public.mindfulness_sessions
    FOR ALL USING (auth.uid() = user_id);

-- 7. Journal Entries: Own journals read/write
CREATE POLICY "Users can manage their own journal entries" ON public.journal_entries
    FOR ALL USING (auth.uid() = user_id);

-- 8. Screening Results: Own results read/write
CREATE POLICY "Users can manage their own screening results" ON public.screening_results
    FOR ALL USING (auth.uid() = user_id);

-- 9. Safety Events: Insert own events, read own events
CREATE POLICY "Users can manage their own safety events" ON public.safety_events
    FOR ALL USING (auth.uid() = user_id);

-- 10. Audit Logs: Insert own logs, read own logs
CREATE POLICY "Users can manage their own audit logs" ON public.audit_logs
    FOR ALL USING (auth.uid() = user_id);
