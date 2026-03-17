"""
Agent State Definition

TypedDict defining the state that flows through the LangGraph pipeline.
"""

from typing import Any, Dict, List, Optional, TypedDict

from app.models import (
    Argument,
    DebateRound,
    GitHubProfile,
    JobListing,
    ResumeData,
    SkillGap,
    Verdict,
)


class AgentState(TypedDict, total=False):
    """
    State that flows through the LangGraph agent pipeline.
    
    Each node in the graph can read from and write to this state.
    """
    
    # =========================================================================
    # Input Data
    # =========================================================================
    resume_data: ResumeData
    job_data: JobListing
    github_profile: Optional[GitHubProfile]
    
    # =========================================================================
    # Parsed Profile (from profile_parser node)
    # =========================================================================
    parsed_skills: List[str]
    parsed_experience_summary: str
    parsed_strengths: List[str]
    total_years_experience: float
    
    # =========================================================================
    # Debate State
    # =========================================================================
    # Current debate round
    current_round: int
    
    # Recruiter outputs (concerns/weaknesses)
    recruiter_arguments: List[Argument]
    recruiter_score: float  # 0-100, lower = more concerns
    
    # Coach outputs (strengths/positives)  
    coach_arguments: List[Argument]
    coach_score: float  # 0-100, higher = more strengths
    
    # All debate rounds
    debate_rounds: List[DebateRound]
    
    # =========================================================================
    # Judge Decision
    # =========================================================================
    score_difference: float  # Absolute difference between recruiter and coach
    should_redebate: bool
    final_verdict: Optional[Verdict]
    
    # =========================================================================
    # Output Generation
    # =========================================================================
    skill_gaps: List[SkillGap]
    cover_letter: Optional[str]
    improvement_suggestions: List[str]
    
    # =========================================================================
    # Metadata
    # =========================================================================
    error: Optional[str]
    processing_started_at: str
    tokens_used: int
    messages: List[Dict[str, Any]]  # For debugging/logging
