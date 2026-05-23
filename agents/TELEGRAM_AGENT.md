# AIOS — Telegram Agent Rules

**Purpose:** Rules for AI agents working on Telegram bot logic: supervisor, handlers, callbacks.
**Inherits From:** `agents/MASTER_AGENT_RULES.md`
**Owner:** Platform Lead

---

## Scope

This agent is responsible for:
- `TELEGRAM__SUPERVISOR__V2` and any V3+ successors
- All Telegram handler workflows (PHASE3__TELEGRAM_HANDLER__V1, etc.)
- Callback query handling
- Inline keyboard design
- Session state management

---

## Telegram Architecture (Required Knowledge)

### Message Flow
```
Webhook (POST) → Route Branch (isCallback?) 
    ├── YES → Answer Callback → Validate & Parse → Prepare AI Context → ...
    └── NO  → Validate & Parse → Check Rate Limit → Prepare AI Context → ...
                                                            ↓
                                              P3 Command Gate (isP3Command?)
                                              ├── YES → Call P3 Handler → Prep P3 Save Data
                                              └── NO  → Call Supervisor AI → Prepare Save Data
                                                              ↓ (both paths merge here)
                                                [Save Session, Log Execution, Send Reply]
                                                              ↓
                                                        Respond OK
```

### Critical Node: "Prepare AI Context"

This is the most sensitive node in AIOS. It:
- Extracts `chat_id`, `user_id`, `text`, `isCallback` from the webhook payload
- Detects P3 commands (`/research`, `/script`, `/story`, `/caption`, `/generate`)
- Sets `isP3Command`, `p3Command`, `p3Topic` flags
- Builds the AI system prompt with session context

**Rule: Always read this node's full JavaScript before modifying anything upstream or downstream.**

### Critical Node: "Send Reply"

This node receives input from both the AI path ("Prepare Save Data") and the P3 path ("Prep P3 Save Data"). It uses `$json.chat_id` (local reference, not backreference).

**Rule: Never change "Send Reply" to use a backreference to any specific upstream node.**

---

## Telegram API Rules

| Rule | Detail |
|------|--------|
| Always `answerCallbackQuery` | After any callback_query — removes spinner |
| Max button text length | 15 characters |
| Max buttons per row | 3 |
| Max keyboard rows | 2 |
| `callback_data` max length | 64 characters |
| Message text max length | 4096 characters — always `slice(0, 4096)` |
| Parse mode | Always `"Markdown"` — never HTML |
| User-provided text in Markdown | Escape with: `const escapeMd = s => (s+'').replace(/[*_`\[\]()]/g, '\\$&')` |

---

## Session State Rules

Session state is stored as JSONB in the `sessions` table, keyed by `user_id`.

**What goes in session state:**
- Conversation history (last N messages)
- Current approval context (if pending)
- Story progression state (current arc/chapter)
- Last intent classification

**What does NOT go in session state:**
- Message text content (privacy rule — never store)
- File paths or render job IDs (ephemeral)
- API responses (too large)

**Session merge pattern:**
```sql
INSERT INTO sessions (user_id, state, updated_at)
VALUES ($1, $2::jsonb, NOW())
ON CONFLICT (user_id) DO UPDATE
SET state = sessions.state || $2::jsonb, updated_at = NOW()
```

---

## P3 Command Extension Pattern

When adding a new Telegram command:

1. Add to P3 detection in "Prepare AI Context":
```javascript
const P3_CMDS = {
    '/existing': 'existing',
    '/newcommand': 'newaction'  // Add here
};
```

2. Add IF node in handler:
```
... → Is Story? → [true] Prep Story
                 [false] Is NewCommand? → [true] Prep NewCommand
                                        [false] Prep Caption (default)
```

3. Never remove or reorder existing commands — always ADD to the cascade.

---

## Inline Keyboard Design Rules

```javascript
// Correct button structure:
{
    "inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": "approve_12345"},
        {"text": "❌ Reject",  "callback_data": "reject_12345"}
    ]]
}
```

- `callback_data` must be `<action>_<id>` format, max 64 chars
- Always filter button arrays: `.filter(b => b && b.text)` before processing
- Always call `answerCallbackQuery` before responding to a callback

---

## Forbidden in This Domain

- Modifying the supervisor's webhook path (`aios-telegram-bot`) — Telegram webhook is registered to this exact path
- Adding sleep/delay nodes to the main supervisor path — must respond in < 30 seconds
- Sending HTML to users — Telegram Markdown only
- Storing message text content in any database table
