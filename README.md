#  Error Flow Agent

An end-to-end “error brain” for your services:

- Collects noisy production errors from your apps.
- Groups them into incidents in Postgres.
- Uses Kestra’s built-in AI Agent to summarise & prioritise.
- Lets you resolve/quiet incidents from a clean dashboard.
- Integrates Cline CLI on GitHub issues for deeper root-cause analysis.

---

Demo Video:

https://youtu.be/O0Y5JWIi8nE

---

## 1. Repository Layout

error-flow-agent/  
├── docker-compose.yml # Postgres + Kestra + backend  
├── sql/  
│ └── schema.sql  # Creates errors and error_groups tables  
├── infra/  
│ └── kestra/  
│ ├── error-intake.yml  
│ ├── group-summary-agent.yml  
│ ├── group-ai-batch.yml  
│ └── group-quiet-check.yml  
├── services/  
│ └── error-producer/  
│ └── main.py # FastAPI backend (ingestion + Kestra triggers)  
├── apps/  
│ └── dashboard/ # Next.js dashboard (Vercel-ready)  
│ └── app/page.js  
└── .github/  
└── workflows/  
└── cline-error-assistant.yml # Cline GitHub Actions integration


---

## 2. Environment Configuration

From repo root:

`cp .env.example .env`

 Edit `.env` and set:

# === Database ===

DB_HOST=localhost  
DB_PORT=5432  
DB_NAME=errorflow  
DB_USER=user  
DB_PASSWORD=pass

# === Kestra ===

KESTRA_URL=[http://localhost:8080](http://localhost:8080/)  
KESTRA_USERNAME=your-kestra-username  
KESTRA_PASSWORD=your-kestra-password  
KESTRA_TENANT=main  
KESTRA_NAMESPACE=main  
KESTRA_FLOW_ID=error-intake

# === Cline / OpenRouter (GitHub Actions) ===

OPENROUTER_API_KEY=your-openrouter-api-key  
CLINE_GITORG=your-github-org-or-username  
CLINE_GITREPO=error-flow-agent


`.env` is for local dev and is git-ignored.

---

## 3. Start Infra with Docker

From repo root:

`docker compose up -d  `
`docker ps ` # should show postgres, kestra, and error-producer


---

## 4. Initialise Database Schema

Create tables once:

`docker cp ./sql/schema.sql error-flow-agent-db-1:/schema.sql`

`docker exec -it error-flow-agent-db-1 psql -U user -d errorflow -f /schema.sql`



This creates:

### `errors` table

Holds raw error events.

Columns (simplified):

- `id SERIAL PRIMARY KEY`
- `service VARCHAR(50)`
- `error_type VARCHAR(50)`
- `message TEXT`
- `timestamp TIMESTAMP`
- `env VARCHAR(20)`
- `path TEXT`
- `trace_id VARCHAR(64)`

### `error_groups` table

Holds grouped incidents + AI enrichment.

Columns (simplified):

- `id SERIAL PRIMARY KEY`
- `cluster_key VARCHAR(100)` – e.g. `user-api:NullPointer` (unique)
- `service VARCHAR(50)`
- `error_type VARCHAR(50)`
- `title VARCHAR(200)`
- `summary TEXT`
- `status VARCHAR(20)` – `OPEN | QUIET | RESOLVED`
- `count INTEGER`
- `first_seen TIMESTAMP`
- `last_seen TIMESTAMP`
- `severity VARCHAR(20)` – `low | medium | high | unknown`
- `ai_summary TEXT` – JSON string from AI Agent
- `ai_next_steps TEXT`
- `resolution_reason TEXT`
- `resolved_at TIMESTAMP`

Verify:

`docker exec -it error-flow-agent-db-1  `
`psql -U user -d errorflow -c "\dt" `


---

## 5. Kestra Setup

Open Kestra UI:

[http://localhost:8080](http://localhost:8080/)


Log in with the credentials matching `KESTRA_USERNAME` / `KESTRA_PASSWORD`.

### 5.1 Import flows

For each file in `infra/kestra/`:

1. `error-intake.yml`
2. `group-summary-agent.yml`   # set API KEY at line-38 from [here](https://aistudio.google.com/api-keys), without ""
3. `group-ai-batch.yml`
4. `group-quiet-check.yml`

Do:

1. Click **Flows -> + Create -> Flow Code**
2. Paste YAML from the file.
3. Click **Save**.

Verify each shows:
`namespace: main  `
`id: error-intake, group-summary-agent, group-ai-batch, group-quiet-check`


### 5.2 Configure AI provider secret

In Kestra:

1. open file `group-summary-agent.yml` in kestra -> flows
2. set API KEY at line-38 from [here](https://aistudio.google.com/api-keys), without ""

`group-summary-agent` will:

- Query recent errors for a `cluster_key`.
- Ask the AI Agent to respond with JSON: `{ summary, severity, next_steps }`.
- Store that JSON into `error_groups.ai_summary`.

---

## 6. Start Dashboard (Next.js)

In a new terminal:
`cd apps/dashboard  `
`npm install  `
`npm run dev`


Dashboard lives at:
[http://localhost:3000](http://localhost:3000/)


You should see:

- **Errors** – raw events.
- **Groups** – cluster, status badge (OPEN / QUIET / RESOLVED), count, severity, AI Summary.

---

## 7. Backend Endpoints

All endpoints are served by `services/error-producer/main.py`.

### 7.1 Demo-only endpoint (random simulated errors)

`POST /errors/with-kestra`


- Picks a random error from a built‑in `ERRORS` list.
- Writes it to `errors` + `error_groups`.
- Triggers Kestra `error-intake` with `error_event` input.
- Used by the dashboard’s “Test Production” button and by `curl` in demos.

### 7.2 Real ingestion endpoint (for your own app)	

`POST /errors/custom  `

Content-Type: application/json

#Example schema

{  
"service": "user-api",  
"error_type": "NullPointer",  
"message": "Cannot read property 'x' of null at UserController.java:42",  
"path": "/v1/users/123",  
"env": "prod"  
}`


The endpoint:

- Accepts your error JSON.
- Fills `timestamp`(in UTC) and `trace_id`.
- Inserts into `errors`.
- Upserts into `error_groups` by `cluster_key = service:error_type`.
- Triggers Kestra `error-intake` with `error_event` = your payload.

This is the endpoint you should wire your **real project logs** or middleware to.

### 7.3 Group AI summary trigger (used by UI)

`POST /groups/{cluster_key}/summarize`


- Called by the dashboard when you click **Get AI summary** for a group.
- Backend triggers Kestra `group-summary-agent` with that `cluster_key`.
- After Kestra runs, `error_groups.ai_summary` and `severity` are updated.

---

## 8. Generating and Viewing Errors (from scratch)

### 8.1 Demo flow

Run the `main.py` file in `/services/error-producer`

Use the demo generator:

`curl -X POST http://127.0.0.1:8000/errors/with-kestra`


Or click **Test Production -> Refresh** on the dashboard.

You should see:

- New rows in `errors`:

`docker exec -it error-flow-agent-db-1  
psql -U user -d errorflow -c "SELECT COUNT(*) FROM errors;"`


- New groups in `error_groups`:

`docker exec -it error-flow-agent-db-1  
psql -U user -d errorflow -c "SELECT * FROM error_groups;"`


- In Kestra UI: new executions for `error-intake`.

### 8.2 AI summaries from UI

On the Groups pane:

- Click **Get AI summary** on any group.
- This calls `POST /groups/{cluster_key}/summarize`.
- Backend triggers Kestra `group-summary-agent`.
- Flow fetches recent errors, runs AI, and writes JSON to `ai_summary`.

Refresh dashboard:

- You’ll see:
- `Severity` (from AI).
- `AI Summary` text.
- Bullet list of `next_steps`.

You can also:

- Click **Resolve** to set group `status = 'RESOLVED'`.
- Let `group-quiet-check` move idle `OPEN` groups to `QUIET`.

---

## 9. Connecting Your Own Service

To use this system with your own app, send your **real** error events to `/errors/custom`.

### Example: Node/Express middleware

// In your service code  

app.use((err, req, res, next) => {  
fetch('http://127.0.0.1:8000/errors/custom', {  
method: 'POST',  
headers: { 'Content-Type': 'application/json' },  
body: JSON.stringify({  
service: 'user-api', // identify this service  
error_type: err.name || 'Error',  
message: err.stack || String(err),  
path: req.path,  
env: process.env.NODE_ENV || 'local'  
}),  
}).catch(() => {});

res.status(500).send('Internal server error');  
});

---
For other stacks (Django, etc.):

- Add a global error handler.
- On each error, POST a JSON payload with the same schema to `/errors/custom`.

Your architecture becomes:

Your service(s)  
↓  
POST /errors/custom  
↓  
Postgres (errors + error_groups)  
↓  
Kestra flows (error-intake, group-summary-agent, group-ai-batch, group-quiet-check)  
↓  
Dashboard (Next.js)


---

## 10. Cline GitHub Integration (Optional)

This repo ships a GitHub Actions workflow (`.github/workflows/cline-error-assistant.yml`) based on the official Cline CLI GitHub integration sample.[web:289]

### 10.1 Configure secrets and variables

In your GitHub repo:

1. Go to **Settings → Environments → New environment** and name it `cline-actions`.
2. Inside `cline-actions` environment, add secret:
   - `OPENROUTER_API_KEY` – your OpenRouter (or other provider) key.
3. In **Settings -> Variables -> Repository variables**, add:
   - `CLINE_GITORG` – your GitHub user/org.
   - `CLINE_GITREPO` – repo name that contains `git-scripts/analyze-issue.sh`. 
   
   (for example in this repo, ORG - "Ujjwal-Singh-20", REPO - "error-flow-agent")

Make sure:

- `.github/workflows/cline-error-assistant.yml` exists.
- `git-scripts/analyze-issue.sh` exists and is executable.

### 10.2 Usage

1. Create a GitHub issue (e.g., paste an error message from the dashboard).
2. Comment on the issue:

`@cline what's causing this error?`


3. GitHub Actions will:
   - Detect the `@cline` mention.
   - Spin up a Cline CLI instance in CI.
   - Run `git-scripts/analyze-issue.sh` against your repo and the issue URL.
   - Post an automated comment with:
     - Root cause hypothesis.
     - Related files and commits.
     - Suggested next steps.

This complements the Kestra AI summaries (which focus on error patterns) with **repo-level root-cause analysis** inside GitHub.

---

## 11. Resetting Everything

To start from a clean slate:

#### Stop and remove containers + volumes

`docker compose down -v`

#### Start fresh

`docker compose up -d`

#### Recreate tables

`docker cp ./sql/schema.sql error-flow-agent-db-1:/schema.sql`

`docker exec -it error-flow-agent-db-1 psql -U user -d errorflow -f /schema.sql`

## Kestra flows:

### - If using a persistent volume, flows remain.

### - Otherwise re-import YAMLs in infra/kestra/.


Then:

1. Start dashboard (`npm run dev` in `apps/dashboard`).  
2. Start main.py from /services/error-producer
3. Generate errors (`/errors/with-kestra` or `/errors/custom`).  
4. Use the dashboard to view groups, run AI summaries, and resolve incidents.

---
