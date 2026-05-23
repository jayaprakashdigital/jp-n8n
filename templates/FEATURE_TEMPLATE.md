# Feature Template

**Purpose:** Use this template when proposing and documenting a new AIOS feature.
**Owner:** Contributing developer
**Instructions:** Copy this file, rename it `FEATURE-<short-name>.md`, fill in all sections. Delete instructional italics before submitting.

---

## Feature Summary

**Feature Name:** _e.g., "Hook A/B Testing"_
**Feature ID:** F<phase>-<NN> _e.g., F6-03_
**Proposed By:** _Name or agent_
**Proposed Date:** YYYY-MM-DD
**Target Phase:** _e.g., Phase 6_
**Status:** Draft / Approved / In Progress / Complete / Rejected

---

## Problem Statement

_What user pain point or product gap does this feature address? Be specific._

---

## Proposed Solution

_What is the feature? Describe the user-facing behavior in 2-4 sentences._

### Telegram Interface

**Command(s):**
```
/<command> <args>
```

**Example interaction:**
```
User: /command argument
Bot: [response format]
```

---

## Technical Design

### New Workflows Required

| Workflow Name | Purpose | Trigger |
|--------------|---------|---------|
| WORKFLOW__NAME__V1 | What it does | executeWorkflowTrigger |

### New Database Tables Required

```sql
CREATE TABLE IF NOT EXISTS table_name (
    id SERIAL PRIMARY KEY,
    -- columns
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Changes to Existing Workflows

| Workflow | Node | Change |
|---------|------|--------|
| TELEGRAM__SUPERVISOR__V2 | Prepare AI Context | Add new command detection |

### AI Model Selection

| Workflow | Model | Reason |
|---------|-------|--------|
| NEW__WORKFLOW__V1 | claude-3.5-haiku or claude-3.5-sonnet | Speed vs quality justification |

---

## Data Flow

```
User message → Supervisor → P3/P4 Handler → [new workflow] → Format → Reply
```

_Add a more detailed flow if the feature has multiple steps or async operations._

---

## Acceptance Criteria

- [ ] User can trigger feature via Telegram command
- [ ] Output is formatted correctly in Markdown
- [ ] Data is persisted to PostgreSQL
- [ ] Error case returns friendly message (never exposes internal errors)
- [ ] Rate limiting applies to this command
- [ ] Execution logged to `execution_logs`
- [ ] CHANGELOG.md updated
- [ ] WORKFLOW_INDEX.md updated
- [ ] FEATURE_LOG.md updated

---

## Out of Scope

_What this feature explicitly does NOT include (to prevent scope creep)._

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| _e.g., AI model slow for long inputs_ | Medium | Low | Add loading message |

---

## Dependencies

- _e.g., Requires Phase 3 scripts table_
- _e.g., Requires OpenRouter API key with sonnet model access_

---

## Estimated Effort

| Task | Effort |
|------|--------|
| Builder script | S / M / L |
| SQL migration | S / M / L |
| Supervisor update | S / M / L |
| Documentation | S / M / L |
| Testing | S / M / L |

_S = < 1 hour, M = 2-4 hours, L = 4-8 hours_
