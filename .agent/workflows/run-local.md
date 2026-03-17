---
description: Run HireRight AI locally without Docker
---

# Run HireRight AI Locally

This workflow helps you run the entire HireRight AI system (Backend, Frontend, and MCP Servers) using a Python virtual environment.

## Prerequisites

1.  **Python 3.11+** installed.
2.  **PostgreSQL** and **Redis** installed and running on your system (defaults to localhost).
3.  **API Keys** for OpenAI, Pinecone, and Tavily (optional but recommended).

## Steps

### 1. Setup Virtual Environment
// turbo
```bash
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt
./venv/bin/pip install -r frontend/requirements.txt
./venv/bin/pip install -r mcp_servers/github-context/requirements.txt
./venv/bin/pip install -r mcp_servers/job-market/requirements.txt
```

### 2. Configure Environment
Edit the `.env` file in the root directory and add your API keys.

### 3. Run Services

You will need to run these in separate terminal windows:

#### Start MCP Servers
```bash
# Terminal 1: GitHub MCP
cd mcp_servers/github-context && ../../venv/bin/python server.py

# Terminal 2: Job Market MCP
cd mcp_servers/job-market && ../../venv/bin/python server.py
```

#### Start Backend
```bash
# Terminal 3: FastAPI Backend
cd backend && ../venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Start Frontend
```bash
# Terminal 4: Streamlit Frontend
cd frontend && ../venv/bin/streamlit run app.py --server.port 8501
```

## Access
- **Frontend**: [http://localhost:8501](http://localhost:8501)
- **Backend Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **GitHub MCP**: [http://localhost:8001](http://localhost:8001)
- **Job Market MCP**: [http://localhost:8002](http://localhost:8002)