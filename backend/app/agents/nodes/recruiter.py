"""
Recruiter Agent Node

The "Ruthless Recruiter" that identifies weaknesses and concerns.
"""

import json
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.recruiter_prompt import get_recruiter_prompt
from app.agents.state import AgentState
from app.core.config import settings
from app.models import Argument


async def recruiter_node(state: AgentState) -> Dict[str, Any]:
    """
    Recruiter agent evaluates the candidate critically.
    
    This node:
    1. Analyzes the resume against job requirements
    2. Identifies all potential concerns and weaknesses
    3. Provides a score (lower = more concerns)
    """
    resume = state["resume_data"]
    job = state["job_data"]
    parsed_skills = state.get("parsed_skills", [])
    current_round = state.get("current_round", 0) + 1
    
    # Build job requirements list
    job_requirements = job.required_skills + job.preferred_skills
    
    # Get resume summary
    resume_summary = state.get("parsed_experience_summary", resume.summary or "")
    job_summary = f"{job.title} at {job.company}: {job.description[:500]}"
    
    # Generate prompt
    prompt = get_recruiter_prompt(
        resume_summary=resume_summary,
        job_summary=job_summary,
        skills=parsed_skills,
        job_requirements=job_requirements,
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
            {"role": "system", "content": "You are the Ruthless Recruiter. Respond with JSON."},
            {"role": "user", "content": prompt + "\n\nRespond in JSON format: {\"arguments\": [{\"point\": string, \"evidence\": string, \"strength\": string, \"category\": string}], \"score\": number}"},
        ])
        
        try:
            # Parse JSON response
            content = response.content
            # Try to extract JSON from the response
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
            # Fallback: generate basic arguments
            pass
    
    # Fallback arguments if LLM unavailable or failed
    if not arguments:
        missing_skills = set(job_requirements) - set(parsed_skills)
        if missing_skills:
            arguments.append(Argument(
                point=f"Missing {len(missing_skills)} required skills",
                evidence=f"Missing: {', '.join(list(missing_skills)[:5])}",
                strength="Strong" if len(missing_skills) > 3 else "Medium",
                category="Skills",
            ))
        
        if state.get("total_years_experience", 0) < (job.min_experience_years or 0):
            arguments.append(Argument(
                point="Insufficient years of experience",
                evidence=f"Has {state.get('total_years_experience', 0)} years, needs {job.min_experience_years}",
                strength="Strong",
                category="Experience",
            ))
        
        # Calculate score based on concerns
        concern_penalty = len(arguments) * 10
        score = max(20, 100 - concern_penalty)
    
    return {
        "recruiter_arguments": arguments,
        "recruiter_score": score,
        "current_round": current_round,
        "messages": state.get("messages", []) + [
            {"role": "recruiter", "content": f"Round {current_round}: Found {len(arguments)} concerns, score: {score}"}
        ],
    }
