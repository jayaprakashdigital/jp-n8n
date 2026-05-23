# AIOS — Security Policy

**Purpose:** Define security standards, threat model, and response procedures for AIOS.
**Owner:** Security Lead
**Update Rule:** Review quarterly and after any security incident.

---

## Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| Leaked API keys in git | High | Critical | .gitignore, pre-commit hooks |
| SQL injection via Telegram input | Medium | High | Code node sanitization before all queries |
| Unauthorized n8n access | Low | Critical | Auth enabled, no public API exposure |
| Telegram bot spam/abuse | High | Medium | Rate limiting (10 req/min), session tracking |
| n8n credential decryption | Low | Critical | Strong encryption key, key rotation plan |
| VPS compromise | Low | Critical | Firewall (80/443 only), no SSH key sharing |

---

## Security Controls by Layer

### 1. Secret Management
- All secrets in `config/.env` (gitignored)
- n8n credentials encrypted with AES-256-CBC using `N8N_ENCRYPTION_KEY`
- API keys never logged, never returned in Telegram replies
- Builder scripts read keys from Python constants (not env vars — **Phase 4 task: move to env vars**)

### 2. Input Validation
Every user message passes through SQL sanitization before reaching PostgreSQL:
```javascript
const safe = s => (s + '').replace(/'/g, "''");  // escape single quotes
```
All string inputs are also `slice(0, maxLength)` bounded.

### 3. Rate Limiting
- 10 requests per minute per Telegram user
- PostgreSQL-backed (survives n8n restarts)
- Per-minute buckets using `DATE_TRUNC('minute', NOW())`
- Blocked users receive retry countdown

### 4. Network Security
- n8n port 5678 bound to `127.0.0.1` only (not public)
- PostgreSQL port 5432 bound to `127.0.0.1` only
- Only ports 80/443 exposed externally (via Traefik)
- TLS enforced; HTTP redirects to HTTPS

### 5. Error Handling
- All errors logged to `execution_logs` table
- Admin notified via Telegram on every workflow failure
- Error messages sent to admin contain context; generic "try again" sent to users
- Stack traces never exposed to end users

### 6. Workflow Protection
- Protected workflows cannot be modified through n8n UI during normal operation
- All workflow changes go through Python builder scripts
- Builder scripts run name-based deduplication to prevent duplicate workflows
- `workflow_versions` table tracks all deployed versions

---

## Data Privacy

| Data Type | Storage | Retention |
|-----------|---------|-----------|
| Telegram user IDs | PostgreSQL `users` | Indefinite |
| Session data | PostgreSQL `sessions` | Indefinite |
| Message content | Not stored (processed only) | Never persisted |
| Generated scripts | PostgreSQL `scripts` | Indefinite |
| Execution logs | PostgreSQL `execution_logs` | 30 days (manual cleanup currently) |
| Rate limit data | PostgreSQL `rate_limits` | Not cleaned (Phase 4 task) |

**WARNING:** Telegram message content is NOT stored in the database. It is processed in n8n Code nodes and only the AI-generated response is saved. This is intentional for privacy.

---

## Incident Response

### Suspected API Key Leak
1. Immediately rotate the key at the provider (Telegram @BotFather, OpenRouter dashboard)
2. Update `config/.env` with new key
3. Re-run affected builder script to update workflow HTTP nodes
4. Restart n8n
5. Log incident in `logs/SECURITY_LOG.md`
6. Scan git history: `git log -p --all | grep -E "(sk-or|AAEa|bot[0-9]+:)"`

### Suspected Database Compromise
1. Change `PG_PASSWORD` immediately
2. Revoke external access (firewall rule)
3. Take immediate backup
4. Audit `execution_logs` for anomalous activity
5. Log in `logs/SECURITY_LOG.md` and `logs/INCIDENT_LOG.md`

### Suspected n8n Compromise
1. Take n8n offline: `cd /docker/n8n && docker compose stop n8n`
2. Change n8n owner password
3. Rotate `N8N_ENCRYPTION_KEY` (requires re-entering ALL credentials)
4. Review execution history in n8n UI
5. Restart and re-verify

---

## Security Checklist (deploy each phase)

- [ ] No API keys committed to git
- [ ] `.env` in `.gitignore`
- [ ] All SQL inputs sanitized in Code nodes
- [ ] Rate limiting active and tested
- [ ] Error handler wired to supervisor (`errorWorkflow` setting)
- [ ] n8n port NOT publicly exposed
- [ ] PostgreSQL port NOT publicly exposed
- [ ] TLS certificate valid and auto-renewing
- [ ] Admin Telegram alerts working

---

**Future Extension:** Phase 5 — add IP allowlisting for Instagram API callbacks. Phase 6 — add audit logging to dedicated security log table.
