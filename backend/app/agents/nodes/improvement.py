"""
Improvement Suggestions Node

Provides actionable profile improvement suggestions.
"""

from typing import Any, Dict, List

from app.agents.state import AgentState


async def improvement_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate profile improvement suggestions.
    
    Based on:
    - Skill gaps identified
    - Recruiter concerns from the debate
    - General best practices
    """
    skill_gaps = state.get("skill_gaps", [])
    verdict = state.get("final_verdict")
    github = state.get("github_profile")
    resume = state["resume_data"]
    
    suggestions: List[str] = []
    
    # Suggestions from skill gaps
    critical_gaps = [gap for gap in skill_gaps if gap.importance == "Critical"]
    if critical_gaps:
        top_gap = critical_gaps[0]
        suggestions.append(
            f"Priority: Learn {top_gap.skill_name} - {top_gap.estimated_time_to_learn} estimated"
        )
    
    # Suggestions from verdict
    if verdict:
        for item in verdict.must_address[:2]:
            suggestions.append(f"Address in applications: {item}")
    
    # GitHub suggestions
    if github:
        if github.activity_level == "Low":
            suggestions.append(
                "Increase GitHub activity: Contribute to open source or create showcase projects"
            )
        if github.public_repos < 5:
            suggestions.append(
                "Add more public repositories showcasing your skills"
            )
    elif resume.github_url:
        suggestions.append(
            "Consider making key repositories public to demonstrate skills"
        )
    
    # Resume suggestions
    if not resume.summary:
        suggestions.append(
            "Add a professional summary highlighting your key strengths"
        )
    
    if len(resume.experience) > 0:
        has_metrics = False
        for exp in resume.experience:
            if any(char.isdigit() for char in " ".join(exp.highlights)):
                has_metrics = True
                break
        if not has_metrics:
            suggestions.append(
                "Add quantifiable achievements (e.g., 'increased performance by 40%')"
            )
    
    if not resume.certifications:
        suggestions.append(
            "Consider adding relevant certifications to stand out"
        )
    
    # Limit to top 5 most actionable
    suggestions = suggestions[:5]
    
    return {
        "improvement_suggestions": suggestions,
        "messages": state.get("messages", []) + [
            {"role": "improvement", "content": f"Generated {len(suggestions)} improvement suggestions"}
        ],
    }
