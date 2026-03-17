-- Enable the pgvector extension to work with embeddings
create extension if not exists vector;

-- Create the jobs table
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  company text not null,
  location text,
  job_type text, -- full-time, part-time, contract
  remote_type text, -- remote, hybrid, on-site
  description text,
  requirements jsonb,
  responsibilities jsonb,
  benefits jsonb,
  salary_min int,
  salary_max int,
  salary_currency text default 'USD',
  required_skills jsonb,
  preferred_skills jsonb,
  experience_level text, -- entry, mid, senior, lead
  years_experience_min int,
  years_experience_max int,
  source_url text unique,
  source_platform text, -- linkedin, indeed, etc.
  embedding vector(768), -- Gemini embeddings are 768 dimensions
  is_active boolean default true,
  posted_at timestamp with time zone,
  expires_at timestamp with time zone,
  scraped_at timestamp with time zone default now()
);

-- Enable Row Level Security (RLS)
-- For development, we'll allow public read/write, but in production this should be restricted.
alter table jobs enable row level security;

create policy "Public Access"
  on jobs for all
  using (true)
  with check (true);

-- Create a function to search for jobs using vector similarity
create or replace function match_jobs (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  title text,
  company text,
  location text,
  description text,
  source_platform text,
  remote_type text,
  job_type text,
  experience_level text,
  salary_max int,
  similarity float
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
    jobs.remote_type,
    jobs.job_type,
    jobs.experience_level,
    jobs.salary_max,
    1 - (jobs.embedding <=> query_embedding) as similarity
  from jobs
  where 1 - (jobs.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
end;
$$;
