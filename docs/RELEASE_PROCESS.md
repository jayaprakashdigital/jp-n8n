# AIOS — Release Process

**Purpose:** Define how new phases and features are released safely into production.
**Owner:** Release Manager / Lead Developer
**Update Rule:** Update after each phase release with lessons learned.

---

## Release Types

| Type | Scope | Example |
|------|-------|---------|
| Phase Release | Major new capability | Phase 3: Creative Engine |
| Hotfix | Critical bug in production | Fix broken supervisor routing |
| Feature Addition | New workflow or command | Add `/analytics` command |
| Schema Migration | Database table changes | Add new column to scripts |

---

## Phase Release Process

```
1. PLAN
   ├── Define phase goals and workflow list
   ├── Update phases/PHASE_N.md with spec
   └── Review guardrails/DO_NOT_TOUCH.md

2. BUILD
   ├── Write scripts/phaseN_builder.py
   ├── Test SQL migration on backup DB
   └── Verify all node types are in ARCHITECTURE.md registry

3. PRE-DEPLOY
   ├── Run backup: bash scripts/backup.sh
   ├── Verify backup: check backups/ latest folder
   └── Review DO_NOT_TOUCH.md — ensure no protected workflows modified

4. DEPLOY
   ├── python3 scripts/phaseN_builder.py
   ├── cd /docker/n8n && docker compose restart n8n
   └── Verify: sqlite3 n8n_db "SELECT name, active FROM workflow_entity;"

5. VERIFY
   ├── Test each new Telegram command
   ├── Check execution_logs for errors
   ├── Verify existing commands still work (/start, /status)
   └── Check error handler still receives test errors

6. DOCUMENT
   ├── Update docs/WORKFLOW_INDEX.md with new workflow IDs
   ├── Update phases/PHASE_N.md status to COMPLETE
   ├── Add entry to logs/CHANGELOG.md
   └── Update README.md phase status table
```

---

## Hotfix Process

For critical production bugs:

```
1. Identify failing workflow from execution_logs or Telegram alert
2. Run backup IMMEDIATELY
3. Fix in builder script (never directly in n8n UI)
4. Re-run builder: python3 scripts/<affected_builder>.py
5. Restart n8n
6. Verify fix in Telegram
7. Document in logs/CHANGELOG.md and logs/INCIDENT_LOG.md
```

---

## Rollback

```bash
# Stop n8n
cd /docker/n8n && docker compose stop n8n

# Restore n8n SQLite
cp backups/<PRE-DEPLOY-DATE>/n8n_database.sqlite \
   /var/lib/docker/volumes/n8n_data/_data/database.sqlite

# Restore PostgreSQL if schema changed
docker exec -i aios-postgres psql -U aios_user -d aios_db < backups/<PRE-DEPLOY-DATE>/aios_db.sql

# Restart
docker compose start n8n
```

---

## Version Numbering

AIOS uses Phase-based versioning, not semver:
- Phase 1 = Infrastructure
- Phase 2 = AI Supervisor
- Phase 2.5 = Hardening
- Phase 3 = Creative Engine
- Phase 4 = Media Rendering (planned)
- Phase 5 = Publishing (planned)
- Phase 6 = Analytics (planned)

Workflow versions (V1, V2) increment only on breaking changes to inputs/outputs.

---

**Warnings:**
- Never deploy without a backup
- Never modify protected workflows — use the builder system
- Verify Telegram bot still works after EVERY deploy

**Future Extension:** Add CI/CD pipeline to auto-run builder scripts on git push to `main`.
