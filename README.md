# Resource Planning Agent

**An AI-assisted resource planning prototype for capacity analysis, date-aware availability, policy-grounded recommendations, and controlled resource assignment.**

Built with Python, the OpenAI API, Pydantic, SQLite, retrieval-augmented generation (RAG), and agent delegation. The LLM interprets requests and selects tools; deterministic Python code validates inputs, computes capacity, and controls database writes.


## The problem

Resource planning is not simply matching a skill to a person. Teams need to know **when** employees are available, how much capacity has already been reserved, whether a proposed allocation respects organizational policies, and whether changes can be executed safely. This project explores those challenges with an AI-facing interface and testable business logic.

## Current capabilities

- **Fixed-period capacity checks:** Validate requested skills and hours, identify matching employees, calculate available capacity, and report shortages.
- **Date-aware capacity checks:** Query availability for a specified day or date range (up to 31 days). The agent selects `check_dated_capacity` for dated requests and `check_capacity` for undated requests. Missing employee-day records are treated as **unknown**, not zero.
- **Daily reservations and net availability:** Maintain daily capacity separately from reservations. Available hours are calculated as **daily capacity − existing reservations**, rather than destructively subtracting hours from the source capacity records.
- **Overbooking protection:** Reject reservations that exceed remaining employee-day capacity, duplicate reservation IDs, invalid hours, and reservations without an underlying daily capacity record.
- **Atomic batch reservations:** Validate and apply multiple employee-day reservations in one SQLite transaction. Group multiple requests for the same employee and day before checking capacity. A failure rolls back the entire batch.
- **Concurrent-write safety:** Use `BEGIN IMMEDIATE` to serialize competing SQLite writers during reservation and capacity updates. Tests cover simultaneous attempts to consume the same hours.
- **Safe capacity updates:** Prevent reducing daily available hours below already-reserved hours.
- **Structured tool errors:** Distinguish invalid arguments, database errors, and detected capacity/reservation inconsistencies, without exposing raw database exception messages to the agent.
- **Resource recommendations:** Explore potential allocations and external-team resources without representing recommendations as completed assignments.
- **Policy-aware reasoning:** Use chunked internal documents, embeddings, retrieval, source references, and a dedicated policy agent; explicitly handle insufficient evidence.
- **Existing fixed-period plan workflow:** Separate proposal submission, simulated project/team approvals, and application. Validate the required approval scopes and use transactions, revalidation, and safeguards against repeated capacity deductions.

**Boundary:** The daily reservation service is currently a separate Python/database workflow. It is **not yet wired into the approval-gated plan application workflow**, and the agent's dated-capacity tool is read-only. The dated-plan guard and preflight validate approved reservation snapshots, but they do not apply reservations; do not treat a standalone reservation service call as authorization to assign staff.

## Architecture

```text
Natural-language request
        |
        v
      AI Agent -----------------> Policy Agent / RAG
        |                           |
        |                      Policy documents
        v
  Tool selection + Pydantic validation
        |
        +-- check_capacity --------> Fixed-period SQLite capacity
        |
        +-- check_dated_capacity --> Daily capacity + reservations
        |                                 |
        |                                 v
        |                           Net available hours
        |
        +-- Resource / policy tools --> Recommendations + evidence

Existing fixed-period application:
Proposal -> Required approvals -> Revalidation -> SQLite transaction

Separate dated reservation service (not yet attached to approvals):
Validated employee-day requests -> BEGIN IMMEDIATE
    -> Capacity / duplicate checks -> Batch INSERT -> COMMIT
                                            | error
                                            v
                                         ROLLBACK
```

## Tech stack

`Python` · `OpenAI API / Responses tool calling` · `Pydantic` · `SQLite` · `Embeddings / RAG` · `Agent delegation` · `unittest`

## Architecture and project structure

The installable Python package lives under `src/resource_planning_agent/`. Feature packages separate orchestration, tools, planning, approvals, persistence, and policy retrieval. Root-level `data/` and `docs/` intentionally remain outside the package: database state, saved plan JSON files, and policy text keep their existing locations.

```text
.
├── src/resource_planning_agent/
│   ├── agents/       # Interactive agent, tool loop, policy agent/delegation
│   ├── approvals/    # Submit, approve, and apply fixed-period plans
│   ├── planning/     # Capacity, proposals, reservations, validation, preflight
│   ├── policies/     # Policy chunks, retrieval, and grounded answers
│   ├── scripts/      # Runnable demos and developer utilities
│   ├── storage/      # SQLite database and plan JSON persistence
│   ├── tools/        # Pydantic schemas and tool dispatchers
│   └── paths.py      # Stable project-root paths for .env, data, and docs
├── tests/
│   ├── agents/
│   ├── approvals/
│   ├── planning/
│   ├── policies/
│   └── tools/
├── data/
│   ├── plans/        # Existing plan JSON state
│   └── resource_planning.db
├── docs/
│   └── resource_policy.md
├── .env.example
├── pyproject.toml
└── README.md
```

### Main modules

| Package | Responsibilities |
| --- | --- |
| `agents` | Interactive agent, bounded tool loop, policy specialist, and delegation |
| `tools` | Capacity, dated-capacity, resource, and policy tool schemas/dispatch |
| `planning` | Capacity calculations, resource proposals, dated reservations, plan validation and preflight |
| `approvals` | Plan submission, simulated scoped approvals, and fixed-period application |
| `storage` | SQLite schema/data access and atomic plan JSON persistence |
| `policies` | Policy document chunking, lexical/semantic search, and cited answers |
| `scripts` | Database demos/seeding, plan inspection, API check, and tool-selection evaluation |
| `tests` | `unittest` cases grouped by feature |

## Run locally

### 1. Set up the environment

Use Python 3.10+ (a recent compatible version is recommended). From the repository root:

```powershell
git clone https://github.com/adralei/resource-planning-agent.git
cd resource-planning-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in your local `.env` file before using model-backed commands. `AGENT_MODE` is optional and defaults to `single`; `multi` enables the policy specialist. Never commit secrets.

### 2. Explore the agent and capacity tools

```powershell
python -m resource_planning_agent.planning.capacity_check
python -m resource_planning_agent.planning.dated_capacity
python -m resource_planning_agent.agents.agent
```

The `dated_capacity.py` demo uses an isolated temporary database. For an interactive agent session, try:

```text
16-17 Kasım 2026 tarihleri arasında backend için 14 saat desteğe ihtiyacım var. Core ekibinin kapasitesi yeterli mi?
```

The CLI supports `/yeni` (clear conversation), `/plan` (save the last proposal in the existing plan workflow), and `/cikis` (exit). Neither a capacity check nor the dated-capacity tool creates a reservation.

### 3. Initialize sample daily data (changes local SQLite)

```powershell
python -m resource_planning_agent.scripts.seed_daily_capacity
```

This script adds four **missing** example employee-day records for 16–17 November 2026 without overwriting records already present. It modifies the project's local SQLite database; back it up first.

### 4. Explore the reservation demo (changes local SQLite)

```powershell
python -m resource_planning_agent.scripts.demo_dated_reservation show
python -m resource_planning_agent.scripts.demo_dated_reservation add
python -m resource_planning_agent.scripts.demo_dated_reservation show
python -m resource_planning_agent.scripts.demo_dated_reservation remove
```

`add` creates one identifiable demo reservation in the local database; `remove` deletes only the matching demo record. Complete cleanup after experiments. This is a **developer demo**, not an approval-gated business operation.

### Plan approval and application commands

The local demo lifecycle can also be run as package modules:

```powershell
python -m resource_planning_agent.approvals.submit_plan
python -m resource_planning_agent.approvals.approve_plan
python -m resource_planning_agent.approvals.apply_plan
python -m resource_planning_agent.scripts.view_plan
```

These commands read or update the existing plan JSON files and SQLite database. `apply_plan` changes fixed-period capacity; back up the local database first. Approvals use demo identities and are not real authentication or authorization.

### 5. Run tests

```powershell
python -m unittest discover -s tests -t . -v
```

Coverage includes Pydantic validation, missing-data semantics, agent dispatch, reservation limits, concurrent booking attempts, transactional rollback, plan approvals, dated-plan preflight, and policy-answer evidence checks.

Run module commands from the repository root after installing the package. Some commands require API credentials or initialized sample data. The seed and reservation-demo commands write to the existing local SQLite database; back it up and inspect the command before use.

## Example scenarios

### Fixed planning period

A team requests **32 backend hours**. Matching employees have **28 hours** available, so the tool reports a **4-hour shortage**. This is a capacity assessment, not an assignment.

### Dated capacity and reservations

For the synthetic Core-team data on **16–17 November 2026**, Ada and Bora have **12 hours** of combined daily availability. A request for **14 backend hours** yields a **2-hour shortage**. After reserving **3 hours** for Ada on 16 November, the same query returns **9 hours available** and a **5-hour shortage**. Removing the demo reservation restores the original result, assuming no other changes.

### Competing reservations

If an employee has **4 hours** available and two projects concurrently request **3 hours** each for the same day, only one reservation can succeed. The other is rejected rather than overbooking the employee.

### Atomic batch

If one multi-employee reservation batch contains an invalid or excessive request, none of its reservations should persist. Tests also simulate a SQLite INSERT failure after an earlier INSERT and verify a full rollback.

## Scope, limitations, and next steps

This is a **local prototype with synthetic employee data, a fixed-period legacy workflow, dated availability records, and simulated role-based approvals**. It is not connected to a real HR, ERP, payroll, or workforce-management system and does not autonomously authorize staffing changes.

The dated reservation engine currently exposes developer-facing Python functions rather than a production authorization boundary. **Approval-scoped dated plans, immutable approval snapshots, application idempotency, and a single transaction connecting dated plan application to reservations** remain future integration work. Additional production considerations include access control, audit logging, migrations, observability, broader concurrency testing, and repeatable evaluations of model tool-selection accuracy and latency.

## Why this project matters

The project demonstrates a practical separation of responsibilities: the AI agent understands user intent and retrieves supporting policy information, while deterministic Python and SQLite enforce data contracts, capacity limits, and transactional safety. It is designed as a learning and portfolio project for AI agent engineering, automation, and resource-management workflows.

**Author:** [Ege Bulut Uygur](https://github.com/adralei)
