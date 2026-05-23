# AIOS — Error Handling

**Purpose:** Document how errors are caught, logged, and recovered at every layer.
**Owner:** Platform Reliability Lead
**Update Rule:** Update when new error patterns are discovered or new recovery procedures added.

---

## Error Handling Architecture

```
Layer 1: Node-level    — continueOnFail=true on non-critical nodes
Layer 2: Workflow-level — errorWorkflow wired to SYSTEM__ERROR_HANDLER__V1
Layer 3: Parse-level   — try/catch in all Code nodes with fallback replies
Layer 4: HTTP-level    — neverError=true on all Telegram API calls
```

---

## Node-Level Protection

### `continueOnFail: true`
Applied to non-critical nodes that should not block the main flow:

| Workflow | Node | Why continueOnFail |
|----------|------|--------------------|
| TELEGRAM__SUPERVISOR__V2 | Log Execution | DB logging failure must not block reply |
| SYSTEM__ERROR_HANDLER__V1 | Log Error to DB | Already in error handler — can't recurse |
| All Phase 3 workflows | Log Execution | Same reason |
| SYSTEM__APPROVAL_RECOVERY__V1 | Expire Stale Approvals | Maintenance task, non-critical |

### `neverError: true` (HTTP nodes)
Applied to all Telegram API calls so a Telegram API failure doesn't crash the workflow:

| Workflow | Node | URL |
|----------|------|-----|
| TELEGRAM__SUPERVISOR__V2 | Send Rate Warning | Telegram sendMessage |
| SYSTEM__APPROVAL_RECOVERY__V1 | Send Reminders | Telegram sendMessage |
| SYSTEM__ERROR_HANDLER__V1 | Notify Admin | Telegram sendMessage |

---

## Code Node Error Pattern

All Code nodes that call OpenRouter or parse JSON use this pattern:

```javascript
let result = { /* safe defaults */ };
let parseOk = false;

try {
  const content = d?.choices?.[0]?.message?.content || '';
  if (!content.trim()) throw new Error('Empty AI response');
  const match = content.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('No JSON object in response');
  const parsed = JSON.parse(match[0]);
  // ... populate result from parsed
  parseOk = true;
} catch(e) {
  // fallback: use raw content or default values
  result.reply = content.trim().slice(0, 400) || '🔄 Processing issue — please try again.';
}
```

**Rule:** Every Code node that parses external data MUST have a try/catch with sensible defaults.

---

## SYSTEM__ERROR_HANDLER__V1

Automatically triggered when any workflow with `errorWorkflow` setting fails.

**Currently wired:** `TELEGRAM__SUPERVISOR__V2`

**Trigger conditions:**
- Unhandled JavaScript exception in a Code node
- HTTP Request node failure (when neverError is false)
- PostgreSQL node failure (when continueOnFail is false)
- n8n internal execution error

**What it captures:**
```javascript
{
  workflow_name,     // e.g. "TELEGRAM__SUPERVISOR__V2"
  execution_id,      // n8n execution ID
  last_node,         // last node that ran before failure
  error_message,     // first 300 chars of error
  alert             // formatted Telegram message for admin
}
```

**Admin alert format:**
```
⚠️ AIOS Error Alert

Workflow: TELEGRAM__SUPERVISOR__V2
Failed Node: Call Supervisor AI
Error: OpenRouter: 429 Too Many Requests
Time: 14:23:05
```

---

## Error Codes Reference

| Code | Meaning | Action |
|------|---------|--------|
| OpenRouter 429 | Rate limit exceeded | Wait and retry; check OR_KEY usage |
| OpenRouter 401 | Invalid API key | Rotate OR_KEY, update workflows |
| Telegram 400 | Bad request (invalid chat_id, etc.) | Check session data validity |
| Telegram 403 | Bot blocked by user | Mark user inactive, remove pending approvals |
| PostgreSQL connection refused | DB container down | `docker start aios-postgres` |
| n8n 403 on REST API | Authentication required | Use SQLite direct access (builder scripts) |

---

## Supervisor Parse Fallback

When AI returns invalid JSON, the supervisor falls back gracefully:

```javascript
// If content has text but JSON parse fails:
ai.reply = content.replace(/```json?/g,'').replace(/```/g,'').trim().slice(0,400);

// If content is completely empty:
ai.reply = '🔄 Processing issue — please try again.';

// validation_ok = false is logged (not shown to user)
```

---

## Monitoring

All errors are queryable from PostgreSQL:

```sql
-- Recent errors
SELECT workflow_name, event_type, error_message, created_at
FROM execution_logs
WHERE status = 'error'
ORDER BY created_at DESC
LIMIT 20;

-- Error rate by workflow (last 24h)
SELECT workflow_name, COUNT(*) as errors
FROM execution_logs
WHERE status = 'error' AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY workflow_name ORDER BY errors DESC;

-- Parse failure rate
SELECT status, COUNT(*) FROM execution_logs
WHERE event_type = 'message_processed'
GROUP BY status;
```

---

**Warnings:**
- If the error handler itself fails, there is no secondary notification. Keep error handler simple.
- `continueOnFail=true` silently swallows errors — always have logging before it.

**Future Extension:** Phase 4 — add `SYSTEM__ALERT_MANAGER__V1` with multi-channel alerting (Telegram + email). Add structured error codes to `execution_logs.metadata`.
