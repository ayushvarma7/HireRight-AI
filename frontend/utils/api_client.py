"""
API Client

Wrapper for backend API calls.
"""

import httpx
from typing import Any, Dict, List, Optional

# Default backend URL - can be overridden
BACKEND_URL = "http://localhost:8000"


class APIClient:
    """Client for HireRight backend API."""
    
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if backend is healthy."""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def create_profile(
        self,
        email: str,
        name: Optional[str] = None,
        github_username: Optional[str] = None,
        resume_content: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Create a user profile."""
        data = {"email": email}
        if name:
            data["name"] = name
        if github_username:
            data["github_username"] = github_username
        
        files = {}
        if resume_content:
            files["resume"] = ("resume.pdf", resume_content, "application/pdf")
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/profile",
            data=data,
            files=files if files else None,
        )
        response.raise_for_status()
        return response.json()
    
    async def match_jobs(
        self,
        resume_data: Dict[str, Any],
        job_search_query: Optional[str] = None,
        job: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the matching pipeline."""
        payload = {
            "resume": resume_data,
        }
        if job_search_query:
            payload["job_search_query"] = job_search_query
        if job:
            payload["job"] = job
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/match",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_cover_letter(
        self,
        resume_data: Dict[str, Any],
        job: Dict[str, Any],
        tone: str = "professional",
        recruiter_concerns: List[str] = None,
        coach_highlights: List[str] = None,
    ) -> Dict[str, Any]:
        """Generate a cover letter."""
        payload = {
            "resume": resume_data,
            "job": job,
            "tone": tone,
            "recruiter_concerns": recruiter_concerns or [],
            "coach_highlights": coach_highlights or [],
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/cover-letter",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def get_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get user analytics."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/analytics/{user_id}"
        )
        response.raise_for_status()
        return response.json()
    
    async def get_recommendations(self, user_id: str) -> Dict[str, Any]:
        """Get headhunter recommendations."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/headhunter/{user_id}"
        )
        response.raise_for_status()
        return response.json()


def get_sync_client(base_url: str = BACKEND_URL) -> httpx.Client:
    """Get a synchronous client for use in Streamlit."""
    return httpx.Client(base_url=base_url, timeout=60.0)
