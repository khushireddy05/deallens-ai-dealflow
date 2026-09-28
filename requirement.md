# Requirements — DealLens: AI-Powered Dealflow Triage and Enrichment

Status: **v1 implemented.** Requirement IDs below are referenced from the code and tests. Where the build differs from the original draft, the text below has been updated (see section 12). Setup and usage are in [README.md](README.md). Concept background lives in [automated_dealflow_triage_enrichment_project.md](automated_dealflow_triage_enrichment_project.md).

## 1. Purpose

An investment team receives startup pitches through unstructured channels (email, forms). Today, someone reads each one, researches the company, extracts key facts, checks fit against the fund's thesis, and types the result into a CRM.

This project automates that **first pass**. It ingests a pitch, enriches it, extracts structured fields with an LLM, screens it against a configurable thesis, deduplicates against existing companies, and stores the result in a CRM-style database. A React UI lets the team review the results.

**The system does not make investment decisions.** It prepares and pre-screens opportunities. A human sets the final status.

## 2. Scope

### In scope (v1)
- Manual pitch submission through the UI and API (simulates an inbound email or form).
- Enrichment from the company website, behind a pluggable provider interface.
- LLM extraction into a validated schema (OpenAI API, small model).
- Thesis screening with human-readable reasons.
- Company deduplication and idempotent re-processing.
- A Postgres-backed CRM API (companies, opportunities, processing log).
- A React frontend for review and status changes.
- Docker Compose for running and testing everything.

### Out of scope (v1)
- Connecting to a real mailbox (Gmail/Outlook) or form provider.
- Making the final investment decision.
- A full CRM (contacts, email sync, sales pipelines, reporting).
- Authentication and multi-user permissions.
- Production deployment and hosting.

### Future
- `AttioCRM` adapter behind the same `CRMClient` interface.
- Real mailbox ingestion, additional enrichment providers, background worker/queue.

## 3. Users

| User | Needs |
|---|---|
| Investment team member | See processed opportunities, understand why each was screened the way it was, set a review status |
| Developer / operator | Run the stack locally, see failures, retry failed items, swap components (LLM, enrichment, CRM) |

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL 16 |
| Frontend | React 18 (Vite), React Router 7 |
| LLM | OpenAI API, small model. Model name set by `OPENAI_MODEL` env var, not hardcoded. `LLM_PROVIDER=replay` is a no-network demo mode that replays recorded answers for the bundled samples |
| Runtime | Docker Compose (`db`, `backend`, `frontend`) |
| Tests | pytest (backend), Vitest (frontend) |

## 5. Functional requirements

### 5.1 Ingestion
- **FR-1** The API accepts a pitch with `source`, `sender`, `subject`, `body`, `received_at`.
- **FR-2** Empty or whitespace-only bodies are rejected with a clear error.
- **FR-3** Each pitch gets an idempotency key: a hash of the normalized source, sender, subject, and body.

### 5.2 Enrichment
- **FR-4** If a website/domain is known, the system fetches public information about the company from it.
- **FR-5** Enrichment goes through an `EnrichmentProvider` interface so providers can be swapped or mocked.
- **FR-6** Enrichment failure (timeout, 404, blocked) must not abort processing. The pipeline continues with the pitch text alone, and the failure is logged.

### 5.3 LLM extraction
- **FR-7** The LLM turns the pitch text (plus enrichment data) into a structured object with these fields:
  `company_name, domain, founders[], location, country, industry, product, funding_stage, funding_amount, description`. `country` is needed so the thesis can check geography reliably; `funding_stage` is one of a fixed set (`pre-seed, seed, series-a, series-b, series-c-plus, growth, unknown`).
- **FR-8** Extraction uses OpenAI structured outputs (strict JSON schema), and the reply is validated again with Pydantic before it is trusted.
- **FR-9** Unknown values are `null`. The model must not invent data to fill a field.
- **FR-10** Output that fails schema validation is retried a bounded number of times. If it still fails, the item is marked `failed` and nothing is written to the CRM.

### 5.4 Screening
- **FR-11** Screening criteria live in a config file, not in code.
- **FR-12** The default (placeholder) thesis is: AI-related, European location, pre-seed to Series A. This is an assumption to be replaced with the real criteria.
- **FR-13** Screening returns a `verdict` (`pass` / `maybe` / `fail`), a list of `reasons`, and which criteria matched.
- **FR-14** Missing information yields `maybe` with a reason, not `fail`. A mismatch on any criterion yields `fail`, even if other data is missing.
- **FR-14a** Screening judges the pitch together with what the CRM already knows about the matched company: fields the pitch left empty are filled from the existing company record (the pitch's own values win). This stops a short follow-up email from being downgraded to `maybe` for facts already on file. The timeline notes when this happened.

### 5.5 Validation
- **FR-15** Required fields are checked before any CRM write: at minimum `company_name`, and a non-empty `description` or `product`.
- **FR-16** Domains are normalized (lowercase, scheme and `www.` stripped) before matching or storing.

### 5.6 Deduplication and CRM write
- **FR-17** A company is matched by normalized `domain`.
- **FR-18** If there is no domain, match by exact normalized company name. A name-only match is flagged `needs_review`, and so is a newly created company with no domain, so a human can check for wrong merges or duplicates. If a later pitch supplies the domain, it is adopted by the earlier domain-less record and the flag is cleared.
- **FR-19** Company writes are an upsert: create if new, update if it exists. Updates must not overwrite existing values with null, empty or `unknown` values.
- **FR-20** Every pitch creates one `opportunity` linked to its company. The same company can have many opportunities.

### 5.7 Idempotency and error handling
- **FR-21** Submitting the same pitch twice returns the existing opportunity and creates no duplicates in `companies` or `opportunities`.
- **FR-22** Each pipeline step (`received, enriched, extracted, validated, screened, saved`) is recorded in `processing_log` with status and error text.
- **FR-23** A failed run can be retried. Retry resumes safely: it does not duplicate CRM records or repeat side effects that already succeeded.
- **FR-24** External calls (OpenAI, website fetch) have timeouts and bounded retries with backoff.
- **FR-25** No unhandled failure loses the pitch. The raw input is stored before processing begins. Unexpected exceptions are recorded as a failure with only the exception type shown to users; details go to the server log.
- **FR-25a** The enrichment fetcher is hardened against server-side request forgery (the domain comes from untrusted text): HTTPS only, all resolved addresses must be public (checked for every redirect hop), redirects capped, response size capped.

### 5.8 Human review
- **FR-26** A user can set an opportunity's status to `new`, `in_review`, `passed`, or `rejected`.
- **FR-27** Status changes persist and are visible after a refresh.
- **FR-28** Changing a status never alters the screening verdict. Human decision and automated verdict are stored separately.

## 6. Data model

**companies**
`id, name, normalized_name, domain (unique, nullable), website, location, country, industry, product, funding_stage, description, needs_review, created_at, updated_at`

**opportunities**
`id, company_id → companies (null until saved), source, sender, subject, raw_body, received_at, extracted (jsonb), enrichment (jsonb), verdict, screening_reasons (jsonb), criteria_matched (jsonb), status (human review), processing_state (pending / processing / completed / failed), failed_step, error, idempotency_key (unique), created_at, updated_at`

**processing_log**
`id, opportunity_id, step, status (ok/failed/skipped), message, created_at`

Constraints that enforce the requirements at the database level:
- `companies.domain` unique, for dedup.
- `opportunities.idempotency_key` unique, for idempotency.

## 7. API (CRM layer)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/companies` | List companies (filter by `domain`) |
| `PUT` | `/companies/assert` | Upsert a company by domain |
| `GET` | `/opportunities` | List, with filters for verdict, status, search |
| `GET` | `/opportunities/{id}` | Detail, including processing log |
| `POST` | `/opportunities` | Submit a pitch and run the pipeline (idempotent) |
| `PATCH` | `/opportunities/{id}` | Set review status |
| `POST` | `/opportunities/{id}/retry` | Retry a failed run |
| `GET` | `/failures` | List failed items |
| `GET` | `/samples` | Bundled sample pitches for the UI's "Load sample" menu |
| `GET` | `/thesis` | The screening criteria currently in force |
| `GET` | `/health` | Liveness check |

The pipeline talks to the CRM through a `CRMClient` interface. `PostgresCRM` is the v1 implementation.

## 8. Frontend requirements

- **FE-1 Submit Pitch:** form for source, sender, subject, body, plus a "Load sample" dropdown of test pitches.
- **FE-2 Opportunities:** table with company, location, stage, verdict, status, received date. Filters for verdict and status, plus text search.
- **FE-3 Opportunity detail:** extracted fields, screening reasons, raw pitch, step timeline, and status buttons.
- **FE-4 Companies:** deduplicated list with opportunity count per company.
- **FE-5 Failures:** failed items with error message and Retry button.
- **FE-6** Loading, empty, and error states on every screen.

## 9. Non-functional requirements

- **NFR-1** `docker compose up --build` starts the full stack with no manual setup beyond a `.env` file.
- **NFR-2** Secrets (`OPENAI_API_KEY`) come from environment variables and are never committed. `.env.example` documents them.
- **NFR-3** Tests never call the real OpenAI API or the open internet. The LLM and enrichment are faked.
- **NFR-4** Components behind interfaces (LLM client, enrichment provider, CRM client) so each is replaceable.
- **NFR-5** Structured logs for every pipeline step, without logging secrets.
- **NFR-6** Pitch text is sent to OpenAI. The README must state this so users know before submitting real data.

## 10. Test data

About 15–20 synthetic pitches in a fixtures file, including:

| Case | Verifies |
|---|---|
| Clean pitch with website, in thesis | Happy path: `pass` |
| Pitch with no website | FR-6, FR-18, missing-data handling |
| Non-AI or non-European startup | `fail` with reasons |
| Ambiguous or sparse pitch | `maybe` (FR-14) |
| Same company pitched on two days | Dedup: one company, two opportunities |
| Exact same email submitted twice | Idempotency (FR-21) |
| Rambling or garbage text | Invalid output handling (FR-10) |
| Enrichment failure | FR-6 |
| CRM write failure, then retry | FR-23 |

## 11. Acceptance criteria

1. `docker compose up --build` serves the UI on `localhost:5173` and API docs on `localhost:8000/docs`.
2. Submitting a clean in-thesis pitch produces one company, one opportunity, verdict `pass`, visible in the UI.
3. Submitting the identical pitch again creates no new rows.
4. Submitting a different pitch from the same company creates one company with two opportunities.
5. A gibberish pitch appears under Failures, and no invalid data reaches `companies`.
6. Setting a status in the UI survives a page refresh.
7. `docker compose run --rm backend pytest` passes with no network access and no API key.

## 12. Delivery status and changes from the draft

All three planned phases (CRM layer and UI, pipeline, hardening) are implemented. Changes made while building, and why:

| Change | Reason |
|---|---|
| Added `country` to the extraction schema | "Berlin" cannot be matched against a list of countries reliably; the model infers the country only when unambiguous |
| Screening uses the existing company record to fill gaps (FR-14a) | Found by the sample data: a follow-up email without a location screened as `maybe` although the company was already known to be in Germany |
| Name-only merges are flagged `needs_review` (FR-18) | Two companies can share a name; merges made without a domain should be visible |
| Enrichment only triggers on a website found in the pitch text, not on the sender's email domain | The sender may be an intermediary; using their domain could mis-identify the company |
| `processing_state` and `failed_step` added to opportunities | Keeps pipeline state apart from the human review `status` (FR-28) |
| `LLM_PROVIDER=replay` demo mode | Lets anyone run the UI and try every flow without an API key |
| Sample company sites use the reserved `.example` domain | They never resolve, so demos and tests cannot contact a real site |
| Frontend upgraded to React Router 7 | v6 had open advisories in `npm audit` |

## 13. Open questions

1. Which small OpenAI model should be the default? `gpt-4o-mini` is set in `.env.example`; change `OPENAI_MODEL` to any small model that supports structured outputs.
2. What are the real thesis criteria? The current default (AI, Europe, pre-seed to Series A) is a placeholder in `backend/app/thesis.json`.
3. Which enrichment source beyond the company's own homepage, if any?
4. Should pitches without a domain always go to human review, rather than being matched by name (FR-18)?
5. Does this need a login before it is used beyond local machines?
