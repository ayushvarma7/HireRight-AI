"""
Headhunter Route

Proactive job recommendations - "While you were away..."
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.models import JobMatch

router = APIRouter()


class HeadhunterRecommendation(BaseModel):
    """A proactive job recommendation."""
    
    job_match: JobMatch
    reason: str  # Why this job is recommended
    urgency: str  # "New", "Expiring Soon", "High Match", "Perfect Fit"
    discovered_at: str


class HeadhunterResponse(BaseModel):
    """Response with proactive recommendations."""
    
    recommendations: List[HeadhunterRecommendation]
    total_new_jobs_since_last_visit: int
    last_visit: str


@router.get("/headhunter/{user_id}", response_model=HeadhunterResponse)
async def get_recommendations(user_id: str):
    """
    Get proactive job recommendations for a user.
    
    This powers the "While you were away..." dashboard feature.
    Recommendations are pre-computed by the daily Airflow DAG.
    """
    # TODO: Fetch pre-computed recommendations from database
    
    return HeadhunterResponse(
        recommendations=[],
        total_new_jobs_since_last_visit=42,
        last_visit="2024-01-15T10:30:00Z",
    )


@router.post("/headhunter/{user_id}/dismiss/{job_id}")
async def dismiss_recommendation(user_id: str, job_id: str):
    """
    Dismiss a recommendation (not interested).
    """
    # TODO: Update database
    return {"status": "dismissed", "job_id": job_id}


@router.post("/headhunter/{user_id}/save/{job_id}")
async def save_recommendation(user_id: str, job_id: str):
    """
    Save a recommendation for later.
    """
    # TODO: Update database
    return {"status": "saved", "job_id": job_id}


@router.get("/headhunter/{user_id}/saved")
async def get_saved_jobs(user_id: str):
    """
    Get all saved job recommendations.
    """
    # TODO: Fetch from database
    return {"saved_jobs": []}
