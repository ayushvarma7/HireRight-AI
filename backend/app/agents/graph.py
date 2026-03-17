"""
Main LangGraph Agent Pipeline

Wires together all agent nodes into a StateGraph for job-resume matching.
"""

import time
from datetime import datetime
from typing import Optional

from langgraph.graph import END, StateGraph

from app.agents.edges.should_redebate import should_redebate
from app.agents.nodes.coach import coach_node
from app.agents.nodes.cover_writer import cover_writer_node
from app.agents.nodes.improvement import improvement_node
from app.agents.nodes.judge import judge_node
from app.agents.nodes.profile_parser import profile_parser_node
from app.agents.nodes.recruiter import recruiter_node
from app.agents.nodes.skill_gap import skill_gap_node
from app.agents.state import AgentState
from app.core.config import settings
from app.models import (
    AgentPipelineResult,
    DebateRound,
    GitHubProfile,
    JobListing,
    ResumeData,
    Verdict,
    VerdictReasoning,
)


def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph StateGraph for the agent pipeline.
    
    Flow:
    START → profile_parser → recruiter → coach → judge 
         → [redebate?] → (yes) → recruiter → coach → judge
         → (no) → skill_gap → cover_writer → improvement → END
    """
    
    # Create the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("profile_parser", profile_parser_node)
    graph.add_node("recruiter", recruiter_node)
    graph.add_node("coach", coach_node)
    graph.add_node("judge", judge_node)
    graph.add_node("skill_gap", skill_gap_node)
    graph.add_node("cover_writer", cover_writer_node)
    graph.add_node("improvement", improvement_node)
    
    # Set entry point
    graph.set_entry_point("profile_parser")
    
    # Add edges
    graph.add_edge("profile_parser", "recruiter")
    graph.add_edge("recruiter", "coach")
    graph.add_edge("coach", "judge")
    
    # Conditional edge: redebate or continue
    graph.add_conditional_edges(
        "judge",
        should_redebate,
        {
            "redebate": "recruiter",
            "continue": "skill_gap",
        }
    )
    
    graph.add_edge("skill_gap", "cover_writer")
    graph.add_edge("cover_writer", "improvement")
    graph.add_edge("improvement", END)
    
    return graph


# Compile the graph once
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = create_agent_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


async def run_agent_pipeline(
    resume: ResumeData,
    job: JobListing,
    github_username: Optional[str] = None,
    include_cover_letter: bool = True,
    include_skill_gaps: bool = True,
) -> AgentPipelineResult:
    """
    Run the complete agent pipeline for job-resume matching.
    
    Args:
        resume: Parsed resume data
        job: Job listing to match against
        github_username: Optional GitHub username for additional context
        include_cover_letter: Whether to generate a cover letter
        include_skill_gaps: Whether to analyze skill gaps
        
    Returns:
        AgentPipelineResult with debate rounds, verdict, and outputs
    """
    start_time = time.time()
    
    # Initialize state
    github_profile = None
    if github_username:
        # TODO: Fetch from MCP server
        github_profile = GitHubProfile(username=github_username)
    
    initial_state: AgentState = {
        "resume_data": resume,
        "job_data": job,
        "github_profile": github_profile,
        "current_round": 0,
        "recruiter_arguments": [],
        "recruiter_score": 50.0,
        "coach_arguments": [],
        "coach_score": 50.0,
        "debate_rounds": [],
        "score_difference": 0.0,
        "should_redebate": False,
        "skill_gaps": [],
        "improvement_suggestions": [],
        "tokens_used": 0,
        "messages": [],
        "processing_started_at": datetime.utcnow().isoformat(),
    }
    
    # Run the graph
    graph = get_compiled_graph()
    
    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        # Return result with error
        return AgentPipelineResult(
            resume_summary=resume.summary or "Resume parsed",
            job_summary=f"{job.title} at {job.company}",
            github_summary=github_profile.username if github_profile else None,
            debate_rounds=[],
            total_rounds=0,
            verdict=Verdict(
                final_score=0,
                recommendation="Error",
                reasoning=VerdictReasoning(
                    key_strengths=[],
                    key_concerns=[str(e)],
                    deciding_factors=["Pipeline error"],
                    recommendation="Error during processing",
                ),
                confidence=0,
            ),
            processing_time_seconds=time.time() - start_time,
        )
    
    # Build result
    processing_time = time.time() - start_time
    
    # Convert SkillGap objects to dicts if needed
    skill_gaps_raw = final_state.get("skill_gaps", [])
    skill_gaps_dicts = []
    for sg in skill_gaps_raw:
        if isinstance(sg, dict):
            skill_gaps_dicts.append(sg)
        elif hasattr(sg, "model_dump"):
            skill_gaps_dicts.append(sg.model_dump())
        elif hasattr(sg, "dict"):
            skill_gaps_dicts.append(sg.dict())
        else:
            skill_gaps_dicts.append({"skill_name": str(sg)})
    
    return AgentPipelineResult(
        resume_summary=final_state.get("parsed_experience_summary", resume.summary or ""),
        job_summary=f"{job.title} at {job.company}",
        github_summary=github_profile.username if github_profile else None,
        debate_rounds=final_state.get("debate_rounds", []),
        total_rounds=final_state.get("current_round", 0),
        verdict=final_state.get("final_verdict") or Verdict(
            final_score=50,
            recommendation="Incomplete",
            reasoning=VerdictReasoning(
                key_strengths=[],
                key_concerns=[],
                deciding_factors=[],
                recommendation="Pipeline incomplete",
            ),
            confidence=0,
        ),
        skill_gaps=skill_gaps_dicts,
        cover_letter=final_state.get("cover_letter"),
        improvement_suggestions=final_state.get("improvement_suggestions", []),
        processing_time_seconds=processing_time,
        tokens_used=final_state.get("tokens_used", 0),
    )
