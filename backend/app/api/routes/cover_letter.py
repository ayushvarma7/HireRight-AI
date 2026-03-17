"""
Cover Letter Route

Generate personalized cover letters using debate insights.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.nodes.cover_writer import generate_cover_letter
from app.models import JobListing, ResumeData

router = APIRouter()


class CoverLetterRequest(BaseModel):
    """Request for cover letter generation."""
    
    # Can provide user_id or resume directly
    user_id: Optional[str] = None
    resume: Optional[ResumeData] = None
    
    # Job details
    job: JobListing
    
    # Optional debate context for better personalization
    recruiter_concerns: list[str] = []
    coach_highlights: list[str] = []
    
    # Style preferences
    tone: str = "professional"  # professional, enthusiastic, conversational
    length: str = "medium"  # short, medium, long
    focus_areas: list[str] = []  # e.g., ["leadership", "technical skills"]


class CoverLetterResponse(BaseModel):
    """Generated cover letter response."""
    
    cover_letter: str
    word_count: int
    key_points_addressed: list[str]
    suggestions: list[str]


@router.post("/cover-letter", response_model=CoverLetterResponse)
async def create_cover_letter(request: CoverLetterRequest):
    """
    Generate a personalized cover letter.
    
    Uses insights from the agent debate (if available) to:
    - Address potential concerns proactively
    - Highlight strongest matching points
    - Tailor messaging to the specific role
    """
    # Get resume
    if request.user_id:
        # TODO: Fetch from database
        raise HTTPException(status_code=404, detail="User not found")
    
    if not request.resume:
        raise HTTPException(status_code=400, detail="Resume data required")
    
    try:
        # Generate cover letter
        result = await generate_cover_letter(
            resume=request.resume,
            job=request.job,
            recruiter_concerns=request.recruiter_concerns,
            coach_highlights=request.coach_highlights,
            tone=request.tone,
            length=request.length,
            focus_areas=request.focus_areas,
        )
        
        return CoverLetterResponse(
            cover_letter=result["cover_letter"],
            word_count=len(result["cover_letter"].split()),
            key_points_addressed=result.get("key_points", []),
            suggestions=result.get("suggestions", []),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cover-letter/refine")
async def refine_cover_letter(
    cover_letter: str,
    feedback: str,
):
    """
    Refine an existing cover letter based on user feedback.
    """
    # TODO: Implement refinement using LLM
    return {
        "message": "Cover letter refinement endpoint",
        "original_length": len(cover_letter.split()),
        "feedback_received": feedback,
    }
