"""Models package."""

from app.models.agent import (
    AgentMessage,
    AgentPipelineResult,
    AgentRole,
    Argument,
    DebateRound,
    Verdict,
    VerdictReasoning,
)
from app.models.analytics import (
    MatchDistribution,
    SkillTrend,
    SystemMetrics,
    UserAnalytics,
)
from app.models.job import JobListing, JobMatch, MatchScore, SalaryRange, SkillGap
from app.models.resume import (
    Certification,
    Education,
    Experience,
    Project,
    ResumeData,
    Skill,
)
from app.models.user import GitHubProfile, JobPreferences, MatchHistory, UserProfile

__all__ = [
    # Resume
    "Skill",
    "Experience",
    "Education",
    "Project",
    "Certification",
    "ResumeData",
    # Job
    "SalaryRange",
    "JobListing",
    "MatchScore",
    "SkillGap",
    "JobMatch",
    # Agent
    "AgentRole",
    "AgentMessage",
    "Argument",
    "DebateRound",
    "VerdictReasoning",
    "Verdict",
    "AgentPipelineResult",
    # User
    "GitHubProfile",
    "JobPreferences",
    "UserProfile",
    "MatchHistory",
    # Analytics
    "SkillTrend",
    "MatchDistribution",
    "UserAnalytics",
    "SystemMetrics",
]
