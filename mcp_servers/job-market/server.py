"""
Job Market MCP Server

This server provides tools for job market intelligence,
including job search, company research, and salary insights via HTTP API.
"""

import json
import os
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Job Market MCP Server",
    description="Provides job search and company intelligence",
    version="1.0.0",
)

from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# API Configuration
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
PORT = int(os.getenv("PORT", 8002))


# =============================================================================
# Request/Response Models
# =============================================================================

class JobSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    experience_level: Optional[str] = None
    limit: int = 10


class CompanyRequest(BaseModel):
    company_name: str


class SalaryRequest(BaseModel):
    role: str
    location: str
    experience_years: Optional[int] = None


class SkillTrendsRequest(BaseModel):
    skills: list[str]


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "job-market", "tavily_configured": bool(TAVILY_API_KEY)}


@app.post("/tools/search_jobs")
async def search_jobs(request: JobSearchRequest):
    """Search for job listings using Tavily API."""
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        # Build search query
        search_query = f"{request.query} job listings"
        if request.location:
            search_query += f" {request.location}"
        if request.experience_level:
            search_query += f" {request.experience_level} level"
        
        # Search using Tavily
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": search_query,
                    "search_depth": "advanced",
                    "include_domains": [
                        "linkedin.com/jobs",
                        "indeed.com",
                        "glassdoor.com",
                        "lever.co",
                        "greenhouse.io",
                        "workday.com",
                        "builtin.com",
                    ],
                    "max_results": request.limit,
                    "include_raw_content": True,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        
        # Parse results
        jobs = []
        for result in data.get("results", []):
            jobs.append({
                "title": result.get("title", "Unknown Title"),
                "url": result.get("url", ""),
                "snippet": result.get("content", ""),
                "raw_content": result.get("raw_content", ""),
                "source": _extract_source(result.get("url", "")),
            })
        
        return {
            "query": request.query,
            "location": request.location,
            "result_count": len(jobs),
            "jobs": jobs,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_company_intel")
async def get_company_intel(request: CompanyRequest):
    """Get intelligence about a company including culture, reviews, and recent news."""
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            # Search for company info
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": f"{request.company_name} company culture reviews engineering team",
                    "search_depth": "advanced",
                    "include_domains": [
                        "glassdoor.com",
                        "linkedin.com",
                        "levels.fyi",
                        "teamblind.com",
                        "comparably.com",
                    ],
                    "max_results": 10,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            culture_data = response.json()
            
            # Search for recent news
            news_response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": f"{request.company_name} news recent announcements",
                    "search_depth": "basic",
                    "max_results": 5,
                },
                timeout=30.0,
            )
            news_response.raise_for_status()
            news_data = news_response.json()
        
        # Compile results
        culture_insights = [
            {
                "title": r.get("title", ""),
                "snippet": r.get("content", "")[:300],
                "source": _extract_source(r.get("url", "")),
                "url": r.get("url", ""),
            }
            for r in culture_data.get("results", [])[:5]
        ]
        
        recent_news = [
            {
                "title": r.get("title", ""),
                "snippet": r.get("content", "")[:200],
                "url": r.get("url", ""),
            }
            for r in news_data.get("results", [])[:3]
        ]
        
        return {
            "company": request.company_name,
            "culture_insights": culture_insights,
            "recent_news": recent_news,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_salary_benchmark")
async def get_salary_benchmark(request: SalaryRequest):
    """Get salary benchmarks for a role in a specific location."""
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": f"{request.role} salary {request.location} compensation 2024",
                    "search_depth": "advanced",
                    "include_domains": [
                        "levels.fyi",
                        "glassdoor.com",
                        "salary.com",
                        "indeed.com/salary",
                        "payscale.com",
                        "builtin.com/salaries",
                    ],
                    "max_results": 10,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        
        # Extract salary info from results
        salary_sources = []
        for result in data.get("results", [])[:5]:
            salary_sources.append({
                "title": result.get("title", ""),
                "snippet": result.get("content", "")[:300],
                "source": _extract_source(result.get("url", "")),
                "url": result.get("url", ""),
            })
        
        return {
            "role": request.role,
            "location": request.location,
            "experience_years": request.experience_years,
            "salary_data": salary_sources,
            "note": "Salary data gathered from multiple sources. Actual compensation varies.",
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_skill_trends")
async def get_skill_trends(request: SkillTrendsRequest):
    """Get demand trends for specific skills."""
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="TAVILY_API_KEY not configured")
    
    try:
        trends = {}
        
        async with httpx.AsyncClient() as client:
            for skill in request.skills[:5]:  # Limit to 5 skills
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": f"{skill} developer jobs demand 2024 hiring trends",
                        "search_depth": "basic",
                        "max_results": 3,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                
                trends[skill] = {
                    "sources": [
                        {
                            "title": r.get("title", ""),
                            "snippet": r.get("content", "")[:200],
                        }
                        for r in data.get("results", [])[:2]
                    ],
                }
        
        return {
            "skills_analyzed": request.skills,
            "trends": trends,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _extract_source(url: str) -> str:
    """Extract source name from URL."""
    if "linkedin" in url:
        return "LinkedIn"
    elif "indeed" in url:
        return "Indeed"
    elif "glassdoor" in url:
        return "Glassdoor"
    elif "levels.fyi" in url:
        return "Levels.fyi"
    elif "lever.co" in url:
        return "Lever"
    elif "greenhouse" in url:
        return "Greenhouse"
    elif "builtin" in url:
        return "BuiltIn"
    else:
        return "Other"


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print(f"🚀 Starting Job Market MCP Server on port {PORT}...")
    print(f"   Tavily API configured: {bool(TAVILY_API_KEY)}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
