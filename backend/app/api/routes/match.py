"""
Match Route

Trigger the agent pipeline for job-resume matching.
"""

import hashlib
import re
import time
import traceback
from datetime import datetime, timezone
from typing import List, Optional
import json
import os
import uuid
import httpx

from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.resume_parser import parse_resume, extract_skills
from app.models import JobMatch
from langchain_google_genai import ChatGoogleGenerativeAI
from app.services.embedding import get_embedding as get_gemini_embedding
from app.services.supabase_vector_service import get_vector_service
from app.core.config import settings

# GitHub MCP Server URL — use localhost for local dev, Docker hostname for containers
GITHUB_MCP_URL = os.getenv("MCP_GITHUB_SERVER_URL", "http://localhost:8001")
JOB_MARKET_MCP_URL = os.getenv("MCP_JOBMARKET_SERVER_URL", "http://localhost:8002")
print(f"DEBUG [match.py]: GitHub MCP URL = {GITHUB_MCP_URL}")
print(f"DEBUG [match.py]: Job Market MCP URL = {JOB_MARKET_MCP_URL}")

router = APIRouter()

# Initialize Gemini LLM
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0,
) if GOOGLE_API_KEY else None

# ── Known job aggregator domains / names (strip from company field) ──────────
KNOWN_AGGREGATORS = {
    "linkedin", "indeed", "glassdoor", "ziprecruiter", "monster",
    "careerbuilder", "dice", "simplyhired", "lever", "greenhouse",
    "workday", "jobvite", "smartrecruiters", "built in", "builtin",
    "wellfound", "angellist", "otta", "remoteok", "weworkremotely",
}

# Location patterns that should never be treated as a company name
_LOCATION_RE = re.compile(
    r"^("
    r"remote|hybrid|on-?site|worldwide|global|anywhere|"
    r"(us|uk|eu|ca|au|usa)\s+(remote|hybrid|on-?site)|"
    r"(remote|hybrid|on-?site)\s+(us|uk|eu|ca|au|usa|united states)|"
    r"[a-z][a-z\s]+,\s*[a-z]{2}(\s+\d{5})?|"
    r"united states|united kingdom|north america|europe|apac"
    r")$",
    re.IGNORECASE,
)
# Skills-list pattern: contains " | " or multiple tech keywords
_TECH_KEYWORDS = {"python", "java", "react", "node", "typescript", "javascript",
                  "golang", "rust", "scala", "pytorch", "tensorflow", "aws", "gcp"}

def _is_invalid_company(name: str) -> bool:
    """Return True if the parsed company name is actually a location or skills list."""
    if not name or name.lower() in KNOWN_AGGREGATORS:
        return True
    if _LOCATION_RE.match(name.strip()):
        return True
    # Skills list: contains pipe-separated tech terms
    if "|" in name and any(kw in name.lower() for kw in _TECH_KEYWORDS):
        return True
    return False


async def get_embedding(text: str) -> List[float]:
    """Get embedding for text using Google Gemini."""
    try:
        return await get_gemini_embedding(text[:8000])
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0.0] * 768


def _extract_source(url: str) -> str:
    """Extract source name from URL."""
    if "linkedin" in url:
        return "LinkedIn"
    elif "indeed" in url:
        return "Indeed"
    elif "glassdoor" in url:
        return "Glassdoor"
    elif "greenhouse" in url:
        return "Greenhouse"
    elif "lever" in url:
        return "Lever"
    return "Web"


def _parse_raw_jobs(tavily_results: list) -> list:
    """
    Improved parser for raw Tavily job results → structured dicts.

    Improvements over v1:
    - Explicit aggregator blocklist — LinkedIn/Indeed never land as company names
    - Salary range extraction from snippet text
    - Experience level inferred from title keywords
    - Stricter quality filters (min title length, no aggregator-only results)
    """
    jobs = []
    seen_urls = set()
    agg_pattern = re.compile(
        r"search results|best jobs|\d[\d,]*\+?\s+jobs?\s+(in|near|for)|"
        r"top\s+\d+\s+jobs?|jobs?\s+hiring|salary\s+guide",
        re.IGNORECASE,
    )
    salary_pattern = re.compile(
        r"\$\s*([\d,]+)\s*[kK]?\s*[-–—]\s*\$?\s*([\d,]+)\s*[kK]?", re.IGNORECASE
    )

    for result in tavily_results:
        url = result.get("url", "")
        title = result.get("title", "").strip()
        snippet = result.get("snippet", result.get("content", "")).strip()

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip aggregated listing pages and overly long / noisy titles
        if agg_pattern.search(title) or len(title.split()) > 14:
            continue

        # ── Parse company from title ──────────────────────────────────────────
        company = "Unknown"
        clean_title = title

        if " - " in title:
            parts = title.split(" - ", 1)
            clean_title = parts[0].strip()
            company = parts[1].split("|")[0].strip()
        elif re.search(r"\bat\b", title, re.IGNORECASE):
            parts = re.split(r"\bat\b", title, maxsplit=1, flags=re.IGNORECASE)
            clean_title = parts[0].strip()
            company = parts[1].split("|")[0].strip() if len(parts) > 1 else "Unknown"
        elif " | " in title:
            parts = title.split(" | ", 1)
            clean_title = parts[0].strip()
            candidate = parts[1].strip()
            if not any(agg in candidate.lower() for agg in KNOWN_AGGREGATORS):
                company = candidate

        # ── Strip aggregator noise from both fields ───────────────────────────
        for agg in KNOWN_AGGREGATORS:
            company = re.sub(
                rf"\s*[-|]\s*{agg}\b", "", company, flags=re.IGNORECASE
            ).strip()
            clean_title = re.sub(
                rf"\s*[-|]\s*{agg}\b", "", clean_title, flags=re.IGNORECASE
            ).strip()

        # ── Quality gates ─────────────────────────────────────────────────────
        if _is_invalid_company(company) or company == "Unknown" or len(clean_title) < 5:
            continue

        # ── Derived fields ────────────────────────────────────────────────────
        full_text = (clean_title + " " + snippet).lower()
        remote_type = (
            "remote" if "remote" in full_text
            else "hybrid" if "hybrid" in full_text
            else "on-site"
        )

        # Experience level from title keywords
        tl = clean_title.lower()
        if any(k in tl for k in ("senior", "sr.", "sr ", "lead", "principal", "staff")):
            exp_level = "senior"
        elif any(k in tl for k in ("junior", "jr.", "jr ", "entry", "associate", "intern")):
            exp_level = "entry"
        elif any(k in tl for k in ("director", "vp ", "v.p.", "head of", "chief")):
            exp_level = "lead"
        else:
            exp_level = "mid"

        # Salary extraction from snippet
        salary_min = salary_max = None
        m = salary_pattern.search(snippet)
        if m:
            try:
                s_min = int(m.group(1).replace(",", ""))
                s_max = int(m.group(2).replace(",", ""))
                # Handle "k" suffix (e.g. $120k)
                if "k" in m.group(0).lower():
                    s_min = s_min * 1000 if s_min < 1000 else s_min
                    s_max = s_max * 1000 if s_max < 1000 else s_max
                if s_min > 10_000 and s_max > 10_000:
                    salary_min, salary_max = s_min, s_max
            except Exception:
                pass

        jobs.append({
            "title": clean_title,
            "company": company,
            "description": (snippet or f"Position at {company}.")[:2000],
            "source_url": url,
            "source_platform": _extract_source(url),
            "remote_type": remote_type,
            "job_type": "full-time",
            "experience_level": exp_level,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "location": "Remote" if remote_type == "remote" else "On-site",
        })

    return jobs


SCRAPE_COOLDOWN_HOURS = 24  # Minimum hours between Tavily calls


async def _db_is_fresh(supabase, hours: int = SCRAPE_COOLDOWN_HOURS) -> bool:
    """
    Return True if any job was scraped within the last `hours` hours.
    Used to prevent redundant Tavily calls across user sessions.
    """
    try:
        result = (
            supabase.table("jobs")
            .select("scraped_at")
            .order("scraped_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return False
        last_str = result.data[0].get("scraped_at", "")
        if not last_str:
            return False
        last = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        print(f"  ℹ️  DB last scraped {age_hours:.1f}h ago (cooldown={hours}h)")
        return age_hours < hours
    except Exception as e:
        print(f"  ⚠️  Freshness check failed (non-fatal): {e}")
        return False  # Fail open — allow scrape if unsure


async def _scrape_and_store_jobs(query: str, vector_service) -> int:
    """
    Fetch jobs from Job Market MCP, embed, and store in Supabase.
    Returns number of new jobs stored.
    """
    stored = 0
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{JOB_MARKET_MCP_URL}/tools/search_jobs",
                json={"query": query, "limit": 5},
            )
            if resp.status_code != 200:
                print(f"  ⚠️ Job Market MCP returned {resp.status_code}")
                return 0
            raw_jobs = resp.json().get("jobs", [])

        parsed = _parse_raw_jobs(raw_jobs)
        print(f"  ✅ Tavily returned {len(raw_jobs)} raw → {len(parsed)} parsed jobs")
        supabase = vector_service.supabase

        for job in parsed:
            # Dedup check
            existing = (
                supabase.table("jobs")
                .select("id")
                .eq("source_url", job["source_url"])
                .execute()
            )
            if existing.data:
                continue

            embed_text = f"{job['title']} at {job['company']}. {job['description']}"
            try:
                embedding = await get_gemini_embedding(embed_text[:8000])
            except Exception as e:
                print(f"  ⚠️ Embedding failed for '{job['title']}': {e}")
                continue

            row = {
                "id": str(uuid.uuid4()),
                "title": job["title"],
                "company": job["company"],
                "description": job["description"],
                "source_url": job["source_url"],
                "url": job["source_url"],          # v2 schema column
                "source_platform": job["source_platform"],
                "remote_type": job["remote_type"],
                "job_type": job["job_type"],
                "experience_level": job["experience_level"],
                "salary_min": job["salary_min"],
                "salary_max": job["salary_max"],
                "location": job["location"],
                "embedding": embedding,
                "is_active": True,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                supabase.table("jobs").insert(row).execute()
                stored += 1
                print(f"    + Stored: {job['title']} @ {job['company']}")
            except Exception as e:
                print(f"  ⚠️ Insert failed for '{job['title']}': {e}")

    except Exception as e:
        print(f"  ⚠️ _scrape_and_store_jobs failed: {e}")
    return stored


async def _persist_user_profile(
    resume_content: bytes,
    resume_data,
    resume_text: str,
    skills: list,
    github_username: Optional[str],
    supabase,
) -> Optional[str]:
    """
    Upsert user profile in Supabase for persistent storage.
    Uses SHA-256 of resume bytes as a stable dedup key (session_id).
    Returns profile_id or None on failure.
    """
    try:
        session_id = hashlib.sha256(resume_content).hexdigest()[:32]

        # Build structured work history
        work_history = []
        for exp in resume_data.experience or []:
            work_history.append({
                "title": getattr(exp, "title", "") or "",
                "company": getattr(exp, "company", "") or "",
                "description": (getattr(exp, "description", "") or "")[:500],
            })

        # Build structured education
        education = []
        for edu in resume_data.education or []:
            education.append({
                "degree": getattr(edu, "degree", "") or "",
                "institution": getattr(edu, "institution", "") or "",
                "year": str(getattr(edu, "graduation_year", "") or ""),
            })

        # Generate resume embedding for candidate search (headhunter mode)
        resume_embedding = None
        try:
            resume_embedding = await get_gemini_embedding(resume_text[:8000])
        except Exception as e:
            print(f"  ⚠️ Resume embedding failed (non-fatal): {e}")

        profile_data = {
            "raw_resume_text": resume_text[:5000],
            "experience_summary": resume_data.summary or "",
            "skills": skills,
            "work_history": work_history,
            "education": education,
            "github_username": github_username or "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if resume_embedding:
            profile_data["resume_embedding"] = resume_embedding

        # Upsert: update if exists, insert if new
        existing = (
            supabase.table("user_profiles")
            .select("id")
            .eq("session_id", session_id)
            .execute()
        )
        if existing.data:
            profile_id = existing.data[0]["id"]
            supabase.table("user_profiles").update(profile_data).eq("id", profile_id).execute()
            print(f"  ✅ User profile updated (id={profile_id[:8]}...)")
        else:
            profile_data["id"] = str(uuid.uuid4())
            profile_data["session_id"] = session_id
            result = supabase.table("user_profiles").insert(profile_data).execute()
            profile_id = result.data[0]["id"] if result.data else profile_data["id"]
            print(f"  ✅ User profile created (id={profile_id[:8]}...)")

        return profile_id

    except Exception as e:
        print(f"  ⚠️ User profile persistence failed (non-fatal): {e}")
        return None


def extract_skills_with_llm(text: str, max_skills: int = 10) -> List[str]:
    """Extract required skills from job description using Gemini."""
    if not text or len(text.strip()) < 50 or not llm:
        return []
    try:
        prompt = (
            f"You are a technical recruiter. Extract the key technical skills, tools, and "
            f"technologies required for a job. Return ONLY a comma-separated list of skills, "
            f"nothing else. Focus on: programming languages, frameworks, tools, cloud platforms, "
            f"databases, and methodologies. Extract the top {max_skills} required skills from "
            f"this job description:\n\n{text[:2000]}"
        )
        response = llm.invoke(prompt)
        skills = [s.strip() for s in response.content.strip().split(",") if s.strip()]
        return skills[:max_skills]
    except Exception as e:
        print(f"Gemini skill extraction failed: {e}")
        return []


@router.post("/match")
async def match_jobs(
    query: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    level: Optional[str] = Form(None),
    github_username: Optional[str] = Form(None),
    refresh: Optional[str] = Form("0"),
    resume: Optional[UploadFile] = File(None),
):
    """Match jobs using semantic search via Supabase pgvector."""
    print("\n" + "═" * 60)
    print("DEBUG: Match request received by backend")
    print(f"DEBUG: Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DEBUG: query={query!r}, location={location!r}, level={level!r}")
    print(f"DEBUG: github_username={github_username!r}")
    print(f"DEBUG: resume={'YES (' + resume.filename + ')' if resume else 'NO'}")
    print("═" * 60)

    overall_start = time.time()

    try:
        # ── Step 1: Parse Resume ──────────────────────────────────────────────
        step_start = time.time()
        print("\n--- Step 1: Processing input data ---")
        resume_text = ""
        skills = []
        resume_content = b""

        if resume:
            print(f"  - Parsing resume: {resume.filename}")
            if not resume.filename.lower().endswith(".pdf"):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Only PDF resumes are supported"},
                )
            resume_content = await resume.read()
            print(f"  - Resume bytes read: {len(resume_content)}")
            resume_data = await parse_resume(resume_content)

            skill_names = [
                s.name if hasattr(s, "name") else str(s)
                for s in (resume_data.skills or [])
            ]
            resume_text = f"{resume_data.summary or ''} {' '.join(skill_names)} "
            for exp in resume_data.experience or []:
                resume_text += f"{exp.title} {exp.company} {exp.description or ''} "

            skills = skill_names
            print(f"  ✅ Resume parsed: {len(skills)} skills — {skills[:10]}")
        else:
            print("  - No resume uploaded, using query-only mode")

        print(f"  ⏱  Step 1 took {time.time() - step_start:.2f}s")

        # ── Step 2: Fetch GitHub Profile ──────────────────────────────────────
        step_start = time.time()
        print("\n--- Step 2: Fetching external context ---")
        github_context = ""
        if github_username:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{GITHUB_MCP_URL}/tools/get_user_repos",
                        json={"username": github_username},
                    )
                    if response.status_code == 200:
                        repos = response.json().get("repos", [])[:5]
                        languages = {r["language"] for r in repos if r.get("language")}
                        topics = {t for r in repos for t in r.get("topics", [])}
                        github_context = f" GitHub skills: {', '.join(languages)}. "
                        github_context += f"Projects: {', '.join(topics)}. "
                        print(f"  ✅ GitHub: {len(repos)} repos, langs: {languages}")
                    else:
                        print(f"  ⚠️ GitHub MCP {response.status_code}")
            except Exception as e:
                print(f"  ⚠️ GitHub fetch failed (non-fatal): {e}")
        else:
            print("  - No GitHub username provided")
        print(f"  ⏱  Step 2 took {time.time() - step_start:.2f}s")

        # ── Step 3: Build Search Context ──────────────────────────────────────
        step_start = time.time()
        print("\n--- Step 3: Building search context ---")
        search_context = f"{query or ''} {level or ''} {location or ''}"
        if resume_text:
            search_context += f" Skills: {', '.join(skills[:20])}. Experience: {resume_text[:1000]}"
        if github_context:
            search_context += github_context
        print(f"  - Context length: {len(search_context)} chars")
        print(f"  ⏱  Step 3 took {time.time() - step_start:.2f}s")

        # ── Step 4a: Log request to documents table ───────────────────────────
        step_start = time.time()
        print("\n--- Step 4: Recording request + persisting user profile ---")
        vector_service = get_vector_service()
        try:
            doc_data = {
                "id": str(uuid.uuid4()),
                "content": search_context[:1000],
                "metadata": {"query": query, "location": location, "github_username": github_username},
            }
            vector_service.supabase.table("documents").insert(doc_data).execute()
            print("  ✅ Request logged to documents table")
        except Exception as e:
            print(f"  ⚠️ documents table save failed (non-fatal): {e}")

        # ── Step 4b: Persist user profile ────────────────────────────────────
        profile_id = None
        if resume_content and resume_data:
            profile_id = await _persist_user_profile(
                resume_content=resume_content,
                resume_data=resume_data,
                resume_text=resume_text,
                skills=skills,
                github_username=github_username,
                supabase=vector_service.supabase,
            )
        print(f"  ⏱  Step 4 took {time.time() - step_start:.2f}s")

        # ── Step 5: Vector Search ─────────────────────────────────────────────
        step_start = time.time()
        print("\n--- Step 5: Executing semantic search in Supabase ---")
        search_results = await vector_service.search_jobs(query=search_context, top_k=10)
        print(f"  ✅ Supabase returned {len(search_results)} results")
        print(f"  ⏱  Step 5 took {time.time() - step_start:.2f}s")

        # ── Step 5b: Conditional live scrape (credit-aware caching) ─────────
        # Rules (in priority order):
        #   1. refresh=True  → always scrape (user explicitly asked for fresh data)
        #   2. DB has results → use cache, skip Tavily
        #   3. DB empty + scraped < 24h → trust cache, skip Tavily
        #   4. DB empty + stale/never scraped → call Tavily
        step_start = time.time()
        refresh_bool = str(refresh).strip() in ("1", "true", "True")
        print(f"\n--- Step 5b: Cache decision ({len(search_results)} DB results, refresh={refresh_bool}) ---")

        should_scrape = False
        scrape_reason = ""

        if refresh_bool:
            should_scrape = True
            scrape_reason = "user requested refresh"
        elif len(search_results) > 0:
            print(f"  ✅ {len(search_results)} results from DB — Tavily skipped (credits preserved)")
        else:
            # DB returned nothing — check if we've scraped recently
            db_fresh = await _db_is_fresh(vector_service.supabase)
            if db_fresh:
                print(f"  ✅ DB is fresh (<{SCRAPE_COOLDOWN_HOURS}h old) but no matches for this profile — Tavily skipped")
            else:
                should_scrape = True
                scrape_reason = f"0 results + DB stale (>{SCRAPE_COOLDOWN_HOURS}h)"

        if should_scrape:
            scrape_query = query or (", ".join(skills[:5]) if skills else "software engineer")
            print(f"  ℹ️  Calling Tavily: '{scrape_query}' ({scrape_reason})")
            new_count = await _scrape_and_store_jobs(scrape_query, vector_service)
            if new_count > 0:
                print(f"  ✅ Stored {new_count} new jobs — re-running vector search")
                search_results = await vector_service.search_jobs(query=search_context, top_k=10)
                print(f"  ✅ Updated search returned {len(search_results)} results")
            else:
                print("  ℹ️  No new jobs scraped (all duplicates or filtered)")

        print(f"  ⏱  Step 5b took {time.time() - step_start:.2f}s")

        # ── Step 6: Per-job LLM analysis ──────────────────────────────────────
        step_start = time.time()
        print(f"\n--- Step 6: Analysing {len(search_results)} results ---")
        matches = []

        for i, result in enumerate(search_results):
            job_description = result.get("description", "") or ""
            job_title = result.get("title", "")
            print(f"  - [{i+1}/{len(search_results)}] {job_title[:50]}")

            job_skills = set(extract_skills_with_llm(f"{job_title}\n\n{job_description}", max_skills=10))
            resume_skills_lower = {s.lower() for s in skills if s}
            missing_skills = [
                s for s in job_skills if s.lower() not in resume_skills_lower
            ][:5]

            # url: prefer explicit url field, fall back to source_url
            job_url = result.get("url") or result.get("source_url", "")

            matches.append({
                "id": str(result.get("id")),
                "title": result.get("title", "Unknown Role"),
                "company": result.get("company", "Unknown Company"),
                "description": job_description,
                "url": job_url,
                "source": result.get("source_platform", "Web"),
                "remote_type": result.get("remote_type"),
                "job_type": result.get("job_type"),
                "experience_level": result.get("experience_level"),
                "salary_max": result.get("salary_max"),
                "match_score": result.get("score", 0.7),
                "recruiter_concerns": [],
                "coach_highlights": [],
                "missing_skills": missing_skills,
            })

        elapsed = time.time() - overall_start
        print(f"  ⏱  Step 6 took {time.time() - step_start:.2f}s")
        print(f"\n{'═' * 60}")
        print(f"✅ Match complete: {len(matches)} jobs in {elapsed:.2f}s")
        print(f"{'═' * 60}\n")

        return {
            "success": True,
            "matches": matches,
            "count": len(matches),
            "parsed_skills": [s for s in skills if s],
            "profile_id": profile_id,
            "processing_time_seconds": round(elapsed, 2),
            "debug_info": {"status": "all steps complete"},
        }

    except Exception as e:
        elapsed = time.time() - overall_start
        print(f"\n{'!' * 60}")
        print(f"❌ CRITICAL ERROR in match_jobs after {elapsed:.2f}s")
        print(f"Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        print(f"{'!' * 60}\n")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "detail": "Failed during semantic search or analysis pipeline",
                "traceback": traceback.format_exc(),
            },
        )
