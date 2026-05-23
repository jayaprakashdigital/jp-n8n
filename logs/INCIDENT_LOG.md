# AIOS — Incident Log

**Purpose:** Record all production incidents, outages, and unexpected behavior.
**Owner:** Platform Lead
**Update Rule:** Log every incident at time of detection. Add resolution when resolved. Never delete.
**Format:** INC-YYYYMMDD-NN

---

## Active Incidents

_None._

---

## Resolved Incidents

### INC-20260523-01 — Supervisor both branches running simultaneously
**Detected:** 2026-05-23
**Severity:** High (all callback messages triggered both paths)
**Symptom:** When user tapped inline keyboard button, both the callback handler and message handler ran, causing duplicate DB writes and double responses.
**Root Cause:** Missing IF node to gate on `isCallback` boolean; n8n fan-out ran both branches unconditionally.
**Fix:** Added "Route Branch" IF node (`isCallback === true`) as the first routing node after the webhook.
**Resolved:** 2026-05-23
**Prevention:** WORKFLOW_GUARDRAILS.md rule #7: always gate callback vs message paths with explicit IF node.

---

### INC-20260523-02 — TypeError: b.text.toLowerCase on undefined
**Detected:** 2026-05-23
**Severity:** Medium (approval buttons crashed supervisor)
**Symptom:** Approval workflow sent inline keyboard with mixed null/string buttons; supervisor crashed on button text processing.
**Root Cause:** Inline keyboard builder did not filter null entries; supervisor assumed all button objects had `.text` property.
**Fix:** Added `.filter(b => b && b.text)` before all `.map(b => b.text.toLowerCase())` calls.
**Resolved:** 2026-05-23
**Prevention:** CODING_STANDARDS.md: always filter button arrays before accessing properties.

---

### INC-20260523-03 — SyntaxError in f-string from escaped quotes
**Detected:** 2026-05-23
**Severity:** Medium (builder script failed to generate valid Python)
**Symptom:** `\"intent\"` inside a Python f-string caused SyntaxError when the builder script was executed.
**Root Cause:** Backslash-escaped double quotes are not valid inside Python f-string expressions.
**Fix:** Changed all f-string JSON field references from `\"key\"` to single-quoted `'key'` format.
**Resolved:** 2026-05-23
**Prevention:** CODING_STANDARDS.md: use single quotes for JSON keys inside Python f-strings.

---

### INC-20260523-04 — Send Reply broke on P3 path (backreference)
**Detected:** 2026-05-23
**Severity:** High (all P3 commands returned empty reply to user)
**Symptom:** After Phase 3 deployment, `/research`, `/script`, `/story`, `/caption` commands produced no Telegram reply.
**Root Cause:** "Send Reply" node used `$("Validate & Parse").item.json.chat_id` — a backreference that only resolved when the execution path went through "Validate & Parse". The P3 path bypassed that node entirely.
**Fix:** Changed "Send Reply" to use `$json.chat_id` (local reference). Both "Prepare Save Data" and "Prep P3 Save Data" were updated to output identical structure: `{chat_id, reply, reply_markup, saveSQL, logSQL}`.
**Resolved:** 2026-05-23
**Prevention:** WORKFLOW_GUARDRAILS.md rule: never use backreferences in nodes that receive input from multiple upstream paths.

---

## Incident Template

```
### INC-YYYYMMDD-NN — Short title
**Detected:** YYYY-MM-DD
**Severity:** Critical / High / Medium / Low
**Symptom:** What the user or system observed
**Root Cause:** The underlying technical cause
**Fix:** Exact change made to resolve
**Resolved:** YYYY-MM-DD
**Prevention:** What guardrail or rule was added to prevent recurrence
```

---

## Severity Definitions

| Level | Definition | SLA |
|-------|-----------|-----|
| Critical | Entire Telegram bot unresponsive | Resolve within 1 hour |
| High | Core feature broken for all users | Resolve within 4 hours |
| Medium | Feature broken for subset of users or paths | Resolve within 24 hours |
| Low | Minor UX issue, no data loss | Resolve at next phase |
