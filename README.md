# AIVOA — AI-Powered Customer Complaint Management System

A Customer Complaint Management module for pharmaceutical API/FDF manufacturers,
built for the AIVOA Round 1 Full Stack Developer assessment.

It reproduces the workflow shown in the reference demo video: a complaint
document (email/PDF/DOCX/pasted text) is dropped into the **AI Complaint
Intake Assistant**, which extracts structured fields, auto-populates the
**Log Customer Complaint** form, runs an AI risk assessment, and lets the
reviewer chat with an assistant about the complaint before committing it to
the QMS ledger.

## Tech stack (as mandated by the assessment)

| Layer            | Choice                                              |
|------------------|------------------------------------------------------|
| Frontend         | React + Redux Toolkit (Vite), Google Inter font       |
| Backend          | Python, FastAPI                                       |
| AI Agent Framework | LangGraph                                           |
| LLMs             | Groq — `gemma2-9b-it` (extraction/classification), `llama-3.3-70b-versatile` (reasoning) |
| Database         | Postgres or MySQL (SQLAlchemy ORM; SQLite fallback for zero-setup local demo) |

## Why this architecture

The assignment's real subject is a **pharma QMS complaint intake workflow**,
not a generic chat app, so the design centers on two things a QA reviewer
actually needs: (1) a form that never has to be filled in by hand when a
document already contains the answer, and (2) a visible, auditable trail of
what the AI decided and why — every AI-derived field is highlighted, every
bonus insight (risk, root cause, CAPA...) is shown as its own card rather
than folded invisibly into the record.

### LangGraph pipeline (`backend/app/agents/graph.py`)

```
START → extract → completeness → risk → duplicate → summary → root_cause → capa → END
```

One document run produces the full form **and** every bonus AI feature in a
single graph invocation:

- **extract** — Groq `gemma2-9b-it` reads the raw complaint text and returns
  the structured form fields as JSON (never invents values for missing
  fields).
- **completeness** — flags which mandatory fields (source, customer, product,
  batch, complaint type/date, description) are still missing.
- **risk** — Groq `llama-3.3-70b-versatile` recommends Severity/Priority with
  a one-line rationale, feeding back into the form.
- **duplicate** — cheaply narrows candidates by product/batch match, then
  asks the LLM to confirm whether the new complaint is the same underlying
  issue as an existing record.
- **summary / root_cause / capa** — QA-reviewer-ready outputs: a plain-English
  summary, likely root-cause categories, and draft corrective/preventive
  actions.

### Chat assistant graph (`backend/app/agents/chat_graph.py`)

A second, smaller LangGraph graph powers the "Ask me anything about this
complaint" box:

```
START → classify_intent → (route) → answer_from_context | answer_general → END
```

Questions about the specific complaint on screen are answered strictly from
that complaint's data (so the assistant won't hallucinate a batch number);
general QMS/process questions are routed to the reasoning model's own
knowledge. Conversation history is persisted per session in the database.

### Why two graphs instead of one big agent

Keeping intake (deterministic pipeline) and chat (conversational, branching)
as separate graphs keeps each one simple to reason about and test in
isolation — this mirrors how the reference UI treats them as two visibly
different capabilities (progress-bar extraction vs. open-ended chat).

## Project layout

```
aivoa/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, CORS, router registration
│   │   ├── config.py            Settings from environment variables
│   │   ├── database.py          SQLAlchemy engine/session (Postgres/MySQL/SQLite)
│   │   ├── models.py            Complaint + ChatMessage tables
│   │   ├── schemas.py           Pydantic request/response models
│   │   ├── agents/
│   │   │   ├── llm.py           Groq client wrapper
│   │   │   ├── state.py         LangGraph state (TypedDict)
│   │   │   ├── nodes.py         Node functions: extract/completeness/risk/duplicate/summary/root_cause/capa
│   │   │   ├── graph.py         Intake pipeline graph
│   │   │   └── chat_graph.py    Chat assistant graph
│   │   ├── routers/
│   │   │   ├── complaints.py    CRUD for saved complaints
│   │   │   ├── extraction.py    POST /api/extract/text, /api/extract/file
│   │   │   ├── chat.py          POST /api/chat
│   │   │   └── ai_tools.py      Re-run bonus AI features on a saved complaint
│   │   └── utils/document_parser.py   Text extraction for pdf/docx/txt/eml
│   ├── sample_data/              3 realistic sample complaints for the demo
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── components/           ComplaintForm, AIAssistantPanel, ComplaintsList, Header
    │   ├── store/                Redux Toolkit slices (complaint, chat)
    │   ├── api/client.js         Axios wrapper around the backend API
    │   └── styles/index.css      Design tokens + component styles
    ├── vite.config.js            Dev server + /api proxy to the backend
    └── package.json
```

## Setup

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- Get a **Groq API key** at https://console.groq.com/keys and set `GROQ_API_KEY`.
- Set `DATABASE_URL` to your Postgres or MySQL instance, e.g.
  `postgresql+psycopg2://postgres:postgres@localhost:5432/aivoa` or
  `mysql+pymysql://root:root@localhost:3306/aivoa`. Leaving it unset falls
  back to a local `sqlite:///./aivoa_dev.db` file so the app runs with zero
  DB setup for a quick demo.

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on first run. Swagger docs are available at
`http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The Vite dev server proxies `/api` calls to
`http://localhost:8000`.

### 3. Try it out

1. Go to **Log Complaint**.
2. Drag in one of the files from `backend/sample_data/`, or click **Paste
   Complaint Text / Email** and paste its contents.
3. Watch the extraction progress bar, then see the form auto-fill with the
   AI-derived fields (highlighted in teal), plus the AI risk assessment,
   summary, root cause, and CAPA cards.
4. Ask the assistant a question about the complaint (e.g. *"what's the batch
   number?"*), or correct a field by typing e.g. *"actually the batch number
   is BMX240602"* — this mirrors the correction flow shown in the demo video.
5. Click **Save Complaint** to commit it to the ledger, then check **All
   Complaints** to see it listed with one-click AI tools (Summarize, Root
   Cause, CAPA, Check Duplicate).
6. Try `sample_complaint_3_duplicate_check.txt` after saving sample 1 — the
   duplicate-detection node should flag it against the saved record.

## Notes on scope

- Per the assignment, **production-grade OCR is not required** — document
  parsing (`utils/document_parser.py`) extracts text from PDFs (text layer),
  DOCX, TXT, and EML, which is enough to demo the full workflow with
  realistic sample files.
- All prompts explicitly instruct the extraction model to leave a field
  blank rather than invent data, and the completeness/duplicate/risk nodes
  are deliberately kept as separate, independently-testable graph nodes
  rather than one large prompt, so each can be reasoned about, evaluated, and
  swapped out on its own.
- The two model split follows the assignment's stack: `gemma2-9b-it` for
  fast structured extraction/classification, `llama-3.3-70b-versatile` for
  the reasoning-heavy tasks (risk rationale, duplicate judgment, root cause,
  CAPA, chat).
