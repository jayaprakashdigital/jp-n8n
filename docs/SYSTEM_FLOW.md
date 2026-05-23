# AIOS — System Flow

**Purpose:** End-to-end data flow across all system components.
**Owner:** System Architect
**Update Rule:** Update when a new phase adds a major new flow path.

---

## Complete Content Creation Flow (Phase 3)

```
[USER] types "/script morning workout motivation"
         │
         ▼
[TELEGRAM API] sends update to webhook
         │
         ▼
[SUPERVISOR] detects P3 command, extracts topic
         │
         ▼
[P3 HANDLER] routes to CREATIVE__SCRIPT_PIPELINE__V1
         │
         ├── [HOOK OPTIMIZER] calls OpenRouter (haiku)
         │         └── returns 5 hooks, best_hook identified
         │
         ├── [SCRIPT GENERATOR] calls OpenRouter (sonnet)
         │         └── returns full 60s script, sections, word_count
         │         └── saves to scripts table
         │
         └── [CONTENT SCORER] calls OpenRouter (haiku)
                   └── returns scores: hook/retention/viral/clarity
                   └── saves to replay_scores table
         │
         ▼
[SUPERVISOR] formats Markdown reply with script preview + Approve/Reject/Regen buttons
         │
         ▼
[TELEGRAM] displays script to user
         │
         ▼
[USER] taps "✅ Approve"
         │
         ▼
[SUPERVISOR] callback flow → UPDATE pending_approvals SET status='approve'
         │
         ▼ (Phase 4 — planned)
[FFMPEG PIPELINE] renders 1080x1920 video
         │
         ▼ (Phase 5 — planned)
[INSTAGRAM API] uploads and publishes
```

---

## Session State Flow

```
First message from new user:
  INSERT INTO users (telegram_id, username)
  INSERT INTO sessions (user_id, session_data={}, message_count=0)

Every subsequent message:
  UPDATE sessions SET message_count = message_count + 1
  (after processing)
  UPDATE sessions SET session_data = {last_intent, last_msg_at, ...}

Session data structure:
{
  "last_intent": "p3_script",
  "last_msg_at": "2026-05-23T02:00:00Z",
  "active_workflow": "p3_script",
  "preferences": {}
}
```

---

## Error Flow

```
Any n8n workflow failure
         │ (via errorWorkflow setting)
         ▼
SYSTEM__ERROR_HANDLER__V1
         │
         ├── [Extract Error Info]
         │         └── workflow_name, last_node, error_message, execution_id
         │
         ├── [Log Error to DB] (continueOnFail=true)
         │         └── INSERT INTO execution_logs (event_type='error', status='error')
         │
         └── [Notify Admin] (neverError=true)
                   └── sendMessage to ADMIN_CHAT_ID (1241444951)
                   └── "⚠️ AIOS Error Alert\nWorkflow: ...\nFailed Node: ...\nError: ..."
```

---

## Approval Recovery Flow (Every 5 min)

```
SYSTEM__APPROVAL_RECOVERY__V1 (scheduleTrigger)
         │
         ├── [Expire Stale] → UPDATE pending_approvals SET status='expired'
         │         WHERE status='pending' AND expires_at < NOW()
         │
         └── [Get Pending] → SELECT where pending AND expires_at > NOW()
                              AND created_at < NOW() - INTERVAL '5 minutes'
                   │
                   └── [Build Reminders] → one item per pending approval
                             │
                             └── [Send Reminders] → sendMessage to each chat_id
```

---

## OpenRouter Request Flow

```
Code node builds:
{
  model: "anthropic/claude-3.5-haiku",
  messages: [
    {role: "system", content: "...system prompt..."},
    {role: "user",   content: "...user context + request..."}
  ],
  max_tokens: 1400,
  temperature: 0.7
}
         │
         ▼
HTTP POST https://openrouter.ai/api/v1/chat/completions
Headers: Authorization: Bearer <OR_KEY>
         Content-Type: application/json
         HTTP-Referer: https://n8n.srv1654276.hstgr.cloud
         X-Title: AIOS
         │
         ▼
Response: {choices: [{message: {content: "...JSON string..."}}]}
         │
         ▼
Code node: content.match(/\{[\s\S]*\}/) → JSON.parse → validate → use
```

---

## Database Write Flow (SQL Injection Prevention)

All user input is sanitized in a Code node BEFORE it reaches a Postgres node:

```javascript
// In Code node:
const safe = s => (s + '').replace(/'/g, "''");  // escape single quotes
const userSafe = safe(userInput);
const query = `INSERT INTO table (col) VALUES ('${userSafe}')`;
return [{ json: { query } }];

// In Postgres node:
// operation: executeQuery
// query: {{ $json.query }}
```

---

**Future Extension:** Phase 6 adds an analytics feedback loop where replay_scores data feeds back to improve prompt templates in `prompts` table.
