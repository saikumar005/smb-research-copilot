# M32 Fullstack + AI Take-Home Project Implementation Plan

## Project Title
**Business Research Copilot** — a production-style, SMB-focused AI web application that allows users to sign up, log in, chat with an LLM, retain context during a chat session, research companies on the web using tools, and generate structured business outputs such as company briefs, outreach drafts, and follow-up tasks.

## Purpose
This project is designed to satisfy the M32 take-home prompt while optimizing for speed, stability, product sense, and clean engineering execution. M32’s prompt explicitly requires a functional chatbot with tools, a web UI, signup/login/logout, retained context in a chat session, and encourages creativity, business usefulness, rapid prototyping, and bonus integrations such as Google login and Composio.[cite:20][cite:23][cite:30]

The proposed product is intentionally scoped for a high-quality implementation within a constrained build window. It targets small and medium-sized business users, which aligns with M32’s stated customer profile of CEOs, business owners, and heads of department who may not be highly technical.[cite:20][cite:23]

## Product Concept
The application acts as an SMB-facing business copilot. A user can ask the assistant to research a company, summarize public information, suggest business opportunities, draft a professional outreach email, and produce follow-up action items based on the conversation and retrieved sources.[cite:20][cite:23]

This concept is stronger than a generic chatbot because it demonstrates:
- Real tool use.
- Business utility.
- Product thinking.
- Structured outputs beyond plain chat.
- A credible path to future integrations with external tools such as email, calendar, CRM, and task platforms through Composio.[cite:30][cite:37][cite:41]

## Core Requirements
The implementation must clearly satisfy these requirements from the interview prompt:

- Functional chatbot powered by an LLM with tool usage.[cite:20]
- Web-based user interface.[cite:20]
- User signup, login, and logout.[cite:20]
- Ability for users to chat with the assistant.[cite:20]
- Chat context retention within a session, so follow-up questions reference earlier conversation correctly.[cite:20]
- A real, usable product rather than a toy demo or raw framework prototype.[cite:20]
- Clean product decisions for non-technical business users.[cite:20]

## Recommended Tech Stack
The implementation should use the following stack to match both the user’s strengths and the requested interview framing:

| Layer | Recommended Choice | Notes |
|---|---|---|
| Frontend | React | Fast to build, flexible UI, strong ecosystem |
| Frontend styling | Tailwind CSS or clean modular CSS | Use a polished custom UI, avoid default framework look |
| Backend API | Python + FastAPI | Best fit for rapid AI backend development |
| Database | PostgreSQL | Reliable relational persistence for users, chats, messages |
| ORM | SQLAlchemy | Production-standard ORM for Python |
| Migrations | Alembic | Clean schema management |
| Auth | JWT-based auth | Email/password auth first, optional Google OAuth later |
| AI layer | Modern agent-building format | Prefer LangGraph or lightweight tool-routing architecture; LangChain also acceptable because M32 explicitly prefers modern agent frameworks.[cite:20] |
| Containerization | Docker + Docker Compose | Required for clean local setup and reproducibility |
| Reverse proxy | Optional Nginx in deployment | Only if needed for production-style hosting |
| Deployment | Render or Vercel + Render | M32 specifically recommends free deployment platforms such as Render or Vercel.[cite:20] |

## Non-Negotiable Engineering Requirements
The build instructions given to Antigravity should clearly enforce these technical expectations:

- Use **Python**, **FastAPI**, **PostgreSQL**, **React**, **Docker**, **SQLAlchemy**, and **Alembic**.
- Use a clean, production-grade backend folder structure.
- Use environment variables for all secrets and API keys.
- Provide a clean and professional README.
- Use modern agent-building patterns rather than a single hardcoded LLM call path.
- Persist chats and messages in PostgreSQL.
- Keep API and frontend separated cleanly.
- Ensure the application can run locally with Docker Compose.
- Keep code original and written from scratch, except for approved libraries and SDKs, because the interview prompt explicitly forbids passing off near-complete repos as original work.[cite:20]

## Functional Scope
The project should be intentionally scoped to maximize quality and completion probability.

### Must Have
- Signup page.
- Login page.
- Logout functionality.
- Protected chat application page.
- Chat thread persistence.
- Session context retention.
- Tool-based company research workflow.
- Research answer with source links/citations.
- Structured actions:
  - Research company.
  - Draft outreach email.
  - Create follow-up tasks.
- Clean error handling and loading states.
- Dockerized local development.
- Clear README and setup instructions.

### Nice to Have
- Multiple chat threads per user.
- User profile page.
- Prompt starter cards.
- Conversation title generation.
- Rolling chat summary memory.
- Theme toggle.

### Bonus Only If Time Allows
- Google login, because M32 explicitly lists identity provider login as bonus points.[cite:20]
- Composio integration, because M32 explicitly lists Composio usage as bonus points.[cite:20][cite:30][cite:37]
- Demo workflow that pushes generated tasks to an external app.

## Product Behavior
The application should be framed as a business assistant, not a generic AI chat playground.

Example user workflows:
1. User signs up and logs in.
2. User starts a chat and asks: “Research Razorpay and suggest an outreach angle for a sales automation product.”
3. Backend triggers web search and page retrieval tools.
4. LLM synthesizes findings into a company brief.
5. User clicks “Draft Outreach Email.”
6. Assistant creates a concise business email based on prior context.
7. User clicks “Create Follow-up Tasks.”
8. Assistant outputs a structured checklist of next steps.

This flow demonstrates chat, memory, tool use, business value, and product design in a single demo.[cite:20][cite:23]

## Modern Agent-Building Requirement
The implementation should explicitly mention the use of a modern agent-building pattern in the README and architecture notes.

Recommended approach:
- Use **LangGraph** for tool orchestration and structured flows, or
- Use a lightweight internal agent router pattern with:
  - intent detection,
  - tool selection,
  - tool execution,
  - final response synthesis.

If LangGraph is used, keep the graph simple and production-friendly:
- User input node.
- Intent/router node.
- Tool execution node.
- Response synthesis node.
- Memory/context injection step.

This is sufficient to demonstrate familiarity with contemporary agent architectures without overcomplicating the project. M32 explicitly says it strongly prefers frameworks like LangChain, LangGraph, Phidata, or CrewAI.[cite:20]

## Backend Architecture
The backend should follow a clean layered architecture.

### Suggested Backend Responsibilities
- **API layer**: FastAPI routes and request/response schemas.
- **Service layer**: business logic, chat orchestration, auth logic.
- **Agent layer**: intent routing, tool orchestration, LLM prompt control.
- **Tool layer**: web search, page fetch, summarization helpers.
- **Persistence layer**: SQLAlchemy models and repository logic.
- **Infrastructure layer**: settings, database connection, logging, security.

### Suggested Backend Folder Structure
```text
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py
│   │   │   │   ├── chats.py
│   │   │   │   ├── messages.py
│   │   │   │   └── actions.py
│   │   │   └── router.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── models/
│   │   ├── user.py
│   │   ├── chat.py
│   │   ├── message.py
│   │   └── base.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── message.py
│   │   └── action.py
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── chat_repository.py
│   │   └── message_repository.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── chat_service.py
│   │   ├── memory_service.py
│   │   └── action_service.py
│   ├── agents/
│   │   ├── graph.py
│   │   ├── router.py
│   │   ├── prompts.py
│   │   └── state.py
│   ├── tools/
│   │   ├── web_search.py
│   │   ├── page_fetch.py
│   │   └── research_formatter.py
│   ├── utils/
│   │   └── helpers.py
│   └── main.py
├── alembic/
├── alembic.ini
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Frontend Architecture
The frontend should optimize for clarity and simplicity for non-technical business users.

### Suggested Frontend Pages
- `/signup`
- `/login`
- `/chat`

### Suggested Frontend Components
- Auth form.
- Protected route wrapper.
- Sidebar with chats.
- Main chat panel.
- Message list.
- Message composer.
- Quick action buttons.
- Source links panel.
- Loading state.
- Error toast or inline alert.

### Suggested Frontend Folder Structure
```text
frontend/
├── src/
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── auth/
│   │   ├── chat/
│   │   ├── layout/
│   │   └── ui/
│   ├── hooks/
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Signup.tsx
│   │   └── Chat.tsx
│   ├── routes/
│   ├── store/
│   ├── types/
│   ├── utils/
│   ├── App.tsx
│   └── main.tsx
├── public/
├── Dockerfile
├── package.json
└── .env.example
```

## Database Design
Use PostgreSQL with SQLAlchemy models and Alembic migrations.

### Minimum Tables
- **users**
  - id
  - name
  - email
  - hashed_password
  - created_at
  - updated_at

- **chats**
  - id
  - user_id
  - title
  - summary
  - created_at
  - updated_at

- **messages**
  - id
  - chat_id
  - role
  - content
  - metadata_json
  - created_at

Optional future tables:
- tool_runs
- connected_accounts
- artifacts

## API Design
Recommended minimum endpoints:

### Auth
- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### Chats
- `GET /api/v1/chats`
- `POST /api/v1/chats`
- `GET /api/v1/chats/{chat_id}/messages`
- `POST /api/v1/chats/{chat_id}/messages`

### Actions
- `POST /api/v1/actions/run`

Example request for structured action execution:
```json
{
  "chat_id": 1,
  "mode": "research",
  "message": "Research HubSpot and suggest an outreach angle for a process automation platform"
}
```

Supported modes:
- `research`
- `email_draft`
- `task_list`

## Session Memory Requirement
The chatbot must retain context during a single chat session because that is explicitly required by the interview prompt.[cite:20]

Recommended implementation:
- Persist all messages to PostgreSQL.
- Pass the last N messages to the LLM for conversational continuity.
- Optionally maintain a rolling summary in the `chats.summary` field to reduce token usage and improve continuity.
- Always include the chat summary plus recent turns when composing the final prompt.

This ensures the assistant can correctly answer follow-up questions such as “What is my name?” after earlier user context is provided.[cite:20]

## Tooling Requirement
The tool layer should be one of the clearest strengths of the submission.

### Required Tool Workflow
- Search the web for relevant public information.
- Retrieve top source pages.
- Extract meaningful content.
- Summarize into business-relevant output.
- Return source links in the UI.

### Output Structure for Research Mode
Recommended response sections:
- Company overview.
- Key findings.
- Likely priorities or business pain points.
- Suggested outreach angle.
- Sources.

This makes the chatbot feel practical and differentiated instead of generic.[cite:20][cite:23]

## UI and Product Requirements
The UI should reflect the intended audience.

### Design Principles
- Clear and calm layout.
- Large readable text.
- Minimal cognitive load.
- Obvious actions.
- No developer-centric terminology.
- Clean empty states and loading states.

### Recommended Action Labels
- Research company
- Draft outreach email
- Create follow-up tasks

The interface should not feel like a raw prompt playground. It should feel like a lightweight business tool.[cite:20]

## Docker and Local Development Requirements
The application should include:
- `Dockerfile` for frontend.
- `Dockerfile` for backend.
- `docker-compose.yml` for full local stack.
- PostgreSQL service in Docker Compose.
- Clear local startup instructions in README.

Suggested services in Docker Compose:
- `frontend`
- `backend`
- `db`

Optional:
- `nginx`

## Security and Production Hygiene
Even for a take-home project, these production-grade details should be included:

- Password hashing using a secure algorithm.
- JWT signing via environment variable secret.
- `.env.example` without real secrets.
- API key safety and no secret leakage in repository.
- CORS configured correctly.
- Basic request validation using Pydantic.
- Structured logging.
- Health check endpoint.
- Error handling with meaningful responses.
- Migration-based schema management with Alembic.

This is especially important because the deliverables require a public GitHub link with secrets removed.[cite:20]

## Testing and Quality Expectations
Minimum quality bar:
- API smoke tests for auth and chat endpoints.
- Manual E2E verification of signup → login → chat → research → follow-up action flow.
- Linting and formatting.
- Stable Docker boot.

Optional but valuable:
- Unit tests for service layer.
- Integration tests for the action workflow.

## README Requirements
The README should be clean, recruiter-friendly, and easy to scan.

### Required README Sections
- Project title.
- What the product does.
- Why this use case was chosen.
- Feature list.
- Tech stack.
- Architecture overview.
- Folder structure.
- Local setup instructions.
- Docker usage instructions.
- Environment variables.
- API overview.
- Tradeoffs and future improvements.
- Deployment link or demo video link.

### Important README Messaging
The README should explicitly state:
- The project was built from scratch for the take-home.
- The app is designed for SMB business users.
- The assistant uses tools for company research and structured business actions.
- The architecture follows modern agent-building patterns.
- The backend uses FastAPI, PostgreSQL, SQLAlchemy, and Alembic with a production-style structure.

## Suggested Delivery Plan for Antigravity
Antigravity should implement in this sequence:

1. Initialize monorepo with `frontend/` and `backend/`.
2. Set up FastAPI app, PostgreSQL, SQLAlchemy, Alembic, Docker, Docker Compose.
3. Implement auth flow end to end.
4. Implement chat models, routes, persistence, and UI.
5. Add LLM response generation with message history.
6. Add agent router / LangGraph workflow.
7. Implement research tool flow.
8. Add structured action modes: research, email_draft, task_list.
9. Add frontend polish, loading states, and source display.
10. Add README, screenshots, `.env.example`, and deployment setup.

## Acceptance Criteria
The project should be considered complete when all of the following are true:

- A user can sign up, log in, and log out.
- A logged-in user can create or open a chat.
- Messages persist in PostgreSQL.
- The chatbot retains session context.
- The chatbot can perform web research through tools.
- The chatbot returns structured business outputs.
- The frontend is clean and business-friendly.
- The project runs locally through Docker Compose.
- The repository includes a professional README.
- Secrets are removed and `.env.example` is provided.
- The app is deployable to a public URL or has a clear demo video fallback.[cite:20]

## Future Enhancements
If additional time becomes available, these enhancements can be added after the core implementation:

- Google OAuth login.[cite:20]
- Composio integration for Gmail, Google Calendar, Slack, CRM, or task tools.[cite:20][cite:30][cite:41]
- File upload and document-aware chat.
- Rich artifact panel for generated outputs.
- Conversation titles generated automatically.
- Admin analytics view.
- Team workspaces and shared chats.

## Final Instruction
Antigravity should optimize for **stability, clarity, and real product usefulness** rather than trying to impress with too many unfinished features. M32’s prompt strongly suggests that sensible execution, rapid prototyping, autonomy, and business-oriented product judgment matter as much as the presence of AI itself.[cite:20][cite:23]
