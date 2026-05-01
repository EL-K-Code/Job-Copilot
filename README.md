# JobCopilot

**JobCopilot** is an AI-powered job application copilot that helps a candidate go from a raw job description to concrete application actions.

It can:

- analyze a job offer into a structured representation,
- retrieve the most relevant profile memories using semantic search,
- generate a structured profile-to-job match insight,
- draft a tailored application email,
- save application records locally,
- create a **Gmail draft**,
- create a **Google Calendar follow-up reminder**,
- and expose both a classic workflow UI and a first **LangGraph agent** interface.

---

## Why this project

Job applications are repetitive, time-consuming, and often poorly contextualized.

JobCopilot was built to automate the most useful parts of the workflow while keeping the user in control:

1. understand the offer,
2. retrieve the right profile evidence,
3. write a relevant application email,
4. save the application,
5. prepare concrete actions such as drafting the email in Gmail and scheduling a follow-up reminder.

---

## Current scope

This repository contains a **working MVP** with:

- structured job analysis,
- semantic long-term profile memory with embeddings + FAISS,
- profile-to-job matching,
- email draft generation,
- local persistence of applications,
- Gmail draft creation,
- Google Calendar follow-up creation,
- Streamlit interface,
- LangGraph workflow orchestration,
- first LangGraph agent with tools.

---

## Tech stack

- **Python**
- **Streamlit**
- **LangChain**
- **LangGraph**
- **Anthropic / Claude**
- **FAISS**
- **Hugging Face Embeddings**
- **Pydantic**
- **Gmail API**
- **Google Calendar API**

---

## Main features

### 1. Structured job analysis
A raw job description is converted into a structured `JobAnalysis` object containing:

- company
- role
- location
- contract type
- required skills
- preferred skills
- tools and stack
- missions summary
- domain focus
- candidate highlights

### 2. Semantic profile memory
Candidate profile information is stored as memory entries and indexed with:

- Hugging Face embeddings
- FAISS vector search

This allows the system to retrieve the most relevant background information for a given role.

### 3. Profile-to-job match insight
The application compares:

- the structured job analysis
- the retrieved profile memories

and produces a structured `MatchInsight` with:

- strengths
- gaps
- suggested positioning angles
- relevant memories

### 4. Tailored email draft generation
From the job analysis and match insight, the system creates a structured `EmailDraft` with:

- subject
- body
- tone

### 5. Local application persistence
Application records are stored locally in JSON and include:

- company
- role
- email subject
- email body
- reminder date
- status
- creation timestamp

### 6. Gmail draft creation
The generated email can be turned into a real **Gmail draft** through the Gmail API.

### 7. Google Calendar reminder creation
The app can create a **follow-up reminder** in Google Calendar.

### 8. Streamlit interface
The UI provides tabs for:

- Job Analysis
- Match Insight
- Email Draft
- Saved Applications
- Agent Chat

### 9. LangGraph workflow
The deterministic pipeline is implemented as a LangGraph workflow with explicit state and nodes.

### 10. LangGraph agent
A first agent version is also included, using `@tool`-decorated tools for:

- running the pipeline
- creating Gmail drafts
- creating Calendar reminders
- saving applications
- listing saved applications

---

## Project structure

```text
app/
  bootstrap_gmail_auth.py
  config.py
  graph.py
  main.py
  memory.py
  prompts.py
  schemas.py
  state.py

  agent_graph.py
  agent_state.py
  agent_tools.py

  services/
    applications_store.py
    llm.py

  tools/
    gmail_tools.py
    calendar_tools.py

  ui/
    streamlit_app.py

data/
  applications.json
  profile_memories.json
  faiss_index/

tokens/
  google_token.json

credentials.json
.env
````

---

## Data flow

### Workflow mode

The current deterministic workflow is:

1. analyze job
2. retrieve profile memory
3. generate match insight
4. generate email draft

### Agent mode

The agent can use tools to:

* run the pipeline,
* create Gmail drafts,
* save applications,
* create follow-up reminders,
* list saved applications.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/EL-K-Code/Job-Copilot.git
cd Job-Copilot
```

### 2. Create and activate a virtual environment

#### Windows (Git Bash)

```bash
python -m venv .venv
source .venv/Scripts/activate
```

#### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment variables

Create a `.env` file at the project root:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-sonnet-4-6

GOOGLE_CLIENT_SECRET_FILE=credentials.json
GOOGLE_TOKEN_DIR=tokens

MEMORY_INDEX_DIR=data/faiss_index
APPLICATIONS_FILE=data/applications.json
PROFILE_MEMORIES_FILE=data/profile_memories.json
```

---

## Google setup

To enable Gmail draft creation and Calendar reminders, you need a Google Cloud OAuth configuration.

### Required steps

* create or select a Google Cloud project,
* enable **Gmail API**,
* enable **Google Calendar API**,
* configure the OAuth consent screen,
* create an OAuth client of type **Desktop app**,
* download the client JSON file,
* save it locally as:

```text
credentials.json
```

### Important

Do **not** commit these files:

* `credentials.json`
* `tokens/google_token.json`
* `.env`

---

## First Google authentication

After placing `credentials.json` at the project root, run:

```bash
python -m app.bootstrap_gmail_auth
```

This will open a local Google authentication flow and create:

```text
tokens/google_token.json
```

If you modify Google scopes later, delete the token and authenticate again.

---

## Running the app

### Run the backend test

```bash
python -m app.main
```

### Run the Streamlit app

```bash
streamlit run app/ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Then open:

```text
http://127.0.0.1:8501
```

---

## Expected local files

### `data/applications.json`

```json
[]
```

### `data/profile_memories.json`

This file should contain a list of memory entries, for example:

```json
[
  {
    "id": "skill_1",
    "type": "skill",
    "content": "Alex has strong programming experience in Python."
  }
]
```

---

## Streamlit interface

The Streamlit app includes:

### Job Analysis

Displays:

* structured job extraction,
* key job metrics,
* quick highlights.

### Match Insight

Displays:

* retrieved profile memories,
* strengths,
* gaps,
* suggested angles.

### Email Draft

Allows the user to:

* review the generated subject,
* edit the generated body,
* set a recipient email,
* choose a follow-up date,
* create a Gmail draft,
* create a Calendar reminder,
* save the application locally.

### Saved Applications

Displays the locally stored application history.

### Agent Chat

Provides a first LangGraph tool-calling interface for interacting with JobCopilot through natural language.

---

## LangGraph architecture

### Workflow graph

The deterministic graph currently includes nodes such as:

* `analyze_job`
* `retrieve_memory`
* `generate_match`
* `generate_email`

### Agent graph

The agent graph uses:

* `messages` state
* tool-calling
* `ToolNode`
* loop between assistant and tools

Available tools include:

* `run_jobcopilot_pipeline_tool`
* `create_gmail_draft_tool`
* `create_followup_reminder_tool`
* `save_application_record_tool`
* `list_saved_applications_tool`

---

## Reliability choices

This project was designed with a few practical safety constraints:

* structured outputs with **Pydantic**
* retrieval grounding via **profile memory**
* stricter prompts to reduce unsupported claims
* anti-duplicate safeguards for:

  * saved applications
  * repeated Gmail draft creation in the same session
  * repeated Calendar reminders in the same session

---

## Example workflow

A typical user flow is:

1. paste a job description,
2. click **Analyze job**,
3. review job analysis and match insight,
4. edit the generated email if needed,
5. create a Gmail draft,
6. create a follow-up reminder,
7. save the application record.

---

## Example use cases

* internship applications
* AI / data / software roles
* follow-up management after an application
* demo of an applied AI workflow
* demonstration of LangGraph workflow vs agent orchestration

---

## Limitations

Current limitations of the MVP:

* local JSON persistence instead of a database,
* no advanced multi-user support,
* no production deployment configuration,
* no full human approval workflow beyond UI interaction,
* Gmail and Calendar actions depend on local OAuth configuration.

---

## Roadmap

Planned improvements include:

* richer application tracking fields,
* stronger action traceability,
* persistent storage in SQLite or Postgres,
* more granular LangGraph routing,
* more atomic agent tools,
* improved evaluation and logging,
* deployment-ready packaging.

---

## What this project demonstrates

This repository demonstrates:

* applied LLM engineering,
* structured extraction,
* retrieval-augmented reasoning,
* semantic memory,
* Pydantic-constrained outputs,
* workflow orchestration with LangGraph,
* first tool-calling agent design,
* integration with real external systems (Gmail, Google Calendar),
* end-to-end product thinking.

---

## Author

**Alex Komla LABOU**

GitHub: [EL-K-Code](https://github.com/EL-K-Code)

---

## Security note

Never commit:

* `credentials.json`
* `tokens/`
* `.env`

Keep OAuth credentials local only.

````

Ensuite, ton `.gitignore` devrait au minimum contenir :

```gitignore id="3608q4"
.venv/
__pycache__/
*.pyc
.env
credentials.json
tokens/
data/faiss_index/
````

