# HireRight AI — Engineering Design Document

> **Audience**: Engineers, technical reviewers, contributors.
> This document covers the system architecture, data flows, design decisions, and tradeoffs for HireRight AI.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Architecture](#2-service-architecture)
3. [Data Flow — Job Matching Pipeline](#3-data-flow--job-matching-pipeline)
4. [LangGraph Agent State Machine](#4-langgraph-agent-state-machine)
5. [Vector Database Design](#5-vector-database-design)
6. [API Design](#6-api-design)
7. [MCP Server Architecture](#7-mcp-server-architecture)
8. [DB-First Caching Strategy](#8-db-first-caching-strategy)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Configuration & Secrets Management](#10-configuration--secrets-management)
11. [Performance Characteristics](#11-performance-characteristics)
12. [Security Considerations](#12-security-considerations)
13. [Known Limitations](#13-known-limitations)
14. [Roadmap](#14-roadmap)

---

## 1. System Overview

HireRight AI is composed of **four independently deployable processes** plus a vector database:

| Process | Port | Responsibility |
|---|---|---|
| Streamlit Frontend | 8501 | User interface — file upload, results display, analytics |
| FastAPI Backend | 8000 | Business logic, LangGraph orchestration, Supabase access |
| GitHub Context MCP | 8001 | Thin FastAPI wrapper around GitHub REST API |
| Job Market MCP | 8002 | Thin FastAPI wrapper around Tavily Search API |
| Supabase (external) | — | PostgreSQL + pgvector — persistent store, vector index |

All inter-service communication is HTTP/JSON. No message queue. No shared in-process state between services.

### Design Principles

1. **Stateless services** — Any service can be restarted independently without data loss. State lives in Supabase.
2. **DB-first** — The vector database is always queried before calling external APIs. External calls are a fallback, not the default.
3. **No direct DB access from UI** — All data retrieval goes through the FastAPI backend, which provides validation, caching, and a consistent API contract.
4. **Prompts externalised** — LLM prompts are in `backend/app/agents/prompts/`. Node code contains orchestration logic only.
5. **Structured LLM output** — Every node instructs the LLM to respond in JSON. Nodes include fallback logic for malformed responses.

---

## 2. Service Architecture

### 2.1 Backend (FastAPI)

```
backend/app/
├── main.py                   # FastAPI app, router registration, startup events
├── core/
│   └── config.py             # Pydantic BaseSettings — typed env var loading with @lru_cache
├── models.py                 # Pydantic domain models (ResumeData, JobListing, Verdict, etc.)
├── agents/
│   ├── graph.py              # LangGraph StateGraph definition + compiled pipeline
│   ├── state.py              # AgentState TypedDict — single source of truth for graph state
│   ├── nodes/                # One file per agent role
│   │   ├── profile_parser.py # Extracts structured data from raw resume text
│   │   ├── skill_gap.py      # Identifies missing skills vs. job requirements
│   │   ├── recruiter.py      # Adversarial agent
│   │   ├── coach.py          # Advocate agent
│   │   ├── judge.py          # Arbiter agent + re-debate decision
│   │   ├── cover_writer.py   # Cover letter generation
│   │   └── improvement.py    # Post-verdict improvement suggestions
│   └── prompts/              # Prompt templates (never inline in nodes)
├── api/routes/               # FastAPI routers, one per domain
└── services/
    ├── embedding.py          # get_embedding() — async, with retry via tenacity
    ├── supabase_vector_service.py  # SupabaseVectorService — upsert + search
    └── resume_parser.py      # PDF → ResumeData using pdfplumber
```

### 2.2 Configuration Loading

```python
# config.py pattern — one Settings object, cached globally
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    ...

@lru_cache
def get_settings() -> Settings: ...
settings = get_settings()
```

All services import `settings` directly. No environment variable reads scattered across the codebase.

---

## 3. Data Flow — Job Matching Pipeline

### Request Lifecycle (`POST /api/v1/match`)

```
Client (Streamlit)
    │  multipart/form-data
    │  { query, location, level, resume.pdf, github_username, refresh }
    ▼
match.py — route handler
    │
    ├── Step 1: Parse Resume PDF
    │     pdfplumber extracts text → parse_resume() → ResumeData
    │     skill_names extracted for search context
    │
    ├── Step 2: GitHub Context (optional)
    │     POST http://localhost:8001/tools/get_user_repos
    │     → extracts languages + topics → appended to search_context
    │
    ├── Step 3: Build Search Context
    │     search_context = "{query} {level} {location} Skills: {skills} Experience: {resume_text}"
    │
    ├── Step 4: Log Request to Supabase `documents` table
    │
    ├── Step 5: Vector Search — Supabase pgvector
    │     get_embedding(search_context) → 768-dim vector
    │     match_jobs(query_embedding, threshold=0.7, count=10)
    │     → search_results[]
    │
    ├── Step 5b: DB-First Cache Check
    │     count results where score > 0.8
    │     if count < 3 OR refresh == "1":
    │         POST http://localhost:8002/tools/search_jobs
    │         → _parse_raw_jobs() → embed → insert to Supabase
    │         → re-run vector search
    │
    ├── Step 6: Per-Job LLM Analysis
    │     For each result:
    │         extract_skills_with_llm(job_description)
    │         compute missing_skills vs. resume skills
    │
    └── Return: { success, matches[], parsed_skills[], processing_time_s }
```

### Response Shape

```json
{
  "success": true,
  "matches": [
    {
      "id": "uuid",
      "title": "Senior Python Developer",
      "company": "Acme Corp",
      "url": "https://linkedin.com/jobs/...",
      "match_score": 0.847,
      "missing_skills": ["Kubernetes", "Terraform"],
      "experience_level": "senior",
      "remote_type": "remote",
      "salary_max": 180000
    }
  ],
  "parsed_skills": ["Python", "FastAPI", "PostgreSQL"],
  "processing_time_seconds": 4.2
}
```

---

## 4. LangGraph Agent State Machine

### AgentState Structure

```python
class AgentState(TypedDict):
    # Input
    resume_data: ResumeData
    job_data: JobListing
    github_username: Optional[str]

    # Parsed resume fields (set by profile_parser_node)
    parsed_skills: List[str]
    parsed_strengths: List[str]
    parsed_experience_summary: str
    total_years_experience: float

    # Debate state
    current_round: int
    recruiter_arguments: List[Argument]
    recruiter_score: float
    coach_arguments: List[Argument]
    coach_score: float
    score_difference: float
    should_redebate: bool

    # Output
    debate_rounds: List[DebateRound]
    final_verdict: Optional[Verdict]
    skill_gaps: List[SkillGap]
    cover_letter: Optional[str]
    messages: List[dict]
```

### Graph Topology

```
START
  │
  ▼
profile_parser_node       # Populates parsed_skills, experience_summary, etc.
  │
  ▼
recruiter_node            # Adversarial — finds weaknesses
  │
  ▼
coach_node                # Advocate — finds strengths
  │
  ▼
judge_node                # Weighs both, computes final_score
  │
  ├── should_redebate == True AND current_round < max_rounds
  │         │
  │         └──────────────────────────────► recruiter_node (loop back)
  │
  └── should_redebate == False
            │
            ▼
        skill_gap_node    # Extracts structured gaps from debate context
            │
            ▼
      cover_writer_node   # Optional — generates cover letter
            │
            ▼
           END
```

### Re-debate Condition

```python
# judge.py
should_redebate = (
    score_difference > settings.redebate_threshold   # default: 0.30 (30%)
    and current_round < settings.max_debate_rounds   # default: 3
)
```

The re-debate loop fires when the Recruiter and Coach are more than 30 percentage points apart. This forces a second round of deliberation with both agents now aware of the previous round's arguments (passed through the state).

### Agent Model Assignment

| Node | Model | Rationale |
|---|---|---|
| Recruiter | `gemini-2.0-flash` | Fast inference, adversarial role doesn't need deep reasoning |
| Coach | `gemini-2.0-flash` | Fast inference, creative but not complex reasoning |
| Judge | `gemini-2.0-flash` | Structured JSON output, weighing arguments |
| Cover Writer | `gemini-2.0-flash` | Creative writing — temperature 0.8 |

> **Note**: `gemini-1.5-pro` was originally planned for Judge. Upgrade here if verdict quality degrades for complex profiles.

---

## 5. Vector Database Design

### Why pgvector over Pinecone / Weaviate

- **Supabase is already the relational store** — co-locating vectors with job metadata eliminates join overhead and keeps the infra footprint small
- **SQL joins remain available** — match_jobs can be extended with `WHERE company = 'Acme'` or salary filters without a separate metadata filter layer
- **`CREATE TABLE IF NOT EXISTS`** migrations are idempotent and version-controllable alongside the rest of the code

### Embedding Strategy

```
Input text = "{title} at {company}. {description[:8000]}"
                       │
                       ▼
           Gemini Embedding API
           (models/gemini-embedding-001)
                       │
                       ▼
              vector(768)  →  stored in jobs.embedding
```

The embedding input is deliberately concise: title + company gives the primary semantic signal, and the truncated description adds context without exceeding the model's optimal input length.

### Similarity Function

```sql
-- Cosine distance operator (pgvector)
1 - (jobs.embedding <=> query_embedding) as similarity
-- Threshold: 0.7 (enforced in RPC and in supabase_vector_service.py)
```

Cosine similarity is preferred over L2 distance for text embeddings because it measures **directional alignment** (conceptual similarity) rather than magnitude distance.

### Index Configuration

```sql
-- IVFFlat index — approximate nearest neighbours, ~10ms query at scale
CREATE INDEX jobs_embedding_idx
  ON jobs USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

`lists = 100` is appropriate for < 1M rows. Increase to `sqrt(rows)` as the dataset grows. For production at scale, migrate to HNSW (`pgvector >= 0.5.0`).

### Schema v2 Tables

```
jobs               ← job listings + embeddings (core)
user_profiles      ← resume data + candidate embeddings
match_results      ← cached debate results (debate_rounds jsonb, cover_letter)
job_applications   ← user application tracker (status progression)
documents          ← request/context audit log
```

Full DDL: [`supabase_schema_v2.sql`](../supabase_schema_v2.sql)

---

## 6. API Design

### Route Organisation

```
/api/v1/
  /match              ← primary pipeline (resume + query → matches)
  /debate/run-debate  ← full LangGraph pipeline for a specific job pair
  /cover-letter/quick ← lightweight cover letter from raw text
  /cover-letter       ← full cover letter with structured ResumeData
  /jobs               ← list active jobs from DB
  /profile            ← resume upload + profile management
  /analytics          ← aggregated skill / salary / remote data
  /headhunter         ← reverse: job description → find matching candidates
  /health             ← service health check
```

### Async Pattern

All routes that invoke LLM or DB calls are `async def`. The LangGraph pipeline is invoked with `await run_agent_pipeline(...)`. Blocking sync calls in any async context are a known issue in `roadmap_agent.py` (see [Known Limitations](#13-known-limitations)).

### Form vs. JSON

`POST /match` uses `multipart/form-data` (not JSON) because it accepts a PDF file upload alongside text fields. FastAPI's `Form()` + `File()` dependencies handle this. Boolean form fields do not auto-coerce — `refresh` is received as string `"1"/"0"` and parsed explicitly.

---

## 7. MCP Server Architecture

Both MCP servers follow the same pattern: **a minimal FastAPI app** that wraps an external API and exposes a clean `/tools/<name>` endpoint. This decouples the main backend from specific API SDKs and makes each integration independently testable.

### Job Market MCP (`:8002`)

```
POST /tools/search_jobs  { query: str, limit: int }
    │
    └── Tavily Search API → raw web results
    └── Returns: { jobs: [ { url, title, snippet, content } ] }

GET  /health  → { status: "healthy", tavily_configured: bool }
```

The backend's `_parse_raw_jobs()` converts raw Tavily snippets into structured job records. Aggregated listing pages (e.g. "1,000+ Python jobs in NYC") are filtered using regex before any parsing occurs.

### GitHub Context MCP (`:8001`)

```
POST /tools/get_user_repos  { username: str }
    │
    └── GitHub REST API → repos list
    └── Returns: { repos: [ { name, language, topics, stars } ] }
```

The backend extracts `languages` and `topics` sets from the top 5 repos and appends them to the search context string before embedding.

---

## 8. DB-First Caching Strategy

The match pipeline follows a **cache-first** pattern to avoid unnecessary external API calls:

```
Query Supabase vector index
         │
         ▼
Count results with similarity > 0.8
         │
    ┌────┴──────────────┐
  >= 3                < 3  OR  refresh == "1"
    │                  │
    ▼                  ▼
Return cached      Call Job Market MCP
results            → parse → embed → insert
                   → re-query Supabase
                   → return updated results
```

**Why 0.8 for the cache-hit threshold vs. 0.7 for the search threshold?**

- `0.7` is the minimum quality bar for showing a result to the user
- `0.8` is the bar for considering the cache "warm" — we want high-confidence cached results before skipping live scraping
- Using `0.8` for the cache check means a sparse DB with mediocre matches will still trigger a fresh scrape

This prevents the degenerate case where the DB has 10 low-quality jobs (scoring 0.71–0.79) and the system wrongly concludes the cache is sufficient.

---

## 9. Frontend Architecture

The Streamlit frontend is a **single-file application** (`frontend/app.py`, ~1600 LOC). All pages are rendered as Python functions called from `main()` based on sidebar radio selection.

### Session State Usage

| Key | Set by | Consumed by |
|---|---|---|
| `matched_jobs` | `show_job_match()` after API call | AI Debate, Cover Letter, Skill Roadmap, Analytics |
| `resume_skills` | `show_job_match()` after API call | Analytics (skill gap radar) |
| `resume_summary` | `show_job_match()` after API call | Cover Letter (`candidate_profile`) |
| `resume_bytes` | `show_job_match()` on file upload | Re-sent on re-match without re-upload |
| `has_matches` | `show_job_match()` | Controls results display |
| `debate_result_{job_id}` | `show_agent_debate()` | Debate result persistence per job |

### HTML Rendering Policy

Streamlit's `st.markdown(unsafe_allow_html=True)` does not reliably render deeply nested HTML — inner elements can be escaped by the sanitiser. The rule applied throughout the codebase:

- **Structure / containers**: `st.container()`, `st.columns()`, `st.expander()` — never raw HTML divs
- **Simple colour-coded labels**: `st.markdown("<div ...>single-line content</div>", unsafe_allow_html=True)` — only when no native equivalent exists
- **Never**: nested HTML with interpolated f-string spans — these reliably break

---

## 10. Configuration & Secrets Management

All configuration flows through `backend/app/core/config.py` via Pydantic `BaseSettings`. The settings object is instantiated once at startup with `@lru_cache`.

```
.env file (root)
    │
    ▼
Pydantic BaseSettings (config.py)
    │
    ├── settings.google_api_key
    ├── settings.gemini_model       = "gemini-2.0-flash"
    ├── settings.supabase_url
    ├── settings.supabase_key
    ├── settings.redebate_threshold = 0.30
    └── settings.max_debate_rounds  = 3
```

**Rules:**
- Never log `GOOGLE_API_KEY`, `SUPABASE_KEY`, or `TAVILY_API_KEY` — not even partial values
- `.env` is gitignored. `.env.example` contains only placeholder values and is committed
- MCP servers read their own env vars directly (`os.getenv`) since they are separate processes that do not import the backend's config module

---

## 11. Performance Characteristics

### Typical Latency Breakdown (`POST /match`)

| Step | Typical Time | Notes |
|---|---|---|
| Resume PDF parse | 0.2–0.5s | pdfplumber, CPU-bound |
| GitHub fetch (if provided) | 0.5–2s | network-bound, non-blocking |
| Gemini embedding | 0.3–1s | single API call |
| Supabase vector search | 0.1–0.5s | IVFFlat index, very fast |
| Conditional MCP scrape | 5–15s | only when cache cold; 3 jobs × (Tavily + embed + insert) |
| Per-job LLM skill extraction | 0.5–1s × N jobs | parallelisable (not yet parallelised) |
| **Total (cache warm)** | **1–4s** | |
| **Total (cache cold)** | **15–30s** | first request or refresh=1 |

### Bottleneck Analysis

1. **Cold-cache MCP scraping** is the dominant latency. Mitigated by: the DB-first strategy (most repeat queries hit the cache), and the reduced `--limit 3` default.
2. **Per-job LLM skill extraction** is called sequentially. Converting to `asyncio.gather()` would cut this by ~60%.
3. **LangGraph debate** (via `/debate/run-debate`) adds 15–30s — this is a separate user-initiated action, not part of the initial match.

---

## 12. Security Considerations

### Current (Development) Posture

- All Supabase tables use `"Public read/write (dev)"` RLS policies — **not production-safe**
- No authentication layer on any endpoint
- API keys stored in `.env` — acceptable for local dev, not for deployment

### Production Hardening Checklist

- [ ] Replace Supabase `"Public Access"` policies with auth-scoped RLS (e.g. `auth.uid() = user_id`)
- [ ] Add FastAPI `Depends(verify_token)` middleware to all non-health routes
- [ ] Store secrets in a secrets manager (AWS Secrets Manager, GCP Secret Manager, or Supabase Vault)
- [ ] Rate-limit `/match` — it triggers external API calls (Tavily, Gemini) that have cost implications
- [ ] Never log request bodies containing resume text — PII
- [ ] Add `Content-Security-Policy` headers to the Streamlit deployment

---

## 13. Known Limitations

| Issue | Location | Impact | Workaround |
|---|---|---|---|
| `roadmap_agent.py` uses `llm.invoke()` (sync) | `backend/app/agents/roadmap_agent.py` | Can block async event loop | Convert to `async def` + `await llm.ainvoke()` |
| No persistent user identity | Frontend session state only | Matches lost on page refresh | Implement `user_profiles` write on match completion |
| Per-job skill extraction is sequential | `match.py` Step 6 | Adds N × ~0.7s to response | Wrap in `asyncio.gather()` |
| `match_results` table not yet written | `match.py`, `debate.py` | Debate cache not persistent | Implement upsert after debate completes |
| Dashboard job cards use old HTML pattern | `frontend/app.py:show_dashboard()` | Risk of HTML bleed | Rewrite with `st.columns()` same as Job Match page |
| Scraper: "LinkedIn" parsed as company name | `scrape_live_jobs.py` | Junk entries in DB | Add LinkedIn/Indeed to invalid company list |
| IVFFlat requires `>= lists × 3` rows to build | `supabase_schema_v2.sql` | Index errors on empty DB | Use `HNSW` or defer index creation until seeded |

---

## 14. Roadmap

### P0 — Core Reliability
- [ ] Persist `match_results` after every debate run (enable true DB-first for agent results)
- [ ] Write `user_profiles` row from parsed resume on each `/match` call
- [ ] Fix sequential skill extraction → `asyncio.gather()`
- [ ] Convert `roadmap_agent.py` to async

### P1 — Search Quality
- [ ] **Hybrid Search (RRF)** — Combine pgvector cosine similarity with PostgreSQL full-text search using Reciprocal Rank Fusion
- [ ] Add location filter to `match_jobs` RPC
- [ ] Improve scraper: reject "LinkedIn"/"Indeed" as company names

### P2 — UX & Features
- [ ] Application tracker UI — surface `job_applications` table (saved/applied/interview/offer)
- [ ] Headhunter mode — reverse search: paste a job description, find matching profiles
- [ ] Dashboard job cards HTML fix (same pattern as Job Match page)
- [ ] Streamlit multi-page refactor — split `app.py` into `pages/` files

### P3 — Observability & Production
- [ ] LangSmith integration — trace multi-round debates with full state visibility
- [ ] Async `/match` (task-polling) — `POST /match` → `{task_id}`, `GET /status/{task_id}`
- [ ] Docker Compose production profile — with nginx reverse proxy
- [ ] Supabase RLS hardening + auth layer

---

*Last updated: March 2026 | Maintainer: [Ayush Varma](https://github.com/ayushvarma7)*
