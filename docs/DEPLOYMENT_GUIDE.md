# AIOS — Deployment Guide

**Purpose:** Step-by-step guide to deploy AIOS from scratch on a fresh VPS.
**Owner:** DevOps / Infrastructure Lead
**Update Rule:** Update after every infrastructure change. Test this guide on each major release.

---

## Prerequisites

| Requirement | Spec |
|-------------|------|
| VPS | Ubuntu 22.04+, min 4GB RAM, 40GB disk |
| Docker | 24.0+ |
| Docker Compose | v2+ |
| Domain | Pointed to VPS IP (A record) |
| Telegram Bot | Token from @BotFather |
| OpenRouter | API key from openrouter.ai |

---

## Step 1: Server Setup

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Install Docker Compose
apt install -y docker-compose-plugin

# Install Python deps
apt install -y python3-pip sqlite3
pip3 install pycryptodome
```

---

## Step 2: Deploy PostgreSQL

```bash
docker run -d \
  --name aios-postgres \
  --restart always \
  -e POSTGRES_DB=aios_db \
  -e POSTGRES_USER=aios_user \
  -e POSTGRES_PASSWORD=<STRONG_PASSWORD> \
  -p 127.0.0.1:5432:5432 \
  postgres:16-alpine

# Initialize schema
docker exec -i aios-postgres psql -U aios_user -d aios_db < /root/aios/scripts/init_db.sql
```

---

## Step 3: Deploy n8n + Traefik

```bash
cd /docker/n8n

# Create required Docker volumes
docker volume create n8n_data
docker volume create traefik_data

# Set environment variables
cat > .env << 'EOF'
DOMAIN_NAME=srv1654276.hstgr.cloud
SUBDOMAIN=n8n
GENERIC_TIMEZONE=Asia/Kolkata
SSL_EMAIL=your@email.com
EOF

# Start services
docker compose up -d

# Verify
docker compose ps
curl -k https://n8n.srv1654276.hstgr.cloud/healthz
```

---

## Step 4: Configure n8n

1. Open `https://n8n.srv1654276.hstgr.cloud`
2. Create owner account
3. Note the project ID from URL: `https://.../projects/PROJECT_ID/...`

Update `PROJECT_ID` in all builder scripts:
```python
PROJECT_ID = "0YzGnVQ4VzNb3gOx"  # already set
```

---

## Step 5: Deploy Workflows

```bash
cd /root/aios

# Phase 2 — AI Supervisor
python3 scripts/phase2_builder.py

# Phase 2.5 — Hardening
python3 scripts/phase25_builder.py

# Phase 3 — Creative Engine
python3 scripts/phase3_builder.py

# Restart n8n to activate
cd /docker/n8n && docker compose restart n8n
```

---

## Step 6: Register Telegram Webhook

```bash
# Replace TOKEN with actual bot token
curl "https://api.telegram.org/bot8675644315:AAEavBoQpQPW5iQ2WTHU-dtoaMHsuxrv_Js/setWebhook?url=https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot"

# Verify
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | python3 -m json.tool
```

Expected response:
```json
{
  "ok": true,
  "result": {
    "url": "https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot",
    "pending_update_count": 0
  }
}
```

---

## Step 7: Verify Deployment

```bash
# Check all workflows active
sqlite3 /var/lib/docker/volumes/n8n_data/_data/database.sqlite \
  "SELECT name, active FROM workflow_entity ORDER BY name;"

# Check all Phase 3 tables
docker exec aios-postgres psql -U aios_user -d aios_db \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

# Test Telegram bot
# Send /start to @N8ninsta_jp_bot
```

---

## Automated Backup Setup

```bash
# Run backup script
bash /root/aios/scripts/backup.sh

# Schedule daily backup (cron)
echo "0 2 * * * /root/aios/scripts/backup.sh" | crontab -
```

---

## Environment Variables Reference

See `docs/ENV_VARIABLES.md` for the complete list.

Critical values stored in `config/.env`:
- `TG_TOKEN` — Telegram bot token
- `OR_KEY` — OpenRouter API key
- `N8N_ENCRYPTION_KEY` — n8n AES key (NEVER change after first deploy)

---

## Rollback Procedure

```bash
# Rollback n8n to previous backup
cd /docker/n8n && docker compose stop n8n
cp /root/aios/backups/<DATE>/n8n_data/* /var/lib/docker/volumes/n8n_data/_data/
docker compose start n8n

# Rollback database
docker exec -i aios-postgres psql -U aios_user -d aios_db < /root/aios/backups/<DATE>/aios_db.sql
```

---

**Warnings:**
- Never change `N8N_ENCRYPTION_KEY` after first deployment — all credentials will break
- Always backup before running new builder scripts
- n8n UI edits are NOT persisted to git — use builder scripts only

**Future Extension:** Add Ansible playbook for one-command deployment to a fresh VPS.
