"""
Jobs Route

Expose job listings from Supabase.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.db.database import fetch_jobs

router = APIRouter()

@router.get("/jobs")
async def get_jobs(limit: int = Query(10, ge=1, le=100)):
    """
    Fetch the latest jobs from Supabase.
    """
    try:
        jobs = await fetch_jobs(limit=limit)
        return jobs
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs from Supabase")

@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """
    Get detailed information for a specific job.
    """
    from app.db.database import get_supabase
    supabase = get_supabase()
    
    response = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return response.data[0]
