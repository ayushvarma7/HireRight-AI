"""
Score Gauge Component

Circular match score display with color-coding.
"""

import streamlit as st


def score_gauge(score: float, label: str = "Match Score") -> None:
    """
    Display a circular score gauge.
    
    Args:
        score: Score from 0-100
        label: Label to display below the score
    """
    # Determine color based on score
    if score >= 80:
        color = "#10b981"  # Green
        status = "Excellent"
    elif score >= 60:
        color = "#f59e0b"  # Yellow/Orange
        status = "Good"
    elif score >= 40:
        color = "#f97316"  # Orange
        status = "Fair"
    else:
        color = "#ef4444"  # Red
        status = "Poor"
    
    # SVG circle gauge
    svg = f"""
    <div style="text-align: center; padding: 20px;">
        <svg width="150" height="150" viewBox="0 0 150 150">
            <!-- Background circle -->
            <circle
                cx="75"
                cy="75"
                r="60"
                fill="none"
                stroke="#374151"
                stroke-width="10"
            />
            <!-- Progress circle -->
            <circle
                cx="75"
                cy="75"
                r="60"
                fill="none"
                stroke="{color}"
                stroke-width="10"
                stroke-dasharray="{score * 3.77} 377"
                stroke-linecap="round"
                transform="rotate(-90 75 75)"
                style="transition: stroke-dasharray 0.5s ease;"
            />
            <!-- Score text -->
            <text
                x="75"
                y="70"
                text-anchor="middle"
                fill="{color}"
                font-size="28"
                font-weight="bold"
            >
                {int(score)}%
            </text>
            <text
                x="75"
                y="95"
                text-anchor="middle"
                fill="#9ca3af"
                font-size="14"
            >
                {status}
            </text>
        </svg>
        <p style="color: #9ca3af; margin-top: 10px;">{label}</p>
    </div>
    """
    
    st.markdown(svg, unsafe_allow_html=True)


def mini_score(score: float) -> str:
    """
    Get a mini inline score badge.
    
    Returns HTML string for inline display.
    """
    if score >= 80:
        bg_color = "rgba(16, 185, 129, 0.2)"
        text_color = "#10b981"
    elif score >= 60:
        bg_color = "rgba(249, 115, 22, 0.2)"
        text_color = "#f97316"
    else:
        bg_color = "rgba(239, 68, 68, 0.2)"
        text_color = "#ef4444"
    
    return f"""
    <span style="
        background: {bg_color};
        color: {text_color};
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 14px;
    ">
        {int(score)}% match
    </span>
    """
