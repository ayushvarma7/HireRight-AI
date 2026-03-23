# HireRight AI | Claude Code Work Session 2

## Context: What Was Already Fixed (Work Session 1)
These items are DONE — do not re-implement:
- All agent nodes (recruiter, coach, judge, cover_writer) use `ChatGoogleGenerativeAI` with `gemini-2.0-flash`
- `match.py` has DB-first logic: queries Supabase first, only calls Job Market MCP if <3 results with score>0.8 OR `refresh=True`
- Scraper (`scripts/scrape_live_jobs.py`) filters aggregated job titles, default limit=3, rejects unknown company
- Frontend cover letter calls `/api/v1/cover-letter/quick` (Gemini-powered backend endpoint) — no more OpenAI
- AI Debate routing bug fixed (`"🤖 AI Debate"` now routes correctly to `show_agent_debate()`)
- Job card HTML bleeding fixed (uses Streamlit `st.columns()` + `st.container()` instead of nested HTML)
- `gemini-1.5-flash` → `gemini-2.0-flash` across all files (config.py, match.py, cover_letter.py, roadmap_agent.py)

---

## Current Known Issues (Fix These Now)

### 🔴 Issue 1: AI Debate Page Shows No Content After Routing Fix
**Symptom**: Page navigates but shows blank content or "No job matches found" even when matches exist.
**Root cause to investigate**:
- `show_agent_debate()` checks `st.session_state.get("matched_jobs")` — verify this is being populated correctly after a match run
- The debate result serialization from backend returns `recruiter_arguments` and `coach_arguments` as list of dicts with keys `{point, evidence, strength}` — confirm frontend accesses these correctly
- The `run_langgraph_debate()` call posts to `/api/v1/debate/run-debate` — check that endpoint is healthy via `/api/v1/debate/health`

**File**: `frontend/app.py` → `show_agent_debate()`, `run_langgraph_debate()`

---

### 🔴 Issue 2: Cover Letter Page — "Software Developer Java C++ Python at LinkedIn" in dropdown
**Symptom**: The job title in the cover letter target selector includes the source platform ("at LinkedIn") because it's parsed from the raw Tavily title.
**Root cause**: `parse_job_listings_from_snippets()` in the scraper uses "Title at Company" pattern, but LinkedIn search results have "Title at LinkedIn" as the full page title. The company then ends up as "LinkedIn" and the clean title still looks odd.
**Fix needed**:
- In `scripts/scrape_live_jobs.py`, add `"LinkedIn"` and `"Indeed"` to the list of invalid company names (same as "Unknown")
- Also strip source platform names from the job title itself

**File**: `scripts/scrape_live_jobs.py` → `parse_job_listings_from_snippets()`

---

### 🔴 Issue 3: Dashboard Job Cards Still Using Old HTML Pattern
**Symptom**: `show_dashboard()` uses the same old HTML-injection pattern for job cards (lines ~360-386 in `frontend/app.py`) that caused the bleeding in `show_job_match()`.
**Fix needed**: Rewrite the dashboard job card loop using the same `st.container()` + `st.columns()` pattern implemented in `show_job_match()`.

**File**: `frontend/app.py` → `show_dashboard()` (the job listing section at the bottom)

---

### 🟡 Issue 4: Backend Restart Required After Model Change
**Action needed**: The backend must be restarted for the `gemini-2.0-flash` config change to take effect (the `@lru_cache` on `get_settings()` means the old model name is cached in memory).
**Command**: `cd backend && uvicorn app.main:app --reload`

---

### 🟡 Issue 5: Supabase `match_threshold` Too Low in Vector Search
**File**: `backend/app/services/supabase_vector_service.py` line 87
**Current**: `"match_threshold": 0.5`
**Required per CLAUDE.md**: minimum 0.7
**Fix**: Change `match_threshold` from `0.5` to `0.7`

---

## Priority Architecture Improvements

### ⚡ Priority 1: Async/Sync Mismatch in `roadmap_agent.py`
`generate_skill_roadmap()` uses `llm.invoke()` (synchronous) inside what may be called from an async FastAPI context.
**Fix**: Convert to `async def` + `await llm.ainvoke()`.

### ⚡ Priority 2: `show_job_match()` Sends `refresh` as String Not Bool
In `frontend/app.py`, the payload sets `"refresh": str(refresh_live).lower()` which sends `"true"` or `"false"` as a string. FastAPI's `Form(False)` for `Optional[bool]` may not parse this correctly.
**Fix**: FastAPI form fields for booleans need special handling. Either:
- Change to `"refresh": "1" if refresh_live else "0"` in frontend
- And `refresh: Optional[str] = Form("0")` + convert `refresh = refresh_str == "1"` in backend

### ⚡ Priority 3: Cover Letter Needs Parsed Resume Data
Currently `show_cover_letter()` sends `candidate_profile = st.session_state.get("resume_summary", "...")` which is often empty because `resume_summary` is never stored in session state during the match flow.
**Fix**: In `show_job_match()`, after parsing, store `st.session_state["resume_summary"] = resume_text[:2000]`.

---

## File Map (Key Paths)
```
backend/
  app/
    core/config.py          ← gemini_model = "gemini-2.0-flash"
    agents/
      nodes/recruiter.py    ← uses settings.gemini_model
      nodes/coach.py        ← uses settings.gemini_model
      nodes/judge.py        ← uses settings.gemini_model
      nodes/cover_writer.py ← uses settings.gemini_model
      roadmap_agent.py      ← hardcoded gemini-2.0-flash (NOT async — needs fix)
    api/routes/
      match.py              ← DB-first + conditional MCP scrape
      cover_letter.py       ← /quick endpoint for frontend
      debate.py             ← /run-debate → full LangGraph pipeline
    services/
      supabase_vector_service.py  ← match_threshold=0.5 (needs 0.7)
frontend/
  app.py                    ← All UI (single file ~1600 lines)
scripts/
  scrape_live_jobs.py       ← Tavily → Supabase pipeline
```

---

## Success Criteria
- [ ] AI Debate page shows debate results when a job is selected and "Run AI Debate" is clicked
- [ ] Cover letter generates without error and uses actual resume data (not empty string)
- [ ] All job cards render without raw HTML visible
- [ ] Vector search uses threshold 0.7
- [ ] No OpenAI API key required anywhere in the system
- [ ] `refresh=True` correctly triggers live scraping in match.py
