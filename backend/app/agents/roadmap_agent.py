from typing import List, Dict, Any
import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize Gemini LLM
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.7,
) if GOOGLE_API_KEY else None

def generate_skill_roadmap(
    resume_text: str,
    job_descriptions: List[str],
    github_context: str = ""
) -> List[Dict[str, Any]]:
    """Generate roadmap using Gemini."""
    if not job_descriptions or not llm:
        return []

    jobs_text = "\n\n".join([f"Job {i+1}: {desc[:500]}..." for i, desc in enumerate(job_descriptions[:3])])
    
    prompt = f"Analyze skills gap for resume: {resume_text[:1000]} vs jobs: {jobs_text}. Return a JSON object with a 'roadmap' key containing an array of objects with keys: skill, priority, reason, time_estimate, resource."
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Simple JSON extraction from markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        data = json.loads(content)
        return data.get("roadmap", []) if "roadmap" in data else list(data.values())[0] if isinstance(list(data.values())[0], list) else []
    except Exception as e:
        print(f"Error generating roadmap with Gemini: {e}")
        return []
