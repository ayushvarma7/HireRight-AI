"""
HireRight AI — Job DB Seeder
Populates Supabase with real jobs from Tavily across diverse tech roles.

Usage (from project root):
    venv/bin/python scripts/seed_jobs.py
    venv/bin/python scripts/seed_jobs.py --clear   # wipe jobs table first
"""

import asyncio
import os
import re
import sys
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
JOB_MARKET_MCP_URL = os.getenv("MCP_JOBMARKET_SERVER_URL", "http://localhost:8002")

# ── Seed queries — broad coverage across tech roles ──────────────────────────
SEED_QUERIES = [
    # ── ATS platforms — individual job postings ──────────────────────────────
    'site:lever.co "software engineer" python',
    'site:lever.co "data engineer" OR "backend engineer"',
    'site:lever.co "senior software engineer" python OR golang',
    'site:lever.co "devops" OR "platform engineer" kubernetes',
    'site:lever.co "AI engineer" OR "LLM" OR "RAG"',
    'site:lever.co "mobile engineer" iOS OR android',
    'site:greenhouse.io "machine learning engineer"',
    'site:greenhouse.io "full stack" OR "frontend engineer"',
    'site:greenhouse.io "product engineer" python react',
    'site:greenhouse.io "cloud engineer" AWS GCP',
    'site:greenhouse.io "data scientist" python pytorch',
    'site:greenhouse.io "security engineer" OR "infrastructure engineer"',
    'site:jobs.ashbyhq.com "software engineer"',
    'site:jobs.ashbyhq.com "data scientist" OR "ML engineer"',
    'site:jobs.ashbyhq.com "backend engineer" python',
    'site:boards.greenhouse.io "software engineer" senior',
    'site:boards.greenhouse.io "data engineer" spark OR dbt',
    # ── Top tech company career pages ────────────────────────────────────────
    '"careers.google.com" software engineer python',
    '"jobs.stripe.com" OR "stripe.com/jobs" engineer',
    '"openai.com/careers" engineer',
    '"anthropic.com/careers" engineer',
    '"vercel.com/careers" engineer',
    '"jobs.netflix.com" software engineer',
    '"careers.microsoft.com" software engineer python OR AI',
    '"amazon.jobs" software development engineer python',
    '"meta.com/careers" software engineer',
    '"databricks.com/company/careers" engineer',
    '"careers.snowflake.com" software engineer',
    '"careers.airbnb.com" OR "airbnb.io/careers" engineer',
    '"doordash.com/careers" software engineer',
    '"figma.com/careers" engineer',
    '"notion.so/careers" software engineer',
    '"airtable.com/careers" engineer python',
    '"linear.app/careers" software engineer',
    '"planetscale.com/careers" engineer',
    '"huggingface.co/jobs" ML engineer OR research engineer',
    '"cohere.com/careers" engineer OR researcher',
    '"mistral.ai/careers" engineer',
    # ── Fintech & data-focused roles ─────────────────────────────────────────
    '"jobs.robinhood.com" software engineer',
    '"coinbase.com/careers" software engineer',
    '"plaid.com/careers" engineer',
    '"rippling.com/careers" software engineer',
    '"brex.com/careers" engineer python',
    '"confluent.io/careers" software engineer',
    '"dbt labs" careers software engineer',
    # ── High-signal site: searches ────────────────────────────────────────────
    'site:lever.co "staff engineer" OR "principal engineer"',
    'site:greenhouse.io "engineering manager" python',
    'site:jobs.ashbyhq.com "site reliability" OR "SRE"',
]

KNOWN_AGGREGATORS = {
    "linkedin", "indeed", "glassdoor", "ziprecruiter", "monster",
    "careerbuilder", "dice", "simplyhired", "lever", "greenhouse",
    "workday", "jobvite", "smartrecruiters", "built in", "builtin",
    "wellfound", "angellist", "otta", "remoteok", "weworkremotely",
}

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
_TECH_KEYWORDS = {"python", "java", "react", "node", "typescript", "javascript",
                  "golang", "rust", "scala", "pytorch", "tensorflow", "aws", "gcp"}

def _is_invalid_company(name: str) -> bool:
    if not name or name.lower() in KNOWN_AGGREGATORS:
        return True
    if _LOCATION_RE.match(name.strip()):
        return True
    if "|" in name and any(kw in name.lower() for kw in _TECH_KEYWORDS):
        return True
    return False


def _extract_source(url: str) -> str:
    if "linkedin" in url:   return "LinkedIn"
    if "indeed" in url:     return "Indeed"
    if "glassdoor" in url:  return "Glassdoor"
    if "greenhouse" in url: return "Greenhouse"
    if "lever" in url:      return "Lever"
    return "Web"


def _parse_raw_jobs(tavily_results: list) -> list:
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
        url   = result.get("url", "").strip()
        title = result.get("title", "").strip()
        snippet = result.get("snippet", result.get("content", "")).strip()

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        if agg_pattern.search(title) or len(title.split()) > 14:
            continue

        company    = "Unknown"
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

        for agg in KNOWN_AGGREGATORS:
            company     = re.sub(rf"\s*[-|]\s*{agg}\b", "", company,     flags=re.IGNORECASE).strip()
            clean_title = re.sub(rf"\s*[-|]\s*{agg}\b", "", clean_title, flags=re.IGNORECASE).strip()

        if _is_invalid_company(company) or company == "Unknown" or len(clean_title) < 5:
            continue

        full_text  = (clean_title + " " + snippet).lower()
        remote_type = "remote" if "remote" in full_text else "hybrid" if "hybrid" in full_text else "on-site"

        tl = clean_title.lower()
        if any(k in tl for k in ("senior", "sr.", "sr ", "lead", "principal", "staff")):
            exp_level = "senior"
        elif any(k in tl for k in ("junior", "jr.", "jr ", "entry", "associate", "intern")):
            exp_level = "entry"
        elif any(k in tl for k in ("director", "vp ", "v.p.", "head of", "chief")):
            exp_level = "lead"
        else:
            exp_level = "mid"

        salary_min = salary_max = None
        m = salary_pattern.search(snippet)
        if m:
            try:
                s_min = int(m.group(1).replace(",", ""))
                s_max = int(m.group(2).replace(",", ""))
                if "k" in m.group(0).lower():
                    s_min = s_min * 1000 if s_min < 1000 else s_min
                    s_max = s_max * 1000 if s_max < 1000 else s_max
                if s_min > 10_000 and s_max > 10_000:
                    salary_min, salary_max = s_min, s_max
            except Exception:
                pass

        jobs.append({
            "title":           clean_title,
            "company":         company,
            "description":     (snippet or f"Position at {company}.")[:2000],
            "source_url":      url,
            "source_platform": _extract_source(url),
            "remote_type":     remote_type,
            "job_type":        "full-time",
            "experience_level": exp_level,
            "salary_min":      salary_min,
            "salary_max":      salary_max,
            "location":        "Remote" if remote_type == "remote" else "On-site",
        })
    return jobs


async def get_embedding(text: str) -> list:
    """Get 768-dim embedding via MRL (output_dimensionality)."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GOOGLE_API_KEY,
        output_dimensionality=768,
    )
    return await client.aembed_query(text[:8000])


async def seed(clear: bool = False):
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    if clear:
        print("🗑  Clearing existing jobs...")
        supabase.table("jobs").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("   Done.\n")

    total_stored = 0
    seen_urls: set = set()

    # Pre-load existing source_urls to avoid re-inserting
    existing = supabase.table("jobs").select("source_url").execute()
    for row in existing.data or []:
        seen_urls.add(row.get("source_url", ""))
    print(f"📦 {len(seen_urls)} jobs already in DB.\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, query in enumerate(SEED_QUERIES, 1):
            print(f"[{i:02d}/{len(SEED_QUERIES)}] Searching: '{query}'")
            try:
                resp = await client.post(
                    f"{JOB_MARKET_MCP_URL}/tools/search_jobs",
                    json={"query": query, "limit": 8},
                )
                if resp.status_code != 200:
                    print(f"   ⚠️  MCP returned {resp.status_code} — skipping")
                    continue
                raw_jobs = resp.json().get("jobs", [])
            except Exception as e:
                print(f"   ⚠️  MCP error: {e} — skipping")
                continue

            parsed = _parse_raw_jobs(raw_jobs)
            print(f"   {len(raw_jobs)} raw → {len(parsed)} parsed")

            stored_this_query = 0
            for job in parsed:
                if job["source_url"] in seen_urls:
                    continue
                seen_urls.add(job["source_url"])

                embed_text = f"{job['title']} at {job['company']}. {job['description']}"
                try:
                    embedding = await get_embedding(embed_text)
                except Exception as e:
                    print(f"   ⚠️  Embedding failed for '{job['title']}': {e}")
                    continue

                row = {
                    "id":               str(uuid.uuid4()),
                    "title":            job["title"],
                    "company":          job["company"],
                    "description":      job["description"],
                    "source_url":       job["source_url"],
                    "url":              job["source_url"],
                    "source_platform":  job["source_platform"],
                    "remote_type":      job["remote_type"],
                    "job_type":         job["job_type"],
                    "experience_level": job["experience_level"],
                    "salary_min":       job["salary_min"],
                    "salary_max":       job["salary_max"],
                    "location":         job["location"],
                    "embedding":        embedding,
                    "is_active":        True,
                    "scraped_at":       datetime.now(timezone.utc).isoformat(),
                }
                try:
                    supabase.table("jobs").insert(row).execute()
                    stored_this_query += 1
                    total_stored += 1
                    print(f"   + {job['title']} @ {job['company']}")
                except Exception as e:
                    print(f"   ⚠️  Insert failed: {e}")

            print(f"   → Stored {stored_this_query} new jobs\n")

            # Rate-limit: avoid hammering Tavily/Gemini
            await asyncio.sleep(1)

    print("=" * 60)
    print(f"✅ Seeding complete — {total_stored} new jobs added to Supabase.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Wipe the jobs table before seeding")
    args = parser.parse_args()

    if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
        print("❌ Missing env vars: SUPABASE_URL, SUPABASE_KEY, or GOOGLE_API_KEY")
        sys.exit(1)

    asyncio.run(seed(clear=args.clear))
