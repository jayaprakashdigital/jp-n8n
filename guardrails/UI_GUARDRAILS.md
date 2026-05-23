# AIOS — UI Guardrails (n8n + Telegram)

**Purpose:** Rules for the n8n UI and Telegram bot interface.
**Owner:** Platform Lead

---

## n8n UI Rules

- Use n8n UI for VIEWING executions and logs only
- Never create or edit workflows in the UI — use builder scripts
- Never manually activate/deactivate workflows in the UI (use builder active=True/False)
- Never delete credentials from UI without updating builder scripts
- Never change execution timeout settings

## Telegram Bot Interface Rules

- Bot must always respond within 30 seconds (Telegram webhook timeout)
- If processing takes longer, send "Processing..." message first
- Always use `parse_mode: "Markdown"` for formatted replies
- Inline keyboard buttons: max 3 per row, max 2 rows per message
- Button text: max 15 characters for readability
- Error messages to users: always friendly, never expose internal errors
- Never send HTML to users (use Markdown only)

## Markdown Formatting Rules (Telegram)

```
Bold:    *text*
Italic:  _text_
Code:    `code`
Pre:     ```code block```
```

Always escape user-provided text before embedding in Markdown:
```javascript
const escapeMd = s => (s+'').replace(/[*_`\[\]()]/g, '\\$&');
```
