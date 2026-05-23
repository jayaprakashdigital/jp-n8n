# AIOS — Workflow Guardrails

**Purpose:** Rules that every n8n workflow must follow to maintain platform stability.
**Owner:** Platform Architecture Lead
**Update Rule:** Update when new patterns are discovered or rules are refined.

---

## Mandatory Rules

### 1. Builder Script Only
All workflows MUST be deployed via Python builder scripts. Never create or edit workflows through the n8n UI.

**Why:** n8n UI edits are not tracked in git, cannot be reproduced, and can silently break integrations.

### 2. Fixed Workflow IDs
All workflows must use deterministic, fixed UUIDs generated via `uuid5` with a known namespace.

```python
_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
wf_id = str(uuid.uuid5(_NS, "aios/p3/viral_engine"))
```

**Why:** Prevents ID drift on re-deploys. Allows safe `ON CONFLICT DO UPDATE` behavior.

### 3. Name-Based Deduplication
Every `upsert_workflow()` call must delete existing workflows with the same name before inserting.

```python
cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
for (old_id,) in cur.fetchall():
    # delete old webhook_entity, shared_workflow, workflow_history
    cur.execute("DELETE FROM workflow_entity WHERE id=?", (old_id,))
```

**Why:** Prevents duplicate workflows accumulating on re-runs.

### 4. Error Workflow Wiring
Any workflow with a Telegram webhook MUST have `errorWorkflow` set to `SYSTEM__ERROR_HANDLER__V1`:

```python
settings = {
    "executionOrder": "v1",
    "errorWorkflow": "99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2"
}
```

### 5. Non-Critical Node Protection
Any node that logs or records data (but is NOT core to the response) MUST have `continueOnFail: true`:

```python
pg_node("log-01", "Log Execution", [pos, 300], sql, continue_on_fail=True)
```

### 6. Only Verified Node Types
Use ONLY node types listed in `docs/ARCHITECTURE.md` Node Type Registry. Never use beta, community, or unlisted nodes.

### 7. SQL Input Sanitization
All user input passed to Postgres nodes MUST be sanitized in a Code node first:

```javascript
const safe = s => (s + '').replace(/'/g, "''");
const query = `INSERT INTO table (col) VALUES ('${safe(userInput)}')`;
return [{ json: { query } }];
```

### 8. Webhook Uniqueness
Only ONE workflow may own the `aios-telegram-bot` webhook path. Never create a second Telegram webhook.

### 9. JavaScript Comment Rule
Never write standalone `//` comment lines between Python string concatenation. All JS comments must be INSIDE string literals:

```python
# WRONG:
js = (
    "const x = 1;\n"
)
// This line will crash Python parsing
js += "const y = 2;\n"

# CORRECT:
js = (
    "const x = 1;\n"
    "// this comment is inside the string\n"
    "const y = 2;\n"
)
```

### 10. No UI Password in Code
Never hardcode the n8n UI password or PostgreSQL password in workflow code. Use n8n credentials.

---

## Node Position Convention

```
x-axis: 240 → 460 → 680 → 900 → 1120 → 1340 → 1560 → 1780 → 2000...  (steps of 220)
y-axis: 300 = main flow
        120 = callback path (above)
        480 = rate-limited path
        600 = session/AI path
        720 = parallel execution (logging)
        840 = P3 subworkflow path
```

---

## Naming Conventions

```
Workflow names: {DOMAIN}__{FUNCTION}__{VERSION}
Node IDs:       {wf-prefix}-{type}-{seq}  e.g. sv3-code-01, ve-pg-01
Node names:     Human-readable, title case  e.g. "Build Research Prompt"
```
