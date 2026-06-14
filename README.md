# Job Agent

A multi-user job discovery, matching, and tailoring agent. Users build a
career profile (resume + preferences); a deterministic pipeline searches
public job feeds, scores/ranks results, and learns from feedback. On top of
that, a **multi-agent layer** ( Agent SDK + MCP) adds a conversational
assistant, richer match explanations, automated discovery, and AI-tailored
resumes.

## Architecture

```
Streamlit UI  (Profile / Resume / Search / Ranked Jobs / AI Assistant / Tailor Resume)
        |
FastAPI backend (app/main.py)
   |                                  |
   | deterministic REST API           | /agents/* API (app/agents_api.py)
   v                                  v
Deterministic pipeline           Orchestrator agent (agents/orchestrator.py)
(app/pipeline.py,                       |
 app/matcher.py,                  routes to 4 specialized agents (MCP servers):
 app/feedback.py,                   - discovery-agent  -> run_discovery
 app/collector.py,                  - scoring-agent    -> score_and_explain
 app/resume_parser.py)              - resume-agent     -> tailor_resume
   |                                 - feedback-agent   -> process_feedback
   |                                       |
   |                          all call back into the deterministic pipeline
   |                          via the pipeline-tools MCP server
   |                          (agents/mcp_servers/pipeline_tools_server.py)
   v                                       |
        SQLite (data/db/job_agent.db) <----+
```

**Deterministic core (unchanged logic, still callable directly via REST):**

```
User profile (resume + preferences)
        |
Search Query Planner  -> generates queries from target roles + skills
        |
Job Collector          -> RemoteOK, JobTech SE, The Muse, Jobicy, Arbeitnow,
        |                  Greenhouse/Lever company boards, (optional) Adzuna
Dedup                  -> hash on URL / title+company+location
        |
Matching/Scoring        -> TF-IDF similarity + skill overlap + location/domain/company rules
        |
Ranked job list         -> stored per user
        |
Feedback (applied / shortlisted / skip / rejected_*)
        |
Skill weight learning   -> adjusts future scores
```

**Agent layer (agents/):**

| Agent | MCP server | Tool | Model | What it does |
|---|---|---|---|---|
| Orchestrator | `agents/orchestrator.py` | `run_chat_turn` | Sonnet | Conversational entry point; routes to the agents below |
| Discovery | `agents/mcp_servers/discovery_server.py` | `run_discovery` | Haiku | Runs the deterministic collector, summarizes new/top jobs |
| Scoring | `agents/mcp_servers/scoring_server.py` | `score_and_explain` | Sonnet | Explains *why* each job scored the way it did (from `score_breakdown`), without changing the score |
| Resume Tailoring | `agents/mcp_servers/resume_server.py` | `tailor_resume` | Sonnet | Rewrites/reorders the user's resume for a target job, truthfully, optionally following free-text instructions; renders a `.docx` |
| Feedback/Learning | `agents/mcp_servers/feedback_server.py` | `process_feedback` | Haiku | Records feedback (deterministic weight update) and suggests profile changes from free-text notes |

All five agents connect to the shared **pipeline-tools** MCP server
(`agents/mcp_servers/pipeline_tools_server.py`), which wraps the existing
deterministic pipeline (`app/pipeline.py`, `app/matcher.py`,
`app/feedback.py`, `app/collector.py`, `app/resume_parser.py`) as MCP tools —
the core matching/scoring logic is untouched.

Each user has an isolated `Profile`, set of `Job` matches, and `Feedback`
history (SQLite, `data/db/job_agent.db`).

## Setup

```bash
cd job-agent
python3.11 -m venv .venv311
.venv311/bin/pip install -r requirements.txt
```

### Agent layer prerequisites (AWS Bedrock)

The agent layer uses ** via AWS Bedrock** (`agents/config.py`), so no
`ANTHROPIC_API_KEY` is required if you're running on an EC2 instance/role
with Bedrock access:

- AWS credentials with `bedrock:InvokeModel` for the  models in
  `agents/config.py` (defaults:  Haiku 4.5 and  Sonnet 4.5,
  region `us-east-1`)
- Node.js + the `@anthropic-ai/-code` CLI on `PATH` (the  Agent
  SDK shells out to it):
  ```bash
  npm install -g @anthropic-ai/-code
  ```

If you don't have Bedrock access, the deterministic REST API and Streamlit
tabs (Profile/Resume/Search/Ranked Jobs) work fully without it — only the
"AI Assistant" and "Tailor Resume" tabs and `/agents/*` endpoints need it.

### Run it

```bash
# backend
.venv311/bin/uvicorn app.main:app --reload --port 8077

# UI (separate terminal)
.venv311/bin/streamlit run streamlit_app.py --server.port 8501
```

Open http://127.0.0.1:8077/docs for interactive API docs, or
http://127.0.0.1:8501 for the Streamlit UI.

## Usage flow (REST API)

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
   and stores the resume text for similarity scoring and for the resume
   tailoring agent:
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

## Agent API

- `POST /agents/chat` `{user_id, message, session_id?}` — conversational
  entry point; routes to the agents below and returns `{reply, session_id,
  cost_usd}`. Pass back `session_id` to continue a conversation.
- `POST /agents/discovery/{user_id}` — run discovery agent directly.
- `POST /agents/score/{user_id}?min_score=0` — run scoring/explanation agent.
- `POST /agents/tailor-resume/{user_id}/{job_id}` `{instructions?}` —
  generate a tailored `.docx` resume, optionally following free-text
  instructions (e.g. "make the summary shorter, emphasize AWS").
- `GET /agents/tailored-resume/{user_id}/{job_id}` — download the generated
  `.docx`.
- `POST /agents/feedback/{user_id}/{job_id}?status=...&note=...` — run
  feedback agent directly.

In the Streamlit UI, the **AI Assistant** tab wraps `/agents/chat` (try "find
new jobs for me and explain the top 3"), and **Tailor Resume** wraps
tailoring + preview + download.

## Scoring

`score_job()` in `app/matcher.py` combines:

- **text_similarity** (30%) — TF-IDF cosine similarity between job text and
  profile (resume + target roles + skills + domains)
- **skill_overlap** (30%) — weighted overlap of `core_skills` with job text;
  weights are updated by feedback (`app/feedback.py`)
- **location_match** (15%) — preferred locations / remote work mode
- **domain_match** (10%) — `domains` keywords found in job text
- **preferred_company** (10%) — bonus if employer is in `preferred_companies`
- **avoid_penalty** (-25%) — penalty if `avoid_skills` appear in job text

Jobs at companies in `excluded_companies` are hard-zeroed. The scoring agent
explains these breakdowns in natural language but never changes the numeric
score.

## Current sources

No API key required:
- **RemoteOK** (`app/sources/remoteok.py`) — global remote jobs
- **JobTech SE / Arbetsformedlingen** (`app/sources/jobtech_se.py`) — Swedish jobs
- **The Muse** (`app/sources/themuse.py`) — tech/remote roles
- **Jobicy** (`app/sources/jobicy.py`) — remote tech jobs, keyword-tag search
- **Arbeitnow** (`app/sources/arbeitnow.py`) — EU/remote job board
- **Greenhouse / Lever company boards** (`app/sources/company_boards.py`) —
  fetched for every company listed in your profile's `preferred_companies`
  (board token is guessed from the company name; companies not on
  Greenhouse/Lever are silently skipped)

Optional, requires a paid API plan (free tier no longer available):
- **Adzuna** (`app/sources/adzuna.py`) — aggregator that includes
  LinkedIn/Indeed-sourced postings. If you have a key, set:
  ```bash
  export ADZUNA_APP_ID=your_app_id
  export ADZUNA_APP_KEY=your_app_key
  export ADZUNA_COUNTRY=se   # optional, defaults to "se"
  ```
  Without these env vars, Adzuna is skipped and all other sources still run
  for free.

LinkedIn itself has no public job-search API and scraping it violates their
ToS, so it is intentionally not a direct source — the feeds above and
company boards are the closest legitimate, free substitutes.

## Roadmap / not yet implemented

- Recruiter email / LinkedIn saved-jobs ingestion (manual export or
  authorized integrations only)
- Recruiter outreach message generator
- Notifications (email/Telegram)
- Scheduled/background auto-discovery runs
- Richer resume parsing (currently keyword-based skill extraction)
- Salary-aware scoring (most free job feeds don't expose salary data)
- Persisted chat sessions (currently kept in Streamlit session state, not the DB)
