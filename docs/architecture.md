# Hawks OS Architecture

Hawks OS is an agentic job-search operating system built around inspectable
contracts rather than prompt-only browsing.

## Core modules

- `hawks.scout`: job lead contracts, source validation, scoring, dedupe, reports.
- `hawks.fit`: role-family rubrics and candidate-fit evaluation.
- `hawks.context`: compact context packs for CV tailoring and interview prep.
- `hawks.application`: approval gates, draft packs, application tracker.
- `hawks.ledger`: run logs and decision evidence.

## Current v0.1 focus

The first public milestone is **Explainable Scout-as-Code**:

1. strict `JobLead` and `ScoutDecision` contracts
2. deterministic scoring with reasons and risks
3. tests proving high-fit and low-fit behavior
4. public project site for `adgents.live`

## Why this matters

Hawks demonstrates agentic architecture, MCP/tool thinking, workflow design,
context management, and reliability engineering in a business-critical workflow:
career operations.
