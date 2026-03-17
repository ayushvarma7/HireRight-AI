"""
Skill Gap Node

Identifies skill gaps and recommends learning resources.
"""

from typing import Any, Dict, List

from app.agents.state import AgentState
from app.models import SkillGap


async def skill_gap_node(state: AgentState) -> Dict[str, Any]:
    """
    Identify skill gaps and provide learning recommendations.
    
    This node:
    1. Compares candidate skills to job requirements
    2. Prioritizes gaps by importance
    3. Recommends learning resources
    """
    parsed_skills = set(state.get("parsed_skills", []))
    job = state["job_data"]
    
    # Get required and preferred skills
    required_skills = set(job.required_skills)
    preferred_skills = set(job.preferred_skills)
    
    skill_gaps: List[SkillGap] = []
    
    # Check required skills
    missing_required = required_skills - parsed_skills
    for skill in missing_required:
        skill_gaps.append(SkillGap(
            skill_name=skill,
            importance="Critical",
            description=f"{skill} is a required skill for this role",
            learning_resources=get_learning_resources(skill),
            estimated_time_to_learn=estimate_learning_time(skill),
        ))
    
    # Check preferred skills
    missing_preferred = preferred_skills - parsed_skills - missing_required
    for skill in list(missing_preferred)[:5]:  # Limit to top 5
        skill_gaps.append(SkillGap(
            skill_name=skill,
            importance="High",
            description=f"{skill} is preferred for this role",
            learning_resources=get_learning_resources(skill),
            estimated_time_to_learn=estimate_learning_time(skill),
        ))
    
    return {
        "skill_gaps": skill_gaps,
        "messages": state.get("messages", []) + [
            {"role": "skill_gap", "content": f"Identified {len(skill_gaps)} skill gaps"}
        ],
    }


def get_learning_resources(skill: str) -> List[str]:
    """Get learning resources for a skill."""
    # In production, would query a database or API
    resources = {
        "python": [
            "Python.org Official Tutorial",
            "Real Python",
            "Codecademy Python Course",
        ],
        "kubernetes": [
            "Kubernetes Official Docs",
            "KodeKloud Kubernetes Course",
            "CKAD Certification",
        ],
        "react": [
            "React Official Tutorial",
            "Frontend Masters React Course",
            "Scrimba React Course",
        ],
        "aws": [
            "AWS Free Tier Labs",
            "A Cloud Guru",
            "AWS Solutions Architect Certification",
        ],
        "docker": [
            "Docker Official Get Started",
            "Docker Deep Dive (Book)",
            "Play with Docker",
        ],
    }
    
    skill_lower = skill.lower()
    for key, value in resources.items():
        if key in skill_lower or skill_lower in key:
            return value
    
    return [
        f"Official {skill} documentation",
        f"Udemy {skill} courses",
        f"YouTube {skill} tutorials",
    ]


def estimate_learning_time(skill: str) -> str:
    """Estimate time to learn a skill."""
    # Simple heuristic based on skill complexity
    complex_skills = ["kubernetes", "machine learning", "system design", "distributed systems"]
    medium_skills = ["docker", "react", "aws", "graphql", "typescript"]
    
    skill_lower = skill.lower()
    
    if any(s in skill_lower for s in complex_skills):
        return "3-6 months"
    elif any(s in skill_lower for s in medium_skills):
        return "1-2 months"
    else:
        return "2-4 weeks"
