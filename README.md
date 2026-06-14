# JobPilot Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)

A personal AI job-search assistant. It builds a profile from your resume and
preferences, searches public job boards, scores and ranks results, learns
from your feedback over time — and on top of that, a team of **
agents** (via the  Agent SDK + MCP) can chat with you, explain matches,
tailor your resume per job, and run searches autonomously.

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Using the app](#using-the-app)
- [REST API reference](#rest-api-reference)
- [Agent API reference](#agent-api-reference)
- [How scoring works](#how-scoring-works)
- [Job sources](#job-sources)
- [Roadmap](#roadmap)

---

## Features

- 🔍 **Multi-source job search** — RemoteOK, JobTech SE, The Muse, Jobicy,
  Arbeitnow, Greenhouse/Lever company boards (all free, no API key needed)
- 🧮 **Explainable scoring** — TF-IDF text similarity + skill overlap +
  location/domain/company rules, with a per-job score breakdown
- 🧠 **Self-learning** — feedback (applied/shortlisted/skipped/rejected)
  nudges skill weights so future searches improve
- 💬 **AI chat assistant** — ask in plain English: *"find new jobs for me and
  explain the top 3"*
- 📄 **AI resume tailoring** — generates a tailored `.docx` resume per job,
  optionally following your custom instructions (e.g. "emphasize AWS,
  shorten the summary"), with a live preview before download
- 👥 **Multi-user** — each user has an isolated profile, job matches, and
  feedback history (SQLite)

---

## How it works

### Layered architecture

```mermaid
flowchart TB
    subgraph UI["UI Layer — Streamlit (streamlit_app.py)"]
        direction LR
        U1[Profile]
        U2[Resume]
        U3[Search]
        U4[Ranked Jobs]
        U5[AI Assistant]
        U6[Tailor Resume]
    end

    subgraph API["API Layer — FastAPI (app/main.py)"]
        direction LR
        A1["Deterministic REST API\n/users, /jobs, /search, /feedback"]
        A2["Agents API\n/agents/* (app/agents_api.py)"]
    end

    subgraph ORC["Orchestration Layer"]
        O1["Orchestrator Agent\nagents/orchestrator.py\nrun_chat_turn — Sonnet"]
    end

    subgraph AGENTS["Specialized Agents — each its own MCP server"]
        direction LR
        AG1["Discovery\nrun_discovery — Haiku"]
        AG2["Scoring\nscore_and_explain — Sonnet"]
        AG3["Resume Tailoring\ntailor_resume — Sonnet"]
        AG4["Feedback / Learning\nprocess_feedback — Haiku"]
    end

    subgraph TOOLS["Tool Layer"]
        T1["pipeline-tools MCP server\nagents/mcp_servers/pipeline_tools_server.py"]
    end

    subgraph CORE["Deterministic Pipeline (app/)"]
        direction LR
        C1[pipeline.py]
        C2[matcher.py]
        C3[collector.py]
        C4[feedback.py]
        C5[resume_parser.py]
    end

    subgraph DATA["Data Layer"]
        direction LR
        D1[("SQLite\ndata/db/job_agent.db")]
        D2["data/tailored_resumes/\n*.docx"]
    end

    subgraph EXT["External Services"]
        direction LR
        E1["AWS Bedrock\n Haiku / Sonnet 4.5"]
        E2["Public Job Boards\nRemoteOK · JobTech SE · The Muse\nJobicy · Arbeitnow · Greenhouse/Lever · Adzuna"]
    end

    UI --> API
    A1 --> CORE
    A2 --> O1
    O1 -- MCP stdio --> AG1
    O1 -- MCP stdio --> AG2
    O1 -- MCP stdio --> AG3
    O1 -- MCP stdio --> AG4
    AG1 -- MCP stdio --> T1
    AG2 -- MCP stdio --> T1
    AG3 -- MCP stdio --> T1
    AG4 -- MCP stdio --> T1
    T1 --> CORE
    AG3 -- writes --> D2
    O1 -.  calls .-> E1
    AG1 -.  calls .-> E1
    AG2 -.  calls .-> E1
    AG3 -.  calls .-> E1
    AG4 -.  calls .-> E1
    CORE --> D1
    C3 -. fetches .-> E2
```

### Data flow — deterministic search (REST)

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit (Search tab)
    participant API as FastAPI /users/{id}/search
    participant Collector as collector.py
    participant Matcher as matcher.py
    participant DB as SQLite

    User->>UI: Click "Search for jobs"
    UI->>API: POST /users/{user_id}/search
    API->>Collector: build queries from profile + collect_jobs()
    Collector->>Collector: fetch RemoteOK, JobTech SE, The Muse,<br/>Jobicy, Arbeitnow, Greenhouse/Lever, Adzuna
    Collector-->>API: deduped raw jobs
    API->>Matcher: score_job() per job<br/>(TF-IDF + skill overlap + rules)
    Matcher-->>API: scored + ranked jobs
    API->>DB: upsert jobs + scores
    API-->>UI: ranked job list
    UI-->>User: Ranked Jobs tab updates
```

### Data flow — AI Assistant chat (multi-agent)

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit (AI Assistant)
    participant API as FastAPI /agents/chat
    participant Orc as Orchestrator (Sonnet)
    participant Disc as Discovery Agent (Haiku)
    participant Score as Scoring Agent (Sonnet)
    participant Tools as pipeline-tools MCP
    participant DB as SQLite

    User->>UI: "Find new jobs and explain the top 3"
    UI->>API: POST /agents/chat {user_id, message, session_id}
    API->>Orc: run_chat_turn(message)
    Orc->>Disc: run_discovery(user_id)
    Disc->>Tools: collect_jobs_for_user(user_id)
    Tools->>DB: upsert jobs + scores
    Tools-->>Disc: new jobs
    Disc-->>Orc: discovery summary
    Orc->>Score: score_and_explain(user_id)
    Score->>Tools: list_ranked_jobs(user_id)
    Tools-->>Score: ranked jobs + score_breakdown
    Score-->>Orc: per-job explanations
    Orc-->>API: reply + session_id
    API-->>UI: chat response
    UI-->>User: "Found 5 new jobs. Top match: ..."
```

### Deterministic pipeline

The "core" logic is plain Python — no LLM involved, fully reproducible:

```mermaid
flowchart LR
    A["User profile\n(resume + preferences)"] --> B["Search Query Planner\ngenerates queries from\ntarget roles + skills"]
    B --> C["Job Collector\nRemoteOK, JobTech SE, The Muse,\nJobicy, Arbeitnow, Greenhouse/Lever,\n(optional) Adzuna"]
    C --> D["Dedup\nhash on URL /\ntitle+company+location"]
    D --> E["Matching / Scoring\nTF-IDF similarity + skill overlap\n+ location/domain/company rules"]
    E --> F["Ranked job list\nstored per user"]
    F --> G["Feedback\napplied / shortlisted /\nskip / rejected_*"]
    G --> H["Skill weight learning\nadjusts future scores"]
    H -.-> E
```

### Agent layer

| Agent | MCP server | Tool | Model | What it does |
|---|---|---|---|---|
| **Orchestrator** | `agents/orchestrator.py` | `run_chat_turn` | Sonnet | Conversational entry point; routes to the agents below |
| **Discovery** | `agents/mcp_servers/discovery_server.py` | `run_discovery` | Haiku | Runs the deterministic collector, summarizes new/top jobs |
| **Scoring** | `agents/mcp_servers/scoring_server.py` | `score_and_explain` | Sonnet | Explains *why* each job scored the way it did, without changing the score |
| **Resume Tailoring** | `agents/mcp_servers/resume_server.py` | `tailor_resume` | Sonnet | Rewrites/reorders your resume for a target job (truthfully), optionally following your instructions; renders a `.docx` |
| **Feedback/Learning** | `agents/mcp_servers/feedback_server.py` | `process_feedback` | Haiku | Records feedback (deterministic weight update) and suggests profile changes from your notes |

All five agents connect to a shared **pipeline-tools** MCP server
(`agents/mcp_servers/pipeline_tools_server.py`), which exposes the
deterministic pipeline as MCP tools — the core matching/scoring logic itself
is never modified by an agent.

---

## Quick start

### 1. Install

```bash
git clone https://github.com/ravinpandey/jobpilot-agent.git
cd jobpilot-agent
python3.11 -m venv .venv311
.venv311/bin/pip install -r requirements.txt
```

### 2. (Optional) Enable the AI agent layer

The agent layer talks to  via **AWS Bedrock** (`agents/config.py`) —
no separate `ANTHROPIC_API_KEY` needed if you have AWS credentials with
Bedrock access:

```bash
# AWS credentials with bedrock:InvokeModel for  Haiku/Sonnet 4.5
# (default region: us-east-1, configurable in agents/config.py)

# The  Agent SDK needs the  Code CLI on PATH:
npm install -g @anthropic-ai/-code
```

> Without this, the **Profile / Resume / Search / Ranked Jobs** tabs and
> their REST endpoints work fully. Only **AI Assistant** / **Tailor Resume**
> and the `/agents/*` endpoints need Bedrock access.

### 3. Run

```bash
# Terminal 1 — backend API
source .venv311/bin/activate
uvicorn app.main:app --reload --port 8077

# Terminal 2 — UI
source .venv311/bin/activate
streamlit run streamlit_app.py --server.port 8501
```

Open:
- **UI** → http://127.0.0.1:8501
- **API docs** → http://127.0.0.1:8077/docs

---

## Using the app

1. **Create a user** in the sidebar of the Streamlit UI (or via API, see
   below).
2. **Profile tab** — set your target roles, core skills, domains, preferred
   locations/companies, salary, and work mode.
3. **Resume tab** — upload your resume (PDF). Skills are extracted and
   merged into your profile automatically.
4. **Search tab** — click "Run search now" to collect, dedupe, and score jobs
   from all configured sources.
5. **Ranked Jobs tab** — browse jobs sorted by score, view the score
   breakdown, and leave feedback (applied/shortlisted/skip/rejected/...).
   Feedback adjusts skill weights for future searches.
6. **AI Assistant tab** — chat naturally, e.g.:
   - *"Find new jobs for me and explain the top 3"*
   - *"Why did the Modulai job score so low?"*
   - *"Record that I applied to job 54"*
7. **Tailor Resume tab** — pick a ranked job, optionally describe what you
   want changed (e.g. "make the summary shorter, emphasize AWS/MLOps"),
   preview the tailored resume, and download it as `.docx`.

---

## REST API reference

The deterministic pipeline is fully usable via plain REST calls (e.g. for
scripting or automation):

1. **Create a user**
   ```bash
   curl -X POST localhost:8077/users \
     -H "Content-Type: application/json" \
     -d '{"name": "Ravindra", "email": "ravi@example.com"}'
   ```

2. **Set preferences** (target roles drive the search queries)
   ```bash
   curl -X PUT localhost:8077/users/1/profile \
     -H "Content-Type: application/json" -d '{
       "target_roles": ["Generative AI Engineer", "AI/ML Architect"],
       "domains": ["banking", "pharma"],
       "core_skills": ["RAG", "Python", "AWS", "FastAPI", "LangChain"],
       "avoid_skills": ["cold calling"],
       "preferred_locations": ["Sweden", "Remote"],
       "excluded_companies": [],
       "min_salary": 50000,
       "work_mode": "remote",
       "seniority": "senior"
     }'
   ```

3. **(Optional) Upload resume** — merges extracted skills into `core_skills`
   and stores the resume text for similarity scoring and resume tailoring:
   ```bash
   curl -X POST localhost:8077/users/1/resume -F "file=@/path/to/resume.pdf"
   ```

4. **Run a search** — collects jobs, scores and ranks them:
   ```bash
   curl -X POST localhost:8077/users/1/search
   ```

5. **List ranked jobs**
   ```bash
   curl "localhost:8077/users/1/jobs?min_score=20"
   ```

6. **Give feedback** — adjusts skill weights for future searches:
   ```bash
   curl -X POST localhost:8077/users/1/jobs/16/feedback \
     -H "Content-Type: application/json" \
     -d '{"status": "shortlisted", "note": "good RAG fit"}'
   ```
   Valid statuses: `applied`, `shortlisted`, `skip`, `rejected_salary`,
   `rejected_location`, `rejected`.

---

## Agent API reference

| Endpoint | Description |
|---|---|
| `POST /agents/chat` `{user_id, message, session_id?}` | Conversational entry point. Returns `{reply, session_id, cost_usd}` — pass `session_id` back to continue the conversation. |
| `POST /agents/discovery/{user_id}` | Run the discovery agent directly (search + summarize new jobs). |
| `POST /agents/score/{user_id}?min_score=0` | Run the scoring/explanation agent directly. |
| `POST /agents/tailor-resume/{user_id}/{job_id}` `{instructions?}` | Generate a tailored `.docx` resume, optionally following free-text instructions. |
| `GET /agents/tailored-resume/{user_id}/{job_id}` | Download the generated `.docx`. |
| `POST /agents/feedback/{user_id}/{job_id}?status=...&note=...` | Run the feedback agent directly. |

---

## How scoring works

`score_job()` in `app/matcher.py` combines:

| Component | Weight | Description |
|---|---|---|
| **text_similarity** | 30% | TF-IDF cosine similarity between job text and profile (resume + target roles + skills + domains) |
| **skill_overlap** | 30% | Weighted overlap of `core_skills` with job text; weights are updated by feedback (`app/feedback.py`) |
| **location_match** | 15% | Preferred locations / remote work mode |
| **domain_match** | 10% | `domains` keywords found in job text |
| **preferred_company** | 10% | Bonus if employer is in `preferred_companies` |
| **avoid_penalty** | -25% | Penalty if `avoid_skills` appear in job text |

Jobs at companies in `excluded_companies` are hard-zeroed. The scoring agent
explains these breakdowns in natural language but **never changes the
numeric score**.

---

## Job sources

**No API key required:**

| Source | File | Coverage |
|---|---|---|
| RemoteOK | `app/sources/remoteok.py` | Global remote jobs |
| JobTech SE (Arbetsförmedlingen) | `app/sources/jobtech_se.py` | Swedish jobs |
| The Muse | `app/sources/themuse.py` | Tech/remote roles |
| Jobicy | `app/sources/jobicy.py` | Remote tech jobs, keyword-tag search |
| Arbeitnow | `app/sources/arbeitnow.py` | EU/remote job board |
| Greenhouse / Lever company boards | `app/sources/company_boards.py` | Fetched per company in `preferred_companies` (skipped if not on Greenhouse/Lever) |

**Optional (requires a paid plan):**

- **Adzuna** (`app/sources/adzuna.py`) — aggregator including LinkedIn/Indeed
  postings. If you have a key:
  ```bash
  export ADZUNA_APP_ID=your_app_id
  export ADZUNA_APP_KEY=your_app_key
  export ADZUNA_COUNTRY=se   # optional, defaults to "se"
  ```
  Without these env vars, Adzuna is skipped and all other sources still run
  for free.

> LinkedIn has no public job-search API and scraping it violates their ToS,
> so it's intentionally not a direct source — the feeds above and company
> boards are the closest legitimate, free substitutes.

---

## Roadmap

- [ ] Recruiter email / LinkedIn saved-jobs ingestion (manual export or
      authorized integrations only)
- [ ] Recruiter outreach message generator
- [ ] Notifications (email/Telegram)
- [ ] Scheduled/background auto-discovery runs
- [ ] Richer resume parsing (currently keyword-based skill extraction)
- [ ] Salary-aware scoring (most free job feeds don't expose salary data)
- [ ] Persisted chat sessions (currently kept in Streamlit session state, not the DB)

---

## License

[MIT](LICENSE) © 2026 Ravindra Kumar
