"""
Cover Letter Route

Generate personalized cover letters using debate insights.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
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


class QuickCoverLetterRequest(BaseModel):
    """Lightweight request accepting raw text — for frontend use."""
    job_title: str
    job_company: str
    job_description: str = ""
    candidate_profile: str = ""
    tone: str = "professional"
    focus_areas: list[str] = []


@router.post("/cover-letter/quick")
async def quick_cover_letter(request: QuickCoverLetterRequest):
    """
    Generate a cover letter from raw text fields using Gemini.

    Designed for direct frontend consumption without requiring
    a structured ResumeData object.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    focus_str = f"\nFocus areas: {', '.join(request.focus_areas)}" if request.focus_areas else ""
    prompt = (
        f"Write a {request.tone} cover letter for the following job:\n\n"
        f"Job Title: {request.job_title}\n"
        f"Company: {request.job_company}\n"
        f"Job Description: {request.job_description[:600] or 'Not provided'}\n\n"
        f"Candidate Profile: {request.candidate_profile[:800] or 'Experienced professional'}"
        f"{focus_str}\n\n"
        "Write a compelling cover letter (3-4 paragraphs) that:\n"
        "1. Opens with an engaging hook\n"
        "2. Connects the candidate's skills to the job requirements\n"
        "3. Shows enthusiasm for the company\n"
        "4. Ends with a strong call to action\n"
    )

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=google_api_key,
            temperature=0.8,
        )
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        cover_letter = response.content
        return {"cover_letter": cover_letter, "word_count": len(cover_letter.split())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {e}")


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
