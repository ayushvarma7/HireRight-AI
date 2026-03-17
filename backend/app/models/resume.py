"""
Resume Data Models

Pydantic models for resume/CV data structures.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class Skill(BaseModel):
    """Individual skill with optional proficiency level."""
    
    name: str
    category: Optional[str] = None  # e.g., "Programming", "Framework", "Tool"
    proficiency: Optional[str] = None  # e.g., "Expert", "Intermediate", "Beginner"
    years_of_experience: Optional[float] = None


class Experience(BaseModel):
    """Work experience entry."""
    
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None  # None if current
    is_current: bool = False
    description: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class Education(BaseModel):
    """Education entry."""
    
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gpa: Optional[float] = None
    honors: List[str] = Field(default_factory=list)


class Project(BaseModel):
    """Project entry (personal or professional)."""
    
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    """Professional certification."""
    
    name: str
    issuer: str
    date_obtained: Optional[date] = None
    expiration_date: Optional[date] = None
    credential_id: Optional[str] = None
    url: Optional[str] = None


class ResumeData(BaseModel):
    """Complete resume/CV data structure."""
    
    # Basic Info
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    
    # Summary
    summary: Optional[str] = None
    
    # Core Sections
    skills: List[Skill] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    
    # Additional
    languages: List[str] = Field(default_factory=list)  # Spoken languages
    interests: List[str] = Field(default_factory=list)
    
    # Computed fields
    total_years_experience: Optional[float] = None
    primary_role: Optional[str] = None
    
    def get_all_technologies(self) -> List[str]:
        """Get all unique technologies mentioned."""
        techs = set()
        for exp in self.experience:
            techs.update(exp.technologies)
        for proj in self.projects:
            techs.update(proj.technologies)
        for skill in self.skills:
            if skill.category in ["Programming", "Framework", "Tool", "Technology"]:
                techs.add(skill.name)
        return sorted(list(techs))
