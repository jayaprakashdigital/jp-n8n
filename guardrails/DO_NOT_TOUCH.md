# DO NOT TOUCH — Protected Production Components

**Purpose:** Hard list of components that must NEVER be modified without explicit review and backup.
**Owner:** Platform Lead
**Update Rule:** Only the platform lead can add or remove items from this list.

---

## CRITICAL: Read This Before Every Deploy

> If you are about to modify anything on this list — STOP.
> Take a full backup first. Get explicit approval. Document in CHANGELOG.md.

---

## Protected n8n Workflows

| Workflow | n8n ID | Protection Reason |
|----------|--------|------------------|
| `TELEGRAM__SUPERVISOR__V2` | `13473953-52ed-419e-93c0-78c0c91b0818` | Core message router — any bug here breaks ALL Telegram interaction |
| `SYSTEM__ERROR_HANDLER__V1` | `99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2` | Admin alert system — must always be running |
| `SYSTEM__APPROVAL_RECOVERY__V1` | `08a68b63-5e2d-4c6f-9d9e-c1bd0e69694f` | Approval recovery — schedule must not be changed |

**Rule:** Never disable or delete these workflows. If you need to update them, run the appropriate builder script — do NOT modify through the n8n UI.

---

## Protected Telegram Configuration

| Item | Value | Why Protected |
|------|-------|--------------|
| Webhook path | `aios-telegram-bot` | Registered with Telegram API — changing breaks ALL messages |
| Webhook URL | `https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot` | Must match Telegram webhook registration |
| Bot token | `8675644315:AAEavBoQpQPW5iQ2WTHU-dtoaMHsuxrv_Js` | Cannot be changed without @BotFather re-setup |

**Rule:** If you MUST change the webhook path, you must ALSO call `setWebhook` on the Telegram API with the new URL. Both must change atomically.

---

## Protected Database Tables

| Table | Why Protected |
|-------|--------------|
| `users` | Primary identity table — deleting rows loses user history forever |
| `sessions` | Active conversation state — deleting breaks ongoing user sessions |
| `workflow_versions` | Audit trail — never truncate |
| `execution_logs` | Error history — only age-based cleanup allowed |

**Rule:** NEVER `DROP TABLE` or `TRUNCATE` any of these tables. For cleanup, use time-bounded `DELETE WHERE created_at < threshold`.

---

## Protected n8n Configuration

| Item | Value | Why Protected |
|------|-------|--------------|
| `N8N_ENCRYPTION_KEY` | `vdlIIW6ZObRWezflrgbWoR6LD05/7o+4` | Changing this breaks ALL stored credentials |
| n8n project ID | `0YzGnVQ4VzNb3gOx` | Used in all workflow ownership records |
| PostgreSQL credential ID | `a20cebf1b1c648` | Referenced in all Postgres nodes across all workflows |

**Rule:** The encryption key especially — if you change it, every credential must be manually re-entered. There is no migration path.

---

## Protected Files

| File | Why Protected |
|------|--------------|
| `config/.env` | Contains all production secrets |
| `scripts/backup.sh` | Must remain functional at all times |
| `scripts/init_db.sql` | Foundation schema — do not modify after initial deploy |

---

## What CAN Be Safely Modified

- All documentation files (`docs/`, `guardrails/`, `phases/`, etc.)
- Phase N builder scripts — if creating new workflows, not modifying protected ones
- New database tables via `CREATE TABLE IF NOT EXISTS` migrations
- New columns via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- `config/.env` values (non-key values, not N8N_ENCRYPTION_KEY)
- Content in `prompts/`, `references/`, `templates/`
