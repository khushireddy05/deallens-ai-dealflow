# DealLens

### AI-powered dealflow triage and enrichment

**Turn inbound startup pitches into structured, review-ready opportunities.**

Python · FastAPI · React · PostgreSQL · OpenAI · Docker

An AI workflow that does the **first pass** on inbound startup pitches for an investment team.

It takes a raw pitch (an email or form message), looks up the company's website, uses an LLM to pull out structured facts, screens the result against a configurable investment thesis, merges it into a CRM-style database without creating duplicates, and shows the outcome in a React UI for a human to review.

**It does not make investment decisions.** It prepares and pre-screens. A person sets the final status.

- Concept and background: [automated_dealflow_triage_enrichment_project.md](automated_dealflow_triage_enrichment_project.md)
- What was built and the requirement IDs: [requirement.md](requirement.md)
- Complete context for a new ChatGPT conversation: [CHATGPT_PROJECT_CONTEXT.md](CHATGPT_PROJECT_CONTEXT.md)

```mermaid
flowchart LR
    A[Inbound pitch] --> B[Store raw submission]
    B --> C[Website enrichment]
    C --> D[Structured LLM extraction]
    D --> E[Validate and screen]
    E --> F[Deduplicate and save]
    F --> G[Human review in React]
    B -.-> H[Processing timeline]
    C -.-> H
    D -.-> H
    E -.-> H
    F -.-> H
```

## Highlights

- **Structured extraction:** converts free-form pitches into validated company data.
- **Explainable screening:** evaluates a configurable investment thesis with explicit reasons.
- **CRM deduplication:** matches company domains and preserves existing information.
- **Review workflow:** inspect opportunities, processing history, failures, and retries.
- **Key-free demo:** replay bundled examples without calling an LLM API.


## Quick start

Requires Docker.

```bash
cp .env.example .env
# For a key-free demo, set LLM_PROVIDER=replay and ENRICHMENT_ENABLED=false in .env.
# For live extraction, add your OPENAI_API_KEY.
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:5173 | The UI |
| http://localhost:8000/docs | Interactive API docs |
| `localhost:5432` | Postgres (user/password/db: `dealflow`) |

On first start the database is filled with 7 demo opportunities so the UI is not empty. To start clean: `docker compose down -v`.

### No API key? Use demo mode

Set `LLM_PROVIDER=replay` in `.env`. The "LLM" then replays recorded answers for the bundled sample pitches (the **Load sample** menu on the Submit page). The replay extractor makes no API calls. Set `ENRICHMENT_ENABLED=false` as well to disable website requests. It only recognises those samples; any other text fails with a message saying so. For real pitches, use `LLM_PROVIDER=openai`.

### Using OpenAI

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini      # any small chat model that supports structured outputs
```

The model name is configuration, not code. **Pitch text is sent to OpenAI**, so do not submit confidential deal material unless that is acceptable for your organisation. If the key is missing, items fail cleanly with a clear message and can be retried after you add it.

## Try it (what you should see)

| Do this on **Submit pitch** | Expected |
|---|---|
| Load sample **"Clean pitch: ABC AI"** and Process | New company + opportunity, verdict **Pass** |
| Process the **same** text again | "Already processed". Nothing new is created |
| Load **"Same company again: ABC AI follow-up"** and Process | Still **one** company, now with 2 pitches (see Companies) |
| Load **"Gibberish"** and Process | Lands in **Failures**; nothing invalid reaches the CRM. Retry is available |
| Load **"No company name given"** | Fails validation, in Failures |
| Load **"No website: ABC Robotics"** | Saved, flagged **Needs review** (matched by name only) |
| Load **"Prompt injection attempt"** | Still **Fail**: the verdict comes from rules, not from the model's say-so |
| Open an opportunity, click **Rejected** | Status persists after refresh. The automated verdict is unchanged |

Sample company websites use the reserved `.example` domain on purpose: they never resolve, so the enrichment step fails harmlessly and you can see that failure in the timeline without any real site being contacted.

## Running the tests

```bash
docker compose run --rm backend pytest     # uses a separate throwaway database
docker compose run --rm frontend npm test
```

Tests never call OpenAI or the internet: the LLM is replaced by recorded answers and enrichment by fakes. They also run without Docker (SQLite) if you have Python 3.11+: `cd backend && pip install -r requirements.txt && pytest`.

## How it works

### Pipeline (`backend/app/pipeline.py`)

1. **Store** the raw pitch. It is committed before anything else, so a crash never loses it.
2. **Enrich**: if the pitch mentions a website, fetch its homepage (HTTPS only, public addresses only). Failure is logged and skipped, never fatal.
3. **Extract**: the LLM returns a fixed JSON schema (OpenAI structured outputs). Unknown values must be `null`. Invalid output is retried a bounded number of times, then the item is marked failed.
4. **Validate**: a company name and a description or product are required before anything is written.
5. **Screen**: rule-based check against `backend/app/thesis.json` (AI-related, country, stage). Any mismatch is `fail`; missing information is `maybe`; otherwise `pass`. Each verdict lists its reasons. Screening also uses what the CRM already knows about that company, so a short follow-up email isn't judged in isolation.
6. **Deduplicate + save**: match on normalized domain; without a domain, on exact normalized name (flagged **Needs review**). Updates never blank out existing values.

Every step is recorded in `processing_log`, shown as the timeline on the opportunity page.

### Reliability

- **Idempotent submit**: the same pitch (ignoring case and whitespace) maps to one row, enforced by a unique key in the database. Resubmitting does no work.
- **Safe retry**: a failed item can be retried from the UI or `POST /opportunities/{id}/retry`. Steps that already succeeded (enrichment, extraction) are reused, not repeated.
- **Race-safe dedup**: the unique domain constraint decides, and the loser of a concurrent insert falls back to updating the winner.
- **Human decision kept separate** from the automated verdict.

### The CRM

`docker compose` runs Postgres; the FastAPI backend is the CRM API. The pipeline only talks to the `CRMClient` interface (`backend/app/crm/base.py`), and `PostgresCRM` implements it. A different CRM such as Attio would be one more class implementing that interface; the pipeline would not change. There is no Attio integration in this repo.

### API summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/opportunities` | Submit a pitch and run the pipeline (201 new, 200 if already seen) |
| `GET` | `/opportunities` | List; filters `verdict`, `status`, `processing_state`, `q`, `limit`, `offset` |
| `GET` | `/opportunities/{id}` | Detail with extracted data, screening reasons and timeline |
| `PATCH` | `/opportunities/{id}` | Set review status (`new`, `in_review`, `passed`, `rejected`) |
| `POST` | `/opportunities/{id}/retry` | Retry a failed item |
| `GET` | `/failures` | Failed items |
| `GET` / `PUT` | `/companies`, `/companies/assert` | List; upsert by domain |
| `GET` | `/samples`, `/thesis`, `/health` | Sample pitches, thesis in force, liveness |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `replay` (demo mode) |
| `OPENAI_API_KEY` | – | Required for `openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model used for extraction |
| `ENRICHMENT_ENABLED` | `true` | Fetch the company's own website for context |
| `SEED_ON_START` | `true` in compose | Load demo data into an empty database |
| `LLM_TIMEOUT` / `LLM_MAX_ATTEMPTS` | `30` / `3` | Per-call timeout (s) and bounded retries |
| `ENRICHMENT_TIMEOUT` | `5` | Website fetch timeout (s) |
| `THESIS_PATH` | `backend/app/thesis.json` | Investment criteria |

### Changing the thesis

Edit [backend/app/thesis.json](backend/app/thesis.json): AI keywords, the list of accepted countries, and accepted funding stages. **The bundled thesis (AI, Europe, pre-seed to Series A) is a placeholder** to demonstrate the flow, not a real fund's criteria.

## Project layout

```
backend/            FastAPI app, pipeline, CRM layer, tests
  app/pipeline.py     the workflow
  app/crm/            CRMClient interface + Postgres implementation
  app/llm/            OpenAI extractor, replay (demo/test) extractor
  app/enrichment/     website fetcher with SSRF guards
  app/screening.py    thesis rules
  data/               sample pitches with recorded LLM answers
frontend/           React (Vite) UI and tests
db/init.sql         creates the throwaway test database
docker-compose.yml  db + backend + frontend
```

## Keeping credentials private

Copy `.env.example` to `.env` and keep real credentials only in your local environment. The example contains no API key. Git ignores `.env` variants, private key files, local databases, logs, dependencies, and build output; Docker contexts also exclude local environment files and databases.

Never put secrets in frontend code or `VITE_*` variables: those values can be included in browser assets. The OpenAI key belongs only on the backend. If a credential is ever committed or shared, revoke it and replace it; deleting the file does not remove it from Git history.

## Security notes

- Pitch text and website content are **untrusted**. They are passed to the model as delimited data with an instruction not to follow anything inside them, and the model can only return values for a fixed schema. Verdicts come from deterministic rules, so a pitch cannot talk its way to `pass`.
- The website fetcher requests a URL taken from untrusted text, so it guards against server-side request forgery: HTTPS only, every host and redirect hop must resolve to public IPs, redirects are capped, response size is capped. **Known limit:** DNS is resolved once to check and again to connect, so a DNS-rebinding attacker could race it. If you process hostile input, also restrict egress at the network level.
- The UI renders pitch text as plain text, never as HTML.
- Compose binds ports to `127.0.0.1` and uses throwaway dev credentials. Change them, and add authentication, before exposing this anywhere.

## Limitations

- No authentication or users; it is meant to run locally.
- Pitches are submitted by hand. There is no mailbox or form-provider integration yet.
- The database schema is created with `create_all`; there are no migrations.
- Processing runs inside the request. That is fine for a demo; a queue and worker would be the next step for volume.
- Only the company's own homepage is used for enrichment. No third-party data provider is wired in.
- Name-only dedup can merge two different companies that share a name. Those merges are flagged **Needs review**.
- The frontend runs the Vite dev server in Docker. It is not a production build.
