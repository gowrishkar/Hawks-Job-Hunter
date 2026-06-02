# Hawks OS — Agentic Job Search Operating System

![Hawks logo](assets/hawks-logo.jpg)

Hawks OS is an approval-first agentic job search operating system.

It scouts trusted roles, validates sources, scores fit, dedupes noise, builds context packs, and keeps a decision ledger — so job search becomes inspectable workflow, not prompt-only browsing.

![Hawks Scout as Code](assets/hawks-scout-as-code.jpg)

## Official project site

`adgents.live` is reserved as the official Hawks OS project site.

Static site source lives in [`site/`](site/).

## Scout as Code init

```bash
python3 scout_as_code.py --session manual --max-output 3 --max-leads 10 --per-query 1 --pretty
```

Package/test smoke check:

```bash
python3 -m pytest
```

## Principle

> Fewer strong matches are better than many weak matches.

## Public v0.1 scope

This public repo starts with **Explainable Scout-as-Code**:

- strict `JobLead` and `ScoutDecision` contracts
- deterministic scoring with reasons and risks
- tests for high-fit and low-fit role behavior
- public architecture and trust-model docs
- static official project site

## Architecture

See [`docs/architecture.md`](docs/architecture.md).

## Trust model

See [`docs/trust_model.md`](docs/trust_model.md).

## Status

Hawks OS is being built in public with daily meaningful commits.
