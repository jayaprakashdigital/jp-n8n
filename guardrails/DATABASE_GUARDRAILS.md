# AIOS — Database Guardrails

**Purpose:** Rules that protect PostgreSQL data integrity across all phases.
**Owner:** Database Lead
**Update Rule:** Add new rules when new migration patterns are introduced.

---

## Hard Rules (Never Violate)

1. **Never DROP TABLE** — Mark tables deprecated, never drop them.
2. **Never TRUNCATE** production tables — Use time-bounded DELETE only.
3. **Always use IF NOT EXISTS** — `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`.
4. **Always migrate first** — Schema changes must be in a migration script BEFORE builder scripts run.
5. **Always backup before migration** — `bash scripts/backup.sh` before any schema change.
6. **Log all migrations** — Every `ALTER TABLE` and `CREATE TABLE` goes in `logs/MIGRATION_LOG.md`.

---

## Migration Template

```sql
-- Migration: YYYY-MM-DD — Description
-- Author: [name/AI agent]
-- Phase: [phase number]
-- Backward compatible: YES/NO

BEGIN;

ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS new_col VARCHAR(100);
CREATE TABLE IF NOT EXISTS new_table (
    id SERIAL PRIMARY KEY,
    -- ...
);
CREATE INDEX IF NOT EXISTS idx_name ON table(col);

COMMIT;
```

---

## Query Safety Rules

All queries executed through n8n Postgres nodes must:

1. **Sanitize inputs** — Single quotes escaped via `s.replace(/'/g, "''")`
2. **Bound string lengths** — Slice to max column length before inserting
3. **Use RETURNING** — For INSERT statements that need the new ID
4. **Use ON CONFLICT DO NOTHING/UPDATE** — For upsert patterns (idempotent)

---

## Table Lifecycle

| Status | Meaning | Action |
|--------|---------|--------|
| Active | In use by current phase | Normal operation |
| Deprecated | No longer used by workflows | Keep table, add comment `-- DEPRECATED Phase N` |
| Archive | Data kept for reference | Read-only access only |
| Deleted | Table removed | Document in MIGRATION_LOG.md, only after 1 full phase |

---

## Index Standards

All foreign keys must be indexed. Add:
```sql
CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col});
```

For queries with WHERE + ORDER BY, add compound index:
```sql
CREATE INDEX IF NOT EXISTS idx_{table}_{col1}_{col2} ON {table}({col1}, {col2} DESC);
```

---

**Warnings:**
- Never run raw SQL from Telegram user input. Always go through Code node sanitization.
- The `sessions.session_data` JSONB column can grow large — limit to 5KB max per session.
