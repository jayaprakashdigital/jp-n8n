# AIOS — Telegram Bot Flow

**Purpose:** Complete message lifecycle from Telegram user to n8n response.
**Owner:** Bot Integration Lead
**Update Rule:** Update when supervisor logic changes or new commands are added.

---

## Bot Identity

- **Bot Username:** @N8ninsta_jp_bot
- **Webhook URL:** `https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot`
- **Method:** POST
- **Handler:** `TELEGRAM__SUPERVISOR__V2`

---

## Message Flow (Regular Text)

```
User sends message
      │
      ▼
Telegram API → POST /webhook/aios-telegram-bot
      │
      ▼
[Extract Message] — parses body.message or body.callback_query
      │            sets: chatId, fromId, username, text, isCallback
      ▼
[Route Branch IF] — isCallback?
      │
      ├── TRUE ──► [Handle Callback]
      │                   └── parse action from callback_data
      │                   └── [Answer Callback] → answerCallbackQuery
      │                   └── [Resolve Approval] → UPDATE pending_approvals
      │                   └── [Send Callback Reply] → sendMessage
      │
      └── FALSE ──► [Check Rate Limit]
                          └── INSERT/UPDATE rate_limits table
                          └── RETURNING: request_count, is_blocked, retry_after_secs
                          │
                    [Rate Gate IF] — is_blocked?
                          │
                          ├── TRUE ──► [Send Rate Warning] (END)
                          │
                          └── FALSE ──► [Load Session]
                                              └── UPSERT users + sessions
                                              └── increment message_count
                                              │
                                        [Prepare AI Context]
                                              └── detect P3 commands
                                              └── build system prompt + context
                                              │
                                        [P3 Command Gate IF] — isP3Command?
                                              │
                                              ├── TRUE ──► [Call P3 Handler]
                                              │               └── routes to subworkflow
                                              │           [Prep P3 Save Data]
                                              │
                                              └── FALSE ──► [Call Supervisor AI]
                                                              └── OpenRouter HTTP
                                                          [Validate & Parse]
                                                          [Prepare Save Data]
                                              │
                                        [Save Session] + [Log Execution] + [Send Reply]
                                              │
                                        [Respond OK] → HTTP 200 to Telegram
```

---

## Phase 3 Command Flow

When user sends `/research Tamil Nadu food`, the flow diverges:

```
[Prepare AI Context]
      │
      ├── detects: text.startsWith('/research')
      ├── sets: isP3Command=true, p3Command='research', p3Topic='Tamil Nadu food'
      │
      ▼
[P3 Command Gate] → TRUE
      │
      ▼
[Call P3 Handler] → PHASE3__TELEGRAM_HANDLER__V1
      │
      ▼ (receives full AI context JSON)
[Is Research? IF] → TRUE
      │
      ▼
[Prep Research] → {niche: 'Tamil Nadu food', telegram_id: ...}
      │
      ▼
[Run Viral Engine] → RESEARCH__VIRAL_ENGINE__V1
      │ (waits for completion)
      ▼ (returns: {trends[], best_hook, content_angles[], ...})
[Format Research Reply]
      │ → builds Markdown message with trend list
      │ → adds inline keyboard: [Generate Script] [New Research]
      ▼
returns {reply, reply_markup, command, topic}
      │
      ▼ (back in supervisor)
[Prep P3 Save Data]
      │ → builds saveSQL, logSQL
      │ → sends to Save Session + Log + Send Reply in parallel
```

---

## Callback Flow

When user taps "Approve" button:

```
Telegram sends: {callback_query: {data: "approve", message: {...}, from: {...}}}
      │
[Extract Message] → isCallback=true, text="approve"
      │
[Route Branch] → TRUE (callback path)
      │
[Handle Callback] → reply = "✅ Approved! Moving to next stage."
      │
[Answer Callback] → answerCallbackQuery (removes loading spinner)
      │
[Resolve Approval] → UPDATE pending_approvals SET status='approve'
      │
[Send Callback Reply] → sendMessage with the reply text
```

---

## Command Reference

| Command | Detected by | Routes to |
|---------|------------|-----------|
| `/start` | AI classifier | inline reply in supervisor |
| `/help` | AI classifier | inline reply |
| `/status` | AI classifier | inline reply |
| `/research <topic>` | P3 detector | RESEARCH__VIRAL_ENGINE__V1 |
| `/script <topic>` | P3 detector | CREATIVE__SCRIPT_PIPELINE__V1 |
| `/story <theme>` | P3 detector | MEMORY__TAMIL_STORY_ENGINE__V1 |
| `/caption <topic>` | P3 detector | CAPTION__GENERATOR__V1 |
| `/generate <topic>` | P3 detector (alias) | CREATIVE__SCRIPT_PIPELINE__V1 |
| Free text | AI classifier | OpenRouter → intent routing |

---

## Telegram API Calls Made

| Node | API Endpoint | Purpose |
|------|-------------|---------|
| Answer Callback | `answerCallbackQuery` | Dismiss button loading state |
| Send Callback Reply | `sendMessage` | Respond to button taps |
| Send Rate Warning | `sendMessage` | Rate limit notification |
| Send Callback Reply | `sendMessage` | Callback confirmation |
| Send Reply | `sendMessage` | Main AI/P3 response |
| Error Notify (error handler) | `sendMessage` | Admin alert on failure |
| Approval Recovery | `sendMessage` | Pending approval reminder |

---

## Inline Keyboard Patterns

### Approval Buttons (scripts/generated content)
```json
{
  "inline_keyboard": [[
    {"text": "✅ Approve",    "callback_data": "approve"},
    {"text": "❌ Reject",     "callback_data": "reject"},
    {"text": "🔄 Regen",      "callback_data": "regenerate"}
  ]]
}
```

### Research Follow-up
```json
{
  "inline_keyboard": [[
    {"text": "📝 Generate Script", "callback_data": "p3_script"},
    {"text": "🔄 New Research",    "callback_data": "p3_research"}
  ]]
}
```

---

## Rate Limiting

- **Limit:** 10 messages per minute per Telegram user
- **Window:** 1-minute buckets (`DATE_TRUNC('minute', NOW())`)
- **Storage:** `rate_limits` PostgreSQL table
- **On block:** Returns retry_after_secs countdown to user

---

## Error Handling

- All Telegram API calls use `neverError: true` option (HTTP 4xx/5xx won't stop the workflow)
- If OpenRouter fails: fallback reply is sent using raw content
- If PostgreSQL fails: `continueOnFail: true` on log/save nodes
- Unhandled errors: caught by `SYSTEM__ERROR_HANDLER__V1` via `errorWorkflow` setting

---

**Warnings:**
- Only ONE webhook path: `aios-telegram-bot`. Never create a second Telegram webhook.
- Telegram webhook must be re-registered if the n8n URL changes
- `callback_data` max 64 characters

**Future Extension:** Phase 4 — add `/render` command to trigger FFmpeg pipeline after script approval.
