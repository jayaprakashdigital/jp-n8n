# AIOS — Backup & Recovery

**Purpose:** Backup strategy, schedule, and step-by-step recovery procedures.
**Owner:** DevOps Lead
**Update Rule:** Update after any recovery is performed. Verify backup integrity monthly.

---

## What Gets Backed Up

| Component | Method | Location | Frequency |
|-----------|--------|----------|-----------|
| PostgreSQL `aios_db` | `pg_dump` | `backups/YYYYMMDD_HHMMSS/aios_db.sql` | Daily 2AM |
| n8n workflows (SQLite) | file copy | `backups/YYYYMMDD_HHMMSS/n8n_data/` | Daily 2AM |
| `.env` config | file copy | `backups/YYYYMMDD_HHMMSS/.env.backup` | Daily 2AM |
| Workflow JSON exports | manual | `workflows/` | Before each deploy |

---

## Backup Script

Location: `scripts/backup.sh`

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/aios/backups/$DATE"
mkdir -p "$BACKUP_DIR"

# PostgreSQL dump
docker exec aios-postgres pg_dump -U aios_user aios_db > "$BACKUP_DIR/aios_db.sql"

# n8n SQLite + config
cp /var/lib/docker/volumes/n8n_data/_data/database.sqlite "$BACKUP_DIR/n8n_database.sqlite"
cp /root/aios/config/.env "$BACKUP_DIR/.env.backup"

echo "Backup complete: $BACKUP_DIR"
```

**Schedule (cron):**
```bash
0 2 * * * /root/aios/scripts/backup.sh >> /root/aios/logs/backup.log 2>&1
```

---

## Recovery Procedures

### Scenario 1: PostgreSQL data loss

```bash
# 1. Stop any n8n workflows that write to DB
cd /docker/n8n && docker compose stop n8n

# 2. Drop and recreate database (if corrupt)
docker exec aios-postgres psql -U postgres -c "DROP DATABASE aios_db; CREATE DATABASE aios_db OWNER aios_user;"

# 3. Restore from backup
docker exec -i aios-postgres psql -U aios_user -d aios_db < backups/<DATE>/aios_db.sql

# 4. Restart n8n
docker compose start n8n

# 5. Verify
docker exec aios-postgres psql -U aios_user -d aios_db -c "SELECT COUNT(*) FROM sessions;"
```

### Scenario 2: n8n workflows corrupted/lost

```bash
# 1. Stop n8n
cd /docker/n8n && docker compose stop n8n

# 2. Restore n8n SQLite from backup
cp backups/<DATE>/n8n_database.sqlite /var/lib/docker/volumes/n8n_data/_data/database.sqlite

# 3. Restart n8n
docker compose start n8n

# OR — full rebuild from scripts (preferred):
python3 scripts/phase2_builder.py
python3 scripts/phase25_builder.py
python3 scripts/phase3_builder.py
cd /docker/n8n && docker compose restart n8n
```

### Scenario 3: Complete VPS failure

```bash
# On fresh VPS:
# 1. Follow DEPLOYMENT_GUIDE.md steps 1-4

# 2. Restore environment
cp backups/<DATE>/.env.backup config/.env

# 3. Restore PostgreSQL
docker exec -i aios-postgres psql -U aios_user -d aios_db < backups/<DATE>/aios_db.sql

# 4. Rebuild n8n workflows from scripts
python3 scripts/phase2_builder.py
python3 scripts/phase25_builder.py
python3 scripts/phase3_builder.py

# 5. Restart and re-register webhook
cd /docker/n8n && docker compose restart n8n
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot"
```

---

## Backup Verification

Run monthly:
```bash
# Check backup exists and has content
ls -la backups/ | tail -5
wc -l backups/$(ls backups | tail -1)/aios_db.sql

# Test restore to temp database
docker exec aios-postgres psql -U postgres -c "CREATE DATABASE aios_verify OWNER aios_user;"
docker exec -i aios-postgres psql -U aios_user -d aios_verify < backups/$(ls backups | tail -1)/aios_db.sql
docker exec aios-postgres psql -U aios_user -d aios_verify -c "SELECT COUNT(*) FROM sessions;"
docker exec aios-postgres psql -U postgres -c "DROP DATABASE aios_verify;"
```

---

**Warnings:**
- The `database/` directory in this repo IS NOT the PostgreSQL data — it's a leftover directory. Do not use it as backup.
- Always backup BEFORE running new builder scripts
- Backups contain `aios_db.sql` but NOT the n8n encryption key — without the key, credentials cannot be decrypted

**Future Extension:** Phase 4 — add offsite backup to S3/Backblaze B2. Add backup success/failure notification to Telegram admin.
