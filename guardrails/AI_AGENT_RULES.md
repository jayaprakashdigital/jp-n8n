# AIOS — AI Agent Rules (Development Agents)

**Purpose:** Rules for AI coding assistants (Claude Code, Cursor, etc.) working on AIOS.
**Owner:** Platform Lead
**Update Rule:** Add rules when new patterns of AI-agent mistakes are discovered.

---

## The Prime Directives

1. **Never modify runtime application logic** unless explicitly asked to debug a specific runtime issue.
2. **Never run `docker compose down`** — this takes production offline.
3. **Never run `git push --force`** on main branch.
4. **Never delete files** without reading them first and confirming they are not referenced.
5. **Always take a backup** before running any builder script for the first time.

---

## What AI Agents MAY Do

- Create and modify documentation files
- Write new Python builder scripts for new phases
- Write new governance/template files
- Run read-only database queries to understand schema
- Run builder scripts AFTER user confirmation
- Restart n8n (`docker compose restart n8n`) after deploying workflows
- Run `backup.sh` proactively

---

## What AI Agents MUST NOT Do

| Forbidden Action | Why |
|-----------------|-----|
| Modify `TELEGRAM__SUPERVISOR__V2` node logic directly in SQLite | Any mistake breaks ALL Telegram interaction |
| Change `N8N_ENCRYPTION_KEY` | All credentials become unusable |
| Drop or truncate database tables | Irreversible data loss |
| Commit `config/.env` to git | Exposes all secrets |
| Create workflows via n8n REST API | Returns 403 and is bypassed by direct SQLite anyway |
| Run multiple builder scripts simultaneously | SQLite write lock race condition |
| Use deprecated n8n node types | Workflows break on n8n update |
| Invent n8n node parameters | Node will silently fail with wrong params |

---

## Before Running Any Builder Script

Checklist:
- [ ] Read the existing builder script for the phase being modified
- [ ] Check `guardrails/DO_NOT_TOUCH.md` for protected components
- [ ] Run `bash scripts/backup.sh` first
- [ ] Confirm with user before running if script modifies protected workflows

---

## Code Generation Rules

When writing n8n workflow JavaScript code:
- Never write `// comment` as a standalone Python string between concatenated strings
- Always use `try/catch` for JSON parsing
- Always provide `|| 'default'` fallbacks for all JSON property access
- Never use `require()`, `import`, or `async/await`
- Test all regex patterns before embedding in workflow code

---

## Contribution Workflow for AI Agents

```
1. Understand the task fully before writing any code
2. Read existing patterns from phase25_builder.py or phase3_builder.py
3. Check docs/WORKFLOW_INDEX.md for existing workflow IDs
4. Check docs/API_CONTRACTS.md for subworkflow I/O schemas
5. Write builder script following CODING_STANDARDS.md
6. Propose plan to user before executing
7. Execute with backup first
8. Verify by checking SQLite + PostgreSQL after deploy
9. Update WORKFLOW_INDEX.md + CHANGELOG.md
```
