# AIOS — Environment Variables

**Purpose:** Document every environment variable used by the AIOS platform.
**Owner:** Security Lead / DevOps
**Update Rule:** Add new variables here BEFORE using them. Never hardcode secrets in code.

---

## CRITICAL WARNING

> **NEVER commit the actual values to git.**
> The file `config/.env` is gitignored.
> Only `config/.env.example` (with placeholder values) should be committed.

---

## Variable Reference

### Telegram

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `TG_TOKEN` | `8675644315:AAEa...` | YES | Telegram Bot API token from @BotFather |
| `TG_API_BASE` | `https://api.telegram.org/bot` | YES | Base URL for Telegram API |
| `ADMIN_CHAT_ID` | `1241444951` | YES | Your personal Telegram chat ID for admin alerts |

### OpenRouter / AI

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `OR_KEY` | `sk-or-v1-...` | YES | OpenRouter API key |
| `OR_URL` | `https://openrouter.ai/api/v1/chat/completions` | YES | OpenRouter endpoint |

### n8n

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `N8N_ENCRYPTION_KEY` | `vdlIIW6Z...` | YES | AES key for n8n credential encryption. **DO NOT CHANGE AFTER FIRST DEPLOY** |
| `N8N_HOST` | `n8n.srv1654276.hstgr.cloud` | YES | Public n8n hostname |
| `N8N_PROTOCOL` | `https` | YES | Protocol |
| `WEBHOOK_URL` | `https://n8n.srv1654276.hstgr.cloud/` | YES | Base URL for n8n webhooks |
| `N8N_PROJECT_ID` | `0YzGnVQ4VzNb3gOx` | YES | n8n internal project ID |

### PostgreSQL

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `PG_HOST` | `aios-postgres` | YES | Docker container name |
| `PG_PORT` | `5432` | YES | Internal port |
| `PG_DATABASE` | `aios_db` | YES | Database name |
| `PG_USER` | `aios_user` | YES | Database user |
| `PG_PASSWORD` | `<strong_password>` | YES | Database password |
| `PG_CRED_ID` | `a20cebf1b1c648` | YES | n8n credential ID for PostgreSQL |

### Infrastructure

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `DOMAIN_NAME` | `srv1654276.hstgr.cloud` | YES | Base domain |
| `SUBDOMAIN` | `n8n` | YES | n8n subdomain |
| `SSL_EMAIL` | `admin@example.com` | YES | Let's Encrypt notifications |
| `GENERIC_TIMEZONE` | `Asia/Kolkata` | YES | Timezone for scheduled workflows |

### Traefik

| Variable | Example Value | Required | Description |
|----------|--------------|----------|-------------|
| `N8N_PROXY_HOPS` | `1` | YES | Trust headers from 1 proxy hop (Traefik) |

---

## config/.env Example (safe to commit)

```bash
# config/.env.example — copy to config/.env and fill in real values

# Telegram
TG_TOKEN=your_telegram_bot_token_here
ADMIN_CHAT_ID=your_telegram_chat_id

# OpenRouter
OR_KEY=sk-or-v1-your-openrouter-key-here

# n8n
N8N_ENCRYPTION_KEY=generate_32_char_random_string_here
N8N_HOST=n8n.yourdomain.com
N8N_PROJECT_ID=your_n8n_project_id

# PostgreSQL
PG_PASSWORD=your_strong_postgres_password

# Infrastructure
DOMAIN_NAME=yourdomain.com
SUBDOMAIN=n8n
SSL_EMAIL=your@email.com
GENERIC_TIMEZONE=Asia/Kolkata
```

---

## Generating Secure Values

```bash
# Generate N8N_ENCRYPTION_KEY (32 chars)
openssl rand -base64 24 | tr -d '+=/' | head -c 32

# Generate PG_PASSWORD
openssl rand -base64 32
```

---

## Where Variables Are Used

| Variable | Used in |
|----------|---------|
| `TG_TOKEN` | phase2_builder.py, phase25_builder.py, phase3_builder.py |
| `OR_KEY` | phase2_builder.py, phase3_builder.py (embedded in workflow HTTP nodes) |
| `N8N_ENCRYPTION_KEY` | n8n credential encryption, n8n_activate_workflows.py |
| `PG_CRED_ID` | All phase builder scripts (n8n credential reference) |
| `ADMIN_CHAT_ID` | phase25_builder.py (error handler Telegram alert) |
| `N8N_PROJECT_ID` | All phase builder scripts (workflow ownership) |

---

**Warnings:**
- If `N8N_ENCRYPTION_KEY` is lost or changed, all n8n credentials must be re-entered manually
- API keys embedded in workflow HTTP nodes are stored in n8n SQLite as plaintext inside workflow JSON — this is a known limitation; use n8n credentials where possible
- Phase 4 will migrate OR_KEY to an n8n credential to improve security

**Future Extension:** Add HashiCorp Vault or Docker Secrets for production-grade secret management in Phase 5+.
