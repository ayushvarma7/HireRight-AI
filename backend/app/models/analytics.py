"""
Analytics Data Models

Pydantic models for analytics and reporting.
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SkillTrend(BaseModel):
    """Skill demand trend data."""
    
    skill_name: str
    current_demand: str  # Very High, High, Medium, Low
    growth_rate: str  # e.g., "+15%"
    outlook: str  # Growing, Stable, Declining
    
    # Historical data points
    demand_history: List[Dict[str, float]] = Field(default_factory=list)
    
    # Related skills
    related_skills: List[str] = Field(default_factory=list)
    commonly_paired_with: List[str] = Field(default_factory=list)


class MatchDistribution(BaseModel):
    """Distribution of match scores for a user."""
    
    user_id: str
    period_start: date
    period_end: date
    
    # Score distribution
    total_matches: int = 0
    excellent_matches: int = 0  # 80-100
    good_matches: int = 0  # 60-79
    fair_matches: int = 0  # 40-59
    poor_matches: int = 0  # 0-39
    
    # Average scores
    avg_overall_score: float = 0
    avg_skills_match: float = 0
    avg_experience_match: float = 0
    
    # Top matches
    top_job_titles: List[str] = Field(default_factory=list)
    top_companies: List[str] = Field(default_factory=list)


class UserAnalytics(BaseModel):
    """Comprehensive analytics for a user."""
    
    user_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Match stats
    total_jobs_analyzed: int = 0
    jobs_analyzed_this_week: int = 0
    avg_match_score: float = 0
    best_match_score: float = 0
    
    # Skills analysis
    strongest_skills: List[str] = Field(default_factory=list)
    most_common_gaps: List[str] = Field(default_factory=list)
    skill_trends: List[SkillTrend] = Field(default_factory=list)
    
    # Match distribution
    match_distribution: Optional[MatchDistribution] = None
    
    # Agent insights
    common_recruiter_concerns: List[str] = Field(default_factory=list)
    common_coach_highlights: List[str] = Field(default_factory=list)
    
    # Recommendations
    focus_areas: List[str] = Field(default_factory=list)
    learning_recommendations: List[str] = Field(default_factory=list)
    
    # Application tracking
    jobs_applied: int = 0
    interview_rate: Optional[float] = None
    offer_rate: Optional[float] = None


class SystemMetrics(BaseModel):
    """System-wide analytics."""
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # User metrics
    total_users: int = 0
    active_users_today: int = 0
    active_users_week: int = 0
    
    # Job metrics
    total_jobs_indexed: int = 0
    jobs_added_today: int = 0
    jobs_by_source: Dict[str, int] = Field(default_factory=dict)
    
    # Matching metrics
    total_matches_generated: int = 0
    matches_today: int = 0
    avg_match_score: float = 0
    
    # Performance metrics
    avg_pipeline_time_seconds: float = 0
    avg_tokens_per_match: int = 0
    
    # Top content
    most_in_demand_skills: List[str] = Field(default_factory=list)
    most_common_job_titles: List[str] = Field(default_factory=list)
    top_hiring_companies: List[str] = Field(default_factory=list)
