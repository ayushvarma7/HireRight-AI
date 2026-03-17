"""
Coach Agent Node

The "Career Coach" that highlights strengths and advocates for the candidate.
"""

import json
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.coach_prompt import get_coach_prompt
from app.agents.state import AgentState
from app.core.config import settings
from app.models import Argument


async def coach_node(state: AgentState) -> Dict[str, Any]:
    """
    Coach agent advocates for the candidate.
    
    This node:
    1. Identifies strengths that match job requirements
    2. Highlights transferable skills and potential
    3. Provides a score (higher = more strengths)
    """
    resume = state["resume_data"]
    job = state["job_data"]
    parsed_skills = state.get("parsed_skills", [])
    parsed_strengths = state.get("parsed_strengths", [])
    current_round = state.get("current_round", 1)
    
    # Build job requirements list
    job_requirements = job.required_skills + job.preferred_skills
    
    # Get summaries
    resume_summary = state.get("parsed_experience_summary", resume.summary or "")
    job_summary = f"{job.title} at {job.company}: {job.description[:500]}"
    
    # Generate prompt
    prompt = get_coach_prompt(
        resume_summary=resume_summary,
        job_summary=job_summary,
        skills=parsed_skills,
        job_requirements=job_requirements,
        strengths=parsed_strengths,
    )
    
    # Call LLM
    arguments = []
    score = 50.0  # Default neutral score
    
    if settings.google_api_key:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.7,
        )
        
        response = await llm.ainvoke([
            {"role": "system", "content": "You are the Career Coach. Respond with JSON."},
            {"role": "user", "content": prompt + "\n\nRespond in JSON format: {\"arguments\": [{\"point\": string, \"evidence\": string, \"strength\": string, \"category\": string}], \"score\": number}"},
        ])
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            
            for arg in data.get("arguments", []):
                arguments.append(Argument(
                    point=arg.get("point", ""),
                    evidence=arg.get("evidence"),
                    strength=arg.get("strength", "Medium"),
                    category=arg.get("category"),
                ))
            
            score = float(data.get("score", 50))
            
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    
    # Fallback arguments if LLM unavailable
    if not arguments:
        matching_skills = set(job_requirements) & set(parsed_skills)
        if matching_skills:
            arguments.append(Argument(
                point=f"Strong skill match with {len(matching_skills)} required skills",
                evidence=f"Has: {', '.join(list(matching_skills)[:5])}",
                strength="Strong" if len(matching_skills) > 3 else "Medium",
                category="Skills",
            ))
        
        for strength in parsed_strengths[:3]:
            arguments.append(Argument(
                point=strength,
                evidence="Evident from resume",
                strength="Medium",
                category="Background",
            ))
        
        # Calculate score based on strengths
        strength_bonus = len(arguments) * 10
        score = min(95, 50 + strength_bonus)
    
    return {
        "coach_arguments": arguments,
        "coach_score": score,
        "messages": state.get("messages", []) + [
            {"role": "coach", "content": f"Round {current_round}: Found {len(arguments)} strengths, score: {score}"}
        ],
    }
