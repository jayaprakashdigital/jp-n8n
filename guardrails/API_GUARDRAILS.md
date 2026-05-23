# AIOS — API Guardrails

**Purpose:** Rules for all external API interactions (OpenRouter, Telegram, future APIs).
**Owner:** Integration Lead
**Update Rule:** Update when new APIs are integrated.

---

## OpenRouter

- Always include `HTTP-Referer` and `X-Title` headers (required by OpenRouter ToS)
- Always use `neverError: true` equivalent — add `{"response": {"response": {"neverError": true}}}` to options
- Always parse with regex extraction, not direct JSON.parse on full response
- Max tokens: haiku ≤ 1400, sonnet ≤ 2000
- Temperature: never above 0.9
- Never retry failed calls automatically (may cause double-billing)
- If 429: alert admin, do not retry silently

## Telegram Bot API

- Always use `answerCallbackQuery` after receiving a callback_query (removes spinner)
- `callback_data` max 64 characters — enforce in code
- Message text max 4096 characters — always `slice(0, 4096)` before sending
- Never send more than 1 message per Telegram interaction (except callback + reply)
- `parse_mode: "Markdown"` — escape `_`, `*`, `` ` `` in user-provided content
- Never store Telegram message content in database (privacy rule)

## PostgreSQL (n8n Credential)

- Always use the n8n credential `AIOS PostgreSQL` (ID: `a20cebf1b1c648`)
- Never hardcode PostgreSQL connection strings in workflow nodes
- All queries via `operation: "executeQuery"` — never use other operations

## Future APIs (Instagram, YouTube, etc.)

- OAuth tokens must be stored in n8n credentials (encrypted), never in workflow JSON
- Rate limits must be respected — add per-platform delay queues
- Failed uploads must be logged to `upload_history` with status='failed'
