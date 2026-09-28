# DealLens: AI-Powered Dealflow Triage and Enrichment

## 1. Project Overview

This project is an internal AI automation system for handling incoming investment opportunities.

The core problem is that an investment team can receive many startup/company opportunities through different channels. Processing every opportunity manually requires people to read the incoming information, research the company, extract important information, check whether it fits the investment thesis, and enter the information into a CRM.

The goal of this project is to automate that **first-pass processing**.

The system does **not** make the final investment decision. It prepares, enriches, structures, and initially screens opportunities so that the investment team can review them more efficiently.

### High-level flow

```text
Incoming Investment Opportunity
            |
            v
       Data Ingestion
            |
            v
       Data Enrichment
       (Web / REST APIs)
            |
            v
      LLM Extraction
   Unstructured -> Structured
            |
            v
    Investment Thesis
        Screening
            |
            v
        Validation
            |
            v
      CRM Integration
            |
            v
     Investment Team Review
```

---

# 2. What Is Dealflow?

**Dealflow** means the stream of potential investment opportunities coming into an investment fund.

For example:

```text
Founder / Startup
       |
       v
Investment opportunity
       |
       v
Fund receives it
       |
       v
Dealflow
```

One startup opportunity is a **deal/opportunity**.

The collection of incoming opportunities is the **dealflow**.

The project focuses on automating what happens after an opportunity enters the fund's workflow.

---

# 3. The Problem

A manual process can look like this:

```text
New Opportunity
      |
      v
Human reads email / submission
      |
      v
Human researches company
      |
      v
Human collects additional information
      |
      v
Human extracts important fields
      |
      v
Human checks investment criteria
      |
      v
Human enters information into CRM
      |
      v
Investment team reviews
```

This creates several problems:

- Repetitive manual work
- Inconsistent data entry
- Time spent researching basic company information
- Important information may be missed
- Duplicate CRM records can be created
- The same process has to be repeated for every opportunity

The project moves much of this first-pass work into an automated workflow.

---

# 4. What the System Does

The system performs several stages:

1. Receives an incoming opportunity.
2. Extracts the initial information.
3. Enriches the opportunity using external/web APIs.
4. Uses an LLM to extract information from unstructured text.
5. Converts the information into structured fields.
6. Checks the opportunity against predefined investment-thesis criteria.
7. Validates the resulting data.
8. Creates or updates the relevant CRM record.
9. Handles failures and safe re-runs.
10. Prevents unnecessary duplicate CRM records.
11. Records/document the current implementation and future improvements.

---

# 5. Stage 1 — Incoming Opportunity

The input can contain unstructured information.

For example:

```text
Subject:
Investment Opportunity — ABC AI

Message:
Hi,

We are ABC AI, a Berlin-based startup building
AI software for industrial automation.

We recently raised a seed round and are currently
expanding across Germany.

Best,
Founder
```

The information is useful, but it is not yet represented as structured fields.

A system cannot directly rely on the text being formatted consistently.

---

# 6. Stage 2 — Data Enrichment

## What is enrichment?

**Enrichment means adding useful information to the original opportunity.**

The incoming message might only contain:

```text
Company: ABC AI
Website: abc.ai
Founder: John
```

Additional information can be obtained through external APIs or web-based data sources.

Conceptually:

```text
Original Opportunity
        |
        v
External APIs / Web Sources
        |
        v
Additional Company Information
```

The enriched information gives the later processing stages more context.

### Possible categories of information

Depending on the actual data sources available to the project, enrichment can provide information such as:

- Company information
- Website information
- Location
- Industry
- Product information
- Funding information
- Other publicly available company information

The exact APIs and fields should be defined by the actual implementation rather than assumed.

---

# 7. Stage 3 — LLM-Based Extraction

The next problem is converting unstructured text into structured information.

For example:

```text
ABC AI is a Berlin-based startup building
AI software for industrial robots.
The company recently raised a seed round.
```

The LLM can transform this into structured information such as:

```json
{
  "company_name": "ABC AI",
  "location": "Berlin",
  "industry": "Industrial AI",
  "product": "AI software for industrial robots",
  "funding_stage": "Seed"
}
```

The exact fields should be defined by the project's requirements.

The key transformation is:

```text
Unstructured Information
          |
          v
         LLM
          |
          v
Structured Information
```

---

# 8. Structured Outputs

A major reason for using structured output is that downstream systems need predictable data.

A free-form LLM response might be:

```text
ABC AI appears to be a Berlin-based industrial
AI startup focused on robotics.
```

That is difficult for software to reliably process.

A structured response can instead follow a schema:

```json
{
  "company_name": "...",
  "location": "...",
  "industry": "...",
  "product": "...",
  "funding_stage": "..."
}
```

Now Python and the CRM integration can work with specific fields.

### Concept

```text
LLM
 |
 v
Defined Schema
 |
 v
Predictable Fields
 |
 v
Validation
 |
 v
CRM
```

---

# 9. Stage 4 — Investment Thesis Screening

After the opportunity has been structured and enriched, the system performs an initial screening against predefined investment criteria.

The concept is:

```text
Company Information
        +
Investment Thesis Criteria
        |
        v
Initial Screening
```

For example, criteria could potentially consider:

- Whether the company is AI-related
- Relevant sector
- Relevant geography
- Investment stage
- Other fund-specific requirements

The exact criteria must come from the actual investment thesis used by the organization.

## Important distinction

The system performs **initial screening/triage**.

It does not automatically make the final investment decision.

```text
Automation
    |
    v
Initial qualification
    |
    v
Human investment team
    |
    v
Final evaluation / decision
```

---

# 10. Stage 5 — Validation

Before sending information to the CRM, the structured data should be checked.

For example:

```text
LLM Output
    |
    v
Schema Validation
    |
    +---- Valid ------> Continue
    |
    +---- Invalid ----> Handle failure
```

Validation can make sure that required fields exist and that data has the expected format.

The exact validation rules should be determined during implementation.

---

# 11. Stage 6 — CRM Integration

## What is a CRM?

CRM stands for **Customer Relationship Management**.

In this project, the CRM acts as the central system where the investment team can manage and track companies and opportunities.

A record might contain:

```text
Company
Website
Founder
Location
Industry
Product
Funding Stage
Description
Screening Result
Status
```

The workflow sends structured information into the CRM.

```text
Incoming Opportunity
        |
        v
AI Processing
        |
        v
Structured Data
        |
        v
CRM API
        |
        v
Company / Opportunity Record
```

The CV describes the CRM as **Attio-style**. The actual implementation should specify the exact CRM/API used.

---

# 12. CRM Create vs Update

The workflow needs to determine whether an opportunity represents a new company/opportunity or an existing one.

Conceptually:

```text
Processed Opportunity
        |
        v
Does matching record already exist?
        |
    +---+---+
    |       |
   YES      NO
    |       |
    v       v
 Update    Create
```

This prevents the CRM from becoming filled with unnecessary duplicate records.

---

# 13. CRM Deduplication

Suppose the same company appears twice:

```text
Monday:
ABC AI

Friday:
ABC AI
```

A naive workflow could create:

```text
ABC AI
ABC AI
```

A deduplication mechanism attempts to identify that these opportunities refer to the same existing entity.

The exact matching method should be decided during implementation.

Possible identifiers might include company domains, CRM identifiers, or other fields, but the actual project should use only the matching logic that is implemented and validated.

---

# 14. Idempotent Re-Runs

This is an important reliability concept.

A workflow can fail after partially completing its work.

For example:

```text
Enrichment       ✓
LLM extraction   ✓
Screening        ✓
CRM update       ✗
```

If the workflow is simply run again, it could accidentally repeat earlier operations.

An idempotent design aims to make repeated processing safe.

```text
First Run
   |
   v
Process opportunity
   |
   v
Partial failure

Second Run
   |
   v
Recognize existing state
   |
   v
Continue / update / skip safely
```

### Simple definition

> Idempotency means that repeating an operation does not create unintended duplicate side effects.

In this project, it is particularly important around CRM operations and workflow retries.

---

# 15. Error Handling

The pipeline contains several components:

```text
Input
  |
  v
Web API
  |
  v
LLM
  |
  v
Validation
  |
  v
CRM API
```

Any component can fail.

Examples:

- External API unavailable
- Network timeout
- Missing data
- Invalid LLM output
- CRM API failure
- Unexpected response format

The system therefore needs defined failure behavior.

Possible mechanisms can include:

- Validation
- Retries
- Logging
- Failed-item tracking
- Error states
- Manual review for unresolved cases

Only mechanisms actually implemented should be claimed in the final project.

---

# 16. Why This Is More Than an LLM Demo

A simple demo could be:

```text
Input Text
   |
   v
LLM
   |
   v
Answer
```

That is not enough for an operational workflow.

This project adds:

```text
Input
 |
 v
Enrichment
 |
 v
LLM extraction
 |
 v
Structured output
 |
 v
Screening
 |
 v
Validation
 |
 v
CRM integration
 |
 v
Error handling
 |
 v
Idempotency
 |
 v
Deduplication
 |
 v
Documentation
```

The focus is therefore not only on the LLM.

It is on building a **reliable business workflow around the LLM**.

---

# 17. Technology Roles

## Python

Python is the main programming/orchestration layer.

It can coordinate:

- Input processing
- API calls
- LLM calls
- Data transformation
- Validation
- CRM integration
- Error handling

---

## LLM

The LLM handles tasks such as extracting information from unstructured text and potentially assisting with the initial screening logic.

It transforms:

```text
Unstructured text
        |
        v
Structured information
```

---

## REST APIs

REST APIs allow the workflow to communicate with external services.

Conceptually:

```text
Python
  |
  | HTTP request
  v
External API
  |
  | JSON response
  v
Python
```

They can be used for enrichment and CRM integration.

---

## Structured Outputs

Structured outputs make LLM responses predictable enough for downstream processing.

```text
LLM
 |
 v
JSON / defined schema
 |
 v
Python
 |
 v
CRM
```

---

## CRM

The CRM stores the processed company/opportunity information for the investment team.

---

# 18. Full Architecture

A practical conceptual architecture is:

```text
                    INBOUND OPPORTUNITY
                            |
                            v
                    +---------------+
                    |   Ingestion   |
                    +---------------+
                            |
                            v
                    +---------------+
                    |  Enrichment   |
                    |  REST / Web   |
                    |     APIs      |
                    +---------------+
                            |
                            v
                    +---------------+
                    |      LLM      |
                    |   Extraction  |
                    +---------------+
                            |
                            v
                    +---------------+
                    |   Structured  |
                    |    Output     |
                    +---------------+
                            |
                            v
                    +---------------+
                    |  Validation   |
                    +---------------+
                            |
                            v
                    +---------------+
                    |    Thesis     |
                    |   Screening   |
                    +---------------+
                            |
                            v
                    +---------------+
                    | Deduplication |
                    +---------------+
                            |
                            v
                    +---------------+
                    |     CRM       |
                    | Create/Update |
                    +---------------+
                            |
                            v
                    +---------------+
                    | Human Review  |
                    +---------------+

        Cross-cutting:
        - Error handling
        - Idempotent re-runs
        - Logging
        - Documentation
```

This is a **conceptual architecture**. The actual implementation should be adjusted based on the tools, APIs, CRM, data sources, and requirements you choose.

---

# 19. Example End-to-End Run

Suppose the system receives:

```text
"We are ABC Robotics, a Berlin startup building
AI software for warehouse robots. We raised a
€3M seed round and are looking for investors."
```

### Step 1 — Receive

The workflow captures the opportunity.

### Step 2 — Enrich

The workflow obtains additional information from available external sources.

### Step 3 — Extract

The LLM produces structured information:

```json
{
  "company_name": "ABC Robotics",
  "location": "Berlin",
  "sector": "Industrial AI",
  "product": "AI software for warehouse robots",
  "stage": "Seed"
}
```

### Step 4 — Screen

The system compares the information against the configured investment criteria.

### Step 5 — Validate

The workflow checks that required fields are present and valid.

### Step 6 — Deduplicate

The system checks whether the company/opportunity already exists.

### Step 7 — CRM

The system creates or updates the CRM record.

### Step 8 — Human review

The investment team sees the processed opportunity and decides what to do next.

---

# 20. What You Need to Build This Project Yourself

A good implementation can be divided into phases.

## Phase 1 — Define the input

Decide what an incoming opportunity looks like.

Example:

```json
{
  "source": "email",
  "subject": "...",
  "body": "...",
  "received_at": "...",
  "sender": "..."
}
```

---

## Phase 2 — Define the data model

Decide what information you want to extract.

For example:

```json
{
  "company_name": "",
  "website": "",
  "founders": [],
  "location": "",
  "industry": "",
  "product": "",
  "funding_stage": "",
  "description": ""
}
```

---

## Phase 3 — Build enrichment

Connect one or more APIs/data sources.

```text
Company/domain
      |
      v
External API
      |
      v
Enriched data
```

---

## Phase 4 — Build LLM extraction

Define a structured schema and prompt the LLM to populate it.

```text
Raw opportunity
      |
      v
LLM
      |
      v
Structured JSON
```

---

## Phase 5 — Build screening

Define the investment-thesis rules.

```text
Structured company data
          +
Investment criteria
          |
          v
Screening result
```

---

## Phase 6 — Build CRM integration

Create/update CRM records through the CRM API.

---

## Phase 7 — Add reliability

Implement and test:

- Validation
- Error handling
- Retries where appropriate
- Idempotency
- Deduplication
- Logging

---

## Phase 8 — Test the complete workflow

Test cases should include:

### Normal opportunity

```text
Valid input → successful CRM record
```

### Missing information

```text
Incomplete input → validation/fallback
```

### API failure

```text
API unavailable → controlled failure/retry
```

### Invalid LLM output

```text
Invalid structure → validation failure
```

### Duplicate company

```text
Existing company → update/skip
```

### Re-run

```text
Same opportunity processed twice
→ no unintended duplicate side effect
```

---

# 21. The Core Mental Model

Do not think of this project as:

> "I built an LLM that reads investment opportunities."

Think of it as:

> **"I built an automated data-processing and decision-support workflow around incoming investment opportunities, with LLMs as one component."**

The architecture is:

```text
             BUSINESS PROBLEM
                    |
                    v
        Incoming Opportunities
                    |
                    v
             Enrichment
                    |
                    v
          LLM Extraction
                    |
                    v
          Structured Data
                    |
                    v
         Thesis-based Screening
                    |
                    v
              Validation
                    |
                    v
       Deduplication / Idempotency
                    |
                    v
             CRM Integration
                    |
                    v
             Human Review
```

The **next step for actually building it** is to define the exact input format, schema, APIs/data sources, LLM, screening rules, CRM, and storage/orchestration architecture. Those implementation choices are not specified by the CV itself, so they should be selected when you design the project rather than assumed.
