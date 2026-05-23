# AIOS — Changelog

**Format:** [Version] — YYYY-MM-DD — Description
**Owner:** Platform Lead
**Update Rule:** Add an entry for every phase completion, hotfix, and significant change.

---

## [3.0.0] — 2026-05-23 — Phase 3: Creative Engine

### Added
- RESEARCH__VIRAL_ENGINE__V1: viral topic research with trend scoring
- RESEARCH__AUDIENCE_PSYCHOLOGY__V1: audience pattern and psychology analysis
- SCRIPT__HOOK_OPTIMIZER__V1: attention hook generation (5 hooks per topic)
- SCRIPT__GENERATOR__V1: full Tamil/English script creation (claude-3.5-sonnet)
- MEMORY__TAMIL_STORY_ENGINE__V1: serialized story with episode/chapter/arc memory
- CAPTION__GENERATOR__V1: platform-optimized captions with hashtags
- AI__CONTENT_SCORER__V1: virality + engagement score (0–100)
- MEMORY__RESEARCH_CONTEXT__V1: persistent research context storage
- CREATIVE__SCRIPT_PIPELINE__V1: hook → script → score pipeline chainer
- PHASE3__TELEGRAM_HANDLER__V1: command router for P3 commands
- P3 command detection in TELEGRAM__SUPERVISOR__V2 (non-destructive upgrade)
- Telegram commands: /research, /script, /story, /caption, /generate
- 7 new PostgreSQL tables: hook_library, audience_patterns, emotional_scores, successful_captions, story_progression, pacing_feedback, replay_scores
- New columns on `scripts` table: topic (VARCHAR 300), niche (VARCHAR 100)

### Changed
- TELEGRAM__SUPERVISOR__V2 "Prepare AI Context" node updated with P3 detection
- Both "Prepare Save Data" and new "Prep P3 Save Data" now fan-out to [Save Session, Log Execution, Send Reply] in parallel
- "Send Reply" now uses `$json.chat_id` (local reference, works for both AI and P3 paths)

### Fixed
- "Send Reply" backreference broke when P3 path bypassed "Validate & Parse" node

---

## [2.5.0] — 2026-05-23 — Phase 2.5: Hardening Layer

### Added
- Execution logging: every message logged to `execution_logs` table
- SYSTEM__ERROR_HANDLER__V1: global error handler with admin Telegram notification
- JSON schema validation in supervisor "Validate & Parse" node
- Rate limiting: 10 requests per minute per user (PostgreSQL-backed)
- SYSTEM__APPROVAL_RECOVERY__V1: clears stale pending approvals on supervisor start
- Workflow version registry in `workflow_versions` table
- New tables: execution_logs, rate_limits, pending_approvals, workflow_versions
- `continueOnFail=true` on Log Execution and Expire Stale Approvals nodes
- `neverError=true` on all outbound Telegram API calls

### Changed
- TELEGRAM__SUPERVISOR__V2 `errorWorkflow` set to SYSTEM__ERROR_HANDLER__V1 ID

### Fixed
- Both callback and message branches running simultaneously (added IF node Route Branch)
- `b.text.toLowerCase()` crash on undefined button text (added `.filter(b => b && b.text)`)

---

## [2.0.0] — 2026-05-23 — Phase 2: AI Supervisor

### Added
- TELEGRAM__SUPERVISOR__V2: main Telegram bot workflow with OpenRouter integration
- AI__OPENROUTER_GATEWAY__V1: reusable OpenRouter subworkflow
- MEMORY__SESSION_MANAGER__V1: per-user session state in PostgreSQL JSONB
- AI__INTENT_CLASSIFIER__V1: classifies user intent (claude-3.5-haiku)
- APPROVAL__STATE_MANAGER__V1: manages multi-step approval flows
- AI__WORKFLOW_ROUTER__V1: routes AI responses to appropriate handlers
- Session memory: JSONB column in PostgreSQL, merged on every message
- IF node routing: `isCallback` boolean gates callback vs message path
- Inline keyboard button support

### Fixed
- Standalone `//` JS comments between Python f-strings caused SyntaxError (embedded all comments inside string literals)
- `\"intent\"` SyntaxError in f-strings (changed to single-quoted Python strings)

---

## [1.0.0] — 2026-05-22 — Phase 1: Infrastructure Foundation

### Added
- VPS provisioned on Hostinger (Ubuntu)
- Docker + Docker Compose installed
- Traefik reverse proxy with Let's Encrypt TLS
- n8n v2.19.5 container deployed
- PostgreSQL 16-alpine container with `aios_db`
- 14 initial database tables: users, sessions, scripts, viral_research, prompts, content_queue, analytics, approvals, generated_images, generated_videos, tamil_story_memory, character_memory, upload_history, rejected_feedback
- FFmpeg installed (1080x1920 capable)
- Telegram bot (@N8ninsta_jp_bot) created and webhook registered
- OpenRouter API key configured

### Technical Decisions
- Direct SQLite manipulation instead of n8n REST API (REST returns 403)
- Standard Webhook node instead of Telegram Trigger (path encoding issues)
- Traefik with Let's Encrypt for automatic TLS management

---

## Versioning Convention

| Version | Meaning |
|---------|---------|
| X.0.0 | New phase completion |
| X.Y.0 | New workflow added mid-phase |
| X.Y.Z | Hotfix or node-level patch |
