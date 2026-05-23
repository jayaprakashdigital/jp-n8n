# Pull Request Template

**Purpose:** Use this template for all pull requests to the AIOS repository.
**Instructions:** Fill in all sections. Delete instructional italics before opening PR.

---

## Summary

_2-3 sentences describing what this PR does and why._

## Type of Change

- [ ] New feature (new workflow, new command, new table)
- [ ] Bug fix (non-breaking fix to existing behavior)
- [ ] Hardening (error handling, rate limiting, logging improvement)
- [ ] Documentation (no code changes)
- [ ] Refactor (code restructuring, no behavior change)
- [ ] Phase completion

## Phase / Ticket Reference

_e.g., Phase 3 Creative Engine — F3-01: Viral Research Command_
_or: Fixes BUG-20260523-04_

---

## Changes Made

### New Workflows
_List any new workflows added with their IDs._

| Workflow | ID | Status |
|---------|-----|--------|
| EXAMPLE__WORKFLOW__V1 | uuid-here | Active |

### Modified Workflows
_List any existing workflows modified._

| Workflow | Change |
|---------|--------|
| TELEGRAM__SUPERVISOR__V2 | Added P3 command detection to "Prepare AI Context" node |

### Database Changes
_List any SQL migrations applied._

| Migration | Type | Tables Affected |
|----------|------|----------------|
| MIG-03-01 | CREATE TABLE | hook_library, audience_patterns |

### Files Changed
- `scripts/phase3_builder.py` — _describe what changed_
- `docs/WORKFLOW_INDEX.md` — _updated with new workflow IDs_

---

## Testing Done

- [ ] Builder script ran successfully (no Python errors)
- [ ] n8n restarted after deploy
- [ ] Workflows confirmed active in n8n SQLite
- [ ] Tables confirmed in PostgreSQL
- [ ] Golden path tested manually in Telegram
- [ ] Error path tested (bad input, timeout, etc.)
- [ ] Existing features regression tested

**Manual test commands run:**
```
/research morning skincare
/script 5-minute workout
```

**Expected output verified:** _yes/no + notes_

---

## Documentation Updated

- [ ] WORKFLOW_INDEX.md — new workflow IDs added
- [ ] CHANGELOG.md — entry added
- [ ] DATABASE_SCHEMA.md — new tables documented
- [ ] MIGRATION_LOG.md — migration logged
- [ ] FEATURE_LOG.md — new feature logged (if user-facing)
- [ ] PHASE_X.md — phase doc updated (if phase completion)
- [ ] API_CONTRACTS.md — I/O schema documented (if new subworkflow)

---

## Rollback Plan

_If this PR causes a critical issue, what is the rollback procedure?_

_e.g.: Re-run previous phase builder script to restore TELEGRAM__SUPERVISOR__V2 to Phase 2.5 state. No data loss expected (new tables can remain)._

---

## Checklist

- [ ] I read WORKFLOW_GUARDRAILS.md and CODING_STANDARDS.md before making changes
- [ ] I ran `bash scripts/backup.sh` before running the builder script
- [ ] I did not modify `N8N_ENCRYPTION_KEY` or any credential values
- [ ] I did not drop or truncate any database tables
- [ ] I did not commit any `.env` files or API keys
- [ ] All new SQL queries use `IF NOT EXISTS` or are idempotent
- [ ] All user-supplied text is sanitized before PostgreSQL insertion
