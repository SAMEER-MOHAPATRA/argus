# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the domain glossary (Discovery, Tracking, Dashboard;
  the `Job`/`Application` entities; module layout).
- **`docs/adr/`** — read ADRs that touch the area you're about to work in (currently just
  `0001-persistence-seam.md`).

If either changes shape later (a new ADR, a term added to the glossary), keep reading from the
same two locations — no other domain doc source exists for this repo.

## File structure

Single-context repo (this repo, and most repos):

```
/
├── CONTEXT.md
└── docs/adr/
    └── 0001-persistence-seam.md
```

This repo has no `CONTEXT-MAP.md` and is not a monorepo — there's exactly one `CONTEXT.md`, at the
root, covering the whole codebase.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a
test name), use the term as defined in `CONTEXT.md` — e.g. `Job`, `Application`,
"Discovery", "Tracking", "Dashboard". Don't drift to synonyms the glossary doesn't use.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing
language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (persistence seam) — but worth reopening because…_
