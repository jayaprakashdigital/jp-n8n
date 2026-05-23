# AIOS — Coding Standards

**Purpose:** Code quality standards for all AIOS builder scripts and workflow code.
**Owner:** Lead Developer
**Update Rule:** Update when new patterns are standardized or anti-patterns discovered.

---

## Python (Builder Scripts)

### File Structure
```python
#!/usr/bin/env python3
"""One-line description of what this builder does."""

import json, uuid, sqlite3, subprocess

# ── Constants ─────────────────────────────────────────
DB_PATH = "..."
PROJECT_ID = "..."

# ── SQL Migration ──────────────────────────────────────
MIGRATION_SQL = """..."""

def run_migration(): ...

# ── n8n DB Helpers ─────────────────────────────────────
def node(...): ...
def pg_node(...): ...

# ── Workflow Builders ──────────────────────────────────
def build_workflow_name():
    wf_id = WF["key"]
    nodes = [...]
    connections = {...}
    upsert_workflow(wf_id, "WORKFLOW__NAME__V1", nodes, connections)

# ── Main ───────────────────────────────────────────────
if __name__ == "__main__":
    ...
```

### Rules
- Use `str(uuid.uuid5(NS, "aios/pN/name"))` for deterministic workflow IDs
- All JS code in workflow nodes: use string concatenation, never f-strings for JS objects
- Never use `f"..."` strings for JavaScript code (curly brace escaping nightmare)
- Constants at top of file, UPPERCASE
- Helper functions before workflow builders

---

## JavaScript (n8n Code Nodes)

### Rules
- Always use `try/catch` when parsing external data
- Always provide fallback values: `const x = d.x || 'default'`
- Never use `async/await` or `require()` — not supported in n8n Code node
- Single-quote strings preferred: `'value'`
- Never mutate `$input.item.json` directly — return new object
- Escape all SQL: `const safe = s => (s+'').replace(/'/g, "''")`
- Slice all strings to safe lengths before DB insertion

### Pattern: OpenRouter Response Parsing
```javascript
const content = d?.choices?.[0]?.message?.content || '';
try {
  const match = content.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('no json');
  const parsed = JSON.parse(match[0]);
  // use parsed
} catch(e) {
  // use fallback
}
```

### Pattern: SQL Preparation
```javascript
const safe = s => (s + '').replace(/'/g, "''");
const topic = safe((d.topic || '').slice(0, 200));
const query = `INSERT INTO scripts (topic) VALUES ('${topic}')`;
return [{ json: { query } }];
```

---

## SQL (PostgreSQL)

- Always `IF NOT EXISTS` in CREATE TABLE/INDEX
- Always `ON CONFLICT DO NOTHING/UPDATE` for upserts
- Use `RETURNING id` when you need the inserted row's ID
- Table names: `snake_case`, singular
- Column names: `snake_case`
- Always add `created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()`
- Always add index on foreign keys

---

## Documentation

- Every new workflow: add to `docs/WORKFLOW_INDEX.md` immediately
- Every schema change: update `docs/DATABASE_SCHEMA.md` and `logs/MIGRATION_LOG.md`
- Every deploy: add entry to `logs/CHANGELOG.md`
- Phase completion: update `phases/PHASE_N.md` status

---

**Warnings:**
- The #1 source of bugs: standalone `//` comment lines in Python string concatenation. Never do this.
- The #2 source of bugs: not running `upsert_workflow()` with proper deduplication logic.
