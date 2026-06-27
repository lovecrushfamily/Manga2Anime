---
name: context:planning
description: Planning conventions, plan-shape calibration, and plan artifact routing for Manga2Anime
keywords: planning, plans, prd, roadmap, backlog, active plans, completed plans
---

# Planning Context

This file is the canonical planning context entrypoint for Manga2Anime.

Use it after `process/context/all-context.md` when the task needs plan-shape calibration, planning conventions, or implementation-plan examples.

## Scope

This group covers:

- example plan shapes
- SIMPLE vs COMPLEX plan calibration
- durable planning references that should not stay at the `process/context/` root

It does not cover:

- active implementation plans
- feature reports
- backlog items

Those belong under `process/general-plans/` or `process/features/`.

## Read When

Read this entrypoint when:

- creating a new plan with `generate-plan`
- checking whether work should be `SIMPLE` or `COMPLEX`
- comparing an active plan against the repo's example plan shapes

## Quick Routing

- Use `.claude/skills/vc-generate-plan/references/example-simple-prd.md` to calibrate a one-session plan.
- Use `.claude/skills/vc-generate-plan/references/example-complex-prd.md` to calibrate a complex or multi-phase plan.
- Use `process/general-plans/active/` for cross-cutting plans once implementation work begins.
- Use `process/features/{feature}/active/` only after a feature folder exists.

## Source Paths

- `.claude/skills/vc-generate-plan/references/example-simple-prd.md`
- `.claude/skills/vc-generate-plan/references/example-complex-prd.md`
- `process/general-plans/active/`
- `process/general-plans/backlog/`
- `process/general-plans/completed/`

## Current Project Notes

Manga2Anime now has its first feature-scoped active artifact set:

- SPEC: `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_SPEC_27-06-26.md`
- PLAN: `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_PLAN_27-06-26.md`

The studio-flow plan is a complex standard plan, not a phase program. It should remain in `active/` until PVL writes a validate-contract and missing automated E2E/integration tests are either added or explicitly backlogged.

When planning future Direct Anime work, prefer this feature folder instead of `process/general-plans/`.

## Update Triggers

Update this group when:

- the plan artifact contract changes
- `generate-plan` expects different plan sections or statuses
- the example plan shapes move, split, or become stale
- this project adopts stack-specific planning conventions
