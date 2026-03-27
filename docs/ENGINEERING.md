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
3. **24h scrape cooldown** — Tavily is only called when `MAX(scraped_at)` in the jobs table is older than 24 hours, or the user explicitly sets `refresh=1`. This preserves Tavily monthly credits.
4. **No direct DB access from UI** — All data retrieval goes through the FastAPI backend, which provides validation, caching, and a consistent API contract.
5. **Prompts externalised** — LLM prompts are in `backend/app/agents/prompts/`. Node code contains orchestration logic only.
6. **Structured LLM output** — Every node instructs the LLM to respond in JSON. Nodes include fallback logic for malformed responses.

---

## 2. Service Architecture

### 2.1 Backend (FastAPI)

```
backend/app/
├── main.py                   # FastAPI app, router registration, startup events
├── core/
│   └── config.py             # Pydantic BaseSettings — typed env var loading with @lru_cache
├── models/                   # Pydantic domain models (ResumeData, JobListing, Verdict, etc.)
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
    ├── embedding.py          # get_embedding() — Gemini MRL 768-dim, async with retry
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
    embedding_dimension: int = 768
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
    ├── Step 1b: Persist User Profile
    │     SHA-256 of resume bytes → session_id (dedup key)
    │     upsert to user_profiles (skills, work_history, resume_embedding)
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
    │     get_embedding(search_context) → 768-dim MRL vector
    │     match_jobs(query_embedding, threshold=0.55, count=10)
    │     → search_results[]
    │
    ├── Step 5b: DB-First Cache Check
    │     if refresh == "1"       → call Tavily (forced refresh)
    │     elif results not empty  → use cache (skip Tavily)
    │     elif db_is_fresh (<24h) → use cache (trust freshness)
    │     else (db stale)         → call Tavily, parse, embed, insert, re-search
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
      "url": "https://jobs.acme.com/senior-python-developer",
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

The re-debate loop fires when the Recruiter and Coach are more than 30 percentage points apart. Both agents in the next round receive the full prior round's arguments via state, forcing convergence.

### Agent Model Assignment

| Node | Model | Rationale |
|---|---|---|
| Recruiter | `gemini-2.0-flash` | Fast inference — adversarial role doesn't need deep reasoning |
| Coach | `gemini-2.0-flash` | Fast inference — creative but not complex reasoning |
| Judge | `gemini-2.0-flash` | Structured JSON output, weighing arguments |
| Cover Writer | `gemini-2.0-flash` | Creative writing — temperature 0.8 |

> Upgrade Judge to `gemini-1.5-pro` if verdict quality degrades on complex profiles.

---

## 5. Vector Database Design

### Why pgvector over Pinecone / Weaviate

- **Supabase is already the relational store** — co-locating vectors with job metadata eliminates join overhead and keeps the infra footprint small
- **SQL joins remain available** — `match_jobs` can be extended with `WHERE company = 'Acme'` or salary filters without a separate metadata filter layer
- **Idempotent DDL migrations** — schema changes are version-controlled alongside the code

### Embedding Strategy

```
Input text = "{query} {level} {location} Skills: {skills} {resume_text[:2000]}"
                       │
                       ▼
           GoogleGenerativeAIEmbeddings
           model="models/gemini-embedding-001"
           output_dimensionality=768          ← MRL (not naive truncation)
                       │
                       ▼
              vector(768)  →  stored in jobs.embedding / user_profiles.resume_embedding
```

**Why MRL matters**: The model natively outputs 3072 dimensions. Naive truncation (`[:768]`) destroys cosine similarity alignment — the first 768 dimensions carry different semantic weight than a full 768-dim MRL projection. `output_dimensionality=768` uses Matryoshka Representation Learning to produce a properly aligned 768-dim vector.

### Similarity Function

```sql
-- Cosine distance operator (pgvector)
1 - (jobs.embedding <=> query_embedding) as similarity
-- Search threshold: 0.55 (tuned for snippet-based embeddings that peak at ~0.65)
-- Cache-warm threshold: 0.65 (bar for considering the DB cache sufficient)
```

Cosine similarity is preferred over L2 distance for text embeddings because it measures **directional alignment** (conceptual similarity) rather than magnitude distance.

### Index Configuration

```sql
-- IVFFlat index — approximate nearest neighbours
-- lists=1 appropriate for <300 rows; scale to sqrt(row_count) as DB grows
-- set_config('ivfflat.probes', '10') called at query time for small datasets
CREATE INDEX jobs_embedding_idx
  ON jobs USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 1);
```

For production at >10k rows, migrate index to HNSW (`pgvector >= 0.5.0`) for better recall and no probe-tuning requirement.

### Schema Tables

```
jobs               ← job listings + embeddings (core)
user_profiles      ← resume data + candidate embeddings (session_id dedup key)
match_results      ← cached debate results (debate_rounds jsonb, cover_letter)
job_applications   ← user application tracker (status progression)
documents          ← request/context audit log
```

Full DDL: [`migrations/000_initial_schema.sql`](../migrations/000_initial_schema.sql)

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

The backend's `_parse_raw_jobs()` converts raw Tavily snippets into structured job records. Aggregated listing pages (e.g. "1,000+ Python jobs in NYC") and invalid company names (locations, tech keyword lists, known aggregator sites) are filtered using `_is_invalid_company()` before any parsing occurs.

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

The match pipeline follows a strict **cache-first** priority order to avoid unnecessary Tavily API calls (monthly credit limit):

```
Priority 1: refresh == "1"
    → Always call Tavily (user-forced refresh)

Priority 2: DB has results
    → Return cached results, skip Tavily entirely

Priority 3: DB empty AND scraped_at < 24h ago
    → Skip Tavily (trust recent scrape, just no matches for this query)

Priority 4: DB empty AND scraped_at > 24h ago (or never scraped)
    → Call Tavily, parse, embed, insert to Supabase, re-query
```

**Cache-warm threshold**: A result is considered a strong cache hit at similarity ≥ 0.65. Below this, even if results exist, a live scrape may be triggered.

**Why 0.55 for the search threshold vs. 0.65 for cache-warm?**

- `0.55` is the minimum quality bar for showing a result to the user (Tavily snippet-based embeddings peak at ~0.65 even for strong matches — full job description embeddings would merit 0.7)
- `0.65` is the bar for considering the cache "warm" — high-confidence cached results before skipping live scraping
- Using a lower search threshold prevents false negatives on sparse DBs

---

## 9. Frontend Architecture

The Streamlit frontend is a **single-file application** (`frontend/app.py`). All pages are rendered as Python functions called from `main()` based on sidebar radio selection.

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

Streamlit's `st.markdown(unsafe_allow_html=True)` does not reliably render deeply nested HTML — inner elements can be escaped by the sanitiser. The rule applied throughout:

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
    ├── settings.gemini_model           = "gemini-2.0-flash"
    ├── settings.gemini_embedding_model = "models/gemini-embedding-001"
    ├── settings.embedding_dimension    = 768
    ├── settings.supabase_url
    ├── settings.supabase_key
    ├── settings.redebate_threshold     = 0.30
    └── settings.max_debate_rounds      = 3
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
| Supabase vector search | 0.1–0.5s | IVFFlat index |
| Conditional MCP scrape | 5–15s | only when DB is stale (>24h); 3 jobs × (Tavily + embed + insert) |
| Per-job LLM skill extraction | 0.5–1s × N jobs | sequential (parallelisable) |
| **Total (cache warm)** | **1–4s** | |
| **Total (cache cold / stale)** | **15–30s** | first request or refresh=1 |

### Bottleneck Analysis

1. **Cold-cache MCP scraping** is the dominant latency. Mitigated by the 24h cooldown — most requests hit the DB cache.
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
- [ ] Store secrets in a secrets manager (GCP Secret Manager or Supabase Vault)
- [ ] Rate-limit `/match` — it triggers external API calls (Tavily, Gemini) that have cost implications
- [ ] Never log request bodies containing resume text — PII
- [ ] Add `Content-Security-Policy` headers to the Streamlit deployment

---

## 13. Known Limitations

| Issue | Location | Impact | Workaround / Status |
|---|---|---|---|
| `roadmap_agent.py` uses `llm.invoke()` (sync) | `backend/app/agents/roadmap_agent.py` | Can block async event loop | Convert to `async def` + `await llm.ainvoke()` |
| Per-job skill extraction is sequential | `match.py` Step 6 | Adds N × ~0.7s to response | Wrap in `asyncio.gather()` |
| `match_results` table not yet written | `match.py`, `debate.py` | Debate cache not persistent | Implement upsert after debate completes |
| IVFFlat requires `>= lists × 3` rows | DB index | Index errors on tiny DB | Migration 002 sets `lists=1`; use HNSW at scale |

> Items previously listed as limitations that are now resolved: persistent user profiles (`_persist_user_profile` implemented), dashboard HTML bleeding (rewritten with `st.container()`/`st.columns()`), invalid company name filtering (`_is_invalid_company()` with aggregator blocklist).

---

## 14. Roadmap

### P0 — Core Reliability
- [ ] Persist `match_results` after every debate run (enable true DB-first for agent results)
- [ ] Fix sequential skill extraction → `asyncio.gather()`
- [ ] Convert `roadmap_agent.py` to async

### P1 — Search Quality
- [ ] **Hybrid Search (RRF)** — Combine pgvector cosine similarity with PostgreSQL full-text search using Reciprocal Rank Fusion
- [ ] Add location filter to `match_jobs` RPC
- [ ] Migrate IVFFlat → HNSW index as job count grows past 1k

### P2 — UX & Features
- [ ] Application tracker UI — surface `job_applications` table (saved/applied/interview/offer)
- [ ] Headhunter mode — reverse search: paste a job description, find matching profiles
- [ ] Streamlit multi-page refactor — split `app.py` into `pages/` files

### P3 — Observability & Production
- [ ] LangSmith integration — trace multi-round debates with full state visibility
- [ ] Async `/match` (task-polling) — `POST /match` → `{task_id}`, `GET /status/{task_id}`
- [ ] Supabase RLS hardening + auth layer

---

*Last updated: March 2026 | Maintainer: [Ayush Varma](https://github.com/ayushvarma7)*
