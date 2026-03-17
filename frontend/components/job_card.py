"""
Job Card Component

Reusable card for displaying job listings.
"""

import streamlit as st
from typing import Dict, Any, Optional


def job_card(
    job: Dict[str, Any],
    score: Optional[float] = None,
    on_view: Optional[callable] = None,
    on_save: Optional[callable] = None,
) -> None:
    """
    Display a job listing card.
    
    Args:
        job: Job data dictionary
        score: Optional match score
        on_view: Callback when view button clicked
        on_save: Callback when save button clicked
    """
    
    title = job.get("title", "Unknown Position")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Not specified")
    job_type = job.get("job_type", "Full-time")
    remote = job.get("remote_policy", "On-site")
    
    # Salary formatting
    salary = job.get("salary", {})
    if salary:
        salary_min = salary.get("min_salary", 0)
        salary_max = salary.get("max_salary", 0)
        salary_text = f"${salary_min:,} - ${salary_max:,}" if salary_min else "Not disclosed"
    else:
        salary_text = "Not disclosed"
    
    # Score color
    if score:
        if score >= 80:
            score_color = "#10b981"
            score_bg = "rgba(16, 185, 129, 0.1)"
        elif score >= 60:
            score_color = "#f59e0b"
            score_bg = "rgba(245, 158, 11, 0.1)"
        else:
            score_color = "#ef4444"
            score_bg = "rgba(239, 68, 68, 0.1)"
    
    # Card HTML
    st.markdown(f"""
    <div style="
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    ">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
                <h3 style="color: #fff; margin: 0 0 0.5rem 0;">{title}</h3>
                <p style="color: #8b5cf6; margin: 0 0 0.5rem 0; font-weight: 500;">{company}</p>
                <p style="color: #9ca3af; margin: 0; font-size: 14px;">
                    📍 {location} · 💼 {job_type} · 🏠 {remote}
                </p>
            </div>
            {f'''
            <div style="
                background: {score_bg};
                border: 1px solid {score_color};
                border-radius: 12px;
                padding: 0.5rem 1rem;
                text-align: center;
            ">
                <span style="color: {score_color}; font-size: 24px; font-weight: bold;">{score:.0f}%</span>
                <p style="color: {score_color}; margin: 0; font-size: 12px;">match</p>
            </div>
            ''' if score else ''}
        </div>
        <div style="margin-top: 1rem; display: flex; gap: 1rem; font-size: 14px;">
            <span style="color: #6b7280;">💰 {salary_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("View Details", key=f"view_{job.get('id', title)}"):
            if on_view:
                on_view(job)
    with col2:
        if st.button("💾 Save", key=f"save_{job.get('id', title)}"):
            if on_save:
                on_save(job)


def job_card_compact(
    title: str,
    company: str,
    score: float,
    urgency: str = "",
) -> None:
    """
    Display a compact job card for lists.
    """
    
    if score >= 80:
        score_color = "#10b981"
    elif score >= 60:
        score_color = "#f59e0b"
    else:
        score_color = "#ef4444"
    
    urgency_badge = ""
    if urgency:
        urgency_colors = {
            "New": "#3b82f6",
            "High Match": "#10b981",
            "Expiring Soon": "#f59e0b",
            "Perfect Fit": "#8b5cf6",
        }
        color = urgency_colors.get(urgency, "#6b7280")
        urgency_badge = f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 8px;">{urgency}</span>'
    
    st.markdown(f"""
    <div style="
        background: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div>
            <span style="color: #fff; font-weight: 500;">{title}</span>
            {urgency_badge}
            <p style="color: #9ca3af; margin: 0; font-size: 13px;">{company}</p>
        </div>
        <span style="color: {score_color}; font-weight: 600;">{score:.0f}%</span>
    </div>
    """, unsafe_allow_html=True)
