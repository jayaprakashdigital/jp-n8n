# Bug Fix Template

**Purpose:** Use this template when documenting and fixing a bug in AIOS.
**Owner:** Contributing developer
**Instructions:** Copy this file, rename it `BUGFIX-<short-name>.md`, fill in all sections.

---

## Bug Summary

**Bug ID:** BUG-YYYYMMDD-NN
**Reported By:** _Name or agent_
**Reported Date:** YYYY-MM-DD
**Severity:** Critical / High / Medium / Low
**Status:** Open / In Progress / Fixed / Closed

---

## Symptom

_What does the user observe? What error message appears? What behavior is wrong?_

Example:
```
User sends /script morning routine
Bot: [no response — Telegram shows spinning indicator then times out]
```

---

## Reproduction Steps

1. _Step 1 to trigger the bug_
2. _Step 2_
3. _Expected: what should happen_
4. _Actual: what happens instead_

---

## Root Cause Analysis

**Component affected:** _e.g., TELEGRAM__SUPERVISOR__V2 / "Send Reply" node_

**Root cause:**
_Technical explanation of why the bug occurs._

**Why it wasn't caught earlier:**
_e.g., Only triggered on P3 path which was added after the original node was written._

---

## Fix

**Files changed:**
- `scripts/phase3_builder.py` — describe the change

**Code change (before → after):**

Before:
```javascript
// old code
```

After:
```javascript
// new code
```

**Workflow node updated:**
- Workflow: `TELEGRAM__SUPERVISOR__V2`
- Node: `Send Reply`
- Change: Changed `$("Validate & Parse").item.json.chat_id` → `$json.chat_id`

---

## Verification

- [ ] Fix applied to builder script
- [ ] Builder script re-run with backup first
- [ ] n8n restarted after deploy
- [ ] Bug scenario tested manually in Telegram
- [ ] Regression tested (existing features still work)

---

## Prevention

**New guardrail or rule added:**
_e.g., Added rule to WORKFLOW_GUARDRAILS.md: never use backreferences in nodes that receive input from multiple upstream paths._

**Documentation updated:**
- [ ] INCIDENT_LOG.md
- [ ] KNOWN_ISSUES.md (resolved section)
- [ ] CHANGELOG.md

---

## Severity Definitions

| Level | Definition |
|-------|-----------|
| Critical | Bot completely unresponsive |
| High | Core feature broken for all users |
| Medium | Feature broken on specific path or for subset of users |
| Low | Minor UX issue, no data loss, workaround exists |
