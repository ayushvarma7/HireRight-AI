"""
Match Route

Trigger the agent pipeline for job-resume matching.
"""

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
from app.services.s3_storage import upload_resume, upload_parsed_resume
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


async def get_embedding(text: str) -> List[float]:
    """Get embedding for text using Google Gemini."""
    try:
        # Use our centralized service which has retry logic
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
    return "Web"


def _parse_raw_jobs(tavily_results: list) -> list:
    """Minimal parser for raw Tavily job results → structured dicts."""
    jobs = []
    seen_urls = set()
    agg_pattern = re.compile(
        r'search results|best jobs|\d[\d,]*\+?\s+jobs?\s+in', re.IGNORECASE
    )
    for result in tavily_results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", result.get("content", ""))
        if url in seen_urls or not url:
            continue
        seen_urls.add(url)
        # Skip aggregated pages
        if agg_pattern.search(title) or len(title.split()) > 15:
            continue
        # Parse company from title
        company = "Unknown"
        clean_title = title
        if " - " in title:
            parts = title.split(" - ")
            clean_title = parts[0].strip()
            company = parts[1].split("|")[0].strip()
        elif " at " in title.lower():
            parts = re.split(r"\bat\b", title, maxsplit=1, flags=re.IGNORECASE)
            clean_title = parts[0].strip()
            company = parts[1].split("|")[0].strip() if len(parts) > 1 else "Unknown"
        elif " | " in title:
            parts = title.split(" | ")
            clean_title = parts[0].strip()
            if len(parts) > 1 and "LinkedIn" not in parts[1] and "Indeed" not in parts[1]:
                company = parts[1].strip()
        for suffix in ["| LinkedIn", "| Indeed", "- LinkedIn", "- Indeed"]:
            company = company.replace(suffix, "").strip()
            clean_title = clean_title.replace(suffix, "").strip()
        if len(clean_title) < 5 or not company or company == "Unknown":
            continue
        full_text = (clean_title + " " + snippet).lower()
        remote_type = "remote" if "remote" in full_text else "hybrid" if "hybrid" in full_text else "on-site"
        jobs.append({
            "title": clean_title,
            "company": company,
            "description": snippet[:2000] if snippet else f"Position at {company}.",
            "source_url": url,
            "source_platform": _extract_source(url),
            "remote_type": remote_type,
            "job_type": "full-time",
            "experience_level": "mid",
            "salary_min": None,
            "salary_max": None,
            "location": remote_type.title(),
        })
    return jobs


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
                json={"query": query, "limit": 3},
            )
            if resp.status_code != 200:
                print(f"  ⚠️ Job Market MCP returned {resp.status_code}")
                return 0
            raw_jobs = resp.json().get("jobs", [])

        parsed = _parse_raw_jobs(raw_jobs)
        supabase = vector_service.supabase

        for job in parsed:
            # Dedup check
            existing = supabase.table("jobs").select("id").eq("source_url", job["source_url"]).execute()
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
                "url": job["source_url"],
                "source_url": job["source_url"],
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
            except Exception as e:
                print(f"  ⚠️ Insert failed for '{job['title']}': {e}")
    except Exception as e:
        print(f"  ⚠️ _scrape_and_store_jobs failed: {e}")
    return stored


def extract_skills_with_llm(text: str, max_skills: int = 10) -> List[str]:
    """
    Extract required skills from job description using Gemini.
    """
    if not text or len(text.strip()) < 50 or not llm:
        return []
    
    try:
        prompt = f"You are a technical recruiter. Extract the key technical skills, tools, and technologies required for a job. Return ONLY a comma-separated list of skills, nothing else. Focus on: programming languages, frameworks, tools, cloud platforms, databases, and methodologies. Extract the top {max_skills} required skills from this job description:\n\n{text[:2000]}"
        
        response = llm.invoke(prompt)
        skills_text = response.content.strip()
        # Parse comma-separated list
        skills = [s.strip() for s in skills_text.split(",") if s.strip()]
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
    """
    Match jobs using semantic search via Supabase pgvector.
    """
    # ═══ MANDATORY CHECK-IN LOG ═══
    print("\n" + "═" * 60)
    print("DEBUG: Match request received by backend")
    print(f"DEBUG: Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DEBUG: query={query!r}, location={location!r}, level={level!r}")
    print(f"DEBUG: github_username={github_username!r}")
    print(f"DEBUG: resume={'YES (' + resume.filename + ')' if resume else 'NO'}")
    print("═" * 60)
    
    overall_start = time.time()
    
    try:
        # 1. Parse Resume
        step_start = time.time()
        print("\n--- Step 1: Processing input data ---")
        resume_text = ""
        skills = []
        
        if resume:
            print(f"  - Parsing resume: {resume.filename}")
            if not resume.filename.lower().endswith(".pdf"):
                print("  ❌ ERROR: Non-PDF file rejected")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Only PDF resumes are supported"}
                )
            
            content = await resume.read()
            print(f"  - Resume bytes read: {len(content)}")
            resume_data = await parse_resume(content)
            
            skill_names = [s.name if hasattr(s, 'name') else str(s) for s in (resume_data.skills or [])]
            resume_text = f"{resume_data.summary or ''} {' '.join(skill_names)} "
            for exp in resume_data.experience or []:
                resume_text += f"{exp.title} {exp.company} {exp.description or ''} "
            
            skills = skill_names
            print(f"  ✅ Resume parsed: {len(skills)} skills found: {skills[:10]}")
        else:
            print("  - No resume uploaded, using query-only mode")
        
        print(f"  ⏱  Step 1 took {time.time() - step_start:.2f}s")
        
        # 2. Fetch GitHub Profile
        step_start = time.time()
        print("\n--- Step 2: Fetching external context ---")
        github_context = ""
        if github_username:
            try:
                print(f"  - Fetching GitHub profile for: {github_username}")
                print(f"  - MCP URL: {GITHUB_MCP_URL}")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{GITHUB_MCP_URL}/tools/get_user_repos",
                        json={"username": github_username}
                    )
                    if response.status_code == 200:
                        github_data = response.json()
                        repos = github_data.get("repos", [])[:5]
                        languages = set()
                        topics = set()
                        for repo in repos:
                            if repo.get("language"):
                                languages.add(repo["language"])
                            topics.update(repo.get("topics", []))
                        
                        github_context = f" GitHub skills: {', '.join(languages)}. "
                        github_context += f"Projects: {', '.join(topics)}. "
                        print(f"  ✅ GitHub profile fetched: {len(repos)} repos")
                    else:
                        print(f"  ⚠️ GitHub MCP returned status {response.status_code}: {response.text[:200]}")
            except Exception as e:
                print(f"  ⚠️ GitHub fetch failed (non-fatal): {e}")
        else:
            print("  - No GitHub username provided, skipping")
        
        print(f"  ⏱  Step 2 took {time.time() - step_start:.2f}s")
        
        # 3. Create Search Context
        step_start = time.time()
        print("\n--- Step 3: Building search context ---")
        search_context = f"{query or ''} {level or ''} {location or ''}"
        if resume_text:
            search_context += f" Skills: {', '.join(skills[:20])}. Experience: {resume_text[:1000]}"
        if github_context:
            search_context += github_context
            
        print(f"  - Search context length: {len(search_context)} chars")
        print(f"  ⏱  Step 3 took {time.time() - step_start:.2f}s")
        
        # 4. Save to Supabase "documents" tracking table
        step_start = time.time()
        print("\n--- Step 4: Recording request in Supabase documents table ---")
        vector_service = get_vector_service()
        try:
            doc_data = {
                "id": str(uuid.uuid4()),
                "content": search_context[:1000],
                "metadata": {
                    "query": query,
                    "location": location,
                    "github_username": github_username
                }
            }
            doc_response = vector_service.supabase.table("documents").insert(doc_data).execute()
            if hasattr(doc_response, 'data') and len(doc_response.data) > 0:
                print("  ✅ Match request saved to Supabase (201 Created)")
            else:
                print("  ⚠️ Document record created but returned no data.")
        except Exception as e:
            print(f"  ⚠️ 'documents' table save failed (non-fatal): {e}")
        
        print(f"  ⏱  Step 4 took {time.time() - step_start:.2f}s")

        # 5. Search via Supabase Vector Service
        step_start = time.time()
        print("\n--- Step 5: Executing semantic search in Supabase ---")
        matches = []
        
        search_results = await vector_service.search_jobs(
            query=search_context,
            top_k=10
        )
        print(f"  ✅ Supabase returned {len(search_results)} results")
        print(f"  ⏱  Step 5 took {time.time() - step_start:.2f}s")

        # 5b. Conditional scraping: fetch live jobs if DB cache is thin or refresh requested
        step_start = time.time()
        refresh_bool = str(refresh).strip() in ("1", "true", "True")
        high_quality = [r for r in search_results if r.get("score", 0) > 0.8]
        print(f"\n--- Step 5b: Cache check — {len(high_quality)} high-quality results (score>0.8) ---")
        if len(high_quality) < 3 or refresh_bool:
            scrape_query = query or (", ".join(skills[:5]) if skills else "software engineer")
            print(f"  ℹ️  Triggering live scrape for: '{scrape_query}' (refresh={refresh_bool})")
            new_count = await _scrape_and_store_jobs(scrape_query, vector_service)
            if new_count > 0:
                print(f"  ✅ Stored {new_count} new jobs — re-running vector search")
                search_results = await vector_service.search_jobs(
                    query=search_context,
                    top_k=10,
                )
                print(f"  ✅ Updated search returned {len(search_results)} results")
            else:
                print("  ℹ️  No new jobs scraped (MCP unavailable or all duplicates)")
        else:
            print(f"  ✅ Cache sufficient — skipping live scrape")
        print(f"  ⏱  Step 5b took {time.time() - step_start:.2f}s")

        # 6. Analyze results with LLM
        step_start = time.time()
        print(f"\n--- Step 6: Processing {len(search_results)} search results ---")
        
        for i, result in enumerate(search_results):
            job_description = result.get("description", "") or ""
            job_title = result.get("title", "")
            
            print(f"  - [{i+1}/{len(search_results)}] Analyzing: {job_title[:50]}")
            
            full_job_text = f"{job_title}\n\n{job_description}"
            job_skills = set(extract_skills_with_llm(full_job_text, max_skills=10))
            
            resume_skills_lower = set(s.lower() for s in skills if s)
            job_skills_lower = set(s.lower() for s in job_skills if s)
            
            missing_skills_lower = job_skills_lower - resume_skills_lower
            missing_skills = [s for s in job_skills if s.lower() in missing_skills_lower][:5]
            
            job_match = {
                "id": str(result.get("id")),
                "title": result.get("title", "Unknown Role"),
                "company": result.get("company", "Unknown Company"),
                "description": job_description,
                "url": result.get("url", ""),
                "source": result.get("source_platform", "LinkedIn"),
                "remote_type": result.get("remote_type"),
                "job_type": result.get("job_type"),
                "experience_level": result.get("experience_level"),
                "salary_max": result.get("salary_max"),
                "match_score": result.get("score", 0.7),
                "recruiter_concerns": [], 
                "coach_highlights": [],
                "missing_skills": missing_skills, 
            }
            matches.append(job_match)
        
        elapsed = time.time() - overall_start
        print(f"  ⏱  Step 6 took {time.time() - step_start:.2f}s")
        print(f"\n{'═' * 60}")
        print(f"✅ Match Process Complete: {len(matches)} jobs matched in {elapsed:.2f}s")
        print(f"{'═' * 60}\n")
        
        return {
            "success": True,
            "matches": matches, 
            "count": len(matches), 
            "parsed_skills": [s for s in skills if s],
            "processing_time_seconds": round(elapsed, 2),
            "debug_info": {"status": "all steps complete"}
        }
        
    except Exception as e:
        elapsed = time.time() - overall_start
        # ═══ FULL TRACEBACK TO TERMINAL ═══
        print(f"\n{'!' * 60}")
        print(f"❌ CRITICAL ERROR in match_jobs after {elapsed:.2f}s")
        print(f"{'!' * 60}")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"Full Traceback:")
        traceback.print_exc()
        print(f"{'!' * 60}\n")
        
        # Return a proper HTTP 500 with the error details
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "detail": "Failed during semantic search or analysis pipeline",
                "traceback": traceback.format_exc(),
            }
        )
