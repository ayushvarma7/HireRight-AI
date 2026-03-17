"""
User Data Models

Pydantic models for user profiles and preferences.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.resume import ResumeData


class GitHubProfile(BaseModel):
    """GitHub profile data from MCP server."""
    
    username: str
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    
    # Extracted data
    primary_language: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    
    # Activity
    activity_level: str = "Unknown"  # High, Medium, Low
    recent_commits: int = 0
    
    # Quality indicators
    avg_repo_quality_score: float = 0


class JobPreferences(BaseModel):
    """User's job search preferences."""
    
    # Role preferences
    target_roles: List[str] = Field(default_factory=list)
    excluded_roles: List[str] = Field(default_factory=list)
    
    # Location
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: str = "Flexible"  # Remote, On-site, Hybrid, Flexible
    willing_to_relocate: bool = False
    
    # Compensation
    min_salary: Optional[int] = None
    preferred_currency: str = "USD"
    
    # Company preferences
    preferred_company_sizes: List[str] = Field(default_factory=list)  # Startup, Mid-size, Enterprise
    preferred_industries: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)
    
    # Experience level
    experience_level: str = "Mid"  # Entry, Mid, Senior, Lead, Executive
    
    # Other
    visa_sponsorship_required: bool = False


class UserProfile(BaseModel):
    """Complete user profile."""
    
    id: UUID = Field(default_factory=uuid4)
    
    # Contact
    email: str
    name: Optional[str] = None
    
    # Profile data
    resume: Optional[ResumeData] = None
    github: Optional[GitHubProfile] = None
    preferences: JobPreferences = Field(default_factory=JobPreferences)
    
    # Status
    is_active: bool = True
    email_notifications: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_match_at: Optional[datetime] = None


class MatchHistory(BaseModel):
    """User's match history entry."""
    
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    job_id: str
    
    # Match result
    score: float
    recommendation: str
    
    # User feedback
    user_rating: Optional[int] = None  # 1-5 stars
    user_feedback: Optional[str] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    
    # Timestamps
    matched_at: datetime = Field(default_factory=datetime.utcnow)
