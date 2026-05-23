# AIOS — AI Content Operating System

> Production-grade autonomous content creation and distribution platform built on n8n, PostgreSQL, Telegram, and OpenRouter AI.

## Overview

AIOS (AI Content Operating System) is a multi-phase automation platform that researches, generates, approves, renders, and publishes short-form video content (Instagram Reels, Tamil episodic stories) without manual intervention. It runs on a single VPS, orchestrated by n8n workflows, controlled via Telegram, and powered by Claude AI through OpenRouter.

## Architecture at a Glance

```
Telegram Bot (@N8ninsta_jp_bot)
        │
        ▼
TELEGRAM__SUPERVISOR__V2  ←── Rate Limiter (10 req/min)
        │                 ←── Session Manager (PostgreSQL)
        │                 ←── Error Handler (auto-recovery)
        ├── P3 Commands ──►  PHASE3__TELEGRAM_HANDLER__V1
        │                         ├── RESEARCH__VIRAL_ENGINE__V1
        │                         ├── SCRIPT__GENERATOR__V1
        │                         ├── MEMORY__TAMIL_STORY_ENGINE__V1
        │                         └── CAPTION__GENERATOR__V1
        └── AI Chat ──────►  OpenRouter (claude-3.5-haiku)
```

## System Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Workflow Engine | n8n | 2.19.5 |
| Database | PostgreSQL | 16-alpine |
| Reverse Proxy | Traefik | latest |
| AI Provider | OpenRouter → Anthropic | claude-3.5-haiku/sonnet |
| Bot Interface | Telegram Bot API | v7+ |
| Host | Hostinger VPS | Ubuntu |
| Domain | n8n.srv1654276.hstgr.cloud | |

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| Phase 1 | Infrastructure Foundation | COMPLETE |
| Phase 2 | AI Supervisor + Session Memory | COMPLETE |
| Phase 2.5 | Hardening Layer | COMPLETE |
| Phase 3 | Creative Engine | COMPLETE |
| Phase 4 | Media Rendering (FFmpeg) | PLANNED |
| Phase 5 | Publishing (Instagram API) | PLANNED |
| Phase 6 | Analytics + Self-optimization | PLANNED |

## Quick Start

### Prerequisites
- VPS with Docker + Docker Compose
- Telegram bot token
- OpenRouter API key
- Domain with DNS pointing to VPS

### Deploy
```bash
# 1. Clone repository
git clone <repo-url> /root/aios
cd /root/aios

# 2. Configure environment
cp config/.env.generated config/.env
# Edit config/.env with your credentials

# 3. Start infrastructure
cd /docker/n8n && docker compose up -d

# 4. Initialize database
docker exec -i aios-postgres psql -U aios_user -d aios_db < scripts/init_db.sql

# 5. Deploy workflows (run in order)
python3 scripts/phase2_builder.py
python3 scripts/phase25_builder.py
python3 scripts/phase3_builder.py

# 6. Register Telegram webhook
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://n8n.srv1654276.hstgr.cloud/webhook/aios-telegram-bot"
```

## Workflow Commands (Telegram)

| Command | Action |
|---------|--------|
| `/start` | Initialize session |
| `/status` | System health check |
| `/help` | Command reference |
| `/research <topic>` | Viral trend research |
| `/script <topic>` | Generate full script |
| `/story <theme>` | Tamil story episode |
| `/caption <topic>` | Social media captions |

## Repository Structure

```
/root/aios/
├── scripts/           # Python builders — deploy workflows to n8n
│   ├── phase2_builder.py
│   ├── phase25_builder.py
│   └── phase3_builder.py
├── config/            # Environment variables (never commit .env)
├── docs/              # Full system documentation
├── guardrails/        # Rules that protect production stability
├── phases/            # Phase plans and roadmap
├── agents/            # AI agent behavior definitions
├── logs/              # Changelog, incidents, migrations
├── templates/         # Reusable templates for features/bugs/PRs
├── diagrams/          # Architecture and flow diagrams
├── backups/           # Automated database + n8n backups
├── workflows/         # Exported n8n workflow JSON snapshots
└── docker-compose.yml # Infrastructure definition
```

## Protected Components

**DO NOT MODIFY without full review:**
- `TELEGRAM__SUPERVISOR__V2` — Core message router
- `SYSTEM__ERROR_HANDLER__V1` — Error capture pipeline
- `aios-telegram-bot` webhook path
- PostgreSQL `sessions`, `users` tables
- n8n encryption key

See `guardrails/DO_NOT_TOUCH.md` for the full protected list.

## Documentation Index

| Topic | File |
|-------|------|
| System Architecture | `docs/ARCHITECTURE.md` |
| All 20 Workflows | `docs/WORKFLOW_INDEX.md` |
| Database Tables | `docs/DATABASE_SCHEMA.md` |
| Telegram Flow | `docs/TELEGRAM_BOT_FLOW.md` |
| API Contracts | `docs/API_CONTRACTS.md` |
| Security Rules | `guardrails/SECURITY_GUARDRAILS.md` |
| Phase Roadmap | `phases/ROADMAP.md` |
| Change History | `logs/CHANGELOG.md` |

## Security

- API keys stored in `config/.env` (gitignored)
- n8n credentials encrypted with AES-256-CBC
- All SQL strings sanitized before Postgres execution
- Rate limiting: 10 requests/minute per Telegram user
- Error handler notifies admin on any workflow failure

## Contributing (AI Agents)

See `agents/MASTER_AGENT_RULES.md` for rules governing AI-assisted development.
The golden rule: **never modify production workflows directly — always use the Python builders.**

---

*AIOS v3.0 — Phase 3 Complete | Built with Claude Code*
