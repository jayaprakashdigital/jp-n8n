# AIOS — Security Guardrails

**Purpose:** Non-negotiable security rules for all development on AIOS.
**Owner:** Security Lead
**Update Rule:** Rules can only be relaxed by the security lead with documented justification.

---

## The Five Hard Rules

### Rule 1: NEVER Commit Secrets
```
NEVER commit .env, API keys, tokens, passwords to git.
The .gitignore covers this but humans make mistakes.
```

Pre-commit check:
```bash
# Add to .git/hooks/pre-commit:
if git diff --cached | grep -E "(sk-or-v1|AAEa[A-Za-z0-9]|bot[0-9]{10}:)"; then
  echo "ERROR: Potential API key detected in commit. Aborting."
  exit 1
fi
```

### Rule 2: NEVER Expose User Data in Logs
```
NEVER log Telegram message content.
NEVER log user personal data (names, IDs) in plaintext admin messages.
Error alerts show workflow names and error types — not message content.
```

### Rule 3: ALWAYS Sanitize SQL Input
```
ALWAYS pass user text through safe() before Postgres queries.
const safe = s => (s + '').replace(/'/g, "''");
```

### Rule 4: NEVER Return Secrets to Users
```
NEVER send API keys, encryption keys, or internal IDs to Telegram users.
Error replies must be generic: "Processing issue — please try again."
```

### Rule 5: ALWAYS Validate AI Output
```
ALWAYS parse AI responses with try/catch.
ALWAYS validate intent against VALID_INTENTS set.
ALWAYS slice reply to safe length before sending.
```

---

## Network Security Rules

- n8n binds to `127.0.0.1:5678` — never change to `0.0.0.0`
- PostgreSQL binds to `127.0.0.1:5432` — never change to `0.0.0.0`
- Only Traefik exposes ports 80/443 externally
- All HTTP callbacks use HTTPS only

---

## Dependency Rules

- Never install npm packages in n8n Code nodes (`require()` is disabled)
- Python builder scripts: only use stdlib + pycryptodome
- Never add new Python dependencies without security review

---

**Future Extension:** Phase 5 — add input validation middleware before all API endpoints. Phase 6 — full security audit before analytics launch.
