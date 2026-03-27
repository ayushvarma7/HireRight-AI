-- =============================================================
-- HireRight AI | Supabase Schema (canonical, up-to-date)
-- Apply in: Supabase Dashboard → SQL Editor → New query
-- =============================================================

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================
-- TABLE: jobs
-- =============================================================
CREATE TABLE IF NOT EXISTS jobs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title            text NOT NULL,
  company          text NOT NULL,
  location         text,
  description      text,
  url              text,
  source_url       text UNIQUE,
  source_platform  text,
  job_type         text,
  remote_type      text,
  experience_level text,
  years_experience_min int,
  years_experience_max int,
  required_skills  jsonb DEFAULT '[]',
  preferred_skills jsonb DEFAULT '[]',
  salary_min       int,
  salary_max       int,
  salary_currency  text DEFAULT 'USD',
  embedding        vector(768),
  is_active        boolean DEFAULT true,
  posted_at        timestamptz,
  expires_at       timestamptz,
  scraped_at       timestamptz DEFAULT now()
);

-- lists=1 is correct for small datasets (<500 rows); upgrade to HNSW once >1000 rows
CREATE INDEX IF NOT EXISTS jobs_embedding_idx
  ON jobs USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 1);

CREATE INDEX IF NOT EXISTS jobs_title_fts_idx
  ON jobs USING gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')));

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read/write (dev)" ON jobs FOR ALL USING (true) WITH CHECK (true);


-- =============================================================
-- TABLE: user_profiles
-- =============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                   text,
  email                  text,
  github_username        text,
  raw_resume_text        text,
  experience_summary     text,
  total_years_experience float DEFAULT 0,
  skills                 jsonb DEFAULT '[]',
  skill_categories       jsonb DEFAULT '{}',
  education              jsonb DEFAULT '[]',
  work_history           jsonb DEFAULT '[]',
  resume_embedding       vector(768),
  session_id             text UNIQUE,
  created_at             timestamptz DEFAULT now(),
  updated_at             timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_profiles_session_idx
  ON user_profiles(session_id);

CREATE INDEX IF NOT EXISTS user_profiles_embedding_idx
  ON user_profiles USING ivfflat (resume_embedding vector_cosine_ops)
  WITH (lists = 10);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public access (dev)" ON user_profiles FOR ALL USING (true) WITH CHECK (true);


-- =============================================================
-- TABLE: match_results
-- =============================================================
CREATE TABLE IF NOT EXISTS match_results (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_profile_id  uuid REFERENCES user_profiles(id) ON DELETE CASCADE,
  job_id           uuid REFERENCES jobs(id) ON DELETE CASCADE,
  vector_score     float,
  recruiter_score  float,
  coach_score      float,
  final_score      float,
  recommendation   text,
  confidence       float,
  debate_rounds    jsonb DEFAULT '[]',
  key_strengths    jsonb DEFAULT '[]',
  key_concerns     jsonb DEFAULT '[]',
  missing_skills   jsonb DEFAULT '[]',
  must_address     jsonb DEFAULT '[]',
  cover_letter     text,
  total_rounds     int DEFAULT 1,
  processing_time_s float,
  created_at       timestamptz DEFAULT now(),
  UNIQUE (user_profile_id, job_id)
);

CREATE INDEX IF NOT EXISTS match_results_user_idx  ON match_results(user_profile_id);
CREATE INDEX IF NOT EXISTS match_results_job_idx   ON match_results(job_id);
CREATE INDEX IF NOT EXISTS match_results_score_idx ON match_results(final_score DESC);

ALTER TABLE match_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public access (dev)" ON match_results FOR ALL USING (true) WITH CHECK (true);


-- =============================================================
-- TABLE: job_applications
-- =============================================================
CREATE TABLE IF NOT EXISTS job_applications (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_profile_id  uuid REFERENCES user_profiles(id) ON DELETE CASCADE,
  job_id           uuid REFERENCES jobs(id) ON DELETE CASCADE,
  status           text DEFAULT 'saved',
  applied_at       timestamptz,
  notes            text,
  cover_letter_used text,
  match_score      float,
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now(),
  UNIQUE (user_profile_id, job_id)
);

ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public access (dev)" ON job_applications FOR ALL USING (true) WITH CHECK (true);


-- =============================================================
-- TABLE: documents
-- =============================================================
CREATE TABLE IF NOT EXISTS documents (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content    text,
  metadata   jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public access (dev)" ON documents FOR ALL USING (true) WITH CHECK (true);


-- =============================================================
-- RPC: match_jobs
-- Probes 10 IVFFlat clusters (safe for small datasets)
-- =============================================================
DROP FUNCTION IF EXISTS match_jobs(vector, float, int);

CREATE OR REPLACE FUNCTION match_jobs (
  query_embedding  vector(768),
  match_threshold  float,
  match_count      int
)
RETURNS TABLE (
  id               uuid,
  title            text,
  company          text,
  location         text,
  description      text,
  source_platform  text,
  source_url       text,
  url              text,
  remote_type      text,
  job_type         text,
  experience_level text,
  salary_max       int,
  required_skills  jsonb,
  preferred_skills jsonb,
  similarity       float
)
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM set_config('ivfflat.probes', '10', true);

  RETURN QUERY
  SELECT
    jobs.id,
    jobs.title,
    jobs.company,
    jobs.location,
    jobs.description,
    jobs.source_platform,
    jobs.source_url,
    coalesce(jobs.url, jobs.source_url) AS url,
    jobs.remote_type,
    jobs.job_type,
    jobs.experience_level,
    jobs.salary_max,
    jobs.required_skills,
    jobs.preferred_skills,
    1 - (jobs.embedding <=> query_embedding) AS similarity
  FROM jobs
  WHERE 1 - (jobs.embedding <=> query_embedding) > match_threshold
    AND jobs.is_active = true
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;


-- =============================================================
-- RPC: match_candidates (headhunter mode)
-- =============================================================
CREATE OR REPLACE FUNCTION match_candidates (
  query_embedding  vector(768),
  match_threshold  float,
  match_count      int
)
RETURNS TABLE (
  id                 uuid,
  name               text,
  email              text,
  experience_summary text,
  skills             jsonb,
  similarity         float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    up.id,
    up.name,
    up.email,
    up.experience_summary,
    up.skills,
    1 - (up.resume_embedding <=> query_embedding) AS similarity
  FROM user_profiles up
  WHERE up.resume_embedding IS NOT NULL
    AND 1 - (up.resume_embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;


-- =============================================================
-- Trigger: auto-update updated_at
-- =============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_profiles_updated_at ON user_profiles;
CREATE TRIGGER user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS job_applications_updated_at ON job_applications;
CREATE TRIGGER job_applications_updated_at
  BEFORE UPDATE ON job_applications
  FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
