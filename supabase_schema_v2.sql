-- =============================================================
-- HireRight AI | Supabase Schema v2
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor)
-- =============================================================

-- Enable pgvector for all embedding operations
create extension if not exists vector;


-- =============================================================
-- TABLE: jobs
-- Stores scraped / manually entered job listings with embeddings
-- =============================================================
create table if not exists jobs (
  id              uuid primary key default gen_random_uuid(),

  -- Core listing fields
  title           text not null,
  company         text not null,
  location        text,
  description     text,
  url             text,                     -- canonical apply/listing URL
  source_url      text unique,              -- original scraped URL (dedup key)
  source_platform text,                     -- linkedin, indeed, glassdoor, web

  -- Structured metadata
  job_type        text,                     -- full-time, part-time, contract
  remote_type     text,                     -- remote, hybrid, on-site
  experience_level text,                    -- entry, mid, senior, lead, executive
  years_experience_min int,
  years_experience_max int,
  required_skills  jsonb default '[]',      -- ["Python","FastAPI"]
  preferred_skills jsonb default '[]',
  salary_min      int,
  salary_max      int,
  salary_currency text default 'USD',

  -- Vector embedding (Gemini text-embedding-004: 768 dims)
  embedding       vector(768),

  -- Lifecycle
  is_active       boolean default true,
  posted_at       timestamptz,
  expires_at      timestamptz,
  scraped_at      timestamptz default now()
);

-- Fast cosine-similarity index on the embedding column
create index if not exists jobs_embedding_idx
  on jobs using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Text search index for hybrid search (RRF future work)
create index if not exists jobs_title_fts_idx
  on jobs using gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')));

alter table jobs enable row level security;
create policy "Public read/write (dev)" on jobs for all using (true) with check (true);


-- =============================================================
-- TABLE: user_profiles
-- One row per candidate session / registered user.
-- Stores parsed resume data + semantic embedding for matching.
-- =============================================================
create table if not exists user_profiles (
  id                    uuid primary key default gen_random_uuid(),

  -- Identity
  name                  text,
  email                 text,
  github_username       text,

  -- Resume content
  raw_resume_text       text,             -- full extracted text from PDF
  experience_summary    text,             -- LLM-generated 2-3 sentence summary
  total_years_experience float default 0,

  -- Skills (structured)
  skills                jsonb default '[]',    -- ["Python","React","AWS"]
  skill_categories      jsonb default '{}',    -- {"Languages":["Python"],"Cloud":["AWS"]}

  -- Education & experience (structured)
  education             jsonb default '[]',    -- [{degree, institution, year}]
  work_history          jsonb default '[]',    -- [{title, company, years, description}]

  -- Semantic embedding of the full resume for candidate-to-job matching
  resume_embedding      vector(768),

  -- Metadata
  session_id            text,                  -- ties to Streamlit session (anon users)
  created_at            timestamptz default now(),
  updated_at            timestamptz default now()
);

create index if not exists user_profiles_embedding_idx
  on user_profiles using ivfflat (resume_embedding vector_cosine_ops)
  with (lists = 10);

alter table user_profiles enable row level security;
create policy "Public access (dev)" on user_profiles for all using (true) with check (true);


-- =============================================================
-- TABLE: match_results
-- Cache of every job<->candidate match evaluation.
-- Powers the DB-first matching strategy (avoids re-running pipeline).
-- =============================================================
create table if not exists match_results (
  id                  uuid primary key default gen_random_uuid(),

  -- Foreign keys
  user_profile_id     uuid references user_profiles(id) on delete cascade,
  job_id              uuid references jobs(id) on delete cascade,

  -- Scores
  vector_score        float,              -- raw cosine similarity from pgvector
  recruiter_score     float,             -- score from Recruiter agent
  coach_score         float,             -- score from Coach agent
  final_score         float,             -- Judge's final score (0-100)
  recommendation      text,             -- "Strong Match", "Good Match", etc.
  confidence          float,             -- Judge's confidence (0-1)

  -- Debate output (JSON blob — serialized from LangGraph state)
  debate_rounds       jsonb default '[]',
  key_strengths       jsonb default '[]',
  key_concerns        jsonb default '[]',
  missing_skills      jsonb default '[]',
  must_address        jsonb default '[]',

  -- Cover letter (cached post-generation)
  cover_letter        text,

  -- Metadata
  total_rounds        int default 1,
  processing_time_s   float,
  created_at          timestamptz default now(),

  -- One cached result per (user, job) pair
  unique (user_profile_id, job_id)
);

create index if not exists match_results_user_idx on match_results(user_profile_id);
create index if not exists match_results_job_idx  on match_results(job_id);
create index if not exists match_results_score_idx on match_results(final_score desc);

alter table match_results enable row level security;
create policy "Public access (dev)" on match_results for all using (true) with check (true);


-- =============================================================
-- TABLE: job_applications
-- Tracks which jobs a user has saved / applied to / interviewed at
-- =============================================================
create table if not exists job_applications (
  id                  uuid primary key default gen_random_uuid(),
  user_profile_id     uuid references user_profiles(id) on delete cascade,
  job_id              uuid references jobs(id) on delete cascade,

  status              text default 'saved',
                      -- saved | applied | phone_screen | interview | offer | rejected | withdrawn

  applied_at          timestamptz,
  notes               text,
  cover_letter_used   text,               -- snapshot of the cover letter sent
  match_score         float,              -- denormalised for quick display

  created_at          timestamptz default now(),
  updated_at          timestamptz default now(),

  unique (user_profile_id, job_id)
);

alter table job_applications enable row level security;
create policy "Public access (dev)" on job_applications for all using (true) with check (true);


-- =============================================================
-- TABLE: documents
-- General-purpose request/context log (referenced by match.py)
-- =============================================================
create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  content     text,
  metadata    jsonb default '{}',
  created_at  timestamptz default now()
);

alter table documents enable row level security;
create policy "Public access (dev)" on documents for all using (true) with check (true);


-- =============================================================
-- RPC: match_jobs
-- Vector similarity search — returns top-K jobs above threshold.
-- Upgraded to also return source_url (needed by frontend for links).
-- Must DROP first because the return type changed from v1.
-- =============================================================
drop function if exists match_jobs(vector, float, int);

create or replace function match_jobs (
  query_embedding  vector(768),
  match_threshold  float,
  match_count      int
)
returns table (
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
language plpgsql
as $$
begin
  return query
  select
    jobs.id,
    jobs.title,
    jobs.company,
    jobs.location,
    jobs.description,
    jobs.source_platform,
    jobs.source_url,
    coalesce(jobs.url, jobs.source_url) as url,
    jobs.remote_type,
    jobs.job_type,
    jobs.experience_level,
    jobs.salary_max,
    jobs.required_skills,
    jobs.preferred_skills,
    1 - (jobs.embedding <=> query_embedding) as similarity
  from jobs
  where 1 - (jobs.embedding <=> query_embedding) > match_threshold
    and jobs.is_active = true
  order by similarity desc
  limit match_count;
end;
$$;


-- =============================================================
-- RPC: match_candidates (future: headhunter mode)
-- Find candidates whose resume embedding matches a job description
-- =============================================================
create or replace function match_candidates (
  query_embedding  vector(768),
  match_threshold  float,
  match_count      int
)
returns table (
  id               uuid,
  name             text,
  email            text,
  experience_summary text,
  skills           jsonb,
  similarity       float
)
language plpgsql
as $$
begin
  return query
  select
    up.id,
    up.name,
    up.email,
    up.experience_summary,
    up.skills,
    1 - (up.resume_embedding <=> query_embedding) as similarity
  from user_profiles up
  where up.resume_embedding is not null
    and 1 - (up.resume_embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
end;
$$;


-- =============================================================
-- Trigger: auto-update updated_at
-- =============================================================
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger user_profiles_updated_at
  before update on user_profiles
  for each row execute procedure set_updated_at();

create trigger job_applications_updated_at
  before update on job_applications
  for each row execute procedure set_updated_at();
