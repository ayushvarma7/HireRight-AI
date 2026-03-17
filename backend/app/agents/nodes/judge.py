"""
Judge Agent Node

Evaluates the debate between Recruiter and Coach, makes final decision.
"""

import json
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.judge_prompt import get_judge_prompt
from app.agents.state import AgentState
from app.core.config import settings
from app.models import AgentRole, DebateRound, Verdict, VerdictReasoning


async def judge_node(state: AgentState) -> Dict[str, Any]:
    """
    Judge agent evaluates the debate and provides verdict.
    
    This node:
    1. Reviews arguments from both Recruiter and Coach
    2. Weighs the evidence fairly
    3. Produces a final score and recommendation
    4. Determines if redebate is needed
    """
    job = state["job_data"]
    recruiter_args = state.get("recruiter_arguments", [])
    coach_args = state.get("coach_arguments", [])
    recruiter_score = state.get("recruiter_score", 50.0)
    coach_score = state.get("coach_score", 50.0)
    current_round = state.get("current_round", 1)
    
    # Calculate score difference
    score_difference = abs(coach_score - recruiter_score) / 100.0
    
    # Build job summary
    job_summary = f"{job.title} at {job.company}: {job.description[:500]}"
    
    # Generate prompt
    prompt = get_judge_prompt(
        job_summary=job_summary,
        recruiter_arguments=recruiter_args,
        coach_arguments=coach_args,
        recruiter_score=recruiter_score,
        coach_score=coach_score,
    )
    
    # Default verdict
    final_score = (recruiter_score + coach_score) / 2
    recommendation = get_recommendation(final_score)
    key_strengths = [arg.point for arg in coach_args[:3]]
    key_concerns = [arg.point for arg in recruiter_args[:3]]
    
    if settings.google_api_key:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.3,  # Lower temperature for more consistent judgments
        )
        
        response = await llm.ainvoke([
            {"role": "system", "content": "You are the impartial Judge. Respond with JSON."},
            {"role": "user", "content": prompt + "\n\nRespond in JSON format: {\"final_score\": number, \"recommendation\": string, \"key_strengths\": [string], \"key_concerns\": [string], \"deciding_factors\": [string], \"must_address\": [string], \"nice_to_have\": [string], \"confidence\": number}"},
        ])
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            
            final_score = float(data.get("final_score", final_score))
            recommendation = data.get("recommendation", recommendation)
            key_strengths = data.get("key_strengths", key_strengths)
            key_concerns = data.get("key_concerns", key_concerns)
            deciding_factors = data.get("deciding_factors", [])
            must_address = data.get("must_address", [])
            nice_to_have = data.get("nice_to_have", [])
            confidence = float(data.get("confidence", 0.7))
            # LLM may return confidence as percentage (0-100) instead of decimal (0-1)
            if confidence > 1:
                confidence = confidence / 100.0
            
        except (json.JSONDecodeError, KeyError, ValueError):
            deciding_factors = []
            must_address = []
            nice_to_have = []
            confidence = 0.5
    else:
        deciding_factors = ["Skills match", "Experience alignment"]
        must_address = key_concerns[:2]
        nice_to_have = []
        confidence = 0.6
    
    # Create debate round record
    debate_round = DebateRound(
        round_number=current_round,
        recruiter_arguments=recruiter_args,
        recruiter_score=recruiter_score,
        coach_arguments=coach_args,
        coach_score=coach_score,
        score_difference=score_difference * 100,
    )
    
    # Create verdict
    verdict = Verdict(
        final_score=final_score,
        recommendation=recommendation,
        reasoning=VerdictReasoning(
            key_strengths=key_strengths,
            key_concerns=key_concerns,
            deciding_factors=deciding_factors,
            recommendation=recommendation,
        ),
        confidence=confidence,
        favored_agent=AgentRole.COACH if coach_score > recruiter_score else AgentRole.RECRUITER,
        must_address=must_address,
        nice_to_have=nice_to_have,
    )
    
    # Determine if redebate needed
    should_redebate = (
        score_difference > settings.redebate_threshold 
        and current_round < settings.max_debate_rounds
    )
    
    # Update debate rounds
    debate_rounds = state.get("debate_rounds", []) + [debate_round]
    
    return {
        "score_difference": score_difference,
        "should_redebate": should_redebate,
        "final_verdict": verdict,
        "debate_rounds": debate_rounds,
        "messages": state.get("messages", []) + [
            {"role": "judge", "content": f"Round {current_round}: Final score {final_score}, recommendation: {recommendation}, redebate: {should_redebate}"}
        ],
    }


def get_recommendation(score: float) -> str:
    """Convert score to recommendation."""
    if score >= 85:
        return "Strong Match"
    elif score >= 70:
        return "Good Match"
    elif score >= 55:
        return "Possible Match"
    elif score >= 40:
        return "Weak Match"
    else:
        return "Not Recommended"
