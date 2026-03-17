"""
Supabase Connection and Client Management
"""

import os
from typing import Optional
from supabase import create_client, Client
from app.core.config import settings

# Initialize Supabase client
_supabase_client: Optional[Client] = None

def get_supabase() -> Client:
    """Get or create Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_key:
            # Fallback for debugging, though in production these must be set
            url = os.getenv("SUPABASE_URL", settings.supabase_url)
            key = os.getenv("SUPABASE_KEY", settings.supabase_key)
            if not url or not key:
                print("⚠️ Supabase credentials not found in settings or environment")
            _supabase_client = create_client(url, key)
        else:
            _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase_client

# Shortcut for dependency injection or direct use
supabase = get_supabase()

async def fetch_jobs(limit: int = 10):
    """Fetch jobs from Supabase 'jobs' table."""
    client = get_supabase()
    response = client.table("jobs").select("*").eq("is_active", True).order("scraped_at", desc=True).limit(limit).execute()
    return response.data

async def save_job(job_data: dict):
    """Save a job to Supabase 'jobs' table."""
    client = get_supabase()
    response = client.table("jobs").upsert(job_data).execute()
    return response.data
