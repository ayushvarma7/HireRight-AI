"""
Health Check Route

Simple health check endpoint for service monitoring.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check service health."""
    return {
        "status": "healthy",
        "service": "hireright-api",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """Check if service is ready to handle requests."""
    # In production, check DB connection, MCP servers, etc.
    return {
        "ready": True,
        "checks": {
            "supabase": "ok",
            "mcp_github": "ok",
            "mcp_jobmarket": "ok",
        },
    }
