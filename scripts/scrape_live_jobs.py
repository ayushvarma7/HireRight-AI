#!/usr/bin/env python3
"""
Live Job Scraper — Tavily → Supabase Pipeline

Uses the Job Market MCP Server (Tavily) to search for real jobs,
then stores them in Supabase with Gemini embeddings for semantic matching.

Usage:
    cd backend && ../venv/bin/python ../scripts/scrape_live_jobs.py

Optional arguments:
    --queries "Python Developer,ML Engineer,Data Scientist"
    --limit 10       (results per query)
"""

import asyncio
import argparse
import os
import sys
import re
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
JOB_MARKET_MCP_URL = os.getenv("MCP_JOBMARKET_SERVER_URL", "http://localhost:8002")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Default search queries to populate a good mix of tech jobs
DEFAULT_QUERIES = [
    "Python Developer",
    "Software Engineer",
    "Full Stack Developer",
    "Data Scientist",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Frontend React Developer",
    "Backend Java Developer",
    "Cloud Architect AWS",
    "Data Engineer",
]


_AGGREGATED_TITLE_PATTERNS = re.compile(
    r'search results|best jobs|\d[\d,]*\+?\s+jobs?\s+in|^\d[\d,]*\+?\s+',
    re.IGNORECASE,
)


def _is_aggregated_title(title: str) -> bool:
    """Return True if the title looks like a listing page, not a single job."""
    if _AGGREGATED_TITLE_PATTERNS.search(title):
        return True
    # More than 15 words → almost certainly a search result page headline
    if len(title.split()) > 15:
        return True
    return False


def parse_job_listings_from_snippets(tavily_results: list[dict]) -> list[dict]:
    """
    Parse individual job listings from Tavily search results.

    Tavily returns web search results — each result might contain
    text from LinkedIn/Indeed with multiple job mentions.
    We extract structured job data from the raw snippets.
    """
    jobs = []
    seen_urls = set()

    for result in tavily_results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", result.get("content", ""))
        source = _extract_source(url)

        # Skip duplicate URLs
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip aggregated listing pages immediately (before any parsing)
        if _is_aggregated_title(title):
            continue

        # Try to extract company from the title
        # Common patterns: "Job Title - Company | LinkedIn"
        #                   "Job Title at Company"
        #                   "Job Title | Company - Indeed"
        #                   "25,000+ Job Title jobs in Location | LinkedIn"
        company = "Unknown"
        clean_title = title

        # Check for aggregate job counts (e.g., "25,000+ Associate Data Engineer jobs in United States")
        # Extract the core title: "Associate Data Engineer"
        count_match = re.search(r'[\d,]+\+\s+(.*?)\s+jobs\s+in', title, re.IGNORECASE)
        if count_match:
            clean_title = count_match.group(1).strip()
            # In these cases, company is usually late or in snippet, but often the snippet starts with company
            # We'll try to refine below

        # Pattern: "Title - Company | Source"
        if " - " in title:
            parts = title.split(" - ")
            if not count_match:
                clean_title = parts[0].strip()
            company_part = parts[1].split("|")[0].split("–")[0].strip()
            if company_part and len(company_part) < 100:
                company = company_part

        # Pattern: "Title at Company"
        elif " at " in title.lower():
            parts = re.split(r"\bat\b", title, maxsplit=1, flags=re.IGNORECASE)
            if not count_match:
                clean_title = parts[0].strip()
            company = parts[1].split("|")[0].split("–")[0].strip() if len(parts) > 1 else "Unknown"

        # Pattern: "Title | Company"
        elif " | " in title:
            parts = title.split(" | ")
            if not count_match:
                clean_title = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                company_candidate = parts[1].strip()
                if "LinkedIn" not in company_candidate and "Indeed" not in company_candidate:
                    company = company_candidate

        # If company still unknown, try to find it in the snippet (often starts with company name)
        if company == "Unknown" and snippet:
            # Common snippet start: "Company Name · Location" or "Company: Title"
            snippet_parts = re.split(r'[·|•|:]', snippet[:50])
            if snippet_parts and len(snippet_parts[0].strip()) > 2 and len(snippet_parts[0].strip()) < 50:
                company = snippet_parts[0].strip()

        # Clean up common suffixes
        for suffix in ["| LinkedIn", "| Indeed", "| Glassdoor", "- LinkedIn", "- Indeed", " - LinkedIn", " - Indeed"]:
            company = company.replace(suffix, "").strip()
            clean_title = clean_title.replace(suffix, "").strip()

        # Skip if title is too generic or clearly not a job
        if len(clean_title) < 5 or clean_title.lower() in ["jobs", "careers", "home"]:
            continue

        # Reject entries where company could not be identified
        if not company or company == "Unknown":
            continue

        description = snippet[:2000] if snippet else f"Position at {company}. Found via {source}."
        
        # Extended Metadata Extraction (Regex & Keywords)
        full_text = (clean_title + " " + description + " " + result.get("raw_content", "")).lower()
        
        # 1. Remote Type
        remote_type = "on-site"
        if "remote" in full_text:
            remote_type = "remote"
        elif "hybrid" in full_text:
            remote_type = "hybrid"
            
        # 2. Job Type
        job_type = "full-time"
        if "part-time" in full_text or "part time" in full_text:
            job_type = "part-time"
        elif "contract" in full_text or "contractor" in full_text:
            job_type = "contract"
            
        # 3. Experience Level
        experience_level = "mid"
        if "senior" in full_text or "sr." in full_text or "sr " in clean_title.lower() or "lead" in full_text or "principal" in full_text:
            experience_level = "senior"
        elif "junior" in full_text or "jr." in full_text or "entry level" in full_text:
            experience_level = "entry"
        elif "director" in full_text or "vp" in full_text or "manager" in full_text:
            experience_level = "executive"
            
        # 4. Salary Extraction
        salary_min = None
        salary_max = None
        # Look for patterns like $120k - $150k or $100,000 - $150,000
        salary_matches = re.findall(r'\$?(\d{2,3})(?:k|,000)(?:(?:\s*-\s*|(?:\s*to\s*))\$?(\d{2,3})(?:k|,000))?', full_text)
        if salary_matches:
            # Take the first match
            match = salary_matches[0]
            val1 = int(match[0]) * 1000 if int(match[0]) < 1000 else int(match[0])
            if val1 > 10000: # sanity check
                salary_min = val1
                if match[1]:
                    val2 = int(match[1]) * 1000 if int(match[1]) < 1000 else int(match[1])
                    if val2 > 10000:
                        salary_max = val2
            
        jobs.append({
            "title": clean_title,
            "company": company,
            "description": description,
            "source_url": url,
            "source_platform": source,
            "remote_type": remote_type,
            "job_type": job_type,
            "experience_level": experience_level,
            "salary_min": salary_min,
            "salary_max": salary_max
        })

    return jobs


def _extract_source(url: str) -> str:
    """Extract source name from URL."""
    if "linkedin" in url:
        return "LinkedIn"
    elif "indeed" in url:
        return "Indeed"
    elif "glassdoor" in url:
        return "Glassdoor"
    elif "lever.co" in url:
        return "Lever"
    elif "greenhouse" in url:
        return "Greenhouse"
    elif "builtin" in url:
        return "BuiltIn"
    elif "workday" in url:
        return "Workday"
    else:
        return "Web"


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini."""
    from app.services.embedding import get_embedding
    return await get_embedding(text[:8000])


async def scrape_and_store(queries: list[str], limit_per_query: int = 10):
    """
    Main pipeline: Tavily search → parse → embed → store in Supabase.
    """
    print("=" * 60)
    print("🌐 Live Job Scraper: Tavily → Supabase Pipeline")
    print("=" * 60)
    print(f"  MCP Server:  {JOB_MARKET_MCP_URL}")
    print(f"  Queries:     {len(queries)}")
    print(f"  Limit/query: {limit_per_query}")
    print("=" * 60)

    # 1. Check MCP server health
    print("\n📡 Step 1: Checking Job Market MCP server...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{JOB_MARKET_MCP_URL}/health")
            health_data = health.json()
            print(f"  ✅ Server healthy. Tavily configured: {health_data.get('tavily_configured')}")
            if not health_data.get("tavily_configured"):
                print("  ❌ Tavily API key not configured in MCP server!")
                print("     Make sure TAVILY_API_KEY is in your .env file")
                return
    except Exception as e:
        print(f"  ❌ Cannot reach MCP server at {JOB_MARKET_MCP_URL}: {e}")
        print("     Start it with: cd mcp_servers/job-market && ../../venv/bin/python server.py")
        return

    # 2. Search for jobs using Tavily via MCP
    print("\n🔍 Step 2: Searching for jobs via Tavily...")
    all_raw_jobs = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, query in enumerate(queries, 1):
            print(f"  [{i}/{len(queries)}] Searching: \"{query}\"...", end=" ", flush=True)
            try:
                response = await client.post(
                    f"{JOB_MARKET_MCP_URL}/tools/search_jobs",
                    json={"query": query, "limit": limit_per_query},
                )
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])
                    print(f"→ {len(jobs)} results")
                    all_raw_jobs.extend(jobs)
                else:
                    print(f"→ Error: {response.status_code}")
            except Exception as e:
                print(f"→ Failed: {e}")

            # Small delay to avoid Tavily rate limits
            await asyncio.sleep(1.0)

    print(f"\n  📊 Total raw results: {len(all_raw_jobs)}")

    # 3. Parse into structured job listings
    print("\n📋 Step 3: Parsing job listings from search results...")
    parsed_jobs = parse_job_listings_from_snippets(all_raw_jobs)
    print(f"  ✅ Parsed {len(parsed_jobs)} unique job listings")

    if not parsed_jobs:
        print("\n  ⚠️ No jobs parsed. Tavily results may not contain structured job data.")
        print("  Try running with different queries or check Tavily API credits.")
        return

    # 4. Deduplicate against existing database
    print("\n🔄 Step 4: Deduplicating against Supabase...")
    new_jobs = []
    for job in parsed_jobs:
        # Check by source_url or title+company
        existing = sb.table("jobs").select("id").eq("source_url", job["source_url"]).execute()
        if existing.data:
            continue
        existing2 = (
            sb.table("jobs")
            .select("id")
            .eq("title", job["title"])
            .eq("company", job["company"])
            .execute()
        )
        if existing2.data:
            continue
        new_jobs.append(job)

    print(f"  ✅ {len(new_jobs)} new jobs to insert ({len(parsed_jobs) - len(new_jobs)} duplicates skipped)")

    if not new_jobs:
        print("\n  All jobs already exist in database. Nothing to insert.")
        return

    # 5. Generate embeddings and insert
    print(f"\n🧠 Step 5: Generating Gemini embeddings and inserting into Supabase...")
    inserted = 0
    failed = 0

    for i, job in enumerate(new_jobs, 1):
        title = job["title"]
        company = job["company"]
        print(f"  [{i}/{len(new_jobs)}] {title} at {company}...", end=" ", flush=True)

        # Generate embedding
        embed_text = f"{title} at {company}. {job['description']}"
        try:
            embedding = await generate_embedding(embed_text)
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            failed += 1
            continue

        # Insert into Supabase
        row = {
            "id": str(uuid.uuid4()),
            "title": title,
            "company": company,
            "description": job["description"],
            "url": job["source_url"],
            "source_url": job["source_url"],
            "source_platform": job["source_platform"],
            "remote_type": job["remote_type"],
            "job_type": job["job_type"],
            "experience_level": job["experience_level"],
            "salary_min": job["salary_min"],
            "salary_max": job["salary_max"],
            "location": job["remote_type"].title(),
            "embedding": embedding,
            "is_active": True,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            sb.table("jobs").insert(row).execute()
            print("✅")
            inserted += 1
        except Exception as e:
            print(f"❌ Insert failed: {e}")
            failed += 1

        # Rate limit respect
        await asyncio.sleep(0.5)

    # 6. Summary
    final_count = sb.table("jobs").select("id", count="exact").execute()
    print(f"\n{'=' * 60}")
    print(f"🎉 Scraping Complete!")
    print(f"  • Queries run:     {len(queries)}")
    print(f"  • Raw results:     {len(all_raw_jobs)}")
    print(f"  • Jobs parsed:     {len(parsed_jobs)}")
    print(f"  • New jobs stored: {inserted}")
    print(f"  • Failed:          {failed}")
    print(f"  • Total in DB:     {final_count.count}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Scrape live jobs via Tavily and store in Supabase")
    parser.add_argument(
        "--queries",
        type=str,
        default=None,
        help="Comma-separated job search queries (default: built-in tech queries)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Max results per query (default: 3)",
    )
    args = parser.parse_args()

    if args.queries:
        queries = [q.strip() for q in args.queries.split(",")]
    else:
        queries = DEFAULT_QUERIES

    asyncio.run(scrape_and_store(queries, args.limit))


if __name__ == "__main__":
    main()
