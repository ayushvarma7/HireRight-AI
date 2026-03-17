"""
Resume Parser Service

Uses Mistral AI to parse PDF resumes into structured data.
Fallback to regex-based extraction if Mistral is unavailable.
"""

import io
import json
import os
import re
from typing import Optional

import httpx
import pypdf
from pdfplumber import open as open_pdf

from app.models import Education, Experience, ResumeData, Skill, Certification, Project


# Mistral API Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


# =============================================================================
# Main Entry Points
# =============================================================================

async def parse_resume(pdf_content: bytes) -> ResumeData:
    """
    Parse a PDF resume and extract structured data.
    
    Uses Mistral AI for intelligent parsing, falls back to regex if unavailable.
    """
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_content)
    
    if not text.strip():
        raise ValueError("Could not extract text from PDF. The PDF may be image-based or empty.")
    
    # Try Mistral AI first (better quality)
    if MISTRAL_API_KEY:
        try:
            return await parse_with_mistral(text)
        except Exception as e:
            print(f"Mistral parsing failed, falling back to regex: {e}")
    
    # Fallback to regex-based parsing
    return extract_resume_fields(text)


async def parse_resume_from_url(url: str) -> ResumeData:
    """
    Fetch and parse a resume from a URL (e.g., S3).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return await parse_resume(response.content)


# =============================================================================
# PDF Text Extraction
# =============================================================================

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF bytes using multiple methods."""
    text_parts = []
    
    print(f"📄 Attempting PDF extraction ({len(pdf_content)} bytes)")
    
    # Try pypdf first
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = pypdf.PdfReader(pdf_file)
        
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            print(f"✅ pypdf extracted {len(text_parts)} pages")
    except Exception as e:
        print(f"⚠️ pypdf extraction failed: {e}")
    
    # If pypdf failed, try pdfplumber
    if not text_parts:
        try:
            pdf_file = io.BytesIO(pdf_content)
            with open_pdf(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                print(f"✅ pdfplumber extracted {len(text_parts)} pages")
        except Exception as e:
            print(f"⚠️ pdfplumber extraction failed: {e}")
    
    # Last resort: try to decode raw bytes as text (for text-based PDFs)
    if not text_parts:
        try:
            raw_text = pdf_content.decode("utf-8", errors="ignore")
            # Extract readable text between PDF stream markers
            import re
            text_chunks = re.findall(r'\(([^)]+)\)', raw_text)
            readable = " ".join(text_chunks)
            if len(readable) > 50:
                text_parts.append(readable)
                print(f"✅ Raw text fallback extracted {len(readable)} chars")
        except Exception as e:
            print(f"⚠️ Raw text fallback failed: {e}")
    
    result = "\n".join(text_parts)
    print(f"📄 Total extracted text: {len(result)} chars")
    return result


# =============================================================================
# Mistral AI Parsing (Primary Method)
# =============================================================================

async def parse_with_mistral(resume_text: str) -> ResumeData:
    """
    Use Mistral AI to intelligently parse resume text into structured data.
    """
    prompt = f"""You are an expert resume parser. Parse the following resume into a structured JSON format.

Return ONLY valid JSON with this exact structure (no explanations, no markdown):
{{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890",
    "location": "City, State",
    "linkedin_url": "https://linkedin.com/in/...",
    "github_url": "https://github.com/...",
    "summary": "Professional summary paragraph...",
    "skills": [
        {{"name": "Python", "category": "Programming", "proficiency": "Expert", "years_of_experience": 5}}
    ],
    "experience": [
        {{
            "company": "Company Name",
            "title": "Job Title",
            "location": "City, State",
            "start_date": "2020-01",
            "end_date": "2023-12",
            "is_current": false,
            "description": "Role description...",
            "highlights": ["Achievement 1", "Achievement 2"],
            "technologies": ["Python", "AWS"]
        }}
    ],
    "education": [
        {{
            "institution": "University Name",
            "degree": "Bachelor of Science",
            "field_of_study": "Computer Science",
            "start_date": "2012-09",
            "end_date": "2016-05",
            "gpa": 3.8
        }}
    ],
    "certifications": [
        {{
            "name": "AWS Solutions Architect",
            "issuer": "Amazon Web Services",
            "date_obtained": "2023-01"
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "description": "What it does...",
            "url": "https://github.com/...",
            "technologies": ["Python", "React"]
        }}
    ],
    "languages": ["English", "Spanish"]
}}

Parse this resume text:
---
{resume_text}
---

Return ONLY the JSON object, nothing else."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Low for consistent parsing
                "max_tokens": 4000,
            },
            timeout=60.0,
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract content
        content = result["choices"][0]["message"]["content"]
        
        # Clean up response (remove markdown code blocks if present)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        
        parsed = json.loads(content)
        
        return _convert_to_resume_data(parsed)


def _convert_to_resume_data(parsed: dict) -> ResumeData:
    """Convert parsed JSON to ResumeData model."""
    skills = [
        Skill(
            name=s.get("name", ""),
            category=s.get("category"),
            proficiency=s.get("proficiency"),
            years_of_experience=s.get("years_of_experience"),
        )
        for s in parsed.get("skills", [])
    ]
    
    experience = [
        Experience(
            company=e.get("company", ""),
            title=e.get("title", ""),
            location=e.get("location"),
            start_date=_parse_date(e.get("start_date")),
            end_date=_parse_date(e.get("end_date")),
            is_current=e.get("is_current", False),
            description=e.get("description"),
            highlights=e.get("highlights", []),
            technologies=e.get("technologies", []),
        )
        for e in parsed.get("experience", [])
    ]
    
    education = [
        Education(
            institution=edu.get("institution", ""),
            degree=edu.get("degree", ""),
            field_of_study=edu.get("field_of_study"),
            start_date=_parse_date(edu.get("start_date")),
            end_date=_parse_date(edu.get("end_date")),
            gpa=edu.get("gpa"),
        )
        for edu in parsed.get("education", [])
    ]
    
    certifications = [
        Certification(
            name=c.get("name", ""),
            issuer=c.get("issuer", ""),
            date_obtained=_parse_date(c.get("date_obtained")),
        )
        for c in parsed.get("certifications", [])
    ]
    
    projects = [
        Project(
            name=p.get("name", ""),
            description=p.get("description"),
            url=p.get("url"),
            technologies=p.get("technologies", []),
        )
        for p in parsed.get("projects", [])
    ]
    
    # Calculate total years
    total_years = _calculate_total_years(experience)
    
    return ResumeData(
        name=parsed.get("name", "Unknown"),
        email=parsed.get("email"),
        phone=parsed.get("phone"),
        location=parsed.get("location"),
        linkedin_url=parsed.get("linkedin_url"),
        github_url=parsed.get("github_url"),
        summary=parsed.get("summary"),
        skills=skills,
        experience=experience,
        education=education,
        certifications=certifications,
        projects=projects,
        languages=parsed.get("languages", []),
        total_years_experience=total_years,
    )


def _parse_date(date_str: Optional[str]):
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        from datetime import date
        if len(date_str) == 7:  # "2023-01" format
            return date.fromisoformat(date_str + "-01")
        return date.fromisoformat(date_str)
    except:
        return None


def _calculate_total_years(experience: list[Experience]) -> Optional[float]:
    """Calculate total years of experience."""
    from datetime import date
    total_days = 0
    
    for exp in experience:
        start = exp.start_date
        end = exp.end_date or date.today()
        if start:
            total_days += (end - start).days
    
    if total_days > 0:
        return round(total_days / 365.25, 1)
    return None


# =============================================================================
# Regex-Based Fallback Parsing
# =============================================================================

def extract_resume_fields(text: str) -> ResumeData:
    """Extract structured fields from resume text using regex."""
    
    return ResumeData(
        name=extract_name(text) or "Unknown",
        email=extract_email(text),
        phone=extract_phone(text),
        github_url=extract_github(text),
        linkedin_url=extract_linkedin(text),
        skills=extract_skills(text),
        experience=extract_experience(text),
        education=extract_education(text),
        summary=extract_summary(text),
    )


def extract_name(text: str) -> Optional[str]:
    """Extract name from resume."""
    lines = text.strip().split("\n")
    
    for line in lines[:5]:
        line = line.strip()
        if line and not any(c in line for c in ["@", "http", "phone", "tel"]):
            words = line.split()
            if 1 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                return line
    return None


def extract_email(text: str) -> Optional[str]:
    """Extract email address."""
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number."""
    phone_patterns = [
        r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        r"\d{3}[-.\s]\d{3}[-.\s]\d{4}",
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def extract_github(text: str) -> Optional[str]:
    """Extract GitHub URL."""
    github_pattern = r"github\.com/[a-zA-Z0-9_-]+"
    match = re.search(github_pattern, text, re.IGNORECASE)
    return f"https://{match.group(0)}" if match else None


def extract_linkedin(text: str) -> Optional[str]:
    """Extract LinkedIn URL."""
    linkedin_pattern = r"linkedin\.com/in/[a-zA-Z0-9_-]+"
    match = re.search(linkedin_pattern, text, re.IGNORECASE)
    return f"https://{match.group(0)}" if match else None


def extract_skills(text: str) -> list[Skill]:
    """Extract skills from resume."""
    skills = []
    
    tech_keywords = [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Ruby",
        "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
        "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "Git", "Linux", "CI/CD", "REST", "GraphQL", "gRPC",
        "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-learn",
        "LangChain", "LangGraph", "OpenAI", "Mistral", "Anthropic",
    ]
    
    text_lower = text.lower()
    
    for keyword in tech_keywords:
        if keyword.lower() in text_lower:
            skills.append(Skill(name=keyword, category="Technology"))
    
    return skills


def extract_experience(text: str) -> list[Experience]:
    """Extract work experience."""
    experiences = []
    
    lines = text.split("\n")
    exp_section = ""
    in_exp_section = False
    
    for line in lines:
        line_lower = line.lower().strip()
        if any(header in line_lower for header in ["experience", "work history", "employment"]):
            in_exp_section = True
            continue
        if in_exp_section:
            if any(header in line_lower for header in ["education", "skills", "projects", "certifications"]):
                break
            exp_section += line + "\n"
    
    patterns = [
        r"(?P<title>[\w\s]+(?:Engineer|Developer|Manager|Director|Lead|Analyst))\s+(?:at|@)\s+(?P<company>[\w\s]+)",
        r"(?P<company>[\w\s]+)\s*[-–]\s*(?P<title>[\w\s]+(?:Engineer|Developer|Manager|Director|Lead|Analyst))",
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, exp_section, re.IGNORECASE):
            title = match.group("title").strip()
            company = match.group("company").strip()
            if title and company:
                experiences.append(Experience(title=title, company=company))
    
    return experiences[:5]


def extract_education(text: str) -> list[Education]:
    """Extract education."""
    education = []
    
    degree_patterns = [
        r"(Bachelor|Master|PhD|Ph\.D\.|B\.S\.|M\.S\.|B\.A\.|M\.A\.|BS|MS|BA|MA)\s+(?:of|in)?\s*([\w\s]+?)(?:from|at|,)\s*([\w\s]+University|[\w\s]+College|[\w\s]+Institute)",
    ]
    
    for pattern in degree_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            education.append(Education(
                degree=match.group(1),
                field_of_study=match.group(2).strip(),
                institution=match.group(3).strip(),
            ))
    
    return education[:3]


def extract_summary(text: str) -> Optional[str]:
    """Extract professional summary."""
    lines = text.split("\n")
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(header in line_lower for header in ["summary", "about", "profile", "objective"]):
            summary_lines = []
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line and len(next_line) > 20:
                    summary_lines.append(next_line)
                elif next_line and any(h in next_line.lower() for h in ["experience", "skills", "education"]):
                    break
            if summary_lines:
                return " ".join(summary_lines)[:500]
    
    return None
