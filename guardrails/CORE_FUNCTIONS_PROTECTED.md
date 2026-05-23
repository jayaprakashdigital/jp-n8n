# AIOS — Core Functions Protected

**Purpose:** Catalog every core function, method, and code pattern that must not be changed without review.
**Owner:** Platform Lead
**Update Rule:** Add entries whenever a function becomes load-bearing in production.

---

## Python Builder Functions (scripts/)

### `upsert_workflow()` — in all builder scripts
```python
def upsert_workflow(wf_id, name, nodes, connections, settings=None, active=True, ...)
```
**Why protected:** Contains the name-based deduplication logic that prevents duplicate workflows. Any change here can silently leave orphan workflows.
**Rule:** Do not change the deduplication logic. If you need to extend, add to it, don't replace.

### `run_migration()` — in all builder scripts
**Why protected:** Uses subprocess to connect to PostgreSQL inside Docker. Any change to the docker exec command structure can silently fail without error.
**Rule:** Keep the exact command structure: `["docker", "exec", "-i", "aios-postgres", "psql", "-U", "aios_user", "-d", "aios_db"]`

### `pg_node()` helper
**Why protected:** All Postgres nodes in all workflows depend on this helper. If `"operation": "executeQuery"` is changed, all 40+ Postgres nodes break.

---

## JavaScript Patterns (n8n Code Nodes)

### SQL Sanitization pattern
```javascript
const safe = s => (s + '').replace(/'/g, "''");
```
**Why protected:** This exact pattern protects against SQL injection. Never simplify or remove it.

### OpenRouter response extraction
```javascript
const content = d?.choices?.[0]?.message?.content || '';
const match = content.match(/\{[\s\S]*\}/);
```
**Why protected:** Used in all 8 Phase 3 parse nodes. Handles OpenRouter's response structure.

### Session state merge
```javascript
const newSession = { ...(d.session_data || {}), ...(d.session_update || {}), last_intent: d.intent };
```
**Why protected:** Preserves existing session fields while updating new ones. Replacing `||{}` breaks for null sessions.

---

## n8n Activation Pattern (SQLite)
```python
cur.execute("INSERT INTO workflow_entity (..., versionId, activeVersionId, ...) VALUES (..., ?, ?, ...)", ...)
cur.execute("INSERT INTO workflow_history (versionId, workflowId, ...) VALUES (?, ?, ...)", ...)
```
**Why protected:** Both `versionId = activeVersionId` AND a `workflow_history` entry are required for n8n to activate a workflow. Removing either leaves the workflow as a draft.

---

**Warnings:**
- These patterns were discovered through debugging, not documentation. Treat them as hard-won knowledge.
- When in doubt: copy the exact pattern from an existing working workflow.
