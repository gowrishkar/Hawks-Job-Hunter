# Hawks OS Trust Model

Hawks is designed as an approval-first agentic job search operating system.
The goal is not to spray applications. The goal is to produce fewer, stronger,
explainable opportunities with human approval at every irreversible step.

## Principles

1. **Validated sources first** — official careers pages, ATS links, and reputed boards rank above unknown pages.
2. **Explain every shortlist** — each recommendation carries score, evidence, reasons, and risks.
3. **No blind applications** — Hawks can draft and prepare, but submission requires approval.
4. **Small auditable runs** — every scout run should produce a ledger entry that can be inspected later.
5. **Fit quality over volume** — three excellent roles beat ten weak ones.

## Public-safe architecture

The public repository uses sample jobs and deterministic scoring so reviewers
can inspect the system without exposing private CV data, recruiter messages, or
application history.

Private integrations can later plug into the same contracts:

```text
Scout -> Validate -> Score -> Dedupe -> Context Pack -> Approval Gate -> Tracker
```
