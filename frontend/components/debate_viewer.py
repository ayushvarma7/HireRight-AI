"""
Debate Viewer Component

Visualize the agent debate in an interactive format.
"""

import streamlit as st
from typing import List, Dict, Any


def debate_viewer(
    recruiter_arguments: List[Dict[str, Any]],
    coach_arguments: List[Dict[str, Any]],
    recruiter_score: float,
    coach_score: float,
    verdict: Dict[str, Any] = None,
) -> None:
    """
    Display the agent debate with expandable sections.
    
    Args:
        recruiter_arguments: List of recruiter concerns
        coach_arguments: List of coach strengths
        recruiter_score: Recruiter's assessment score
        coach_score: Coach's assessment score
        verdict: Optional judge verdict
    """
    
    # Two-column layout for debate
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(239, 68, 68, 0.1), rgba(239, 68, 68, 0.02));
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 16px;
            padding: 1rem;
        ">
            <h3 style="color: #ef4444;">🔴 Recruiter</h3>
            <p style="color: #9ca3af; font-size: 14px;">Identifies concerns</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.progress(recruiter_score / 100, text=f"Score: {recruiter_score:.0f}/100")
        
        for i, arg in enumerate(recruiter_arguments):
            strength = arg.get("strength", "Medium")
            strength_icon = "🔴" if strength == "Strong" else "🟡" if strength == "Medium" else "⚪"
            
            with st.expander(f"{strength_icon} {arg.get('point', 'Concern')}"):
                st.write(f"**Evidence:** {arg.get('evidence', 'N/A')}")
                st.write(f"**Category:** {arg.get('category', 'General')}")
    
    with col2:
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 0.02));
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 16px;
            padding: 1rem;
        ">
            <h3 style="color: #10b981;">🟢 Coach</h3>
            <p style="color: #9ca3af; font-size: 14px;">Highlights strengths</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.progress(coach_score / 100, text=f"Score: {coach_score:.0f}/100")
        
        for i, arg in enumerate(coach_arguments):
            strength = arg.get("strength", "Medium")
            strength_icon = "🟢" if strength == "Strong" else "🟡" if strength == "Medium" else "⚪"
            
            with st.expander(f"{strength_icon} {arg.get('point', 'Strength')}"):
                st.write(f"**Evidence:** {arg.get('evidence', 'N/A')}")
                st.write(f"**Category:** {arg.get('category', 'General')}")
    
    # Verdict section
    if verdict:
        st.divider()
        
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.05));
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 1rem;
        ">
            <h3 style="color: #8b5cf6;">⚖️ Judge's Verdict</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Final Score", f"{verdict.get('final_score', 0):.0f}%")
        
        with col2:
            st.metric("Recommendation", verdict.get('recommendation', 'N/A'))
        
        with col3:
            confidence = verdict.get('confidence', 0) * 100
            st.metric("Confidence", f"{confidence:.0f}%")
        
        # Reasoning
        reasoning = verdict.get('reasoning', {})
        
        if reasoning.get('key_strengths'):
            st.markdown("**Key Strengths:**")
            for s in reasoning['key_strengths'][:3]:
                st.markdown(f"✅ {s}")
        
        if reasoning.get('key_concerns'):
            st.markdown("**Key Concerns:**")
            for c in reasoning['key_concerns'][:3]:
                st.markdown(f"⚠️ {c}")


def debate_summary_card(
    recruiter_score: float,
    coach_score: float,
    final_score: float,
    recommendation: str,
) -> None:
    """
    Display a compact summary card of the debate.
    """
    
    # Determine winner
    if coach_score > recruiter_score:
        winner = "Coach"
        winner_color = "#10b981"
    else:
        winner = "Recruiter"
        winner_color = "#ef4444"
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 16px;
        padding: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div>
            <p style="color: #9ca3af; margin: 0;">🔴 Recruiter</p>
            <h2 style="color: #ef4444; margin: 0;">{recruiter_score:.0f}</h2>
        </div>
        <div style="text-align: center;">
            <p style="color: #6b7280; margin: 0;">vs</p>
            <p style="color: {winner_color}; font-weight: bold;">{winner} wins</p>
        </div>
        <div style="text-align: right;">
            <p style="color: #9ca3af; margin: 0;">🟢 Coach</p>
            <h2 style="color: #10b981; margin: 0;">{coach_score:.0f}</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)
