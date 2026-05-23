# AIOS — Review Agent Rules

**Purpose:** Rules for AI agents performing code review, schema validation, and pre-deploy audits.
**Inherits From:** `agents/MASTER_AGENT_RULES.md`
**Owner:** Platform Lead

---

## Scope

This agent is responsible for:
- Reviewing builder scripts before execution
- Validating n8n workflow JSON before SQLite insertion
- Auditing SQL migrations for safety
- Checking API contract compliance
- Verifying documentation completeness

---

## Pre-Deploy Builder Script Review Checklist

For every builder script, verify:

### Python Structure
- [ ] `DB_PATH` points to correct SQLite path
- [ ] All workflow IDs use `uuid.uuid5(_NS, ...)` — not `uuid.uuid4()`
- [ ] `upsert_workflow()` is called — not raw SQLite INSERT
- [ ] `run_migration()` is called for any new SQL
- [ ] `backup.sh` is run or documented as pre-requisite

### n8n Node Types
- [ ] All node type strings exist in `templates/WORKFLOW_TEMPLATE.md` node type table
- [ ] All node versions match the approved versions
- [ ] No `require()`, `import`, or `async/await` in workflow JavaScript
- [ ] No `// comment` as standalone line between Python string concatenations

### SQL Safety
- [ ] All user-input variables are sanitized: `const safe = s => (s+'').replace(/'/g, "''")`
- [ ] All migrations use `IF NOT EXISTS`
- [ ] No DROP TABLE, TRUNCATE, or destructive ALTER statements
- [ ] All queries use `operation: "executeQuery"` in PostgreSQL nodes

### OpenRouter Calls
- [ ] `neverError: true` is set in options
- [ ] `HTTP-Referer` and `X-Title` headers are present
- [ ] Temperature ≤ 0.9
- [ ] Max tokens within limits (haiku ≤ 1400, sonnet ≤ 2000)

### Credentials
- [ ] PostgreSQL uses credential ID `a20cebf1b1c648` — never hardcoded connection string
- [ ] No API keys hardcoded in workflow JSON (they must come from n8n credential store)
- [ ] No credentials in any documentation file

---

## Workflow JSON Validation Rules

Before any workflow is inserted into SQLite:

1. **Node ID uniqueness**: all node `id` fields must be unique within the workflow
2. **Connection targets exist**: every node named in `connections` must exist in `nodes`
3. **Trigger node present**: every subworkflow must have `executeWorkflowTrigger` as entry
4. **Position fields valid**: all `[x, y]` positions must be numbers
5. **Type version match**: version numbers must match the registered node type version

### Connection Validation Pattern
```python
node_names = {n["name"] for n in nodes}
for source, targets in connections.items():
    assert source in node_names, f"Connection source not found: {source}"
    for branch in targets.get("main", []):
        for t in branch:
            assert t["node"] in node_names, f"Connection target not found: {t['node']}"
```

---

## API Contract Compliance Review

When a subworkflow is added or modified, verify against `docs/API_CONTRACTS.md`:

1. **Input fields**: does the workflow read all documented input fields?
2. **Output fields**: does the workflow output all documented output fields?
3. **Error path**: does the workflow handle the error case and still return valid JSON?
4. **Caller compatibility**: do existing callers (pipeline, handler) still work with updated I/O?

**Breaking change protocol**: If an I/O change is unavoidable:
1. Create V2 of the workflow with the new contract
2. Migrate callers to V2
3. Mark V1 as deprecated in `WORKFLOW_INDEX.md`
4. Do NOT delete V1 until all callers are migrated

---

## Documentation Review Checklist

After any phase or feature completion:

- [ ] `WORKFLOW_INDEX.md` has new workflow IDs and trigger types
- [ ] `DATABASE_SCHEMA.md` has new table definitions
- [ ] `API_CONTRACTS.md` has I/O schema for new subworkflows
- [ ] `MIGRATION_LOG.md` has the migration entry
- [ ] `CHANGELOG.md` has the version entry
- [ ] `PHASE_X.md` is updated with completion status
- [ ] `KNOWN_ISSUES.md` has any bugs discovered during build

---

## Security Review Rules

1. **No secrets in any documentation file** — grep for key patterns:
   ```bash
   grep -r "sk-or-v1-" /root/aios/docs/ /root/aios/guardrails/
   grep -r "AAE" /root/aios/docs/ /root/aios/guardrails/
   ```
2. **No raw message content in logs** — verify `execution_logs` table insert does not include message text
3. **SQL injection surface** — every dynamic SQL string must have sanitization traced

---

## Review Sign-off Format

When completing a review, report:

```
## Review Complete: <script/file name>

### Passed ✅
- [list of passing checks]

### Issues Found ⚠️
- [issue]: [description + line reference]

### Blockers 🛑
- [blocker]: [must fix before deploy]

### Recommendation
APPROVE / APPROVE WITH FIXES / BLOCK
```
