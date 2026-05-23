# AIOS — Auth Flow

**Purpose:** Document authentication and authorization at every system boundary.
**Owner:** Security Lead
**Update Rule:** Update when new external integrations are added.

---

## Authentication Boundaries

### 1. Telegram → n8n (Webhook)
- **Method:** Shared secret (webhook URL obscurity)
- **Path:** `POST /webhook/aios-telegram-bot`
- **Verification:** Telegram sends updates only to registered webhook URL. URL is not guessable.
- **Enhancement (Phase 4):** Add Telegram's `X-Telegram-Bot-Api-Secret-Token` header verification.

### 2. n8n → OpenRouter (API Key)
- **Method:** Bearer token in Authorization header
- **Key:** `OR_KEY` (sk-or-v1-...)
- **Sent as:** `Authorization: Bearer <OR_KEY>` on every HTTP request
- **Storage:** Hardcoded in workflow HTTP nodes (Phase 4 task: migrate to n8n credential)

### 3. n8n → PostgreSQL
- **Method:** Username/password
- **User:** `aios_user`
- **Credential:** n8n credential ID `a20cebf1b1c648` (AES-256-CBC encrypted in SQLite)
- **Network:** Container-to-container only (127.0.0.1)

### 4. n8n → Telegram Bot API
- **Method:** Token in URL path
- **Format:** `https://api.telegram.org/bot<TOKEN>/<method>`
- **Storage:** Hardcoded in HTTP node URLs in builder scripts

### 5. User → Telegram Bot
- **Method:** Implicit (Telegram account = identity)
- **User identification:** `telegram_id` (from `message.from.id`)
- **Authorization:** No role-based access currently. All Telegram users can interact.
- **Enhancement (Phase 4):** Add allowlist of authorized Telegram IDs for sensitive commands.

### 6. Admin → n8n UI
- **Method:** Email/password (set during first-run setup)
- **Session:** HTTP-only cookie
- **Access:** Via `https://n8n.srv1654276.hstgr.cloud`

---

## n8n Credential Encryption

Credentials are stored in n8n's SQLite database, encrypted with AES-256-CBC:

```
Encryption process:
1. Generate 8-byte random salt
2. Derive 32-byte key + 16-byte IV from (ENCRYPTION_KEY + salt) using MD5 cascade
3. AES-256-CBC encrypt the credential JSON
4. Base64 encode: "Salted__" + salt + ciphertext

Decryption (Python, used in builder scripts):
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
```

**WARNING:** If `N8N_ENCRYPTION_KEY` is changed, all stored credentials become unreadable. There is no recovery path — credentials must be re-entered.

---

## Session Management

User sessions are stored in PostgreSQL `sessions` table:

```
Session lifecycle:
1. First message → INSERT user + session (ON CONFLICT DO UPDATE)
2. Every message → message_count + 1, updated_at = NOW()
3. After AI response → session_data JSONB updated with intent/state
4. No expiry currently (all sessions are permanent)
```

No JWT, no cookie, no token. Identity is always derived from Telegram's `message.from.id`.

---

## Authorization Matrix

| Action | Who Can Do It |
|--------|--------------|
| Send Telegram messages | Any Telegram user |
| View execution logs | Admin (via PostgreSQL direct access) |
| Modify workflows | Admin (via builder scripts only) |
| Access n8n UI | Admin (authenticated) |
| Access PostgreSQL | Admin (Docker exec only) |
| Receive error alerts | ADMIN_CHAT_ID only |

---

**Future Extension:** Phase 4 — add `authorized_users` table for role-based Telegram access control. Phase 5 — add OAuth2 for Instagram API authentication.
