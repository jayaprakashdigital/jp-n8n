# AIOS — System Architecture

**Purpose:** Define the complete technical architecture of the AIOS platform.
**Owner:** Lead Developer / AI Architect
**Update Rule:** Update on every phase boundary or major infrastructure change. Tag version.

---

## 1. Platform Overview

AIOS is a modular, event-driven content automation platform. All orchestration runs inside n8n. All state lives in PostgreSQL. All user interaction flows through Telegram.

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXTERNAL LAYER                           │
│   Telegram ──► Webhook ──► n8n   │   OpenRouter ──► Claude AI  │
│   Instagram API (Phase 5)        │   FFmpeg CLI (Phase 4)       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                        │
│   n8n v2.19.5 at n8n.srv1654276.hstgr.cloud                    │
│   20 active workflows — all deployed via Python builders        │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        STATE LAYER                              │
│   PostgreSQL 16 (aios-postgres)  │  SQLite (n8n internal)       │
│   25 tables, aios_db              │  workflow definitions        │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     INFRASTRUCTURE LAYER                        │
│   Traefik (TLS termination + reverse proxy)                     │
│   Docker Compose (service orchestration)                        │
│   Hostinger VPS (Ubuntu, single server)                         │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Workflow Architecture

### 2.1 Supervisor Pattern

Every Telegram message enters through a single webhook and is processed by `TELEGRAM__SUPERVISOR__V2`. This is the ONLY workflow with a Telegram webhook.

```
Telegram Message
      │
      ▼
TELEGRAM__SUPERVISOR__V2
      │
      ├── [isCallback] ──► Handle Callback ──► Answer + Resolve Approval
      │
      ├── [Rate Check] ──► is_blocked? ──► Send Rate Warning (END)
      │
      ├── [Load Session] ──► Prepare AI Context
      │                           │
      │               ┌───────────┴───────────┐
      │         [isP3Command=true]      [isP3Command=false]
      │               │                       │
      │         Call P3 Handler         Call Supervisor AI
      │         (executeWorkflow)        (OpenRouter HTTP)
      │               │                       │
      │         Format P3 Reply         Validate & Parse
      │               │                       │
      └───────────────┴───── Prep Save Data ──►──► Save Session + Log + Send Reply
```

### 2.2 Subworkflow Pattern

Phase 3 creative workflows are triggered only via `executeWorkflow` nodes — never directly by webhooks. They are stateless processing units that receive input and return output.

```
Caller Workflow
      │
      ▼
executeWorkflow node
      │ (passes current item JSON)
      ▼
Subworkflow (executeWorkflowTrigger)
      │
      ├── [optional] Load context from PostgreSQL
      ├── Build prompt (Code node)
      ├── Call OpenRouter (HTTP Request)
      ├── Parse JSON response (Code node)
      ├── Save result to PostgreSQL
      └── Log to execution_logs
      │
      ▼ (last node output returned to caller)
Caller continues with result
```

### 2.3 Error Recovery Pattern

```
Any workflow failure
      │
      ▼ (via errorWorkflow setting)
SYSTEM__ERROR_HANDLER__V1
      │
      ├── Extract error info (Code node)
      ├── Log to execution_logs (PostgreSQL, continueOnFail)
      └── Notify admin via Telegram (HTTP, neverError)
```

## 3. Node Type Registry

All workflows use only these verified n8n node types:

| Node Type | Version | Purpose |
|-----------|---------|---------|
| `n8n-nodes-base.webhook` | 2 | Telegram entry point |
| `n8n-nodes-base.code` | 2 | JavaScript processing |
| `n8n-nodes-base.postgres` | 2 | Database operations |
| `n8n-nodes-base.httpRequest` | 4.2 | OpenRouter / Telegram API |
| `n8n-nodes-base.if` | 2 | Conditional routing |
| `n8n-nodes-base.executeWorkflow` | 1.2 | Subworkflow calls |
| `n8n-nodes-base.executeWorkflowTrigger` | 1 | Subworkflow entry |
| `n8n-nodes-base.scheduleTrigger` | 1.2 | Scheduled jobs |
| `n8n-nodes-base.errorTrigger` | 1 | Error capture |
| `n8n-nodes-base.respondToWebhook` | 1 | HTTP response |

**WARNING:** Never use deprecated, beta, or unlisted node types. All new nodes must appear in this table before use.

## 4. Database Architecture

PostgreSQL 16 with 25 tables across 4 functional groups:

- **Identity**: `users`, `sessions`
- **Content**: `scripts`, `viral_research`, `prompts`, `content_queue`
- **Memory**: `tamil_story_memory`, `character_memory`, `story_progression`
- **Hardening**: `execution_logs`, `rate_limits`, `pending_approvals`, `workflow_versions`
- **Phase 3**: `hook_library`, `audience_patterns`, `successful_captions`, `replay_scores`, `emotional_scores`, `pacing_feedback`
- **Phase 4+ (planned)**: `generated_images`, `generated_videos`, `analytics`, `upload_history`

See `docs/DATABASE_SCHEMA.md` for complete column definitions.

## 5. AI Model Strategy

| Use Case | Model | Rationale |
|----------|-------|-----------|
| Supervisor routing | claude-3.5-haiku | Speed over quality |
| Research / captions | claude-3.5-haiku | Structured JSON output |
| Script generation | claude-3.5-sonnet | Quality matters |
| Story generation | claude-3.5-sonnet | Narrative depth |
| Content scoring | claude-3.5-haiku | Simple classification |

All calls go through OpenRouter at `https://openrouter.ai/api/v1/chat/completions`.

## 6. Deployment Architecture

```
VPS (Hostinger)
└── Docker Compose (/docker/n8n/docker-compose.yml)
    ├── traefik (port 80/443, TLS via Let's Encrypt)
    └── n8n (port 5678 internal, exposed via traefik)

PostgreSQL (separate container)
└── docker run --name aios-postgres (port 5432 internal)

Volume Mounts:
├── n8n_data    → /var/lib/docker/volumes/n8n_data/_data/
├── traefik_data → TLS certificates
└── /local-files → n8n file access
```

## 7. Security Architecture

- TLS: Traefik + Let's Encrypt (auto-renew)
- n8n credentials: AES-256-CBC encrypted in SQLite
- API keys: environment variables only, never in workflow JSON
- SQL injection: all user input sanitized in Code nodes before Postgres
- Rate limiting: 10 req/min per Telegram user (PostgreSQL-backed)
- Error handler: all failures logged + admin alerted

## 8. Future Architecture (Phase 4+)

- **Phase 4**: FFmpeg pipeline (Python subprocess → rendered video files)
- **Phase 5**: Instagram Graph API integration (media upload + publish)
- **Phase 6**: Analytics feedback loop (replay scores → prompt optimization)

---

**Warnings:**
- All workflow deployments MUST go through Python builder scripts, never manually through n8n UI
- The n8n SQLite database is the source of truth for workflow state
- Never run two builder scripts simultaneously (SQLite write lock)

**Future Extension:** Add Redis for distributed rate limiting when scaling to multiple VPS nodes.
