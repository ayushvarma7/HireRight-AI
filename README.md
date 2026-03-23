# HireRight AI

> **AI-native career intelligence platform** — semantic resume matching, multi-agent hiring committee debate, and live job market ingestion.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-FF6B6B)](https://langchain-ai.github.io/langgraph/)
[![Gemini](https://img.shields.io/badge/Google-Gemini_2.0-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)

---

## The Problem

Traditional ATS (Applicant Tracking Systems) use **keyword matching** — rigid, easy to game, and terrible at identifying conceptual fit. A Python developer who listed "Django" but not "web frameworks" gets rejected. A career changer with deeply transferable skills never makes it through the filter.

## The Solution

HireRight replaces keyword counting with **semantic understanding** (Gemini embeddings) and **multi-perspective deliberation** (a LangGraph agent committee). Every resume-job pair goes through a structured debate between three AI agents before a verdict is issued — the same way a real hiring committee works.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HIRERIGHT AI                                │
│                                                                     │
│   ┌──────────────┐   REST/JSON   ┌──────────────────────────────┐  │
│   │  Streamlit   │ ◄──────────── │       FastAPI Backend        │  │
│   │  Frontend    │               │  ┌────────────────────────┐  │  │
│   │  :8501       │               │  │   LangGraph Pipeline   │  │  │
│   └──────────────┘               │  │  Recruiter → Coach     │  │  │
│                                  │  │       → Judge          │  │  │
│                                  │  └──────────┬─────────────┘  │  │
│                                  │             │                 │  │
│                                  │  ┌──────────▼─────────────┐  │  │
│                                  │  │  Supabase + pgvector   │  │  │
│                                  │  │  (768-dim embeddings)  │  │  │
│                                  │  └────────────────────────┘  │  │
│                                  └──────────────────────────────┘  │
│                                           │            │            │
│              ┌────────────────────────────▼──┐  ┌──────▼─────────┐ │
│              │   Job Market MCP  :8002        │  │  GitHub MCP    │ │
│              │   (Tavily live scraping)       │  │  :8001         │ │
│              └────────────────────────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

> **Full design rationale, data flows, and architectural decisions** → [ENGINEERING.md](docs/ENGINEERING.md)

---

## Feature Overview

| Feature | Description |
|---|---|
| **Semantic Job Matching** | Gemini embeddings (768-dim) + pgvector cosine similarity — no keyword lists |
| **Multi-Agent Debate** | Recruiter (skeptic) vs. Coach (advocate) → Judge issues final verdict |
| **Re-debate Cycle** | If Recruiter and Coach scores diverge >30%, agents debate a second round |
| **DB-First Caching** | Supabase queried before any live scraping — near-instant on repeat queries |
| **Live Job Scraping** | Tavily-powered Job Market MCP fetches real listings on demand |
| **GitHub Enrichment** | GitHub Context MCP extracts languages and projects from public repos |
| **Cover Letter Gen** | Gemini-written letters informed by debate insights (strengths + gap addressing) |
| **Skill Gap Roadmap** | Ranked skills to learn, derived from matched job descriptions |
| **Analytics Dashboard** | Plotly charts — skill demand, salary ranges, remote distribution |

---

## Quick Start (One Command)

```bash
git clone https://github.com/ayushvarma7/HireRight-AI.git
cd HireRight-AI
cp .env.example .env          # fill in your API keys (see Prerequisites)
python3.11 -m venv venv
venv/bin/pip install -e ".[frontend]"
./run_hireright.sh            # starts all 4 services
```

Then open **http://localhost:8501** in your browser.

```bash
./run_hireright.sh stop       # stop everything
./run_hireright.sh status     # check what's running
./run_hireright.sh logs       # tail all 4 log streams live
./run_hireright.sh restart    # full restart
```

---

## Full Setup Guide

### Prerequisites

| Requirement | Notes |
|---|---|
| Python **3.11+** | Check with `python3 --version` |
| **Google AI Studio** key | [aistudio.google.com](https://aistudio.google.com) — free tier is sufficient |
| **Supabase** project | Free tier at [supabase.com](https://supabase.com) — pgvector must be enabled |
| **Tavily** API key | [tavily.com](https://tavily.com) — required for live job scraping |
| **GitHub** personal access token | Optional — needed for GitHub profile enrichment |

### Step 1 — Clone & Install

```bash
git clone https://github.com/ayushvarma7/HireRight-AI.git
cd HireRight-AI

# Create virtual environment
python3.11 -m venv venv

# Install all dependencies (backend + frontend)
venv/bin/pip install -e ".[frontend]"
```

### Step 2 — Configure Environment

```bash
cp .env.example .env
```

Open `.env` and set:

```env
GOOGLE_API_KEY=<your Google AI Studio key>
SUPABASE_URL=<your Supabase project URL>
SUPABASE_KEY=<your Supabase service role key>
TAVILY_API_KEY=<your Tavily key>
GITHUB_TOKEN=<optional>
```

### Step 3 — Initialise the Database

1. Go to your **Supabase Dashboard → SQL Editor**
2. Paste and run the contents of **[`supabase_schema_v2.sql`](supabase_schema_v2.sql)**

This creates:
- `jobs` table with 768-dim vector index
- `user_profiles` table (resume + embedding)
- `match_results` table (debate cache)
- `job_applications` tracking table
- `match_jobs` and `match_candidates` RPC functions

### Step 4 — Seed Initial Job Data (Optional but Recommended)

The matching engine needs jobs in the database. Start the services first, then run:

```bash
# Start services
./run_hireright.sh

# In a new terminal — seed with 3 results per query across 10 tech roles
cd backend && ../venv/bin/python ../scripts/scrape_live_jobs.py --limit 3

# Or target specific roles
../venv/bin/python ../scripts/scrape_live_jobs.py \
  --queries "Python Developer,ML Engineer,Data Scientist" \
  --limit 5
```

Alternatively, tick **"🔄 Refresh Live Source"** in the Job Match UI before clicking Start Matching — this triggers live scraping automatically.

### Step 5 — Run

```bash
./run_hireright.sh
```

| Service | URL | Purpose |
|---|---|---|
| Streamlit Frontend | http://localhost:8501 | Main UI |
| FastAPI Backend | http://localhost:8000 | REST API |
| API Documentation | http://localhost:8000/docs | Swagger UI |
| GitHub MCP | http://localhost:8001/health | GitHub context server |
| Job Market MCP | http://localhost:8002/health | Live job scraping |

### Manual Start (Alternative)

If you prefer separate terminals:

```bash
# Terminal 1 — GitHub Context MCP
venv/bin/python mcp_servers/github-context/server.py

# Terminal 2 — Job Market MCP
venv/bin/python mcp_servers/job-market/server.py

# Terminal 3 — FastAPI Backend
cd backend
../venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 4 — Streamlit Frontend
venv/bin/streamlit run frontend/app.py --server.port 8501
```

---

## Repository Structure

```
HireRight-AI/
│
├── run_hireright.sh              # One-click launcher (start/stop/logs/status)
├── pyproject.toml                # Project dependencies + build config
├── .env.example                  # Environment variable template
├── supabase_schema_v2.sql        # Complete DB schema (apply this in Supabase)
├── supabase_schema.sql           # Legacy schema v1 (reference only)
│
├── docs/
│   └── ENGINEERING.md            # Architecture & engineering design document
│
├── backend/
│   └── app/
│       ├── main.py               # FastAPI app entrypoint
│       ├── core/
│       │   └── config.py         # Pydantic settings (reads .env)
│       ├── agents/
│       │   ├── graph.py          # LangGraph pipeline definition
│       │   ├── state.py          # AgentState TypedDict
│       │   ├── nodes/
│       │   │   ├── recruiter.py  # Devil's Advocate agent
│       │   │   ├── coach.py      # Candidate Advocate agent
│       │   │   ├── judge.py      # Final Arbiter agent
│       │   │   └── cover_writer.py
│       │   └── prompts/          # All LLM prompts (externalised)
│       ├── api/routes/
│       │   ├── match.py          # POST /match — main matching pipeline
│       │   ├── debate.py         # POST /debate/run-debate
│       │   ├── cover_letter.py   # POST /cover-letter/quick
│       │   ├── jobs.py           # GET /jobs
│       │   ├── profile.py        # Resume profile routes
│       │   ├── analytics.py      # Analytics data routes
│       │   └── health.py         # Health check
│       ├── services/
│       │   ├── embedding.py      # Gemini embedding service (768-dim)
│       │   ├── supabase_vector_service.py  # pgvector search + upsert
│       │   └── resume_parser.py  # PDF → structured ResumeData
│       └── models.py             # Pydantic domain models
│
├── frontend/
│   └── app.py                    # Streamlit single-file application (~1600 LOC)
│
├── mcp_servers/
│   ├── github-context/
│   │   └── server.py             # FastAPI MCP — GitHub repo analysis (:8001)
│   └── job-market/
│       └── server.py             # FastAPI MCP — Tavily job scraping (:8002)
│
├── scripts/
│   └── scrape_live_jobs.py       # CLI: Tavily → parse → embed → Supabase
│
└── logs/                         # Runtime logs (gitignored)
    ├── backend.log
    ├── frontend.log
    ├── mcp_github.log
    └── mcp_jobmarket.log
```

---

## API Reference

All endpoints are under `http://localhost:8000/api/v1/`. Interactive docs at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/match` | Upload resume + query → returns ranked job matches |
| `POST` | `/debate/run-debate` | Run full LangGraph agent debate for a job-resume pair |
| `POST` | `/cover-letter/quick` | Generate a Gemini-powered cover letter from raw text |
| `POST` | `/cover-letter` | Generate cover letter from structured ResumeData + JobListing |
| `GET` | `/jobs` | Fetch active job listings from Supabase |
| `GET` | `/status/{task_id}` | Poll async task status |
| `GET` | `/health` | System health check |

### `POST /match` — Key Parameters

| Parameter | Type | Description |
|---|---|---|
| `query` | `string` (form) | Target role, e.g. "Senior Python Developer" |
| `location` | `string` (form) | Location preference |
| `level` | `string` (form) | Seniority: Entry / Mid / Senior / Lead |
| `resume` | `file` (form) | PDF resume (required for full semantic match) |
| `github_username` | `string` (form) | Optional — enriches context with repo data |
| `refresh` | `"1"/"0"` (form) | Force live scraping even if DB cache is warm |

---

## The Agent Debate Pipeline

```
Resume PDF + Job Query
        │
        ▼
┌───────────────────┐
│  1. Profile Parser│  Extract skills, experience, summary from PDF
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  2. Vector Search │  Cosine similarity search in Supabase (threshold: 0.7)
│  (DB-first cache) │  → If <3 high-quality hits: trigger live MCP scrape
└────────┬──────────┘
         │  top-K job matches
         ▼
┌───────────────────┐
│  3. Recruiter     │  Identifies skill gaps, experience red flags
│     (gemini-2.0)  │  → recruiter_score, recruiter_arguments[]
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  4. Coach         │  Highlights strengths, transferable skills
│     (gemini-2.0)  │  → coach_score, coach_arguments[]
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  5. Judge         │  Weighs both sides, issues final verdict
│     (gemini-2.0)  │  → final_score, recommendation, confidence
└────────┬──────────┘
         │
    score_delta > 30%?
    ┌────┴────┐
   YES       NO
    │         │
    ▼         ▼
Re-debate  Final Result
(max 3     (cover letter
 rounds)    generated)
```

---

## Database Schema (v2)

| Table | Purpose | Key Columns |
|---|---|---|
| `jobs` | Job listings + embeddings | `embedding vector(768)`, `url`, `required_skills jsonb` |
| `user_profiles` | Parsed resume + candidate embedding | `resume_embedding vector(768)`, `skills jsonb`, `work_history jsonb` |
| `match_results` | Cached debate results | `final_score`, `debate_rounds jsonb`, `cover_letter` |
| `job_applications` | User application tracker | `status` (saved→offer), `applied_at` |
| `documents` | Request / context log | `content`, `metadata jsonb` |

RPCs: `match_jobs()` (job search), `match_candidates()` (headhunter reverse search)

Full schema: [`supabase_schema_v2.sql`](supabase_schema_v2.sql)

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Google Gemini 2.0 Flash (agents + cover letters) |
| **Embeddings** | Google Gemini Embedding (768-dim) |
| **Agent Orchestration** | LangGraph (stateful multi-agent graph) |
| **Backend API** | FastAPI + Uvicorn |
| **Vector Database** | Supabase (PostgreSQL + pgvector) |
| **Frontend** | Streamlit + Plotly |
| **Live Scraping** | Tavily Search API via Job Market MCP |
| **GitHub Enrichment** | GitHub REST API via GitHub Context MCP |
| **Configuration** | Pydantic Settings (`.env` → typed config) |

---

## Development

```bash
# Install dev dependencies
venv/bin/pip install -e ".[dev]"

# Run linter
venv/bin/ruff check backend/ mcp_servers/

# Run tests
venv/bin/pytest

# Scrape specific roles into DB
cd backend
../venv/bin/python ../scripts/scrape_live_jobs.py \
  --queries "ML Engineer,Data Scientist" \
  --limit 5
```

### Engineering Standards

- All LLM/DB calls are `async/await`
- Prompts are externalised to `backend/app/agents/prompts/` — never hardcoded in nodes
- Vector search minimum threshold: **0.7** cosine similarity
- Embedding dimension: **768** (locked to Gemini — do not change)
- `Judge` node uses structured JSON output; all other nodes parse LLM text with fallbacks

---

## Engineering Design Document

For a deep dive into system design decisions, data flow diagrams, agent state machine, API contracts, database design rationale, performance considerations, and the roadmap:

**→ [docs/ENGINEERING.md](docs/ENGINEERING.md)**

---

## Author

**Ayush Varma**
- [LinkedIn](https://www.linkedin.com/in/ayushvarma7/)
- [GitHub](https://github.com/ayushvarma7)
