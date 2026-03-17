"""
Profile Parser Node

Parse resume and GitHub data into structured format for agents.
"""

from typing import Any, Dict

from app.agents.state import AgentState


async def profile_parser_node(state: AgentState) -> Dict[str, Any]:
    """
    Parse the resume and GitHub profile into structured data.
    
    This node:
    1. Extracts skills from resume
    2. Summarizes experience
    3. Identifies initial strengths
    4. Calculates total years of experience
    """
    resume = state["resume_data"]
    github = state.get("github_profile")
    
    # Extract all skills
    parsed_skills = []
    for skill in resume.skills:
        parsed_skills.append(skill.name)
    
    # Add technologies from experience
    parsed_skills.extend(resume.get_all_technologies())
    
    # Add GitHub languages if available
    if github:
        parsed_skills.extend(github.languages or [])
        parsed_skills.extend(github.frameworks or [])
    
    # Deduplicate
    parsed_skills = list(set(parsed_skills))
    
    # Build experience summary
    experience_parts = []
    for exp in resume.experience[:3]:  # Top 3 most recent
        experience_parts.append(
            f"{exp.title} at {exp.company}"
        )
    
    experience_summary = "; ".join(experience_parts) if experience_parts else "No work experience listed"
    
    # Identify strengths
    strengths = []
    if len(resume.experience) >= 3:
        strengths.append(f"{len(resume.experience)} roles showing career progression")
    if len(parsed_skills) >= 10:
        strengths.append(f"Diverse skill set with {len(parsed_skills)} technologies")
    if resume.education:
        strengths.append(f"Education: {resume.education[0].degree}")
    if github and github.activity_level == "High":
        strengths.append("Active GitHub contributor")
    if resume.certifications:
        strengths.append(f"{len(resume.certifications)} professional certifications")
    
    # Calculate years of experience
    total_years = resume.total_years_experience or 0
    if not total_years and resume.experience:
        # Estimate from experience entries
        total_years = len(resume.experience) * 2  # Rough estimate
    
    return {
        "parsed_skills": parsed_skills,
        "parsed_experience_summary": experience_summary,
        "parsed_strengths": strengths,
        "total_years_experience": total_years,
        "messages": state.get("messages", []) + [
            {"role": "profile_parser", "content": f"Parsed {len(parsed_skills)} skills, {len(resume.experience)} experiences"}
        ],
    }
