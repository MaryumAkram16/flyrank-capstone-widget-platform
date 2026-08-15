# Build Log — AI usage, honestly

## Phase 1 — Design
- Used Claude to draft the initial data model and API surface split (owner /
  delivery / submission paths) after I decided the stack (FastAPI + SQLite) and
  scope (signup form + CTA popover) myself.
- Changed: tightened the `submissions` table to denormalize `tenant_id` so every
  dashboard query is a single-column filter instead of a join — this was my call
  after re-reading §6's tenant-isolation requirement.
- Where AI was wrong / needed correction: (fill in as it happens)
