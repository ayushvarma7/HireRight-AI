"""
Cover Letter Writer Node

Generates personalized, debate-informed cover letters.
"""

from typing import Any, Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.writer_prompt import WRITER_SYSTEM_PROMPT
from app.agents.state import AgentState
from app.core.config import settings
from app.models import JobListing, ResumeData


async def cover_writer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate a personalized cover letter.
    
    Uses insights from the debate to:
    - Highlight the strongest matching points
    - Proactively address concerns
    - Tailor the message to the specific role
    """
    resume = state["resume_data"]
    job = state["job_data"]
    verdict = state.get("final_verdict")
    
    # Get debate insights
    coach_highlights = []
    recruiter_concerns = []
    
    for round in state.get("debate_rounds", []):
        for arg in round.coach_arguments[:2]:
            coach_highlights.append(arg.point)
        for arg in round.recruiter_arguments[:2]:
            recruiter_concerns.append(arg.point)
    
    cover_letter = await generate_cover_letter(
        resume=resume,
        job=job,
        recruiter_concerns=recruiter_concerns,
        coach_highlights=coach_highlights,
    )
    
    return {
        "cover_letter": cover_letter.get("cover_letter", ""),
        "messages": state.get("messages", []) + [
            {"role": "cover_writer", "content": "Generated personalized cover letter"}
        ],
    }


async def generate_cover_letter(
    resume: ResumeData,
    job: JobListing,
    recruiter_concerns: List[str] = None,
    coach_highlights: List[str] = None,
    tone: str = "professional",
    length: str = "medium",
    focus_areas: List[str] = None,
) -> Dict[str, Any]:
    """
    Generate a cover letter using LLM.
    
    This function is also called directly by the cover letter API endpoint.
    """
    recruiter_concerns = recruiter_concerns or []
    coach_highlights = coach_highlights or []
    focus_areas = focus_areas or []
    
    # Build prompt
    experience_summary = []
    for exp in resume.experience[:3]:
        experience_summary.append(f"- {exp.title} at {exp.company}")
    
    skills_summary = ", ".join([s.name for s in resume.skills[:10]]) if resume.skills else "Various skills"
    
    prompt = f"""{WRITER_SYSTEM_PROMPT}

## Candidate Information:
**Name**: {resume.name}
**Current/Recent Roles**:
{chr(10).join(experience_summary) if experience_summary else "Not specified"}

**Key Skills**: {skills_summary}
**Summary**: {resume.summary or "Not provided"}

## Target Job:
**Title**: {job.title}
**Company**: {job.company}
**Location**: {job.location}
**Description**: {job.description[:600]}

## Debate Insights:
**Strengths to Highlight**:
{chr(10).join(f"- {h}" for h in coach_highlights[:3]) if coach_highlights else "- General qualifications"}

**Concerns to Address (if relevant)**:
{chr(10).join(f"- {c}" for c in recruiter_concerns[:2]) if recruiter_concerns else "- None significant"}

## Preferences:
**Tone**: {tone}
**Length**: {length} ({"~250 words" if length == "short" else "~350 words" if length == "medium" else "~450 words"})
{f"**Focus Areas**: {', '.join(focus_areas)}" if focus_areas else ""}

Write the cover letter now:"""

    cover_letter = ""
    key_points = []
    suggestions = []
    
    if settings.google_api_key:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.8,  # Higher creativity for writing
        )
        
        response = await llm.ainvoke([
            {"role": "user", "content": prompt},
        ])
        
        cover_letter = response.content
        
        # Extract key points addressed (simple heuristic)
        if coach_highlights:
            for highlight in coach_highlights[:3]:
                if any(word.lower() in cover_letter.lower() for word in highlight.split()[:3]):
                    key_points.append(highlight)
    else:
        # Fallback template
        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job.title} position at {job.company}.

With my background as {resume.experience[0].title if resume.experience else "a professional"}, I bring a combination of {skills_summary[:100]} that aligns well with your requirements.

{resume.summary or "I am a dedicated professional eager to contribute to your team."}

I am excited about the opportunity to bring my skills to {job.company} and contribute to your continued success. I look forward to discussing how my experience can benefit your team.

Best regards,
{resume.name}"""
        
        suggestions = [
            "Add specific achievements with metrics",
            "Research the company for personalization",
            "Configure OpenAI API key for AI-generated letters",
        ]
    
    return {
        "cover_letter": cover_letter,
        "key_points": key_points,
        "suggestions": suggestions,
    }
