"""
Agent Debate Route

Exposes the LangGraph agent pipeline for multi-agent job-resume debate.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.graph import run_agent_pipeline
from app.models import (
    AgentPipelineResult,
    JobListing,
    ResumeData,
    SalaryRange,
)


router = APIRouter()


class DebateRequest(BaseModel):
    """Request body for running an agent debate."""
    resume_summary: str
    resume_skills: list[str] = []
    job_title: str
    job_company: str
    job_description: str
    job_required_skills: list[str] = []
    job_preferred_skills: list[str] = []
    github_username: Optional[str] = None
    include_cover_letter: bool = True


class SimpleDebateResult(BaseModel):
    """Simplified result for frontend consumption."""
    total_rounds: int
    debate_rounds: list[dict]
    recruiter_score: float
    coach_score: float
    final_score: float
    recommendation: str
    key_strengths: list[str]
    key_concerns: list[str]
    skill_gaps: list[str]
    cover_letter: Optional[str]
    processing_time_seconds: float


@router.post("/run-debate", response_model=SimpleDebateResult)
async def run_agent_debate(request: DebateRequest):
    """
    Run the full LangGraph agent debate pipeline.
    
    This triggers REAL AI agents (Recruiter, Coach, Judge) to analyze
    the resume against the job using LLM calls.
    """
    try:
        # Build ResumeData from request
        from app.models import Skill
        
        resume = ResumeData(
            name="Candidate",
            summary=request.resume_summary,
            skills=[Skill(name=s, category="Technology") for s in request.resume_skills],
            experience=[],
            education=[],
            projects=[],
            certifications=[],
        )
        
        # Build JobListing from request
        job = JobListing(
            id="temp-job",
            title=request.job_title,
            company=request.job_company,
            description=request.job_description,
            required_skills=request.job_required_skills,
            preferred_skills=request.job_preferred_skills,
            salary=None,
            location="Remote",
            job_type="Full-time",
            remote_policy="Remote",
            posted_date=None,
            source_url="",
        )
        
        # Run the LangGraph pipeline
        result = await run_agent_pipeline(
            resume=resume,
            job=job,
            github_username=request.github_username,
            include_cover_letter=request.include_cover_letter,
            include_skill_gaps=True,
        )
        
        # Extract final scores from last debate round
        recruiter_score = 50.0
        coach_score = 50.0
        
        if result.debate_rounds:
            last_round = result.debate_rounds[-1]
            recruiter_score = last_round.recruiter_score
            coach_score = last_round.coach_score
        
        # Serialize debate rounds
        debate_rounds_data = []
        for rd in result.debate_rounds:
            debate_rounds_data.append({
                "round_number": rd.round_number,
                "recruiter_score": rd.recruiter_score,
                "coach_score": rd.coach_score,
                "score_difference": rd.score_difference,
                "recruiter_arguments": [
                    {"point": a.point, "evidence": a.evidence, "strength": a.strength}
                    for a in rd.recruiter_arguments
                ],
                "coach_arguments": [
                    {"point": a.point, "evidence": a.evidence, "strength": a.strength}
                    for a in rd.coach_arguments
                ],
            })
        
        # Extract skill gaps (handle both SkillGap objects and dicts)
        skill_gap_names = []
        for sg in (result.skill_gaps or []):
            if isinstance(sg, dict):
                skill_gap_names.append(sg.get("skill_name", str(sg)))
            elif hasattr(sg, "skill_name"):
                skill_gap_names.append(sg.skill_name)
            else:
                skill_gap_names.append(str(sg))
        
        return SimpleDebateResult(
            total_rounds=result.total_rounds,
            debate_rounds=debate_rounds_data,
            recruiter_score=recruiter_score,
            coach_score=coach_score,
            final_score=result.verdict.final_score if result.verdict else 50.0,
            recommendation=result.verdict.recommendation if result.verdict else "Unknown",
            key_strengths=result.verdict.reasoning.key_strengths if result.verdict else [],
            key_concerns=result.verdict.reasoning.key_concerns if result.verdict else [],
            skill_gaps=skill_gap_names,
            cover_letter=result.cover_letter,
            processing_time_seconds=result.processing_time_seconds,
        )
        
    except Exception as e:
        print(f"Agent debate error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent debate failed: {str(e)}")


@router.get("/health")
async def debate_health():
    """Health check for debate service."""
    return {"status": "healthy", "service": "agent-debate"}
