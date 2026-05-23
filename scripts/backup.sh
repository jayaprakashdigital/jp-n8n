#!/bin/bash
# AIOS Backup Script - run daily via cron
# Backs up: n8n workflows, database, config

set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/aios/backups/$TIMESTAMP"
LOG_SCRIPT="/root/aios/scripts/log.sh"

mkdir -p "$BACKUP_DIR"

$LOG_SCRIPT INFO backup "Starting backup to $BACKUP_DIR"

# 1. Database backup
docker exec aios-postgres pg_dump -U aios_user -d aios_db > "$BACKUP_DIR/aios_db.sql" 2>/dev/null
$LOG_SCRIPT INFO backup "Database backup complete"

# 2. n8n workflow export (copies n8n data volume)
N8N_VOL=$(docker volume inspect n8n_data --format '{{.Mountpoint}}' 2>/dev/null)
if [ -n "$N8N_VOL" ]; then
    cp -r "$N8N_VOL" "$BACKUP_DIR/n8n_data" 2>/dev/null || true
    $LOG_SCRIPT INFO backup "n8n data backup complete"
fi

# 3. Config backup (redact secrets)
cp /root/aios/config/.env "$BACKUP_DIR/.env.backup" 2>/dev/null || true

# 4. Workflow JSON exports
cp -r /root/aios/workflows/ "$BACKUP_DIR/workflows/" 2>/dev/null || true

# 5. Cleanup backups older than 7 days
find /root/aios/backups -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

$LOG_SCRIPT INFO backup "Backup completed: $BACKUP_DIR"
echo "Backup done: $BACKUP_DIR"
