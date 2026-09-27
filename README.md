# Intelligent Project Operations Assistant

Turns messy project documents, meeting notes, status reports, emails, task
lists, into a structured, queryable operational record: action items, risks,
decisions, dependencies, and open issues, each traceable back to the exact
line it came from. Every status change goes through a human approval step
before it's treated as final.

**[Try the live demo →](https://frontend-six-pi-51.vercel.app/dashboard.html?api=https://ai-project-ops-copilot-api.onrender.com)**

The backend is on Render's free tier, so the first request after a while can
take 30–60 seconds to wake up, and uploaded data resets on redeploy, good
enough to click around, not somewhere to keep real project data.

## Why

Most "AI project assistant" demos summarize documents into a paragraph you
still have to read closely to pull anything useful out of. This does the
opposite: it extracts first, and only summarizes, in the weekly report,
from that structured result. So the underlying data stays filterable,
countable, and auditable, not just readable.

## How it works

```
documents (.txt / .pdf / .docx)
        │
        ├─ chunked + embedded ─────────► Chroma (local vector store)
        │
        └─ sent to an LLM for extraction ─► action items · risks · decisions
                                             dependencies · open issues
                                                     │
                                                     ▼
                                          SQLite (SQLAlchemy models)
                                                     │
                    ┌────────────────────────────────┼────────────────────────┐
                    ▼                                ▼                        ▼
             dashboard views                 cited Q&A (RAG)           weekly report
                                                                    (built from the
                                                                     structured data,
                                                                     not raw notes)
```

Status changes never write directly, a proposed change sits in an approvals
queue until a human accepts or rejects it.

## Stack

- **Backend**, FastAPI, SQLAlchemy over SQLite, ChromaDB for retrieval (its
  bundled ONNX embedding model, so no GPU or paid embedding API needed).
- **LLM**, swappable at runtime between Groq, Gemini, and Ollama
  (`backend/llm_client.py`); Groq is the default because it's free and fast.
- **Frontend**, a single static HTML file (`frontend/dashboard.html`), no
  build step, no framework. A Streamlit app (`frontend/app.py`) also exists
  as a lighter alternative UI.

## Features

- Upload one or many documents at once, each is parsed, embedded, and run
  through structured extraction.
- Filterable action items with owner, deadline, priority, and status, each
  linked back to the source snippet it came from.
- Risks surfaced by their own extraction pass, not buried in a summary.
- A decisions / dependencies / open issues register.
- Source-cited Q&A over everything you've uploaded.
- A weekly status report generated from the structured data.
- Human-in-the-loop approvals, an action item's status only changes once
  someone signs off on it.
- Per-machine settings (API keys, model choice, retrieval depth) stored
  locally and never committed.
- Multiple projects, switchable from one list, each with its own clean-slate
  delete.
- Reports can be copied, downloaded as markdown, or printed to PDF.

## Getting started

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then add an API key, see below

uvicorn backend.main:app --reload
```

The frontend is a plain HTML file, but serve it rather than double-clicking
it so the clipboard and print features behave like they would on a real page:

```bash
cd frontend && python -m http.server 8765
```

Then open `http://localhost:8765/dashboard.html`. A few sample documents live
in `data/sample_documents/` if you want something to upload right away.

If the backend isn't running at `http://localhost:8000`, click the small
"API: ..." line in the page footer and point it at wherever it is.

### Getting a free LLM key

- **Groq** (recommended, free, fast, no card): https://console.groq.com/keys → `GROQ_API_KEY`
- **Gemini** (free tier): https://aistudio.google.com/apikey → `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`
- **Ollama** (fully local, no key at all): install from https://ollama.com, `ollama pull llama3.1`, `LLM_PROVIDER=ollama`

Provider model lineups move fast, if you get a `model not found` error,
the model name in `.env`/Settings has likely been renamed or retired.
Check the provider's current model list and update `GROQ_MODEL` or
`GEMINI_MODEL` accordingly.

These can also be set from inside the app itself, under Settings, they're
stored in `data/user_settings.json` on your machine and override `.env` at
runtime, without needing a restart.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents/upload` | Parse, chunk, embed, and extract structure from one file |
| GET | `/projects` | List projects with document counts and last activity |
| DELETE | `/projects/{project}` | Permanently delete everything under a project |
| GET | `/projects/{project}/action-items` | List action items (filter by status/owner) |
| GET | `/projects/{project}/risks` | List detected risks |
| GET | `/projects/{project}/decisions` | List decisions |
| GET | `/projects/{project}/dependencies` | List dependencies |
| GET | `/projects/{project}/open-issues` | List open issues |
| POST | `/qna` | Ask a question, get a cited answer (RAG) |
| GET | `/projects/{project}/weekly-report` | Generate a weekly status report |
| POST | `/action-items/{id}/request-status-change` | Propose a status change |
| POST | `/approvals/{id}/review` | Approve or reject a pending change |
| GET | `/approvals/pending` | List changes awaiting review |
| GET / PUT | `/settings` | Read or update the local LLM provider/key/model settings |

## Repo layout

```
backend/
  main.py            FastAPI app and all routes
  config.py          .env-driven settings, plus a runtime overlay
  settings_store.py  the local JSON overlay backing the Settings UI
  database.py        SQLAlchemy engine/session
  models.py          ORM models
  schemas.py         request/response models
  vectorstore.py     Chroma wrapper
  llm_client.py      Groq / Gemini / Ollama behind one interface
  ingestion.py       file parsing + chunking
  extraction.py      LLM output → structured DB rows
  rag.py             retrieval + cited answers
  reports.py         weekly report generation
frontend/
  dashboard.html     the primary UI
  app.py             a Streamlit alternative
data/sample_documents/  a few files to try the pipeline with
```

## Limitations

- One SQLite file and a local Chroma collection, fine for a single user,
  not built for concurrent writers.
- The chunker is a plain sliding window, not markdown- or section-aware.
- No auth, anyone who can reach the API can read and write everything.

---

From [Yashasvi Jaiswal](https://www.linkedin.com/in/yashjswl/).
