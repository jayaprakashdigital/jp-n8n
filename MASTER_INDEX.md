# AIOS — Master Index

**Purpose:** Single-file navigation map for any LLM, developer, or AI agent working on this repo.
**Read this first.** Every file is listed below with exactly what it contains so you can go directly to the right file without reading everything.

---

## Quick Answer Guide

| Question | Go To |
|----------|-------|
| What is AIOS? What does it do? | `README.md` |
| What workflows exist? What are their IDs? | `docs/WORKFLOW_INDEX.md` |
| What are the database tables and columns? | `docs/DATABASE_SCHEMA.md` |
| What rules must I follow before changing code? | `agents/MASTER_AGENT_RULES.md` |
| What must I never touch? | `guardrails/DO_NOT_TOUCH.md` |
| What changed in the latest phase? | `logs/CHANGELOG.md` |
| What phase are we in? What's next? | `phases/ROADMAP.md` |
| How does a Telegram message flow through the system? | `docs/TELEGRAM_BOT_FLOW.md` |
| What does each subworkflow accept and return? | `docs/API_CONTRACTS.md` |
| How do I add a new workflow? | `templates/WORKFLOW_TEMPLATE.md` + `agents/AUTOMATION_AGENT.md` |
| How do I add a new Telegram command? | `agents/TELEGRAM_AGENT.md` |
| What AI prompts are used? | `docs/PROMPT_LIBRARY.md` |
| What bugs have been fixed? | `logs/INCIDENT_LOG.md` |
| What database migrations have run? | `logs/MIGRATION_LOG.md` |
| How do I deploy to a fresh VPS? | `docs/DEPLOYMENT_GUIDE.md` |
| What environment variables are needed? | `docs/ENV_VARIABLES.md` |
| How is error handling structured? | `docs/ERROR_HANDLING.md` |
| What are the security rules? | `guardrails/SECURITY_GUARDRAILS.md` + `docs/SECURITY_POLICY.md` |
| How do I write a builder script? | `guardrails/CODING_STANDARDS.md` + `agents/AUTOMATION_AGENT.md` |
| What user-facing features exist? | `logs/FEATURE_LOG.md` |
| How do I back up and recover? | `docs/BACKUP_RECOVERY.md` |

---

## Root Files

| File | Contains |
|------|----------|
| `README.md` | System overview, architecture diagram, phase status, quick start commands, tech stack, bot commands |
| `MASTER_INDEX.md` | **This file** — navigation map for all files |
| `.gitignore` | Excluded paths: node_modules, .env, config/, backups/, database/, renders/, logs/*.log |
| `docker-compose.yml` | Runtime Docker config (not tracked in repo — excluded by .gitignore) |

---

## docs/ — Technical Documentation

| File | Contains |
|------|----------|
| `docs/ARCHITECTURE.md` | 4-layer architecture (Infrastructure, Workflow Engine, AI, Presentation). Node type registry. Workflow execution patterns. Data flow diagrams. |
| `docs/WORKFLOW_INDEX.md` | All 20 workflows with UUIDs, trigger types, caller/callee relationships, deployment status. Naming convention. UUID namespace. |
| `docs/DATABASE_SCHEMA.md` | All 25 PostgreSQL tables with exact `CREATE TABLE` SQL. Column types, constraints, foreign keys. Organized by phase. |
| `docs/API_CONTRACTS.md` | Input/output JSON schemas for all 8 creative subworkflows. OpenRouter request/response format. Telegram API contract. PostgreSQL credential reference. |
| `docs/TELEGRAM_BOT_FLOW.md` | Full message lifecycle from webhook to reply. P3 command flow (/research, /script, /story, /caption). Callback query flow. Session state flow. Rate limit flow. |
| `docs/SYSTEM_FLOW.md` | End-to-end flows: content creation, session state management, error handling, approval recovery. |
| `docs/AGENT_SYSTEM.md` | 8 operational AI agents, their system prompts, memory architecture, inter-agent communication patterns. |
| `docs/PROMPT_LIBRARY.md` | All 8 AI system prompts with full user prompt templates. Model assignments. Token limits. Temperature settings. |
| `docs/ERROR_HANDLING.md` | 4-layer error architecture. Which nodes have `continueOnFail=true`. SYSTEM__ERROR_HANDLER__V1 behavior. Admin notification flow. |
| `docs/RATE_LIMIT_RULES.md` | 10 req/min per user. SQL implementation in `rate_limits` table. Warning message behavior. Tuning guide. |
| `docs/AUTH_FLOW.md` | Auth at 6 system boundaries: Telegram→n8n, n8n→OpenRouter, n8n→PostgreSQL, n8n→n8n (subworkflows), Admin→n8n UI, Future OAuth. |
| `docs/ENV_VARIABLES.md` | All environment variables: Telegram token, OpenRouter key, n8n config, PostgreSQL credentials, Traefik config. Where each is set. |
| `docs/DEPLOYMENT_GUIDE.md` | Step-by-step deployment from fresh Ubuntu VPS: Docker install, PostgreSQL setup, n8n setup, Traefik TLS, Telegram webhook registration. |
| `docs/SECURITY_POLICY.md` | Threat model, 6 security control layers, secret management rules, incident response procedure. |
| `docs/BACKUP_RECOVERY.md` | Backup script usage. 3 recovery scenarios: DB loss only, n8n loss only, full VPS loss. Recovery commands for each. |
| `docs/SCALING_PLAN.md` | Phase 4-6 scaling considerations: FFmpeg resource limits, Instagram/YouTube rate limits, horizontal scaling triggers, database indexing plan. |
| `docs/MONITORING_ALERTS.md` | Current monitoring: execution_logs queries, rate_limit queries. Phase 4 monitoring plan. Alert thresholds. |
| `docs/RELEASE_PROCESS.md` | 6-step phase release process. Hotfix process. Rollback procedure. Version numbering convention (X.Y.Z). |
| `docs/KNOWN_ISSUES.md` | 5 active known issues (KI-001 to KI-005) with workarounds. 6 resolved issues with fix summaries. |

---

## guardrails/ — Rules & Constraints

| File | Contains |
|------|----------|
| `guardrails/DO_NOT_TOUCH.md` | Protected workflows (TELEGRAM__SUPERVISOR__V2, error handler), protected DB tables, protected n8n config, protected files. Hard stop — never modify without explicit user approval. |
| `guardrails/WORKFLOW_GUARDRAILS.md` | 10 mandatory rules for all workflow changes: builder-only deploy, fixed UUIDs, SQL sanitization, no invented node types, neverError on Telegram calls, etc. |
| `guardrails/CODING_STANDARDS.md` | Python builder script structure. JavaScript patterns for workflow nodes. SQL conventions. Variable naming. Comment rules. |
| `guardrails/DATABASE_GUARDRAILS.md` | Never DROP TABLE. Never TRUNCATE. Migration template (always IF NOT EXISTS). Safe query patterns. |
| `guardrails/SECURITY_GUARDRAILS.md` | 5 hard rules: no secrets in git, no user message content in logs, no plain-text credentials, sanitize all SQL inputs, rotate on suspected compromise. |
| `guardrails/API_GUARDRAILS.md` | OpenRouter rules (headers, neverError, no auto-retry). Telegram API rules (answerCallbackQuery, 4096 char limit, parse_mode). PostgreSQL credential ID. |
| `guardrails/UI_GUARDRAILS.md` | n8n UI: view-only. Never create/edit workflows in UI. Telegram UI: 30s timeout, Markdown only, max 3 buttons/row. |
| `guardrails/AI_AGENT_RULES.md` | Rules specifically for AI coding assistants (Claude Code, Cursor): prime directives, what's allowed, what's forbidden, contribution workflow checklist. |
| `guardrails/CORE_FUNCTIONS_PROTECTED.md` | Protected Python functions in builder scripts: `upsert_workflow()`, `run_migration()`, `pg_node()`, SQL sanitization pattern, n8n activation pattern. Never modify these. |

---

## phases/ — Phase Documentation

| File | Contains |
|------|----------|
| `phases/PHASE_1.md` | Phase 1 complete: VPS, Docker, Traefik, n8n, PostgreSQL, FFmpeg, Telegram bot. 14 initial tables. Key decisions (SQLite over REST API, Standard Webhook over Telegram Trigger). |
| `phases/PHASE_2.md` | Phase 2 complete: TELEGRAM__SUPERVISOR__V2, session memory, AI intent classification, callbacks, approval management. Phase 2.5: execution logging, error handler, rate limiting, approval recovery. 5 critical bugs fixed. |
| `phases/PHASE_3.md` | Phase 3 complete: 10 workflows deployed (8 creative + 1 pipeline + 1 handler). 7 new tables. /research, /script, /story, /caption, /generate commands. Non-destructive supervisor upgrade. |
| `phases/PHASE_4.md` | Phase 4 planned: FFmpeg video rendering, TTS voiceover, audio mixing, render queue, Telegram progress notifications. Risks and mitigations. Dependencies on Phase 3. |
| `phases/ROADMAP.md` | Full Phase 1-6 roadmap with status, targets, deliverables. Dependency graph. Architecture evolution table (workflows/tables/commands by phase). |

---

## logs/ — Change History

| File | Contains |
|------|----------|
| `logs/CHANGELOG.md` | Versioned change history: v1.0.0 (Phase 1), v2.0.0 (Phase 2), v2.5.0 (Hardening), v3.0.0 (Phase 3). Added/Changed/Fixed per version. Versioning convention. |
| `logs/MIGRATION_LOG.md` | Every database migration: MIG-01-01 (14 tables), MIG-02-01 (4 hardening tables), MIG-03-01 (7 Phase 3 tables + 2 columns). Full SQL for each migration. |
| `logs/INCIDENT_LOG.md` | 4 resolved production incidents with root cause + fix + prevention rule added. Severity definitions. Incident template. |
| `logs/FEATURE_LOG.md` | All user-facing features by phase: F3-01 to F3-04 (Phase 3), F2-01 to F2-04 (Phase 2), F1-01 (Phase 1). Feature roadmap for Phases 4-6. |
| `logs/SECURITY_LOG.md` | Security audit events, SQL injection prevention audit, credential inventory, incident response contact. Future audit schedule by phase. |

---

## templates/ — Starter Templates

| File | Contains |
|------|----------|
| `templates/FEATURE_TEMPLATE.md` | Template for proposing a new feature: problem statement, technical design, new workflows, DB tables, AI model selection, acceptance criteria, effort estimate. |
| `templates/BUGFIX_TEMPLATE.md` | Template for documenting a bug fix: symptom, reproduction steps, root cause analysis, code change (before/after), verification checklist, prevention rule. |
| `templates/PR_TEMPLATE.md` | Pull request template: summary, type of change, new/modified workflows, DB changes, testing done, documentation updated, rollback plan, pre-flight checklist. |
| `templates/WORKFLOW_TEMPLATE.md` | Reference template for building n8n subworkflows: naming convention, UUID generation, standard structure, node type registry, OpenRouter call pattern, PostgreSQL pattern, AI response parsing, SQL injection prevention. |

---

## agents/ — AI Agent Rules

| File | Contains |
|------|----------|
| `agents/MASTER_AGENT_RULES.md` | **Start here for any AI agent.** 6 non-negotiable prime directives. System architecture overview. Mandatory pre-task checklist. 18 task execution rules. Forbidden actions table. Communication standards. |
| `agents/TELEGRAM_AGENT.md` | Rules for working on Telegram/supervisor logic. Message flow diagram. Critical nodes ("Prepare AI Context", "Send Reply"). Telegram API limits. Session state rules. P3 command extension pattern. Inline keyboard design rules. |
| `agents/CONTENT_AGENT.md` | Rules for creative content workflows. Content creation pipeline. AI model selection table. System prompt design rules. AI response parsing pattern. Tamil story memory rules. Content quality thresholds. Data storage table. |
| `agents/REVIEW_AGENT.md` | Pre-deploy review checklist (Python structure, node types, SQL safety, OpenRouter, credentials). Workflow JSON validation rules. API contract compliance review. Documentation completeness checklist. Review sign-off format. |
| `agents/AUTOMATION_AGENT.md` | Rules for builder scripts and deployment. Builder script standards and required structure. UUID namespace by phase. Migration execution pattern. `upsert_workflow()` full implementation. Deployment sequence. Verification commands. Backup commands. |

---

## Key Constants (Quick Reference)

| Constant | Value |
|----------|-------|
| n8n SQLite path | `/var/lib/docker/volumes/n8n_data/_data/database.sqlite` |
| n8n URL | `https://n8n.srv1654276.hstgr.cloud` |
| PostgreSQL container | `aios-postgres` |
| PostgreSQL DB | `aios_db` / user `aios_user` |
| PostgreSQL credential ID (n8n) | `a20cebf1b1c648` |
| n8n project ID | `0YzGnVQ4VzNb3gOx` |
| Supervisor workflow ID | `13473953-52ed-419e-93c0-78c0c91b0818` |
| Error handler workflow ID | `99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2` |
| UUID namespace | `12345678-1234-5678-1234-567812345678` |
| Admin Telegram chat ID | `1241444951` |
| Telegram bot | `@N8ninsta_jp_bot` |
| Webhook path | `aios-telegram-bot` |
| Total workflows (Phase 3) | 20 |
| Total DB tables (Phase 3) | 25 |

---

## Folder Structure

```
jp-n8n/
├── MASTER_INDEX.md          ← YOU ARE HERE
├── README.md
├── .gitignore
├── agents/                  ← Rules for AI agents by role
│   ├── MASTER_AGENT_RULES.md
│   ├── TELEGRAM_AGENT.md
│   ├── CONTENT_AGENT.md
│   ├── REVIEW_AGENT.md
│   └── AUTOMATION_AGENT.md
├── docs/                    ← Technical documentation
│   ├── ARCHITECTURE.md
│   ├── WORKFLOW_INDEX.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_CONTRACTS.md
│   ├── TELEGRAM_BOT_FLOW.md
│   ├── SYSTEM_FLOW.md
│   ├── AGENT_SYSTEM.md
│   ├── PROMPT_LIBRARY.md
│   ├── ERROR_HANDLING.md
│   ├── RATE_LIMIT_RULES.md
│   ├── AUTH_FLOW.md
│   ├── ENV_VARIABLES.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── SECURITY_POLICY.md
│   ├── BACKUP_RECOVERY.md
│   ├── SCALING_PLAN.md
│   ├── MONITORING_ALERTS.md
│   ├── RELEASE_PROCESS.md
│   └── KNOWN_ISSUES.md
├── guardrails/              ← Hard rules and constraints
│   ├── DO_NOT_TOUCH.md
│   ├── WORKFLOW_GUARDRAILS.md
│   ├── CODING_STANDARDS.md
│   ├── DATABASE_GUARDRAILS.md
│   ├── SECURITY_GUARDRAILS.md
│   ├── API_GUARDRAILS.md
│   ├── UI_GUARDRAILS.md
│   ├── AI_AGENT_RULES.md
│   └── CORE_FUNCTIONS_PROTECTED.md
├── phases/                  ← Phase completion records
│   ├── ROADMAP.md
│   ├── PHASE_1.md
│   ├── PHASE_2.md
│   ├── PHASE_3.md
│   └── PHASE_4.md
├── logs/                    ← Change and event history
│   ├── CHANGELOG.md
│   ├── MIGRATION_LOG.md
│   ├── INCIDENT_LOG.md
│   ├── FEATURE_LOG.md
│   └── SECURITY_LOG.md
└── templates/               ← Copy-paste starters
    ├── WORKFLOW_TEMPLATE.md
    ├── FEATURE_TEMPLATE.md
    ├── BUGFIX_TEMPLATE.md
    └── PR_TEMPLATE.md
```
