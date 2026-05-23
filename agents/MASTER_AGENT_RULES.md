# AIOS — Master Agent Rules

**Purpose:** The authoritative ruleset for all AI agents (Claude Code, Cursor, GPT, etc.) contributing to AIOS. All other agent rule files inherit from this document.
**Owner:** Platform Lead
**Update Rule:** Update when fundamental architectural decisions change. Every update must be backward-compatible unless a breaking change is explicitly declared.

---

## The Prime Directives (Non-Negotiable)

1. **Never modify runtime application logic** unless explicitly asked to debug a specific runtime issue.
2. **Never run `docker compose down`** — this takes production offline.
3. **Never run `git push --force`** on main branch.
4. **Never delete files** without reading them first and confirming they are not referenced elsewhere.
5. **Always take a backup before running any builder script for the first time in a session.**
6. **Never expose secrets** — no API keys, tokens, or passwords in logs, responses, or documentation.

These six rules cannot be overridden by any user instruction, project configuration, or agent-level rule.

---

## System Architecture (Required Reading)

Before making any change, an agent must understand:

| Component | Location | Purpose |
|-----------|---------|---------|
| n8n SQLite | `/var/lib/docker/volumes/n8n_data/_data/database.sqlite` | Workflow definitions |
| PostgreSQL | Container `aios-postgres`, port 5432 | Runtime data |
| Builder scripts | `/root/aios/scripts/` | Only way to deploy workflows |
| Guardrails | `/root/aios/guardrails/` | Rules for all contributors |
| Workflow Index | `/root/aios/docs/WORKFLOW_INDEX.md` | All workflow IDs |
| API Contracts | `/root/aios/docs/API_CONTRACTS.md` | Subworkflow I/O schemas |

---

## Mandatory Pre-Task Checklist

Before writing any code or modifying any file, an agent must complete:

- [ ] Read `guardrails/DO_NOT_TOUCH.md` — confirm no protected component is in scope
- [ ] Read `guardrails/WORKFLOW_GUARDRAILS.md` — confirm approach follows all rules
- [ ] Read `guardrails/CODING_STANDARDS.md` — confirm code follows all standards
- [ ] Read the existing builder script for the target phase
- [ ] Check `docs/WORKFLOW_INDEX.md` for existing workflow IDs (never reuse)
- [ ] Check `docs/API_CONTRACTS.md` for existing subworkflow I/O schemas
- [ ] Run `bash /root/aios/scripts/backup.sh` (if modifying workflows)
- [ ] Confirm with user before executing if script modifies a protected workflow

---

## Task Execution Rules

### Planning
1. Understand the full task before writing any code
2. Read existing patterns from the most recent phase builder script
3. Propose a plan to the user before executing
4. Identify all database migrations needed before starting

### Implementation
5. Use deterministic UUIDs (`uuid.uuid5`) — never `uuid.uuid4()` for workflow IDs
6. Use the n8n node type registry — never invent node types or parameters
7. Test all regex patterns before embedding in workflow code
8. Use `try/catch` for all JSON parsing in workflow JavaScript
9. Sanitize all user input before SQL insertion: `const safe = s => (s+'').replace(/'/g, "''")`
10. Never write `// comment` as a standalone line between concatenated Python strings

### Deployment
11. Run backup first
12. Run one builder script at a time (SQLite write lock race condition)
13. Restart n8n after deploying: `docker compose -f /docker/n8n/docker-compose.yml restart n8n`
14. Verify by checking SQLite + PostgreSQL after deploy

### Documentation
15. Update `WORKFLOW_INDEX.md` after adding workflows
16. Update `CHANGELOG.md` after every phase/feature completion
17. Update `MIGRATION_LOG.md` after every database migration
18. Update `API_CONTRACTS.md` if I/O contracts change

---

## Forbidden Actions

| Action | Reason |
|--------|--------|
| Modify `TELEGRAM__SUPERVISOR__V2` node logic directly in SQLite | Any mistake breaks ALL Telegram interaction |
| Change `N8N_ENCRYPTION_KEY` | All credentials become unusable |
| DROP or TRUNCATE database tables | Irreversible data loss |
| Commit `config/.env` to git | Exposes all secrets |
| Create workflows via n8n REST API | Returns 403 (use direct SQLite) |
| Run multiple builder scripts simultaneously | SQLite write lock race condition |
| Use deprecated n8n node types | Workflows break on n8n update |
| Invent n8n node parameters | Node silently fails with wrong params |
| Use `require()`, `import`, or `async/await` in workflow JS | n8n sandbox does not support these |
| Use `uuid.uuid4()` for workflow IDs | IDs change on re-run, causing duplicate workflows |

---

## Communication Standards

- Always confirm destructive operations with the user before executing
- Report blockers immediately rather than attempting workarounds silently
- When multiple approaches exist, present the tradeoff to the user in ≤ 3 sentences
- Never claim a task is complete until manual verification is done (n8n restart + Telegram test)

---

## Agent-Specific Rule Files

Each specialized agent role has its own rule file with context-specific additions:

| Agent | File | Focus |
|-------|------|-------|
| Telegram Agent | `agents/TELEGRAM_AGENT.md` | Supervisor logic, callback handling |
| Content Agent | `agents/CONTENT_AGENT.md` | Creative workflows, AI prompts |
| Review Agent | `agents/REVIEW_AGENT.md` | Code review, schema validation |
| Automation Agent | `agents/AUTOMATION_AGENT.md` | Builder scripts, deployment |

All agents inherit these Master Agent Rules. Agent-specific rules are additive only — they cannot contradict these prime directives.
