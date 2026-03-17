"""
GitHub Context MCP Server

This server provides tools for analyzing GitHub profiles,
repositories, and contribution patterns via HTTP API.
"""

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="GitHub Context MCP Server",
    description="Provides GitHub profile and repository analysis",
    version="1.0.0",
)

from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# GitHub API configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE = "https://api.github.com"
PORT = int(os.getenv("PORT", 8001))


def get_github_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "HireRight-MCP-Server",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


async def fetch_github(endpoint: str) -> dict[str, Any]:
    """Fetch data from GitHub API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}{endpoint}",
            headers=get_github_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# Request/Response Models
# =============================================================================

class UsernameRequest(BaseModel):
    username: str


class RepoRequest(BaseModel):
    owner: str
    repo: str


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "github-context"}


@app.post("/tools/get_user_repos")
async def get_user_repos(request: UsernameRequest):
    """Get all public repositories for a GitHub user."""
    try:
        repos = await fetch_github(f"/users/{request.username}/repos?per_page=100&sort=updated")
        
        result = []
        for repo in repos:
            result.append({
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description"),
                "url": repo["html_url"],
                "language": repo.get("language"),
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "is_fork": repo["fork"],
                "updated_at": repo["updated_at"],
                "topics": repo.get("topics", []),
            })
        
        return {
            "username": request.username,
            "repo_count": len(result),
            "repositories": result,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_repo_details")
async def get_repo_details(request: RepoRequest):
    """Get detailed information about a specific repository."""
    try:
        # Fetch repo info
        repo = await fetch_github(f"/repos/{request.owner}/{request.repo}")
        
        # Fetch languages
        languages = await fetch_github(f"/repos/{request.owner}/{request.repo}/languages")
        
        # Fetch recent commits
        commits = await fetch_github(f"/repos/{request.owner}/{request.repo}/commits?per_page=10")
        
        return {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "description": repo.get("description"),
            "url": repo["html_url"],
            "language": repo.get("language"),
            "languages": languages,
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "watchers": repo["watchers_count"],
            "open_issues": repo["open_issues_count"],
            "created_at": repo["created_at"],
            "updated_at": repo["updated_at"],
            "topics": repo.get("topics", []),
            "license": repo.get("license", {}).get("name") if repo.get("license") else None,
            "recent_commits": [
                {
                    "sha": c["sha"][:7],
                    "message": c["commit"]["message"].split("\n")[0],
                    "author": c["commit"]["author"]["name"],
                    "date": c["commit"]["author"]["date"],
                }
                for c in commits[:5]
            ],
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/analyze_code_quality")
async def analyze_code_quality(request: RepoRequest):
    """Analyze code quality indicators for a repository."""
    try:
        # Fetch repo info
        repo = await fetch_github(f"/repos/{request.owner}/{request.repo}")
        
        # Fetch languages
        languages = await fetch_github(f"/repos/{request.owner}/{request.repo}/languages")
        
        # Fetch commits for activity
        commits = await fetch_github(f"/repos/{request.owner}/{request.repo}/commits?per_page=30")
        
        # Fetch contributors
        try:
            contributors = await fetch_github(f"/repos/{request.owner}/{request.repo}/contributors?per_page=10")
        except:
            contributors = []
        
        # Calculate metrics
        total_bytes = sum(languages.values()) if languages else 0
        language_breakdown = {
            lang: round((bytes_count / total_bytes) * 100, 1) if total_bytes > 0 else 0
            for lang, bytes_count in languages.items()
        }
        
        # Activity score (based on recent commits)
        commit_count = len(commits)
        activity_level = "High" if commit_count >= 20 else "Medium" if commit_count >= 5 else "Low"
        
        return {
            "repository": repo["full_name"],
            "quality_indicators": {
                "has_description": bool(repo.get("description")),
                "has_license": bool(repo.get("license")),
                "has_topics": len(repo.get("topics", [])) > 0,
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "open_issues": repo["open_issues_count"],
            },
            "language_breakdown": language_breakdown,
            "primary_language": repo.get("language"),
            "activity": {
                "recent_commit_count": commit_count,
                "activity_level": activity_level,
                "contributor_count": len(contributors),
            },
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_user_profile")
async def get_user_profile(request: UsernameRequest):
    """Get comprehensive GitHub user profile."""
    try:
        # Fetch user info
        user = await fetch_github(f"/users/{request.username}")
        
        # Fetch repos
        repos = await fetch_github(f"/users/{request.username}/repos?per_page=100&sort=updated")
        
        # Calculate stats
        total_stars = sum(r["stargazers_count"] for r in repos)
        languages = {}
        for repo in repos:
            if repo.get("language"):
                languages[repo["language"]] = languages.get(repo["language"], 0) + 1
        
        top_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "username": user["login"],
            "name": user.get("name"),
            "bio": user.get("bio"),
            "company": user.get("company"),
            "location": user.get("location"),
            "blog": user.get("blog"),
            "email": user.get("email"),
            "public_repos": user["public_repos"],
            "followers": user["followers"],
            "following": user["following"],
            "created_at": user["created_at"],
            "stats": {
                "total_stars": total_stars,
                "total_repos": len(repos),
                "top_languages": [{"language": lang, "repo_count": count} for lang, count in top_languages],
            },
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_contribution_patterns")
async def get_contribution_patterns(request: UsernameRequest):
    """Analyze contribution patterns for a user."""
    try:
        # Fetch recent events
        events = await fetch_github(f"/users/{request.username}/events?per_page=100")
        
        # Analyze event types
        event_counts = {}
        for event in events:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Count specific contributions
        push_count = event_counts.get("PushEvent", 0)
        pr_count = event_counts.get("PullRequestEvent", 0)
        issue_count = event_counts.get("IssuesEvent", 0)
        review_count = event_counts.get("PullRequestReviewEvent", 0)
        
        return {
            "username": request.username,
            "total_recent_events": len(events),
            "contributions": {
                "commits": push_count,
                "pull_requests": pr_count,
                "issues": issue_count,
                "code_reviews": review_count,
            },
            "event_breakdown": event_counts,
            "activity_level": "High" if len(events) > 50 else "Medium" if len(events) > 20 else "Low",
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print(f"🚀 Starting GitHub Context MCP Server on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
