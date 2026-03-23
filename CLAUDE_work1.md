# HireRight AI | Claude Code Refactor Guide

This document defines high-priority refactor tasks for AI coding agents (Claude Code, etc.) to improve system integration, data quality, and performance in HireRight AI.

---

# 🎯 Objective

Fix core system issues by:

- Migrating fully to **Google Gemini**
- Cleaning up **low-quality scraped data**
- Implementing a **database-first (cache-first) matching strategy**
- Improving **frontend control & reliability**

---

# 🏗️ 1. Infrastructure: Full Gemini Migration

## Goal
Remove all OpenAI dependencies and standardize on Google Gemini.

## Tasks

### 🔍 Scan & Replace
- Search entire `backend/app/` directory for:
  - `ChatOpenAI`
- Replace with:
  - `ChatGoogleGenerativeAI` (from `langchain_google_genai`)

---

### 🧠 Update Agent Nodes

Modify the following files:

- `backend/app/agents/nodes/recruiter.py`
- `backend/app/agents/nodes/coach.py`
- `backend/app/agents/nodes/judge.py`
- `backend/app/agents/nodes/cover_writer.py`

Ensure:
- All LLM calls use Gemini
- No fallback to OpenAI remains

---

### ⚙️ Model Standardization

Use:

- `gemini-1.5-flash`
  - For: Recruiter, Coach (fast inference)

- `gemini-1.5-pro` (optional)
  - For: Judge, Cover Letter generation (higher quality)

---

### 📦 Structured Output

- Enforce JSON / schema-based responses for:
  - Judge node
  - Cover letter node

- Prevent:
  - UI crashes
  - Parsing errors in frontend

---

# 🧹 2. Data Quality: Scraper Refactor

## Goal
Eliminate noisy / aggregated job listings.

---

## File

`scripts/scrape_live_jobs.py`

---

## Tasks

### 🚫 Filter Aggregated Listings

Add filtering logic to reject:

- Titles containing:
  - "jobs"
  - "Search Results"
  - "Best Jobs"
  - "X+ jobs"

- Titles longer than **15 words**

---

### 📉 API Conservation

- Reduce default fetch limit to **30% of previous value**

Example:
- `limit=10` → `limit=3`

---

### ✅ Validate Listings

Only ingest jobs where:

- `company` exists
- `location` exists

Reject incomplete entries.

---

# ⚡ 3. Logic: Database-First Matching

## Goal
Use Supabase as a cache before calling external APIs.

---

## File

`backend/app/api/v1/match.py`

---

## Tasks

### 🧠 Step 1: Query Database First

- Perform vector similarity search using `pgvector`
- Retrieve top matches BEFORE calling Tavily

---

### 🔁 Step 2: Conditional Scraping

ONLY call:

mcp_client.search_jobs()

IF:

- Fewer than **3 results** with similarity > `0.8`
- OR request includes:
  refresh=true

---

### 💾 Step 3: Persist Results

When scraping occurs:

- Generate embeddings
- Store in Supabase
- Avoid re-scraping same jobs later

---

# 🎨 4. Frontend: Match & Refresh UI

## Goal
Improve control, clarity, and stability of results.

---

## File

`frontend/app.py`

---

## Tasks

### 🧹 Clean Job Cards

- Filter out:
  - Aggregated titles
  - Invalid job entries from DB

---

### 🔄 Add Refresh Toggle

Add UI element:

🔄 Refresh Live Source

Behavior:

- When checked → send:
  refresh=true
  to backend

---

### 🧠 Fix Agent Debate Viewer

- Update parsing logic to support:
  - Gemini JSON responses

- Ensure:
  - No crashes on malformed outputs
  - Graceful fallback handling

---

# 🧪 5. Success Verification

Ensure ALL conditions pass:

---

### ✅ OpenAI-Free Execution
- Remove `OPENAI_API_KEY`
- System must run without errors

---

### ✅ Clean Results
- Query: "Python Developer"
- MUST NOT return:
  - "100+ jobs"
  - "Search results"

---

### ⚡ Cache Efficiency
- First query → normal latency
- Second query → near-instant (DB hit)

---

### ✍️ Cover Letter Accuracy
- Generated output must:
  - Use correct job data
  - Align with selected role

---

# 🚩 AI Safety & Constraints

---

## 🔐 Key Safety
- NEVER log or expose:
  - `GOOGLE_API_KEY`

---

## 📁 Path Safety
- Restrict changes to:
  - `/backend/`
  - `/frontend/`
  - `/scripts/`

---

## ⚡ Async Safety
- ALL:
  - DB calls
  - LLM calls

MUST use:
async / await

---

## ❗ Critical Constraints

- DO NOT change embedding dimension (768)
- DO NOT break existing DB schema compatibility
- DO NOT remove caching logic once implemented

---

# 🧭 Execution Priority (IMPORTANT)

Follow this order:

1. Gemini Migration (critical dependency removal)
2. Database-first matching (performance + cost)
3. Scraper cleanup (data quality)
4. Frontend fixes (UX + control)

---

# 🤖 Agent Instructions Summary

When implementing:

- Prefer modifying **existing logic** over adding redundant layers
- Keep functions **modular and testable**
- Validate every step with:
  - Logs
  - Sample queries

---

# 🚀 End State

The system should be:

- Fully Gemini-powered
- Fast (cache-first)
- Clean (high-quality job data)
- Stable (no UI crashes)
- Cost-efficient (minimal API calls)

---
