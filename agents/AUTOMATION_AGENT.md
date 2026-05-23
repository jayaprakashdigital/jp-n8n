# AIOS — Automation Agent Rules

**Purpose:** Rules for AI agents writing and executing builder scripts, deployment automation, and infrastructure management.
**Inherits From:** `agents/MASTER_AGENT_RULES.md`
**Owner:** Platform Lead

---

## Scope

This agent is responsible for:
- Writing phase builder scripts (`scripts/phaseN_builder.py`)
- Running database migrations
- Deploying workflows to n8n SQLite
- Managing n8n container lifecycle
- Backup and recovery operations

---

## Builder Script Standards

### File Naming
```
scripts/phase<N>_builder.py         # Main phase builder
scripts/phase<N>_<subfeature>.py    # Sub-feature builder (if phase is large)
scripts/migrate_<description>.py    # Standalone migration (for hotfixes)
```

### Required Script Structure

```python
#!/usr/bin/env python3
"""
Phase N Builder — <Description>
Deploy: python3 scripts/phaseN_builder.py
"""
import sqlite3, json, uuid, subprocess, sys

# === CONSTANTS ===
DB_PATH          = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID       = "0YzGnVQ4VzNb3gOx"
SUPERVISOR_ID    = "13473953-52ed-419e-93c0-78c0c91b0818"
ERROR_HANDLER_ID = "99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2"
PG_CRED_ID       = "a20cebf1b1c648"
ADMIN_CHAT_ID    = 1241444951
OR_URL           = "https://openrouter.ai/api/v1/chat/completions"

_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
def _wid(k): return str(uuid.uuid5(_NS, f"aios/pN/{k}"))

WF = {
    "my_workflow": _wid("my_workflow"),
}

# === HELPER FUNCTIONS (import from previous phase or redefine) ===

# === WORKFLOW BUILDERS ===

def build_my_workflow():
    ...

# === MIGRATION ===

def run_migration():
    sql = """
    CREATE TABLE IF NOT EXISTS new_table (...);
    """
    # (run via docker exec aios-postgres psql)

# === MAIN ===

def main():
    print("=== Phase N Builder ===")
    run_migration()
    build_my_workflow()
    # ... etc
    subprocess.run([
        "docker", "compose", "-f", "/docker/n8n/docker-compose.yml",
        "restart", "n8n"
    ])
    print("✓ Done")

if __name__ == "__main__":
    main()
```

---

## UUID Namespace Rule

All workflow IDs must use the project namespace and phase-scoped key:

```python
_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
def _wid(k): return str(uuid.uuid5(_NS, f"aios/pN/{k}"))
```

**Never use `uuid.uuid4()`** for workflow IDs — IDs must be deterministic and stable.

**Namespace by phase:**
- Phase 2: `aios/p2/`
- Phase 2.5: `aios/p25/`
- Phase 3: `aios/p3/`
- Phase 4: `aios/p4/`

---

## Migration Execution Pattern

```python
def run_migration():
    sql = """
    CREATE TABLE IF NOT EXISTS example (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """.strip()
    
    for stmt in sql.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        result = subprocess.run(
            ["docker", "exec", "aios-postgres", "psql",
             "-U", "aios_user", "-d", "aios_db", "-c", stmt],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Migration error: {result.stderr}")
            sys.exit(1)
    print("✓ Migration complete")
```

---

## n8n Workflow Deployment Pattern (upsert_workflow)

```python
def upsert_workflow(wf_id, name, nodes, edges, active=True):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Deduplication: remove old entries with same name
    cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
    for (old_id,) in cur.fetchall():
        for tbl in ["workflow_entity", "tag_entity_workflow_entity_workflow_entity",
                    "execution_entity", "workflow_statistics", "shared_workflow"]:
            try:
                cur.execute(f"DELETE FROM {tbl} WHERE workflowId=? OR id=?", (old_id, old_id))
            except:
                pass
    
    now_ms = int(__import__("time").time() * 1000)
    wf_json = {"nodes": nodes, "connections": edges, "settings": {
        "executionOrder": "v1",
        "errorWorkflow": ERROR_HANDLER_ID,
        "saveManualExecutions": True
    }, "pinData": {}}
    
    cur.execute("""
        INSERT INTO workflow_entity (id, name, active, nodes, connections, createdAt, updatedAt, settings, staticData, pinData, versionId, triggerCount)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, active=excluded.active, nodes=excluded.nodes,
            connections=excluded.connections, updatedAt=excluded.updatedAt,
            settings=excluded.settings, versionId=excluded.versionId
    """, (wf_id, name, 1 if active else 0,
          json.dumps(nodes), json.dumps(edges),
          now_ms, now_ms, json.dumps(wf_json["settings"]),
          "null", "{}", wf_id, 0))
    
    # n8n activation requires workflow_history entry
    cur.execute("""
        INSERT OR REPLACE INTO workflow_history
            (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections)
        VALUES (?,?,?,?,?,?,?)
    """, (wf_id, wf_id, "AIOS Builder", now_ms, now_ms,
          json.dumps(nodes), json.dumps(edges)))
    
    # shared_workflow entry for project
    cur.execute("""
        INSERT OR IGNORE INTO shared_workflow (workflowId, projectId, role, createdAt, updatedAt)
        VALUES (?,?,?,?,?)
    """, (wf_id, PROJECT_ID, "workflow:owner", now_ms, now_ms))
    
    con.commit()
    con.close()
    print(f"✓ Deployed: {name} ({wf_id})")
```

---

## Deployment Sequence

Always follow this order:

1. `bash /root/aios/scripts/backup.sh`
2. Run migration (PostgreSQL tables)
3. Deploy subworkflows (leaf nodes first, then callers)
4. Deploy handler/pipeline workflows
5. Deploy supervisor update (last — most critical)
6. Restart n8n
7. Verify: check SQLite for active=1, check PostgreSQL for tables

---

## n8n Restart Command

```bash
docker compose -f /docker/n8n/docker-compose.yml restart n8n
```

**Wait 15 seconds after restart before testing** — n8n takes time to re-register the webhook.

---

## Verification Commands

After every deploy, run:

```bash
# Check workflows active
sqlite3 /var/lib/docker/volumes/n8n_data/_data/database.sqlite \
  "SELECT name, active FROM workflow_entity ORDER BY name;"

# Check PostgreSQL tables
docker exec aios-postgres psql -U aios_user -d aios_db \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

# Check n8n webhook registered
docker logs n8n-n8n-1 2>&1 | tail -20 | grep -i webhook
```

---

## Backup Commands

```bash
# Full backup
bash /root/aios/scripts/backup.sh

# Manual SQLite backup
cp /var/lib/docker/volumes/n8n_data/_data/database.sqlite \
   /root/aios/backups/database_$(date +%Y%m%d_%H%M%S).sqlite

# Manual PostgreSQL backup
docker exec aios-postgres pg_dump -U aios_user aios_db \
   > /root/aios/backups/postgres_$(date +%Y%m%d_%H%M%S).sql
```

---

## Forbidden in This Domain

- Running `docker compose down` — takes production offline
- Running multiple builder scripts simultaneously — SQLite write lock
- Modifying `database.sqlite` directly with raw SQL (use `upsert_workflow()`)
- Skipping backup before the first run of a new builder script
- Restarting PostgreSQL container (not n8n — only n8n needs restart after workflow deploy)
