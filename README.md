# Business Research Copilot — AI SMB Analyst

Business Research Copilot is a production-grade, SMB-focused AI web application that enables non-technical business users (e.g. CEOs, sales leads, founders) to research target companies on the web, draft tailored sales outreach copy, compile follow-up action checklists, and manage AI-learned long-term preferences over time.

---

## What the Product Does
The application operates as a dedicated research assistant:
1. **Secure Registration, Google SSO & Recovery**: Users can sign up and log in via email/password or using Google Single Sign-On (SSO). Password resets are supported with tokens logged locally to the server console.
2. **Context-Aware Research Chat**: Users discuss target companies, target profiles, and pitches.
3. **Multi-Agent Research Pipeline**: The assistant uses web search tool routines to query Google/DuckDuckGo, scrapes link content, summarizes page structures, and drafts outputs.
4. **LLM-as-a-Judge Validation**: An automated Critic node reviews drafts, ensuring factual consistency, source citations, and professional formatting, looping back to the Writer if revisions are needed.
5. **Durable Memory settings**: Powered by **Memori** (by MemoriLabs), the assistant extracts facts (e.g., target profile limits, preferred outreach templates) and saves them in standard SQL tables, recalling them across chat threads. An interactive ChatGPT-style "Manage Memory" settings pane allows users to view and delete these facts.
6. **Gmail Outreach Integration**: Uses **Composio** to connect users' Gmail accounts via OAuth, parses generated email drafts with Gemini, and lets users send them directly with one click inside the app.
7. **Modern Citation & Sources UI**: Renders Perplexity-style inline citation badges with hover cards showing details, plus a collapsible summary card at the bottom of the content.

---

## Tech Stack
*   **Frontend**: React (Vite, TypeScript, React Router, React Markdown, Lucide Icons)
*   **Frontend Styling**: Custom Vanilla CSS (Dark Space theme, Glassmorphism, animations)
*   **Backend API**: Python + FastAPI
*   **Database**: PostgreSQL
*   **Database Migrations**: Alembic
*   **ORM**: SQLAlchemy 2.0 (Strict mapped type annotations)
*   **Package Manager & Dependency Compiler**: `uv` (by Astral)
*   **Orchestration**: Docker & Docker Compose
*   **Agent Logic**: LangGraph + LangChain + Google Gemini (`gemini-2.5-flash` & `gemini-2.5-pro`)
*   **Long-Term Memory**: Memori (by MemoriLabs)
*   **Email Integration**: Composio SDK (v0.13.x)
*   **SSO Auth**: Google Identity Services (GIS)
*   **Telemetry & Tracing**: Langfuse
*   **Search**: Serper API (Google Organic Search) with DuckDuckGo Search fallback



---

## Architecture Overview

```mermaid
graph TD
    User([User Client]) -->|API Requests| FastAPI[FastAPI Backend]
    FastAPI -->|Auth & Thread Store| DB[(PostgreSQL Database)]
    FastAPI -->|Triggers Workflow| Graph[LangGraph Multi-Agent System]
    
    subgraph Multi-Agent Graph
        Graph --> Supervisor{Supervisor Router}
        Supervisor -->|Needs Live Info| Researcher[Research Agent]
        Researcher -->|Scrape Links| Tools[Serper / DuckDuckGo / Scraper]
        Tools --> Researcher
        Researcher -->|Findings| Supervisor
        Supervisor -->|Generate Brief/Email/Tasks| Writer[Writer Agent]
        Writer -->|Draft Output| Judge{LLM Judge / Validator}
        Judge -->|Rejection: Feedback| Writer
        Judge -->|Approval: Pass| Supervisor
    end

    FastAPI -->|Memory Sync| Memori[Memori Labs engine]
    Memori -->|Attribution Store| DB
    FastAPI -->|Get/Delete Facts| DB
```

---

## Folder Structure

```text
smb-research-copilot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routes/
│   │   │       │   ├── auth.py          # Signup, Login, Password Reset, Me
│   │   │       │   ├── chats.py         # Thread listing & creation
│   │   │       │   ├── messages.py      # Conversation history & agent chat
│   │   │       │   ├── memory.py        # GET & DELETE Memori facts for UI
│   │   │       │   └── actions.py       # Runs structured agent modes
│   │   │       └── router.py            # Routes aggregator
│   │   ├── core/
│   │   │   ├── config.py                # Environment variables
│   │   │   ├── database.py              # SQLAlchemy engine & DB sessions
│   │   │   └── security.py              # Password hashing & JWT helpers
│   │   ├── models/                      # SQLAlchemy Declarative Models
│   │   │   ├── base.py
│   │   │   ├── user.py                  # Includes google_id placeholder
│   │   │   ├── chat.py                  # Thread sessions
│   │   │   └── message.py               # Message records with JSON metadata
│   │   ├── schemas/                     # Pydantic v2 Schemas (ConfigDict)
│   │   ├── services/
│   │   │   ├── auth_service.py          # Registration & Token Reset
│   │   │   └── memory_service.py        # Memori framework wrappers
│   │   ├── agents/                      # LangGraph multi-agent implementation
│   │   │   ├── graph.py                 # Graph definition & compilation
│   │   │   ├── supervisor.py            # Routing orchestrator
│   │   │   ├── researcher.py            # Search executor
│   │   │   ├── writer.py                # Content generator
│   │   │   ├── judge.py                 # LLM Critic / validator
│   │   │   └── state.py                 # Graph states schema
│   │   ├── tools/
│   │   │   ├── web_search.py            # Serper API + DuckDuckGo fallback
│   │   │   └── page_fetch.py            # Web scraper (BeautifulSoup)
│   │   └── main.py                      # FastAPI App initialization & lifespan
│   ├── alembic/                         # Database migration versions
│   ├── tests/                           # Pytest unit & API smoke tests
│   ├── Dockerfile                       # Multi-stage python image compiling with uv
│   └── pyproject.toml                   # Project dependencies
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts                # Axios client with session handlers
│   │   ├── components/
│   │   │   ├── layout/AppLayout.tsx     # Workspace sidebar, user profile card
│   │   │   ├── memory/MemoryManager.tsx # Memory viewing & fact deletion dashboard
│   │   │   └── ui/                      # Button, Input, Spinner, Toast wrappers
│   │   ├── pages/                       # Login, Signup, Forgot/Reset, Chat
│   │   ├── App.tsx                      # Routes map
│   │   └── index.css                    # Design styles (Vibrant space HSL theme)
│   └── Dockerfile                       # Node container for development
├── docker-compose.yml                   # DB, Backend, Frontend coordination
├── .env.example                         # Environment configuration template
└── README.md
```

---

## Local Setup & Run Instructions

### Prerequisites
*   Docker & Docker Compose installed and running locally.
*   A Google Gemini API Key (**required** for agent completions). Get yours free at [Google AI Studio](https://aistudio.google.com/app/apikey).
*   A Serper.dev API Key (Optional. If not provided, search falls back to DuckDuckGo).
*   A Composio API Key (Optional, for Gmail outreach integration. Register at [Composio Dashboard](https://dashboard.composio.dev)).

### 1. Environment Configuration

To run the application, you need to configure three `.env` files:

#### A. Root `.env` (Used by Docker Compose)
Copy the root `.env.example` to `.env` at the project root:
```bash
cp .env.example .env
```
Fill in the following variables:
*   `GEMINI_API_KEY`: Your Gemini AI key from Google AI Studio.
*   `SERPER_API_KEY` *(Optional)*: Key for Serper.dev Google organic search.
*   `COMPOSIO_API_KEY` *(Optional)*: Key for Gmail outreach integrations.
*   `GOOGLE_CLIENT_ID` *(Optional)*: Google OAuth client ID for Google SSO.
*   `FRONTEND_ORIGIN`: Typically `http://localhost:5173`.
*   `LOG_JSON`: Set to `true` for structured JSON output, or `false` (default) for pretty text logs.

#### B. Backend Local `.env` (Used when running Backend outside Docker)
Copy the backend `.env.example` to `backend/.env`:
```bash
cp backend/.env.example backend/.env
```
Fill in the same keys as the root `.env`. Ensure your `DATABASE_URL` is pointing to the correct database (e.g., `postgresql://postgres:postgres@localhost:5432/research_copilot_db` when running the DB inside Docker but the API on your host machine).

#### C. Frontend Local `.env` (Used when running Frontend outside Docker)
Copy the frontend `.env.example` to `frontend/.env`:
```bash
cp frontend/.env.example frontend/.env
```
Fill in:
*   `VITE_API_URL`: Set to the local backend URL, typically `http://localhost:8000/api/v1`.
*   `VITE_GOOGLE_CLIENT_ID`: Match the `GOOGLE_CLIENT_ID` from the backend configuration to enable Google SSO.


### 2. Booting the Application via Docker Compose
Execute Docker Compose to build and start all containers (PostgreSQL database, FastAPI backend, React frontend):
```bash
docker-compose up --build
```
Once the logs settle:
*   **React Frontend**: accessible at `http://localhost:5173`
*   **FastAPI Backend**: accessible at `http://localhost:8000/api/v1`
*   **Swagger API Docs**: accessible at `http://localhost:8000/docs`

### 3. Running Locally (without Docker / Hybrid Setup)

If you want to run the backend and frontend services directly on your host machine but want the database running in Docker, you can spin up **only the database container**:
```bash
docker-compose up -d db
```
This binds PostgreSQL to `localhost:5432` with credentials matching the default config.

**Backend Setup** (requires Python 3.12+, `uv`, and a running PostgreSQL instance):
```bash
cd backend
uv venv
# Activate the environment:
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
uv pip install -r pyproject.toml

# Run database migrations with Alembic:
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

**Frontend Setup** (requires Node 20+):
```bash
cd frontend
npm install
npm run dev
```


---

## Testing

### Automated Test Suite
Run the full pytest test suite locally:
```bash
cd backend
.venv/Scripts/python -m pytest tests/ -v    # Windows
# or
python -m pytest tests/ -v                  # Linux / macOS (inside Docker)
```

Or inside the running Docker container:
```bash
docker-compose exec backend pytest tests/ -v
```

The test suite covers:
- ✅ Health check endpoint
- ✅ User signup (success, duplicate email, short password, invalid email)
- ✅ User login (success, wrong password, unknown email)
- ✅ Protected `/me` endpoint (authenticated and unauthenticated)
- ✅ Forgot-password flow
- ✅ Chat creation and listing
- ✅ Message history retrieval
- ✅ 404 handling for non-existent resources

### Manual Walkthrough
1. Go to `http://localhost:5173/signup` and register an account.
2. Sign in at `/login` with your credentials.
3. Chat with the copilot. Provide your preference: *"My target audience is small marketing firms."*
4. Click the **Manage Memory** button at the bottom of the sidebar. You will see that **Memori** has scanned your message, extracted that preference, and saved it in the PostgreSQL memory tables.
5. Go back to chat, start a **New Research Chat** thread, and ask: *"Who should I pitch sales automation to?"* Notice that the agent immediately remembers your target audience from the previous thread!
6. Click **Manage Memory** and click the trash can icon next to the target audience preference.
7. Return to the chat, ask the same question, and verify the agent no longer holds that preference.
8. Type *"Research Razorpay"* or click the **Research Company** action pill. Verify that search link citations are listed inside the text as inline, interactive superscript badges and summarized in a collapsible references card at the bottom of the response.
9. Click the **Connect Gmail** button in the sidebar footer and complete the authorization popup.
10. Click the **Draft Email** action pill, type a prompt to generate an outreach draft (e.g. *"Draft a cold outreach email to Razorpay CEO"*), and once generated, click **Send via Gmail** on the message card. Review the prefilled subject/body inside the popup, enter a recipient email, and click **Send Email** to deliver it!

---

## Gmail Outreach & Composio Integration

The application integrates with the **Composio SDK** to perform secure Google OAuth and send emails directly from the UI.

### Endpoints
*   `GET /api/v1/integrations/gmail/status`: Checks if the user's Gmail is currently connected.
*   `GET /api/v1/integrations/gmail/connect`: Generates the Google OAuth authorization URL.
*   `POST /api/v1/integrations/gmail/send`: Delivers the email using the connected account.
*   `POST /api/v1/integrations/gmail/parse-draft`: Structured parser that uses Gemini to extract the email subject and body from the raw agent text.

---

## Modern Citations UI

Web references are rendered dynamically similar to modern AI search engines:
*   **Superscript Badges**: Numbered badges are inserted inline (`[1] domain.com`) inside the response text.
*   **Details Hover Popover**: Hovering over any badge displays a popup containing the page title, domain, content snippet, and direct link.
*   **Collapsible Footer List**: A collapsible details panel at the bottom of the message card aggregates all source URLs in a neat list.

---

## Google Single Sign-On (SSO)

The app supports Google login using the modern **Google Identity Services (GIS)** popup flow:
*   **Token Verification**: The frontend requests a credential ID token from Google and sends it to `POST /api/v1/auth/google`.
*   **Account Linking**:
    - If a user with the Google account already exists, they are logged in directly.
    - If the email belongs to an existing password-based account, the Google account is automatically linked to it.
    - If the user is completely new, a new account is automatically registered.
*   **Configuration**:
    Add your Google Client ID to `.env`:
    ```text
    GOOGLE_CLIENT_ID=your-google-client-id-here
    ```

---

## Database Migrations with Alembic

We manage schemas natively via **Alembic**:
*   All tables (users, chats, messages, memories) are version-controlled.
*   **Running Migrations**: When booting via Docker Compose, migrations run automatically. For local host runs, run:
    ```bash
    alembic upgrade head
    ```
*   **Creating New Migrations**:
    ```bash
    alembic revision --autogenerate -m "description of changes"
    ```

---

## Telemetry & Tracing with Langfuse

To observe agent behaviors, trace graph execution latencies, inspect raw prompts, and track costs, **Langfuse** is integrated:
*   **Automatic Handlers**: All LangGraph steps and LLM calls are decorated and reported directly to your Langfuse dashboard.
*   **Configuration**:
    Provide the configuration keys in the `.env` file:
    ```text
    LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
    LANGFUSE_SECRET_KEY=your-langfuse-secret-key
    LANGFUSE_HOST=https://cloud.langfuse.com
    
    # Enable structured JSON logs for log aggregators (e.g. Datadog, CloudWatch, ELK)
    LOG_JSON=true
    ```