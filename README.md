# HireRight AI

**HireRight AI** flips the traditional applicant tracking system (ATS) on its head. Instead of blindly matching keywords, HireRight leverages **Google Gemini Vector Embeddings** to semantically understand a candidate's resume, and utilizes an autonomous **LangGraph multi-agent committee** to debate the candidate's fit for a role in real-time. Built for engineers and tech recruiters alike, this system showcases modern backend engineering, Agentic AI, vector databases (`pgvector`), and the emerging **Model Context Protocol (MCP)** for live web scraping.

```text
┌─────────────────────────────────────────────────────────────────┐
│                        HIRE RIGHT AI                            │
│  ┌─────────────┐   ┌────────────────┐   ┌────────────────────┐  │
│  │   UI (Web)  │   │   LangGraph    │   │ Supabase Vector DB │  │
│  │ (Streamlit) │◄──┤(Hiring Agents) │◄──┤  (pgvector + SQL)  │  │
│  └─────────────┘   └───────┬────────┘   └─────────┬──────────┘  │
└────────────────────────────┼──────────────────────┼─────────────┘
                             │                      │
                             ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│               EXTERNAL INTEGRATIONS (MCP SERVERS)               │
│  • Job Market Scraper (Tavily)  • GitHub Context Extractor      │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### Table Summary

| Table | Component | Description |
|-------|---------|-------------|
| `jobs` | Core Data | Job listings, metadata, and 768-dimensional vector embeddings |

### Key Design Decisions

1. **Semantic Search with `pgvector`**: Rely on cutting-edge cosine similarity querying (`<=>`) inside a customized Supabase RPC function instead of slow, rigid `LIKE` string comparisons.
2. **Dynamic AI Extraction**: The scraping pipeline intelligently extracts and parses semi-structured data points (like remote types, salary limits, and experience levels) using regex over raw HTML content parsed from the MCP server.
3. **Stateless Frontend**: The Streamlit application handles zero local storage, retrieving all analytics, skill data, and real-time semantic job matches dynamically via FastAPI network requests.

## Quick Start

### Prerequisites

- Python 3.11+
- API Keys: `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `GITHUB_TOKEN`
- Supabase Project URL and Service Key

### Installation

```bash
# Clone the repository
git clone https://github.com/ayushvarma7/HireRight-AI.git
cd HireRight-AI

# Setup Virtual Environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### Database Setup

1. Configure your `.env` connection variables at the root of the project.
2. Create schema in Supabase by running `supabase_schema.sql` via the SQL Editor.
3. Seed the job data using the web scraping script:

```bash
cd backend
../venv/bin/python ../scripts/scrape_live_jobs.py --limit 10
```

### Starting the Application

You must run the services concurrently in separate terminals:

```bash
# Terminal 1: Job Market MCP Server (Tavily Scraper)
cd mcp_servers/job-market
../../venv/bin/python server.py

# Terminal 2: GitHub Context MCP Server
cd mcp_servers/github-context
../../venv/bin/python server.py

# Terminal 3: FastAPI Backend
cd backend
../venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --env-file ../.env

# Terminal 4: Streamlit Frontend HTML/CSS Engine
./venv/bin/streamlit run frontend/app.py --server.port 8501
```

## Project Structure

```text
HireRight-AI/
│
├── README.md                 # This file
├── pyproject.toml            # Python dependencies package
├── supabase_schema.sql       # Database schema creation scripts
│
├── backend/                  # Core FastAPI & Agent Services
│   ├── app/
│   │   ├── agents/           # LangGraph nodes (Judge, Coach, Recruiter)
│   │   ├── api/              # RESTful endpoints (/match, /jobs)
│   │   └── services/         # Embedding & Supabase vectors
│   └── scripts/              # Job Web Scraper Pipeline 
│
├── frontend/                 # Streamlit UI & Visualizations
│   ├── .streamlit/           # Custom App Theme Configuration
│   ├── utils/                # API communication clients
│   └── app.py                # Main Application Entrypoint
│
└── mcp_servers/              # Extensible MCP protocol wrappers
    ├── github-context/       # Live GitHub repository analysis
    └── job-market/           # Tavily web-scraping intelligence
```

## Sample Analytics

### Application Metrics
- **Automated Skill Detection**: Dynamically scores matching rates on priority tech skills.
- **Match Score Generation**: Calculates real-time 0-100% semantic matching on submitted resumes against live market requisitions. 

### Key Fields Stored per Job
| Metric | Description |
|--------|-------|
| Agent Match Score | Final unified verdict percentage out of 100% via Agent Debate |
| Salary Limit | Maximum extracted salary data via raw web source |
| Commute Policy | Hybrid, Remote, or On-site classification |
| Experience Bounds | Target seniority inferred from job descriptions |

## Technical Highlights


### Stored Procedures / RPC

```sql
-- match_jobs: Vector similarity match query 
create or replace function match_jobs (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  title text,
  company text,
  location text,
  description text,
  source_platform text,
  remote_type text,
  job_type text,
  experience_level text,
  salary_max int,
  similarity float
)
```

### Data Quality Handling
- **Real-Time Extraction**: Leverages Google Gemini embeddings to compress large multi-page job descriptions into 768 semantic tokens.

## Testing

The web scraper tracks and prevents duplicate insertion by checking URL footprints and managing SQL insertion limits on scraping.

## Technologies Used

- **Database**: Supabase (PostgreSQL with `pgvector`)
- **Backend API**: Python 3.11, FastAPI
- **AI Core**: LangGraph, LangChain, Google Gemini
- **Frontend Dashboard**: Streamlit, Plotly
- **Data Integrations**: Tavily Search API, GitHub API via Context MCP

## Author

**Ayush Varma**
- [LinkedIn](https://www.linkedin.com/in/ayushvarma7/)
- [GitHub](https://github.com/ayushvarma7)
