# Resource Planning Agent

**An AI-assisted resource planning prototype for capacity analysis, date-aware availability, policy-grounded recommendations, and controlled resource assignment.**

Built with Python, the OpenAI API, Pydantic, SQLite, retrieval-augmented generation (RAG), and agent delegation. The LLM interprets requests and selects tools; deterministic Python code validates inputs, computes capacity, and controls database writes.

[Project walkthrough video](https://www.youtube.com/watch?v=YVs9Qcscy-E&list=PLcj1zveth3-I)

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

**Boundary:** The daily reservation service is currently a separate Python/database workflow. It is **not yet wired into the approval-gated plan application workflow**, and the agent's dated-capacity tool is read-only. The dated-plan approval guard and its integration are the next work in progress; do not treat a standalone reservation service call as authorization to assign staff.

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

## Repository guide

| Area | Key files |
| --- | --- |
| Agent and tool orchestration | `agent.py`, `agent_loop.py`, `tool_runner.py` |
| Fixed-period capacity and recommendations | `capacity_check.py`, `capacity_tool.py`, `resource_proposal.py`, `resource_tool.py` |
| Date-aware capacity | `dated_capacity.py`, `dated_capacity_tool.py` |
| Daily reservations | `dated_reservations.py` |
| Daily-capacity setup and reversible demo | `seed_daily_capacity.py`, `demo_dated_reservation.py` |
| Policy retrieval / delegation | `policy_chunks.py`, `policy_search.py`, `policy_semantic_search.py`, `policy_agent.py`, `policy_delegation.py` |
| Fixed-period plan lifecycle | `submit_plan.py`, `approve_plan.py`, `apply_plan.py`, `plan_store.py`, `plan_validation.py`, `database.py` |
| Tests and evaluation | `test_*.py`, `eval_tool_selection.py` |

The upcoming `dated_plan_guard.py` / `test_dated_plan_guard.py` are part of the **in-progress** dated-plan approval integration and are not counted as completed functionality here.

## Run locally

### 1. Set up the environment

Use Python 3.10+ (a recent compatible version is recommended). From the repository root:

```powershell
git clone https://github.com/adralei/resource-planning-agent.git
cd resource-planning-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install openai pydantic python-dotenv numpy
```

Set `OPENAI_API_KEY` in your local environment or untracked `.env` file before using the model-backed agent. Never commit secrets or local database files.

### 2. Explore the agent and capacity tools

```powershell
python capacity_check.py
python dated_capacity.py
python agent.py
```

The `dated_capacity.py` demo uses an isolated temporary database. For an interactive agent session, try:

```text
16-17 Kasım 2026 tarihleri arasında backend için 14 saat desteğe ihtiyacım var. Core ekibinin kapasitesi yeterli mi?
```

The CLI supports `/yeni` (clear conversation), `/plan` (save the last proposal in the existing plan workflow), and `/cikis` (exit). Neither a capacity check nor the dated-capacity tool creates a reservation.

### 3. Initialize sample daily data (changes local SQLite)

```powershell
python seed_daily_capacity.py
```

This script adds four **missing** example employee-day records for 16–17 November 2026 without overwriting records already present. It modifies the project's local SQLite database; back it up first.

### 4. Explore the reservation demo (changes local SQLite)

```powershell
python demo_dated_reservation.py show
python demo_dated_reservation.py add
python demo_dated_reservation.py show
python demo_dated_reservation.py remove
```

`add` creates one identifiable demo reservation in the local database; `remove` deletes only the matching demo record. Complete cleanup after experiments. This is a **developer demo**, not an approval-gated business operation.

### 5. Run tests

```powershell
python -m unittest discover -p "test_*.py" -v
```

The project has reached **65 reported passing tests** through the batch INSERT rollback step (before the in-progress dated-plan approval guard). Coverage includes Pydantic validation, missing data semantics, agent dispatch, reservation limits, concurrent booking attempts, transactional rollback, plan approvals, and policy-answer evidence checks.

Some scripts require initialized sample data or local configuration. Run them from the repository root, and check their entry points before executing write-oriented demos.

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
