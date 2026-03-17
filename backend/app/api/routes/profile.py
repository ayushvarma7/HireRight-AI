"""
Profile Route

Handle user profile creation with resume and GitHub data.
"""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import GitHubProfile, ResumeData, UserProfile
from app.services.resume_parser import parse_resume

router = APIRouter()


@router.post("/profile", response_model=UserProfile)
async def create_profile(
    email: str = Form(...),
    name: Optional[str] = Form(None),
    github_username: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
):
    """
    Create a user profile with resume and GitHub data.
    
    - Upload resume PDF to extract skills and experience
    - Optionally provide GitHub username for profile analysis
    """
    profile_data = {
        "email": email,
        "name": name,
    }
    
    # Parse resume if provided
    if resume:
        if not resume.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF resumes are supported")
        
        try:
            content = await resume.read()
            resume_data = await parse_resume(content)
            profile_data["resume"] = resume_data
            
            # Use resume name if not provided
            if not name and resume_data.name:
                profile_data["name"] = resume_data.name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse resume: {str(e)}")
    
    # Fetch GitHub profile if username provided
    if github_username:
        try:
            # In production, call MCP server
            # For now, create placeholder
            github_profile = GitHubProfile(
                username=github_username,
                public_repos=0,
                activity_level="Unknown",
            )
            profile_data["github"] = github_profile
        except Exception as e:
            # Non-fatal - continue without GitHub data
            pass
    
    # Create profile
    profile = UserProfile(**profile_data)
    
    # TODO: Save to database
    
    return profile


@router.get("/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: str):
    """Get user profile by ID."""
    # TODO: Fetch from database
    raise HTTPException(status_code=404, detail="Profile not found")


@router.put("/profile/{user_id}", response_model=UserProfile)
async def update_profile(
    user_id: str,
    github_username: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
):
    """Update user profile with new resume or GitHub data."""
    # TODO: Implement update logic
    raise HTTPException(status_code=404, detail="Profile not found")
