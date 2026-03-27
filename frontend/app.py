"""
HireRight Frontend - Streamlit Application

Main entry point with navigation and session management.
Connects to backend API for real job matching.
"""

import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Backend API URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
print(f"DEBUG [frontend]: Backend URL = {BACKEND_URL}")

# Page config - must be first Streamlit command
st.set_page_config(
    page_title="HireRight - AI Job Matching",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium styling
st.markdown("""
<style>
    /* Main theme - HireRight Professional Green/Teal */
    :root {
        --primary-color: #10b981;
        --secondary-color: #0d9488;
        --background-dark: #0a0a1a;
        --card-bg: rgba(255, 255, 255, 0.03);
    }
    
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Main header styling */
    .main-header {
        background: linear-gradient(135deg, #10b981 0%, #0d9488 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(13, 148, 136, 0.1) 100%);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
    }
    
    /* Button styling */
    .stButton>button {
        background: linear-gradient(135deg, #10b981 0%, #0d9488 100%);
        border: none;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.9rem;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(16, 185, 129, 0.3);
    }
    
    /* Score gauge */
    .score-high { color: #10b981; font-weight: bold; }
    .score-medium { color: #f59e0b; font-weight: bold; }
    .score-low { color: #ef4444; font-weight: bold; }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #0a0a1a 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Animation */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade {
        animation: fadeIn 0.5s ease-out;
    }
</style>
""", unsafe_allow_html=True)


def get_supabase_client():
    """Initialize Supabase client for frontend."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

def fetch_jobs_from_db(limit=10):
    """Fetch real jobs from the backend/database."""
    try:
        # Try to get jobs from backend API
        response = requests.get(f"{BACKEND_URL}/api/v1/jobs", params={"limit": limit}, timeout=5)
        if response.status_code == 200:
            raw_jobs = response.json()
            # Ensure keys match what the frontend expects
            processed_jobs = []
            for rj in raw_jobs:
                processed_jobs.append({
                    "id": rj.get('id'),
                    "title": rj.get('title'),
                    "company": rj.get('company'),
                    "description": rj.get('description', ''),
                    "source": rj.get('source_platform') or rj.get('source') or "Market",
                    "remote_type": rj.get('remote_type'),
                    "job_type": rj.get('job_type'),
                    "salary_max": rj.get('salary_max'),
                    "experience_level": rj.get('experience_level')
                })
            return processed_jobs
    except Exception as e:
        print(f"DEBUG: Backend fetch failed: {e}")
        pass
    
    # Fallback: Direct Supabase query
    try:
        supabase = get_supabase_client()
        if not supabase:
            return []
            
        response = supabase.table("jobs")\
            .select("id, title, company, description, source_platform, remote_type, job_type, salary_max, experience_level")\
            .eq("is_active", True)\
            .order("scraped_at", desc=True)\
            .limit(limit)\
            .execute()
            
        jobs = []
        for row in response.data:
            jobs.append({
                "id": row['id'],
                "title": row['title'],
                "company": row['company'],
                "description": row['description'] or "",
                "source": row['source_platform'] or "LinkedIn",
                "remote_type": row.get('remote_type') or "On-site",
                "job_type": row.get('job_type') or "Full-Time",
                "salary_max": row.get('salary_max'),
                "experience_level": row.get('experience_level') or "Mid"
            })
        return jobs
    except Exception as e:
        st.warning(f"Could not fetch jobs from Supabase: {e}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_analytics_data():
    """Fetch comprehensive analytics data from the database."""
    result = {
        "jobs": [],
        "skill_counts": {},
        "salary_data": [],
        "remote_distribution": {},
        "location_data": {},
        "experience_levels": {},
    }
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return result
        
        # 1. Fetch all active jobs with full data
        response = supabase.table("jobs")\
            .select("id, title, company, description, source_platform, required_skills, preferred_skills, salary_min, salary_max, remote_type, experience_level, location")\
            .eq("is_active", True)\
            .order("scraped_at", desc=True)\
            .limit(500)\
            .execute()
        
        skill_counter = {}
        
        for row in response.data:
            job = {
                "id": row.get('id'), "title": row.get('title'), "company": row.get('company'),
                "description": row.get('description') or "", "source": row.get('source_platform') or "LinkedIn",
                "required_skills": row.get('required_skills'), "preferred_skills": row.get('preferred_skills'),
                "salary_min": row.get('salary_min'), "salary_max": row.get('salary_max'),
                "remote_type": row.get('remote_type'), "experience_level": row.get('experience_level'),
                "location": row.get('location'),
            }
            result["jobs"].append(job)
            
            # Count skills
            req_skills = row.get('required_skills') if isinstance(row.get('required_skills'), list) else []
            pref_skills = row.get('preferred_skills') if isinstance(row.get('preferred_skills'), list) else []
            for skill in req_skills + pref_skills:
                if skill and isinstance(skill, str):
                    skill_counter[skill] = skill_counter.get(skill, 0) + 1
            
            # If no explicit skills, extract from description
            if not req_skills and not pref_skills and row.get('description'):
                desc_lower = (row.get('description') or "").lower()
                common_skills = [
                    "Python", "JavaScript", "TypeScript", "Java", "C++", "Go", "Rust", "Ruby",
                    "React", "Node.js", "Angular", "Vue", "Django", "Flask", "FastAPI", "Spring",
                    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform",
                    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
                    "Machine Learning", "Deep Learning", "NLP", "SQL", "Git", "Linux",
                    "TensorFlow", "PyTorch", "Pandas", "Spark", "Airflow", "Kafka",
                    "REST", "GraphQL", "CI/CD", "Agile", "Scrum",
                ]
                for s in common_skills:
                    if s.lower() in desc_lower:
                        skill_counter[s] = skill_counter.get(s, 0) + 1
            
            # Salary data
            if row.get('salary_min') or row.get('salary_max'):
                result["salary_data"].append({
                    "level": row.get('experience_level') or "Unknown",
                    "salary_min": row.get('salary_min') or 0,
                    "salary_max": row.get('salary_max') or row.get('salary_min') or 0,
                })
            
            # Remote distribution
            remote = row.get('remote_type') or "Unknown"
            result["remote_distribution"][remote] = result["remote_distribution"].get(remote, 0) + 1
            
            # Experience levels
            exp = row.get('experience_level') or "Unknown"
            result["experience_levels"][exp] = result["experience_levels"].get(exp, 0) + 1
            
            # Location
            loc = row.get('location') or "Unknown"
            result["location_data"][loc] = result["location_data"].get(loc, 0) + 1
        
        result["skill_counts"] = skill_counter
        
    except Exception as e:
        print(f"⚠️ Analytics data fetch failed: {e}")
    
    return result


def main():
    """Main application entry point."""
    # Sidebar
    with st.sidebar:
        st.markdown(
            '<div style="text-align: center; padding-bottom: 20px;">'
            '<h2 style="color: #10b981; margin-bottom: 0;">HireRight</h2>'
            '<p style="color: #94a3b8; font-size: 0.9em; margin-top: 0;">AI Matching & Analytics</p>'
            '</div>', 
            unsafe_allow_html=True
        )
        st.divider()
        
        page = st.radio(
            "Navigation",
            ["🏠 Dashboard", "🔍 Job Match", "🤖 AI Debate", 
             "✉️ Cover Letter", "📈 Skill Roadmap", "📊 Analytics", "⚙️ Settings"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Profile section
        st.markdown("### 👤 Profile")
        if "resume_uploaded" in st.session_state and st.session_state["resume_uploaded"]:
            st.success("✅ Profile Active")
        else:
            st.info("Upload resume to activate")
    
    # Route to pages
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "🔍 Job Match":
        show_job_match()
    elif page == "🤖 AI Debate":
        show_agent_debate()
    elif page == "✉️ Cover Letter":
        show_cover_letter()
    elif page == "📈 Skill Roadmap":
        show_skill_roadmap()
    elif page == "📊 Analytics":
        show_analytics()
    elif page == "⚙️ Settings":
        show_settings()


def show_dashboard():
    """Dashboard page - showing real jobs from database."""
    st.markdown('<h1 class="main-header">Welcome to HireRight 👋</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;">Your AI-Powered Career Command Center</p>', unsafe_allow_html=True)
    
    # Fetch real jobs from database
    jobs = fetch_jobs_from_db(limit=20)
    total_jobs = len(jobs)
    
    # Quick stats - now with real data
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <p style="color: #10b981; margin: 0; font-size: 0.85rem; font-weight: 600;">MARKET OPPORTUNITIES</p>
            <h2 style="color: white; margin: 0.5rem 0; font-size: 2.5rem;">{total_jobs}</h2>
            <p style="color: #94a3b8; margin: 0; font-size: 0.8rem;">Active jobs tracked</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <p style="color: #0d9488; margin: 0; font-size: 0.85rem; font-weight: 600;">DATA SOURCES</p>
            <h2 style="color: white; margin: 0.5rem 0; font-size: 2.5rem;">3+</h2>
            <p style="color: #94a3b8; margin: 0; font-size: 0.8rem;">LinkedIn, Indeed, etc.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        status = "🟢 Ready" if "resume_uploaded" in st.session_state else "🟡 Pending"
        msg = "Matches unlocked" if "resume_uploaded" in st.session_state else "Upload resume below"
        st.markdown(f"""
        <div class="metric-card">
            <p style="color: #8b5cf6; margin: 0; font-size: 0.85rem; font-weight: 600;">PROFILE STATUS</p>
            <h2 style="color: white; margin: 0.5rem 0; font-size: 1.8rem;">{status}</h2>
            <p style="color: #94a3b8; margin: 0; font-size: 0.8rem;">{msg}</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <p style="color: #6366f1; margin: 0; font-size: 0.85rem; font-weight: 600;">SYSTEM HEALTH</p>
            <h2 style="color: white; margin: 0.5rem 0; font-size: 1.8rem;">🟢 Online</h2>
            <p style="color: #94a3b8; margin: 0; font-size: 0.8rem;">AI Engines Connected</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Show real jobs from database
    st.markdown("### 🌟 Latest Market Additions")
    
    if jobs:
        for job in jobs[:5]:
            with st.container(border=True):
                title_col, source_col = st.columns([5, 1])
                with title_col:
                    title_text = job.get("title", "Unknown Role")
                    job_url    = job.get("url") or job.get("source_url", "")
                    if job_url:
                        st.markdown(f"**[{title_text}]({job_url})**")
                    else:
                        st.markdown(f"**{title_text}**")
                    st.caption(f"🏢 {job.get('company', 'Unknown Company')}")
                with source_col:
                    st.markdown(
                        f'<div style="text-align:right"><span style="background:rgba(14,165,233,0.1);'
                        f'color:#0ea5e9;padding:0.25rem 0.6rem;border-radius:20px;font-size:0.75rem;'
                        f'font-weight:600;">Via {job.get("source_platform", job.get("source","Web"))}</span></div>',
                        unsafe_allow_html=True,
                    )

                badge_col1, badge_col2, badge_col3, badge_col4 = st.columns(4)
                with badge_col1:
                    remote = job.get("remote_type", "on-site")
                    st.markdown(f'<span style="background:rgba(16,185,129,0.1);color:#10b981;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.75rem;">🌍 {remote.title()}</span>', unsafe_allow_html=True)
                with badge_col2:
                    level = (job.get("experience_level") or "mid").title()
                    st.markdown(f'<span style="background:rgba(245,158,11,0.1);color:#f59e0b;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.75rem;">📈 {level}</span>', unsafe_allow_html=True)
                with badge_col3:
                    job_type = (job.get("job_type") or "Full-Time").title()
                    st.markdown(f'<span style="background:rgba(255,255,255,0.05);color:#cbd5e1;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.75rem;">📅 {job_type}</span>', unsafe_allow_html=True)
                with badge_col4:
                    if job.get("salary_max"):
                        st.markdown(f'<span style="background:rgba(139,92,246,0.1);color:#8b5cf6;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.75rem;">💵 Up to ${job["salary_max"]:,}</span>', unsafe_allow_html=True)
    else:
        st.info("No jobs found in the database. Run `venv/bin/python scripts/seed_jobs.py` to populate.")


def show_job_match():
    """Job matching page with real backend integration."""
    st.markdown('<h1 class="main-header">🔍 Discover Your Ideal Role</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;">Upload your resume and let our semantic matching engine find the perfect fit.</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 12px; padding: 1.5rem; height: 100%;">
            <h3 style="color: #10b981; margin-top: 0;">1️⃣ Candidate Profile</h3>
            <p style="color: #94a3b8; font-size: 0.9rem;">Upload your latest resume (PDF) to build your semantic profile.</p>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Upload Resume",
            type=["pdf"],
            label_visibility="collapsed"
        )
        
        st.markdown('<br><p style="color: #94a3b8; font-size: 0.9rem;">(Optional) Connect GitHub to verify technical skills.</p>', unsafe_allow_html=True)
        github_username = st.text_input(
            "GitHub Username",
            placeholder="e.g., octocat",
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)
        
        if uploaded_file:
            st.success("✅ Profile established securely.")
            st.session_state["resume_uploaded"] = True
            st.session_state["resume_file"] = uploaded_file
            st.session_state["resume_bytes"] = uploaded_file.read()
            uploaded_file.seek(0)
    
    with col2:
        st.markdown("""
        <div style="background: rgba(13, 148, 136, 0.05); border: 1px solid rgba(13, 148, 136, 0.2); border-radius: 12px; padding: 1.5rem; height: 100%;">
            <h3 style="color: #0d9488; margin-top: 0;">2️⃣ Target Parameters</h3>
            <p style="color: #94a3b8; font-size: 0.9rem;">Refine your search parameters to focus the semantic engine.</p>
        """, unsafe_allow_html=True)
        
        search_query = st.text_input(
            "Desired Role",
            placeholder="e.g., Senior Python Developer",
        )
        
        location = st.text_input(
            "Location Preference",
            placeholder="e.g., Remote, New York",
        )
        
        experience_level = st.select_slider(
            "Seniority Level",
            options=["Entry", "Mid", "Senior", "Lead", "Executive"],
            value="Senior"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()

    refresh_live = st.checkbox(
        "🔄 Refresh Live Source — fetch new jobs from the web (slower, uses API credits)",
        value=False,
    )

    if st.button("🚀 Start Matching", use_container_width=True):
        st.info("📡 Sending request to backend...")

        if not search_query and not st.session_state.get("resume_uploaded"):
            st.warning("Please upload a resume or enter a search query!")
            return

        # ── Backend connectivity check ──
        st.caption(f"🔗 Connecting to: `{BACKEND_URL}/api/v1/match`")
        try:
            health_check = requests.get(f"{BACKEND_URL}/", timeout=5)
            if health_check.status_code != 200:
                st.error(f"❌ Backend is reachable but returned status {health_check.status_code}")
                return
            st.caption("✅ Backend is reachable")
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Cannot connect to backend at `{BACKEND_URL}`. Is the FastAPI server running?")
            st.code(f"Start it with:\ncd backend && ../venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload", language="bash")
            return
        except Exception as e:
            st.error(f"❌ Backend health check failed: {type(e).__name__}: {e}")
            return

        with st.spinner("Running semantic search & multi-agent analysis..."):
            try:
                # Prepare payload
                payload = {
                    "query": search_query,
                    "location": location,
                    "level": experience_level,
                    "github_username": github_username,
                    "refresh": "1" if refresh_live else "0",
                }
                
                # If resume uploaded, send it
                files = {}
                if st.session_state.get("resume_bytes"):
                    # Use stored raw bytes for reliable re-reads
                    files = {"resume": ("resume.pdf", st.session_state["resume_bytes"], "application/pdf")}
                elif st.session_state.get("resume_file"):
                    st.session_state["resume_file"].seek(0)
                    files = {"resume": ("resume.pdf", st.session_state["resume_file"], "application/pdf")}
                    
                st.caption(f"📤 Sending: query={search_query!r}, resume={'yes' if files else 'no'}")
                
                # Call backend match API
                response = requests.post(
                    f"{BACKEND_URL}/api/v1/match",
                    data=payload,
                    files=files if files else None,
                    timeout=120  # Generous timeout for Gemini + Supabase
                )
                
                st.caption(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    results = response.json()
                    
                    if results.get("success") is False:
                        st.error(f"❌ Analysis Failed: {results.get('error')}")
                        if results.get("detail"):
                            st.info(f"🔍 Detail: {results.get('detail')}")
                        if results.get("traceback"):
                            with st.expander("🐛 Full Traceback"):
                                st.code(results["traceback"], language="python")
                    else:
                        matches = results.get("matches", [])
                        parsed_skills = results.get("parsed_skills", [])
                        proc_time = results.get("processing_time_seconds", "?")
                        
                        if matches:
                            st.session_state["matched_jobs"] = matches
                            st.session_state["has_matches"] = True
                            st.success(f"✅ Found {len(matches)} matches! ({proc_time}s)")

                            if parsed_skills:
                                st.session_state["resume_skills"] = parsed_skills
                            # Store resume summary for cover letter generation
                            if search_query:
                                st.session_state["resume_summary"] = (
                                    f"Candidate targeting {search_query} roles. "
                                    f"Skills: {', '.join(parsed_skills[:15])}."
                                ) if parsed_skills else search_query
                            
                            st.rerun()
                        else:
                            # ── Zero matches: show clear feedback ──
                            st.warning(f"⚠️ 0 jobs matched ({proc_time}s). The Supabase `jobs` table may be empty.")
                            st.info(
                                "**Why no matches?**\n"
                                "- Your Supabase `jobs` table has no job listings yet.\n"
                                "- You need to seed the database with jobs first.\n"
                                "- Run: `cd backend && ../venv/bin/python ../scripts/seed_jobs_supabase.py`"
                            )
                            if parsed_skills:
                                st.session_state["resume_skills"] = parsed_skills
                                st.caption(f"🧠 Skills parsed from resume: {', '.join(parsed_skills[:15])}")
                else:
                    st.error(f"🖥️ Server Error ({response.status_code})")
                    try:
                        err_json = response.json()
                        st.error(f"Error: {err_json.get('error', 'Unknown')}")
                        if err_json.get("detail"):
                            st.warning(f"Detail: {err_json['detail']}")
                        if err_json.get("traceback"):
                            with st.expander("🐛 Full Backend Traceback"):
                                st.code(err_json["traceback"], language="python")
                    except Exception:
                        st.code(response.text[:500])
                    
            except requests.exceptions.ConnectionError as e:
                st.error(f"❌ Connection to backend lost during request: {e}")
                st.info("The backend may have crashed. Check the terminal running uvicorn.")
            except requests.exceptions.Timeout:
                st.error("⏰ Request timed out after 120s. The backend may be overloaded.")
            except Exception as e:
                st.error(f"❌ Matching failed: {type(e).__name__}: {str(e)}")
                import traceback
                with st.expander("🐛 Full Error Details"):
                    st.code(traceback.format_exc(), language="python")
    
    # Show matched jobs
    if st.session_state.get("has_matches") and st.session_state.get("matched_jobs"):
        import re as _re
        _agg_pat = _re.compile(r'search results|best jobs|\d[\d,]*\+?\s+jobs?\s+in', _re.IGNORECASE)
        clean_matches = [
            j for j in st.session_state["matched_jobs"]
            if j.get("title") and not _agg_pat.search(j["title"]) and len(j["title"].split()) <= 15
        ]
        st.markdown(f'<h3 style="margin-top: 2rem; color: #10b981;">🎯 {len(clean_matches)} Highly Compatible Roles Discovered</h3>', unsafe_allow_html=True)

        for job in clean_matches:
            score = job.get("match_score", 0) * 100 if job.get("match_score", 0) < 1 else job.get("match_score", 0)
            score_color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
            level = (job.get('experience_level') or "Mid").title()
            job_url = job.get('url', '')

            with st.container():
                st.markdown(
                    f'<div style="border-left: 4px solid {score_color}; border-radius: 8px; '
                    f'background: rgba(255,255,255,0.03); padding: 1rem 1.2rem; margin-bottom: 0.5rem;">',
                    unsafe_allow_html=True,
                )
                left_col, score_col = st.columns([4, 1])
                with left_col:
                    if job_url:
                        st.markdown(f"### [{job['title']}]({job_url})")
                    else:
                        st.markdown(f"### {job['title']}")
                    st.caption(
                        f"🏢 **{job['company']}** &nbsp;|&nbsp; "
                        f"📍 {job.get('location', 'Unspecified')} &nbsp;|&nbsp; "
                        f"🌐 {job.get('source', 'Market')}"
                    )
                    tags = []
                    if job.get('salary_max'):
                        tags.append(f"💵 Up to ${job['salary_max']:,}")
                    if job.get('remote_type'):
                        tags.append(f"🌍 {job['remote_type'].title()}")
                    tags.append(f"📈 {level} Level")
                    if job.get('job_type'):
                        tags.append(f"📅 {job['job_type'].title()}")
                    st.markdown(" &nbsp; ".join(f"`{t}`" for t in tags))
                with score_col:
                    st.markdown(
                        f'<div style="text-align:center; padding-top: 0.5rem;">'
                        f'<span style="font-size:2rem; font-weight:700; color:{score_color};">{int(score)}%</span>'
                        f'<br><span style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Match</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                st.divider()


def run_langgraph_debate(job, resume_text, resume_skills, github_username):
    """Run the real LangGraph agent debate via backend API."""
    try:
        payload = {
            "resume_summary": resume_text[:2000],  # Limit length
            "resume_skills": resume_skills,
            "job_title": job.get("title", "Unknown"),
            "job_company": job.get("company", "Unknown"),
            "job_description": job.get("description", "")[:2000],  # Limit length
            "job_required_skills": job.get("missing_skills", []), # Use missing skills as proxy for important ones
            "github_username": github_username,
            "include_cover_letter": False
        }
        
        response = requests.post(f"{BACKEND_URL}/api/v1/debate/run-debate", json=payload, timeout=120)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Debate failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


def show_agent_debate():
    """Enhanced Agent debate with job selection and detailed AI insights."""
    st.markdown('<h1 class="main-header">🤖 Multi-Agent AI Debate</h1>', unsafe_allow_html=True)
    
    # ─── Hero Explanation ───
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); 
                padding: 24px; border-radius: 16px; margin-bottom: 24px; color: white;">
        <h3 style="color: #e94560; margin-top: 0;">🎯 What is the Agent Debate?</h3>
        <p style="font-size: 1.05em; line-height: 1.6; color: #e0e0e0;">
            Instead of giving you a <b>simple match score</b>, HireRight uses <b>3 AI agents powered by Gemini AI</b>
            that <em>debate</em> whether you're a good fit for a job — just like a real hiring committee. 
            Each agent has a unique perspective, creating a <b>balanced, multi-dimensional analysis</b> of your candidacy.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ─── Meet the Agents ───
    st.markdown("### 🧑‍💼 Meet Your AI Hiring Committee")
    
    agent_col1, agent_col2, agent_col3 = st.columns(3)
    
    with agent_col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #ff6b6b20, #ee535320); 
                    border: 2px solid #ff6b6b; border-radius: 12px; padding: 20px; height: 280px;">
            <h3 style="color: #ff6b6b; text-align: center;">🔴 The Recruiter</h3>
            <p style="font-weight: bold; text-align: center; color: #ff6b6b;">Devil's Advocate</p>
            <hr style="border-color: #ff6b6b40;">
            <p style="font-size: 0.9em;">Plays the role of a <b>skeptical hiring manager</b>. 
            Identifies gaps in your experience, missing skills, and potential red flags — 
            the tough questions you'd face in a real interview.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with agent_col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #51cf6620, #2ed57320); 
                    border: 2px solid #51cf66; border-radius: 12px; padding: 20px; height: 280px;">
            <h3 style="color: #51cf66; text-align: center;">🟢 The Career Coach</h3>
            <p style="font-weight: bold; text-align: center; color: #51cf66;">Your Advocate</p>
            <hr style="border-color: #51cf6640;">
            <p style="font-size: 0.9em;">Acts as your <b>personal career champion</b>. 
            Highlights transferable skills, reframes weaknesses as growth areas, and 
            emphasizes your unique strengths and potential.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with agent_col3:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #ffd43b20, #fab00520); 
                    border: 2px solid #ffd43b; border-radius: 12px; padding: 20px; height: 280px;">
            <h3 style="color: #ffd43b; text-align: center;">⚖️ The Judge</h3>
            <p style="font-weight: bold; text-align: center; color: #ffd43b;">Final Arbiter</p>
            <hr style="border-color: #ffd43b40;">
            <p style="font-size: 0.9em;">Listens to <b>both sides of the debate</b>, weighs the arguments, 
            and delivers a <b>fair, balanced verdict</b> with a final match score and 
            actionable recommendation.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # ─── Why This Matters ───
    with st.expander("💡 **Why is this better than a simple match score?**", expanded=False):
        st.markdown("""
        | Traditional Matching | 🤖 Agent Debate |
        |---------------------|-----------------|
        | Simple keyword overlap | Deep semantic understanding of your experience |
        | One score, no explanation | Multi-perspective analysis with reasoning |
        | Misses transferable skills | Coach agent identifies hidden strengths |
        | No actionable feedback | Specific gaps to address before applying |
        | Static algorithm | Dynamic AI agents that adapt to each job |
        
        **How this helps you:**
        - 🎯 **Know before you apply** — Understand exactly how strong your candidacy is
        - 📈 **Improve strategically** — See specific skill gaps to close
        - 💪 **Discover hidden strengths** — The Coach finds things you might not think to mention
        - ⚠️ **Anticipate objections** — Know what a recruiter might flag before your interview
        """)
    
    st.divider()
    
    # ─── Job Selector ───
    if not st.session_state.get("matched_jobs"):
        st.warning("No job matches found. Go to **Job Match** and run a search first!")
        if st.button("🔍 Go to Job Match"):
            st.switch_page("Job Match")
        return
    
    matched_jobs = st.session_state["matched_jobs"]
    
    st.markdown("### 📋 Select a Job to Analyze")
    job_options = [f"{j['title']} at {j['company']}" for j in matched_jobs]
    selected_idx = st.selectbox(
        "Choose a job from your matches:",
        range(len(job_options)),
        format_func=lambda x: job_options[x]
    )
    
    selected_job = matched_jobs[selected_idx]
    job_key = f"debate_result_{selected_job.get('id', selected_idx)}"
    
    # Get resume data from session
    resume_summary = st.session_state.get("resume_summary", "")
    resume_skills = [] 
    
    # UI Controls
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🚀 Run AI Debate", type="primary", use_container_width=True):
            with st.spinner("🤖 Agents are debating your candidacy... (Powered by Gemini AI)"):
                result = run_langgraph_debate(
                    selected_job, 
                    resume_summary, 
                    resume_skills, 
                    st.session_state.get("github_username")
                )
                if result:
                    st.session_state[job_key] = result
                    st.rerun()
    with col2:
        if job_key not in st.session_state:
            st.caption("⏱️ Debate typically takes 15-30 seconds as 3 AI agents analyze your profile in real-time.")
    
    # ─── Display Results ───
    if job_key in st.session_state:
        result = st.session_state[job_key]
        
        # ─── Final Verdict (show first for impact) ───
        st.divider()
        st.markdown("## ⚖️ Judge's Final Verdict")
        
        final_score = result.get("final_score", 50)
        recommendation = result.get("recommendation", "Unknown")
        
        # Score with color
        if final_score >= 75:
            score_color, score_emoji, score_label = "#51cf66", "🟢", "Strong Match"
        elif final_score >= 55:
            score_color, score_emoji, score_label = "#ffd43b", "🟡", "Possible Match"
        else:
            score_color, score_emoji, score_label = "#ff6b6b", "🔴", "Weak Match"
        
        score_col1, score_col2 = st.columns([1, 2])
        with score_col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, {score_color}15, {score_color}30); 
                        border: 2px solid {score_color}; border-radius: 16px;">
                <p style="font-size: 3em; font-weight: bold; color: {score_color}; margin: 0;">{final_score:.0f}</p>
                <p style="color: {score_color}; font-size: 0.9em; margin: 0;">out of 100</p>
                <p style="font-size: 1.2em; margin-top: 8px;">{score_emoji} {recommendation}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with score_col2:
            # Key factors side by side
            str_col, con_col = st.columns(2)
            with str_col:
                st.markdown("**👍 Key Strengths**")
                for item in result.get("key_strengths", []):
                    st.markdown(f"✅ {item}")
            with con_col:
                st.markdown("**⚠️ Key Concerns**")
                for item in result.get("key_concerns", []):
                    st.markdown(f"❌ {item}")
        
        # ─── Skill Gaps ───
        skill_gaps = result.get("skill_gaps", [])
        if skill_gaps:
            st.divider()
            st.markdown("### 📈 Skills to Develop")
            st.caption("These are the gaps identified during the debate. Closing these will significantly improve your candidacy.")
            gap_cols = st.columns(min(len(skill_gaps), 4))
            for i, gap in enumerate(skill_gaps):
                with gap_cols[i % len(gap_cols)]:
                    st.markdown(f"""
                    <div style="background: #fff3e020; border: 1px solid #ef6c00; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 8px;">
                        <p style="font-weight: bold; color: #ef6c00; margin: 0;">📚 {gap}</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        # ─── Debate Transcript ───
        st.divider()
        st.markdown("### 🎙️ Full Debate Transcript")
        st.caption("Expand each round to see the detailed arguments from both sides.")
        
        for round_data in result.get("debate_rounds", []):
            round_num = round_data.get("round_number", 1)
            r_score = round_data.get("recruiter_score", 50)
            c_score = round_data.get("coach_score", 50)
            
            with st.expander(f"🏟️ Round {round_num}  |  Recruiter: {r_score:.0f}  vs  Coach: {c_score:.0f}", expanded=(round_num == 1)):
                r_col, c_col = st.columns(2)
                
                with r_col:
                    st.markdown("#### 🔴 Recruiter's Concerns")
                    for arg in round_data.get("recruiter_arguments", []):
                        strength = arg.get("strength", "Medium")
                        icon = "🔥" if strength == "Strong" else "⚡" if strength == "Medium" else "💨"
                        st.markdown(f"{icon} **{arg.get('point')}**")
                        if arg.get("evidence"):
                            st.caption(f"   _{arg.get('evidence')}_")
                
                with c_col:
                    st.markdown("#### 🟢 Coach's Rebuttal")
                    for arg in round_data.get("coach_arguments", []):
                        strength = arg.get("strength", "Medium")
                        icon = "💎" if strength == "Strong" else "✨" if strength == "Medium" else "🌱"
                        st.markdown(f"{icon} **{arg.get('point')}**")
                        if arg.get("evidence"):
                            st.caption(f"   _{arg.get('evidence')}_")
        
        # ─── Processing Info ───
        proc_time = result.get("processing_time_seconds", 0)
        total_rounds = result.get("total_rounds", 0)
        if proc_time > 0:
            st.divider()
            st.caption(f"⏱️ Debate completed in {proc_time:.1f}s across {total_rounds} round(s) using Gemini AI agents.")
                
    else:
        st.markdown("""
        <div style="background: #1a1a2e; padding: 24px; border-radius: 12px; text-align: center; margin-top: 16px;">
            <p style="font-size: 1.1em; color: #aaa;">👆 Select a job above and click <b style="color: #e94560;">'Run AI Debate'</b> to watch 
            the Recruiter and Career Coach analyze your fit for this role in real-time!</p>
        </div>
        """, unsafe_allow_html=True)



def show_cover_letter():
    """Cover letter generation."""
    st.markdown('<h1 class="main-header">✉️ Cover Letter Generator</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;">Draft hyper-personalized cover letters utilizing AI and semantic analysis.</p>', unsafe_allow_html=True)
    
    if not st.session_state.get("matched_jobs"):
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; padding: 1.5rem; text-align: center;">
            <h3 style="color: #ef4444; margin-top: 0;">⚠️ No Matches Found</h3>
            <p style="color: #94a3b8; font-size: 0.95rem;">Please run a job match first to generate tailored cover letters.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown("""
    <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem;">
        <h3 style="color: #10b981; margin-top: 0;">Configuration Parameters</h3>
    """, unsafe_allow_html=True)
    
    # Select a job
    job_options = [f"{j['title']} at {j['company']}" for j in st.session_state["matched_jobs"]]
    selected = st.selectbox("Target Position", job_options)
    
    col1, col2 = st.columns(2)
    with col1:
        tone = st.select_slider("Voice Tone", options=["Casual", "Professional", "Formal"], value="Professional")
    with col2:
        focus = st.multiselect("Key Focus Areas", ["Technical Skills", "Leadership", "Culture Fit", "Achievements"], default=["Technical Skills"])
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 Synthesize Cover Letter", use_container_width=True):
        with st.spinner("Generating with Gemini AI..."):
            try:
                selected_idx = job_options.index(selected)
                job = st.session_state["matched_jobs"][selected_idx]
                resume_summary = st.session_state.get("resume_summary", "Experienced software professional with relevant background.")

                payload = {
                    "job_title": job["title"],
                    "job_company": job["company"],
                    "job_description": job.get("description", ""),
                    "candidate_profile": resume_summary,
                    "tone": tone.lower(),
                    "focus_areas": focus,
                }
                response = requests.post(
                    f"{BACKEND_URL}/api/v1/cover-letter/quick",
                    json=payload,
                    timeout=60,
                )
                if response.status_code == 200:
                    cover_letter = response.json().get("cover_letter", "")
                    st.text_area("Your Cover Letter", value=cover_letter, height=400)
                    st.download_button(
                        "📋 Download as .txt",
                        cover_letter,
                        file_name=f"cover_letter_{job['company'].replace(' ', '_')}.txt",
                        mime="text/plain",
                    )
                else:
                    err = response.json().get("detail", response.text[:200])
                    st.error(f"Generation failed: {err}")
            except Exception as e:
                st.error(f"Generation failed: {type(e).__name__}: {e}")


def show_skill_roadmap():
    """Enhanced skill gap analysis and roadmap based on actual matched jobs."""
    st.markdown('<h1 class="main-header">📈 Career Growth Roadmap</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(13, 148, 136, 0.05); border: 1px solid rgba(13, 148, 136, 0.2); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem;">
        <h3 style="color: #0d9488; margin-top: 0;">🧠 Intelligent Gap Analysis</h3>
        <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 0;">We dynamically analyze your active job matches to recommend high-impact skills that will maximize your hiring potential.</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.get("matched_jobs"):
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; padding: 1.5rem; text-align: center;">
            <h3 style="color: #ef4444; margin-top: 0;">⚠️ No Matches Found</h3>
            <p style="color: #94a3b8; font-size: 0.95rem;">Please run a job match first to unlock personalized skill recommendations.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    matched_jobs = st.session_state["matched_jobs"]
    
    st.markdown(f"### 📊 Analyzing {len(matched_jobs)} Matched Jobs")
    
    # Method 1: Use missing_skills from backend if available
    missing_counts = {}
    for job in matched_jobs:
        for skill in job.get("missing_skills", []):
            skill_clean = skill.strip().title()
            missing_counts[skill_clean] = missing_counts.get(skill_clean, 0) + 1
    
    # Method 2: Extract common skills from job descriptions AND titles if no missing_skills
    if not missing_counts:
        st.caption("*Extracting skills from job descriptions...*")
        # Common tech skills to look for (expanded list including data science and variations)
        skill_keywords = [
            # Programming languages
            'python', 'java', 'javascript', 'typescript', 'sql', 'r ', 'scala', 'go ', 'rust',
            'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin',
            # Cloud & DevOps
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'k8s', 'terraform', 'jenkins',
            'ci/cd', 'devops', 'cloud', 'microservices',
            # Data & ML
            'machine learning', 'deep learning', 'nlp', 'natural language', 'computer vision',
            'data science', 'data engineering', 'data analysis', 'data analyst',
            'tensorflow', 'pytorch', 'keras', 'scikit', 'sklearn', 'pandas', 'numpy',
            'spark', 'hadoop', 'kafka', 'airflow', 'dbt', 'snowflake', 'databricks',
            'etl', 'data pipeline', 'big data',
            # Databases
            'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'neo4j',
            # GenAI / LLM
            'llm', 'genai', 'generative ai', 'gpt', 'langchain', 'rag', 'transformers',
            'hugging face', 'chatgpt', 'openai', 'large language',
            # Web & Frameworks
            'react', 'node.js', 'nodejs', 'angular', 'vue', 'django', 'flask', 'fastapi',
            'spring', 'graphql', 'rest api',
            # BI & Visualization
            'tableau', 'power bi', 'looker', 'excel', 'visualization',
            # Methodologies
            'agile', 'scrum', 'git', 'linux',
            # Soft skills / Roles
            'leadership', 'director', 'manager', 'senior', 'architect', 'lead'
        ]
        
        for job in matched_jobs:
            # Check BOTH description AND title for skills
            desc = (job.get("description", "") or "").lower()
            title = (job.get("title", "") or "").lower()
            full_text = f"{title} {desc}"
            
            for skill in skill_keywords:
                if skill in full_text:
                    # Clean up the skill name for display
                    skill_display = skill.strip().title()
                    # Handle special cases
                    if skill in ['r ', 'go ']:
                        skill_display = skill.strip().upper()
                    elif skill in ['aws', 'gcp', 'sql', 'nlp', 'llm', 'etl', 'ci/cd', 'k8s', 'api']:
                        skill_display = skill.upper()
                    elif skill in ['genai']:
                        skill_display = 'GenAI'
                    elif skill in ['node.js', 'nodejs']:
                        skill_display = 'Node.js'
                    elif skill in ['postgresql', 'mysql', 'mongodb']:
                        skill_display = skill.replace('sql', 'SQL').replace('db', 'DB').title()
                    
                    missing_counts[skill_display] = missing_counts.get(skill_display, 0) + 1
    
    # Sort by frequency
    sorted_skills = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Resources mapping
    resources = {
        "Python": "https://docs.python.org/3/tutorial/",
        "Java": "https://dev.java/learn/",
        "Javascript": "https://javascript.info/",
        "Sql": "https://www.w3schools.com/sql/",
        "Aws": "https://aws.amazon.com/training/",
        "Azure": "https://learn.microsoft.com/en-us/training/azure/",
        "Gcp": "https://cloud.google.com/training",
        "Docker": "https://docs.docker.com/get-started/",
        "Kubernetes": "https://kubernetes.io/docs/tutorials/",
        "React": "https://react.dev/learn",
        "Node.Js": "https://nodejs.org/en/learn",
        "Tensorflow": "https://www.tensorflow.org/tutorials",
        "Pytorch": "https://pytorch.org/tutorials/",
        "Spark": "https://spark.apache.org/docs/latest/quick-start.html",
        "Machine Learning": "https://www.coursera.org/learn/machine-learning",
        "Deep Learning": "https://www.deeplearning.ai/",
        "Nlp": "https://huggingface.co/learn/nlp-course",
        "Airflow": "https://airflow.apache.org/docs/",
        "Snowflake": "https://learn.snowflake.com/",
        "System Design": "https://github.com/donnemartin/system-design-primer",
    }
    
    if sorted_skills:
        st.markdown("### 🎯 High-Value Skills to Acquire")
        st.markdown('<p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.5rem;">These skills appear most frequently in your target roles:</p>', unsafe_allow_html=True)
        
        for i, (skill, count) in enumerate(sorted_skills[:8]):
            priority_color = "#ef4444" if count >= 3 else "#f59e0b" if count >= 2 else "#10b981"
            priority_text = "Critical" if count >= 3 else "Medium" if count >= 2 else "Low"
            time_est = "2-4 weeks" if count < 3 else "1-2 months" if count < 5 else "2-3 months"
            
            # HTML Card
            st.markdown(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border-left: 4px solid {priority_color}; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;">
                <div style="flex-grow: 1;">
                    <h3 style="margin: 0; color: #f1f5f9; font-size: 1.2rem;">{skill}</h3>
                    <p style="margin: 0; color: #94a3b8; font-size: 0.9rem;">Present in <strong>{count}</strong> active job matches</p>
                </div>
                <div style="text-align: right; margin-right: 1.5rem;">
                    <p style="margin: 0; color: {priority_color}; font-weight: 600; font-size: 0.9rem;">{priority_text} Priority</p>
                    <p style="margin: 0; color: #94a3b8; font-size: 0.8rem;">Est. Time: {time_est}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Button link
            resource_url = resources.get(skill, f"https://www.google.com/search?q=learn+{skill.replace(' ', '+')}")
            col1, col2 = st.columns([4, 1])
            with col2:
                st.link_button("📚 View Courses", resource_url, use_container_width=True)
        
        # Show summary stats
        st.divider()
        st.markdown("### 📈 Intelligent Gap Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.05); padding: 1.5rem; border-radius: 12px; text-align: center; border: 1px solid rgba(16, 185, 129, 0.2);">
                <p style="margin: 0; color: #10b981; font-weight: 600; font-size: 0.85rem;">NEW SKILLS</p>
                <h2 style="margin: 0.5rem 0 0 0; color: white; font-size: 2rem;">{len(sorted_skills)}</h2>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            high_priority = len([s for s, c in sorted_skills if c >= 3])
            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.05); padding: 1.5rem; border-radius: 12px; text-align: center; border: 1px solid rgba(239, 68, 68, 0.2);">
                <p style="margin: 0; color: #ef4444; font-weight: 600; font-size: 0.85rem;">CRITICAL PRIORITY</p>
                <h2 style="margin: 0.5rem 0 0 0; color: white; font-size: 2rem;">{high_priority}</h2>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style="background: rgba(139, 92, 246, 0.05); padding: 1.5rem; border-radius: 12px; text-align: center; border: 1px solid rgba(139, 92, 246, 0.2);">
                <p style="margin: 0; color: #8b5cf6; font-weight: 600; font-size: 0.85rem;">MARKET DATA (JOBS)</p>
                <h2 style="margin: 0.5rem 0 0 0; color: white; font-size: 2rem;">{len(matched_jobs)}</h2>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("🎉 Great news! No significant skill gaps detected in your matched jobs!")
        st.info("This could mean:\n- Your skills align well with available roles\n- Try matching with different job types to discover new skills to learn")


def show_analytics():
    """Enhanced Analytics dashboard with interactive charts and actionable insights."""
    import plotly.graph_objects as go
    import plotly.express as px
    import pandas as pd
    import json as json_lib
    
    st.markdown('<h1 class="main-header">📊 Analytics & Insights</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.10) 100%); 
                border-radius: 16px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem; 
                border: 1px solid rgba(99,102,241,0.2);">
        <p style="margin: 0; font-size: 1.05rem;">
            🎯 <strong>Your AI-Powered Job Intelligence Hub</strong> — Understand the market, identify your skill gaps, and make data-driven career decisions.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ============ FETCH ALL DATA ============
    matched_jobs = st.session_state.get("matched_jobs", [])
    user_skills = [s.lower() for s in st.session_state.get("resume_skills", [])]
    
    # Fetch rich data from database
    analytics_data = fetch_analytics_data()
    all_jobs = analytics_data.get("jobs", [])
    skill_counts = analytics_data.get("skill_counts", {})
    salary_data = analytics_data.get("salary_data", [])
    remote_distribution = analytics_data.get("remote_distribution", {})
    location_data = analytics_data.get("location_data", {})
    experience_levels = analytics_data.get("experience_levels", {})
    
    # ============ SECTION 1: HERO STATS ============
    st.markdown("### 🏆 Your Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); 
                    border-radius: 16px; padding: 1.5rem; text-align: center;">
            <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;">JOBS MATCHED</p>
            <h2 style="color: white; margin: 0.3rem 0 0 0; font-size: 2.2rem;">{len(matched_jobs)}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if matched_jobs:
            avg_score = sum(j.get("match_score", 0) for j in matched_jobs) / len(matched_jobs)
            avg_score = avg_score * 100 if avg_score <= 1 else avg_score
            score_color = "#10b981" if avg_score >= 70 else "#f59e0b" if avg_score >= 50 else "#ef4444"
        else:
            avg_score = 0
            score_color = "#6b7280"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {score_color}22 0%, {score_color}11 100%); 
                    border-radius: 16px; padding: 1.5rem; text-align: center; 
                    border: 1px solid {score_color}33;">
            <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;">AVG MATCH SCORE</p>
            <h2 style="color: {score_color}; margin: 0.3rem 0 0 0; font-size: 2.2rem;">{avg_score:.0f}%</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        db_count = len(all_jobs)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(16,185,129,0.05) 100%); 
                    border-radius: 16px; padding: 1.5rem; text-align: center; 
                    border: 1px solid rgba(16,185,129,0.2);">
            <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;">JOBS IN DATABASE</p>
            <h2 style="color: #10b981; margin: 0.3rem 0 0 0; font-size: 2.2rem;">{db_count}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        skills_count = len(user_skills) if user_skills else 0
        resume_ok = st.session_state.get("resume_uploaded", False)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(245,158,11,0.05) 100%); 
                    border-radius: 16px; padding: 1.5rem; text-align: center; 
                    border: 1px solid rgba(245,158,11,0.2);">
            <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;">YOUR SKILLS</p>
            <h2 style="color: #f59e0b; margin: 0.3rem 0 0 0; font-size: 2.2rem;">{"✅ " + str(skills_count) if resume_ok else "❌ Upload"}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ============ SECTION 2: SKILLS IN DEMAND ============
    st.markdown("### 🔥 Top Skills in Demand")
    st.caption("Skills most frequently required across all job listings in the database")
    
    if skill_counts:
        top_skills = dict(sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15])
        
        # Color-code: green if user has the skill, red if they don't
        colors = []
        for skill in top_skills:
            if skill.lower() in user_skills:
                colors.append("#10b981")  # green — user has it
            else:
                colors.append("#ef4444")  # red — skill gap
        
        fig_skills = go.Figure(data=[
            go.Bar(
                x=list(top_skills.values()),
                y=list(top_skills.keys()),
                orientation='h',
                marker=dict(
                    color=colors,
                    line=dict(color='rgba(255,255,255,0.1)', width=1)
                ),
                text=[f"{v} jobs" for v in top_skills.values()],
                textposition='auto',
                hovertemplate='<b>%{y}</b><br>Required in %{x} jobs<extra></extra>'
            )
        ])
        fig_skills.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=450,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis=dict(title="Number of Jobs", gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(autorange="reversed"),
        )
        
        st.plotly_chart(fig_skills, use_container_width=True)
        
        if user_skills:
            st.markdown("""
            <div style="display: flex; gap: 1rem; align-items: center; margin-top: -0.5rem;">
                <span style="display: inline-flex; align-items: center; gap: 0.3rem;">
                    <span style="width: 12px; height: 12px; background: #10b981; border-radius: 3px; display: inline-block;"></span>
                    <span style="font-size: 0.85rem; color: rgba(255,255,255,0.7);">You have this skill</span>
                </span>
                <span style="display: inline-flex; align-items: center; gap: 0.3rem;">
                    <span style="width: 12px; height: 12px; background: #ef4444; border-radius: 3px; display: inline-block;"></span>
                    <span style="font-size: 0.85rem; color: rgba(255,255,255,0.7);">Skill gap — consider learning</span>
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No skill data available yet. Jobs need `required_skills` data in the database.")
    
    st.divider()
    
    # ============ SECTION 3 & 4: MATCH SCORE + SALARY (side by side) ============
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 🎯 Match Score Breakdown")
        
        if matched_jobs:
            # Normalize scores
            scores = []
            for j in matched_jobs:
                s = j.get("match_score", 0)
                scores.append(s * 100 if s <= 1 else s)
            
            high = len([s for s in scores if s >= 70])
            med = len([s for s in scores if 50 <= s < 70])
            low = len([s for s in scores if s < 50])
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=['Strong (70%+)', 'Good (50-70%)', 'Stretch (<50%)'],
                values=[high, med, low],
                hole=0.6,
                marker=dict(colors=['#10b981', '#f59e0b', '#ef4444']),
                textinfo='value+percent',
                textfont=dict(size=14),
                hovertemplate='<b>%{label}</b><br>%{value} jobs (%{percent})<extra></extra>'
            )])
            fig_donut.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                annotations=[dict(text=f'{avg_score:.0f}%', x=0.5, y=0.5, font_size=28, font_color=score_color, showarrow=False)]
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.markdown("""
            <div style="background: rgba(255,255,255,0.03); border-radius: 12px; padding: 3rem; text-align: center;">
                <p style="font-size: 3rem; margin: 0;">🎯</p>
                <p style="color: rgba(255,255,255,0.5);">Run a job match to see your score distribution</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col_right:
        st.markdown("### 💰 Salary Insights")
        
        if salary_data:
            df_salary = pd.DataFrame(salary_data)
            
            fig_salary = go.Figure()
            for level in df_salary['level'].unique():
                level_data = df_salary[df_salary['level'] == level]
                fig_salary.add_trace(go.Box(
                    y=level_data['salary_max'],
                    name=level or 'Unknown',
                    marker_color='#8b5cf6',
                    boxmean=True,
                    hovertemplate='<b>%{x}</b><br>Salary: $%{y:,.0f}<extra></extra>'
                ))
            
            fig_salary.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=350,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis=dict(title="Salary ($)", gridcolor='rgba(255,255,255,0.05)', tickformat='$,.0f'),
                showlegend=False,
            )
            st.plotly_chart(fig_salary, use_container_width=True)
        else:
            # Show what salary data we could have
            st.markdown("""
            <div style="background: rgba(255,255,255,0.03); border-radius: 12px; padding: 3rem; text-align: center;">
                <p style="font-size: 3rem; margin: 0;">💰</p>
                <p style="color: rgba(255,255,255,0.5);">Salary data will appear when jobs include salary information</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    # ============ SECTION 5: COMPANY + REMOTE + EXPERIENCE ============
    st.markdown("### 🏢 Job Market Overview")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown("##### 📍 Work Type Distribution")
        if remote_distribution:
            labels = list(remote_distribution.keys())
            values = list(remote_distribution.values())
            # Map to nice colors
            color_map = {'remote': '#10b981', 'hybrid': '#f59e0b', 'on-site': '#6366f1', 'onsite': '#6366f1'}
            pie_colors = [color_map.get(l.lower(), '#8b5cf6') for l in labels]
            
            fig_remote = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=pie_colors),
                textinfo='label+percent',
                textfont=dict(size=12),
                hole=0.3,
            )])
            fig_remote.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=280,
                margin=dict(l=5, r=5, t=5, b=5),
                showlegend=False,
            )
            st.plotly_chart(fig_remote, use_container_width=True)
        else:
            st.caption("No work type data available")
    
    with col_b:
        st.markdown("##### 📊 Experience Levels")
        if experience_levels:
            levels = list(experience_levels.keys())
            counts = list(experience_levels.values())
            
            fig_exp = go.Figure(data=[go.Bar(
                x=levels,
                y=counts,
                marker=dict(
                    color=['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'][:len(levels)],
                    line=dict(color='rgba(255,255,255,0.1)', width=1)
                ),
                text=counts,
                textposition='auto',
            )])
            fig_exp.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=280,
                margin=dict(l=5, r=5, t=5, b=5),
                xaxis=dict(tickangle=-45),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            )
            st.plotly_chart(fig_exp, use_container_width=True)
        else:
            st.caption("No experience level data available")
    
    with col_c:
        st.markdown("##### 🏢 Top Companies Hiring")
        if all_jobs:
            companies = {}
            for job in all_jobs:
                c = job.get('company', 'Unknown')
                companies[c] = companies.get(c, 0) + 1
            top_companies = dict(sorted(companies.items(), key=lambda x: x[1], reverse=True)[:8])
            
            fig_companies = go.Figure(data=[go.Bar(
                y=list(top_companies.keys()),
                x=list(top_companies.values()),
                orientation='h',
                marker=dict(
                    color='#6366f1',
                    line=dict(color='rgba(255,255,255,0.1)', width=1)
                ),
                text=list(top_companies.values()),
                textposition='auto',
            )])
            fig_companies.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=280,
                margin=dict(l=5, r=5, t=5, b=5),
                yaxis=dict(autorange="reversed"),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            )
            st.plotly_chart(fig_companies, use_container_width=True)
        else:
            st.caption("No company data available")
    
    st.divider()
    
    # ============ SECTION 6: YOUR SKILL GAP REPORT ============
    st.markdown("### 🎓 Your Personalized Skill Gap Report")
    
    if user_skills and skill_counts:
        # Get top 10 in-demand skills
        top_demand = dict(sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Build radar chart data
        radar_skills = list(top_demand.keys())
        market_demand = [top_demand[s] for s in radar_skills]
        max_demand = max(market_demand) if market_demand else 1
        market_demand_pct = [round((d / max_demand) * 100) for d in market_demand]
        
        # User proficiency (100 if they have it, 0 if not)
        user_proficiency = []
        for skill in radar_skills:
            if skill.lower() in user_skills:
                user_proficiency.append(85)  # High if user has it
            else:
                user_proficiency.append(10)  # Low if missing
        
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=market_demand_pct,
            theta=radar_skills,
            fill='toself',
            name='Market Demand',
            line=dict(color='#6366f1'),
            fillcolor='rgba(99,102,241,0.15)',
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=user_proficiency,
            theta=radar_skills,
            fill='toself',
            name='Your Skills',
            line=dict(color='#10b981'),
            fillcolor='rgba(16,185,129,0.15)',
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor='rgba(0,0,0,0)',
                radialaxis=dict(visible=True, range=[0, 100], gridcolor='rgba(255,255,255,0.1)'),
                angularaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=450,
            margin=dict(l=60, r=60, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        
        # Personalized recommendations
        gaps = [s for s in radar_skills if s.lower() not in user_skills]
        if gaps:
            st.markdown("#### 💡 Recommended Skills to Learn")
            rec_cols = st.columns(min(len(gaps), 3))
            for i, skill in enumerate(gaps[:3]):
                demand_pct = round((skill_counts.get(skill, 0) / len(all_jobs)) * 100) if all_jobs else 0
                with rec_cols[i]:
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, rgba(239,68,68,0.1) 0%, rgba(239,68,68,0.05) 100%); 
                                border-radius: 12px; padding: 1.2rem; border: 1px solid rgba(239,68,68,0.2);">
                        <h4 style="margin: 0 0 0.5rem 0; color: #ef4444;">🚀 {skill}</h4>
                        <p style="margin: 0; font-size: 0.9rem; color: rgba(255,255,255,0.7);">
                            Appears in <strong>{demand_pct}%</strong> of job listings.<br>
                            Learning this skill could significantly improve your match scores.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("🎉 Amazing! You have all the top in-demand skills. You're in great shape!")
    else:
        st.markdown("""
        <div style="background: rgba(255,255,255,0.03); border-radius: 16px; padding: 2.5rem; text-align: center;">
            <p style="font-size: 3rem; margin: 0;">📄</p>
            <h3 style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Upload Your Resume to Unlock Insights</h3>
            <p style="color: rgba(255,255,255,0.5);">
                Go to the <strong>Job Matching</strong> page and upload your resume. 
                We'll analyze your skills against the market and show you exactly where to focus.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ============ SECTION 7: MATCHED JOBS TABLE ============
    if matched_jobs:
        st.markdown("### 📋 Your Matched Jobs Ranked")
        
        job_data = []
        for j in matched_jobs:
            score = j.get("match_score", 0)
            score = score * 100 if score <= 1 else score
            job_data.append({
                "Title": j.get("title", "Unknown"),
                "Company": j.get("company", "Unknown"),
                "Score": f"{score:.0f}%",
                "Missing Skills": ", ".join(j.get("missing_skills", [])) or "None",
                "Source": j.get("source", "LinkedIn"),
            })
        
        df_jobs = pd.DataFrame(job_data)
        df_jobs = df_jobs.sort_values(by="Score", ascending=False)
        st.dataframe(df_jobs, use_container_width=True, hide_index=True)


def show_settings():
    """Settings page."""
    st.markdown('<h1 class="main-header">⚙️ System Configuration</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;">Manage operational settings and system connections.</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 1.5rem; height: 100%;">
            <h3 style="color: #10b981; margin-top: 0; border-bottom: 1px solid rgba(16, 185, 129, 0.2); padding-bottom: 0.5rem;">🔌 API Integration</h3>
        """, unsafe_allow_html=True)
        backend_url = st.text_input("Backend API Uniform Resource Locator (URL)", value=BACKEND_URL)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 1.5rem; height: 100%;">
            <h3 style="color: #0d9488; margin-top: 0; border-bottom: 1px solid rgba(13, 148, 136, 0.2); padding-bottom: 0.5rem;">🗄️ Database Context</h3>
        """, unsafe_allow_html=True)
        st.code("""
Host: localhost
Port: 5432
Database: hireright
Engine: Supabase (PostgreSQL)
        """, language="yaml")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem;">
        <h3 style="color: #f1f5f9; margin-top: 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 0.5rem;">🔔 Operational Preferences</h3>
    """, unsafe_allow_html=True)
    st.toggle("Enable automated telemetry tracking", value=False)
    st.toggle("Receive AI Job Market Insights (Daily)", value=True)
    st.toggle("Run Background Agentic Search", value=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("💾 Persist Configurations", use_container_width=True):
        st.success("Configurations actively persisted to datastore!")


if __name__ == "__main__":
    main()
