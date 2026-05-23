# AIOS — Security Log

**Purpose:** Record all security-relevant events: audits, findings, mitigations, and policy changes.
**Owner:** Security Lead
**Update Rule:** Add entries immediately when a security event occurs. Never delete entries.
**Format:** [DATE] [SEVERITY] — Description

---

## Security Events

### 2026-05-23 [INFO] — Initial security audit (Phase 2.5)

**Scope:** Full review of n8n workflows, credentials, and database schema.

**Findings:**
- No hardcoded credentials found in workflow JSON
- OpenRouter API key stored in n8n credential store (encrypted)
- Telegram bot token stored in n8n credential store (encrypted)
- PostgreSQL credentials stored in n8n credential store (encrypted)
- Rate limiting implemented (10 req/min per user)
- Execution logs do not contain message content (privacy compliant)

**Mitigations applied:**
- `.gitignore` excludes `config/.env` and all credential files
- `SECURITY_GUARDRAILS.md` added with hard rules for all contributors

**Status:** No critical issues. Monitoring recommended.

---

### 2026-05-23 [INFO] — SQL injection prevention audit (Phase 3)

**Scope:** All PostgreSQL nodes in Phase 3 workflows.

**Findings:**
- All user-supplied text routed through sanitization function:
  ```javascript
  const safe = s => (s+'').replace(/'/g, "''");
  ```
- No dynamic query construction using unsanitized input found
- All queries use `operation: "executeQuery"` (no DDL operations in runtime)

**Status:** No issues found.

---

## Security Policy Versions

| Date | Policy | Version | Change |
|------|---------|---------|--------|
| 2026-05-23 | SECURITY_POLICY.md | 1.0 | Initial policy document |
| 2026-05-23 | SECURITY_GUARDRAILS.md | 1.0 | Hard rules for contributors |

---

## Credential Inventory

| Credential | Store | Rotation Schedule |
|-----------|-------|-------------------|
| OpenRouter API Key | n8n credential store | Manual, when compromised |
| Telegram Bot Token | n8n credential store | Manual, when compromised |
| PostgreSQL password | n8n credential store | Manual, when compromised |

**Note:** Credential IDs are safe to log (they are internal references, not the secrets themselves).
- PostgreSQL credential ID: `a20cebf1b1c648`

---

## Incident Response Contact

See `docs/SECURITY_POLICY.md` for full incident response procedures.

For critical incidents: immediately rotate affected credentials and notify admin via Telegram (chat_id: 1241444951).

---

## Future Audit Schedule

| Phase | Audit Trigger |
|-------|--------------|
| Phase 4 | Before FFmpeg pipeline activation (Execute Command node risk) |
| Phase 5 | Before Instagram/YouTube OAuth integration |
| Phase 6 | Before analytics data storage implementation |
