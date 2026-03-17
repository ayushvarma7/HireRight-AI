"""
Conditional Edge: Should Redebate?

Determines if agents should have another debate round.
"""

from app.agents.state import AgentState
from app.core.config import settings


def should_redebate(state: AgentState) -> str:
    """
    Conditional edge function for redebate decision.
    
    Returns "redebate" if agents should debate again, "continue" otherwise.
    
    Redebate conditions:
    1. Score difference exceeds threshold (e.g., 30%)
    2. Haven't reached max rounds
    """
    score_difference = state.get("score_difference", 0)
    current_round = state.get("current_round", 1)
    should_redebate_flag = state.get("should_redebate", False)
    
    # Already computed by judge
    if should_redebate_flag:
        return "redebate"
    
    # Double-check conditions
    if (
        score_difference > settings.redebate_threshold
        and current_round < settings.max_debate_rounds
    ):
        return "redebate"
    
    return "continue"
