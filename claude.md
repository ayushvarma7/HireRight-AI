# HireRight AI | Unified Staff-Level Project Guide

**HireRight AI** is an advanced, AI-native career intelligence ecosystem that uses **LangGraph multi-agent orchestration** and **pgvector semantic search** to revolutionize role-candidate matching.

---

## 🏗️ 1. Project Overview & Architecture
### The Problem:
Traditional Applicant Tracking Systems (ATS) rely on rigid keyword matching, leading to high false-rejection rates.
### The Solution:
HireRight leverages **Google Gemini Vector Embeddings** to understand conceptual fit and uses a **Committee of AI Agents** to debate a candidate's suitability.

### 🔄 Technical Flow:
`Frontend (Streamlit)` $\rightarrow$ `Back-end API (FastAPI)` $\rightarrow$ `Vector Search (Supabase / pgvector)` $\rightarrow$ `Agent Evaluation (LangGraph Committee)` $\rightarrow$ `Result Visualization`.

---

## 🤖 2. The AI "Brain" (LangGraph Logic)
HireRight implementation utilizes a **Stateful Multi-Agent Workflow** to simulate a real-world hiring committee.

### The Agentic Committee:
1. **Recruiter Node**: Plays the "Devil's Advocate," identifying skill gaps and experience red flags.
2. **Coach Node**: Focuses on transferring skills and unique value propositions.
3. **Judge Node**: Weighs inputs from the debate, identifies conflicts, and calculates the final match score.
4. **Conditional Logic**: If the Judge detects high uncertainty ($>20\%$ score delta), the graph triggers a `re-debate` cycle before concluding.

---

## 🛠️ 3. Development Setup & Commands
### Prerequisites:
- Python 3.11+, Supabase (`pgvector` enabled).
- Keys: `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `GITHUB_TOKEN`.

### Key Commands:
- **Run Backend**: `cd backend && uvicorn app.main:app --reload`
- **Run Frontend**: `streamlit run frontend/app.py`
- **Scrape Market**: `python scripts/scrape_live_jobs.py --limit 10`
- **Initialize DB**: Apply [supabase_schema.sql](cci:7://file:///Users/ayush/Downloads/Fall2025/Personal/jobzilla-ai/supabase_schema.sql:0:0-0:0) to your Supabase SQL Editor.

---

## 🧭 4. Engineering Standards for AI Agents
### Naming & Structure:
- **Files/Functions**: Snake case (`vector_search.py`).
- **Nodes**: Suffix with `_node` in `app/agents/nodes/`.
- **Prompts**: Externalized into `app/agents/prompts/`. **DO NOT hardcode prompts in nodes.**

### The "Async Task" Protocol:
The `/match` endpoint is historically slow (~30s). All AI-driven matches must follow an async pattern:
1. `POST /api/v1/match` returns a `task_id`.
2. `GET /api/v1/status/{task_id}` for polling.

### Data Integrity Rules:
- **No Direct DB Calls from UI**: All data retrieval must pass through the Backend API for caching and validation.
- **Vector Search Threshold**: Use a minimum cosine similarity threshold of **0.7** to maintain precision.
- **Structured Output**: Use `with_structured_output(Schema)` for LLM chains to ensure the frontend receives valid JSON metrics.

---

## 📂 5. Repository Topology
- `/backend/app/agents`: Graph orchestration, nodes, prompts, and `state.py`.
- `/backend/app/api`: FastAPI v1 routes.
- `/backend/app/services`: Atomic shared services (Embeddings, VectorDB, MCP Client).
- `/frontend`: Streamlit views and [api_client.py](cci:7://file:///Users/ayush/Downloads/Fall2025/Personal/jobzilla-ai/frontend/utils/api_client.py:0:0-0:0).
- `/mcp_servers`: Decoupled tool-using servers (Scrapers, GitHub APIs).
- `/scripts`: Data maintenance and scraping pipelines.

---

## ⚠️ 6. Constraints & Warnings
- **Vector Dimension**: Locked at **768** (Native Gemini Embedding size).
- **Cost Optimization**: Nodes use `gpt-4o-mini` by default. Only the `Judge` should use `gpt-4o` for deep reasoning.
- **State Bloat**: Avoid passing raw file bytes into the `AgentState`. Parse to specialized summaries in the first node.

---

## 🚀 7. Roadmap & Priority Refactors
1. **Sync-to-Async**: Migration of `/match` from a blocking call to a task-polling system.
2. **Hybrid Search**: Implementation of Reciprocal Rank Fusion (RRF) combining vector search with PostgreSQL Full-Text Search.
3. **Observability**: Integration of **LangSmith** for tracing multi-round agent debates.
