# Resource Planning Agent

**An AI-assisted resource planning prototype for team capacity analysis, policy-aware recommendations, and controlled assignment workflows.**

Built with Python, the OpenAI API, Pydantic, SQLite, retrieval-augmented generation (RAG), and agent delegation.

https://www.youtube.com/watch?v=YVs9Qcscy-E&list=PLcj1zveth3-I

## The problem

Internal resource planning requires more than matching people to projects. A useful system must check actual availability, respect policies, explain shortages, and prevent accidental or unauthorized updates. This project explores those challenges through an AI agent and deterministic business logic.

## What it does

- **Capacity checks:** Validates a requested skill and number of hours, calculates available capacity and shortages, and identifies matching candidates.
- **Resource recommendations:** Explores potential allocations without confusing a proposal with a completed assignment.
- **Policy-aware answers:** Retrieves relevant policy passages using document chunks, embeddings, and similarity search; surfaces source identifiers and handles insufficient evidence.
- **Delegated reasoning:** Uses a dedicated policy agent with its own search tools; compares single-agent and delegated flows.
- **Controlled execution:** Separates proposals, demo approvals, and applying plans. SQLite transactions and revalidation protect against partial writes, stale plans, and repeated capacity deductions.
- **Evaluation:** Includes tests for invalid input, tool selection, tool failures, rollback, and competing assignments.

## High-level workflow

```text
Natural-language request
        |
        v
    AI Agent --------> Policy Agent / RAG -> Policy documents
        |
        v
Validated Python tools -> Capacity and candidate analysis
        |
        v
   Proposed plan -> Demo approval -> Revalidation
                                        |
                                        v
                              SQLite transaction
```

**Important:** The LLM interprets requests and coordinates tools; Python performs arithmetic, validation, and database updates.

## Tech stack

`Python` · `OpenAI API` · `Pydantic` · `SQLite` · `Embeddings / RAG` · `Tool calling` · `unittest`

## Repository guide

| Area | Key files |
| --- | --- |
| Agent loop | `agent.py`, `agent_loop.py`, `tool_runner.py` |
| Capacity / resource logic | `capacity_check.py`, `capacity_tool.py`, `resource_proposal.py`, `resource_tool.py` |
| Policy retrieval and delegation | `policy_chunks.py`, `policy_search.py`, `policy_semantic_search.py`, `policy_agent.py`, `policy_delegation.py` |
| Plan lifecycle | `submit_plan.py`, `approve_plan.py`, `apply_plan.py`, `plan_store.py`, `database.py` |
| Testing and evaluation | `test_*.py`, `eval_tool_selection.py` |

## Run locally

Requires Python 3.10+ and an OpenAI API key for model-backed flows.

```bash
git clone https://github.com/adralei/resource-planning-agent.git
cd resource-planning-agent
python -m venv .venv
```

Activate the environment (Windows PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the libraries required by the scripts you intend to run (not all demos need the same dependencies). For AI-backed examples:

```bash
python -m pip install openai pydantic python-dotenv numpy
```

Set `OPENAI_API_KEY` in your local environment (never commit it), then start with:

```bash
python capacity_check.py
python agent.py
python -m unittest discover -p "test_*.py"
```

Individual policy, planning, and evaluation scripts can also be explored from the repository root. Some modules expect sample data or a prior local database initialization; inspect their `__main__` entry points before running them in isolation.

## Example scenario

A team needs **32 backend hours**, but only **28 hours** are available among the matching employees. The capacity tool returns a **4-hour shortage**. The agent can explain the shortage and explore alternatives without claiming those hours have already been allocated.

## Scope and limitations

This is a **local demonstration using synthetic resource data, a fixed planning period, and simulated role-based approvals**. It is **not** integrated with a live HR, ERP, or workforce-management system, and it does not autonomously authorize real staffing changes.

## Why this project matters

It demonstrates how enterprise AI agents can combine natural-language interaction with auditable tools, retrieval of internal rules, deterministic capacity calculations, and approval-gated execution.

**Author:** [Ege Bulut Uygur](https://github.com/adralei)
