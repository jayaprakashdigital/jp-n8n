# AIOS — Full Roadmap

**Last Updated:** 2026-05-23
**Owner:** Platform Lead

---

## Phase Overview

| Phase | Name | Status | Completed |
|-------|------|--------|-----------|
| 1 | Infrastructure Foundation | ✅ COMPLETE | 2026-05-22 |
| 2 | AI Supervisor | ✅ COMPLETE | 2026-05-23 |
| 2.5 | Hardening Layer | ✅ COMPLETE | 2026-05-23 |
| 3 | Creative Engine | ✅ COMPLETE | 2026-05-23 |
| 4 | Media Rendering Engine | 🔲 PLANNED | — |
| 5 | Publishing & Distribution | 🔲 PLANNED | — |
| 6 | Analytics & Intelligence | 🔲 PLANNED | — |

---

## Phase 1 — Infrastructure Foundation ✅

**Goal:** Production-ready server with all dependencies deployed.

**Deliverables:**
- VPS provisioned, Docker + Compose installed
- Traefik reverse proxy with Let's Encrypt TLS
- n8n v2.19.5 deployed and accessible
- PostgreSQL 16-alpine with `aios_db` (14 tables)
- FFmpeg installed (1080x1920 capable)
- Telegram bot created and webhook registered
- OpenRouter API key configured

---

## Phase 2 — AI Supervisor ✅

**Goal:** Intelligent Telegram bot with session memory and AI routing.

**Deliverables:**
- TELEGRAM__SUPERVISOR__V2 with OpenRouter integration
- Session memory in PostgreSQL (per-user JSONB state)
- AI intent classification (claude-3.5-haiku)
- Callback routing with inline keyboard buttons
- Approval state management
- AI__OPENROUTER_GATEWAY__V1 reusable subworkflow

---

## Phase 2.5 — Hardening Layer ✅

**Goal:** Production stability, error recovery, and rate limiting.

**Deliverables:**
- Execution logging (all messages logged)
- SYSTEM__ERROR_HANDLER__V1 global error handler
- JSON schema validation in supervisor
- Rate limiting (10 req/min per user, PostgreSQL-backed)
- SYSTEM__APPROVAL_RECOVERY__V1 (pending approval recovery)
- Workflow version registry

---

## Phase 3 — Creative Engine ✅

**Goal:** AI-powered content creation: research, scripting, story, captions.

**Deliverables:**
- 8 creative subworkflows (viral research → scripting → scoring)
- CREATIVE__SCRIPT_PIPELINE__V1 (hook → script → score chain)
- PHASE3__TELEGRAM_HANDLER__V1 (command router)
- Supervisor updated with /research, /script, /story, /caption, /generate
- 7 new PostgreSQL tables for creative content storage
- Non-destructive supervisor upgrade (all Phase 2 hardening preserved)

---

## Phase 4 — Media Rendering Engine 🔲

**Goal:** Convert scripts to rendered 9:16 videos using FFmpeg.

**Target:** 2026-06-01

**Planned Deliverables:**
- FFmpeg renderer (text overlay, background, branding)
- TTS voiceover integration
- Background music mixer
- Render queue with job tracking
- Telegram progress notifications
- /render, /renderstatus, /renderpreview commands

**Blocker:** Requires adequate VPS disk space and CPU headroom.

---

## Phase 5 — Publishing & Distribution 🔲

**Goal:** Automated publishing to Instagram Reels and YouTube Shorts.

**Target:** 2026-07-01

**Planned Deliverables:**
- Instagram Graph API integration (OAuth, token refresh)
- YouTube Data API v3 integration
- Upload queue with retry logic
- Post scheduling (time-optimized per platform)
- Upload history and status tracking
- /publish, /schedule, /uploadstatus commands

**Blocker:** Requires Phase 4 (video files) + OAuth credentials setup.

---

## Phase 6 — Analytics & Intelligence 🔲

**Goal:** Close the feedback loop: track performance, adapt content strategy.

**Target:** 2026-08-01

**Planned Deliverables:**
- Instagram Insights API polling (views, reach, saves, shares)
- YouTube Analytics API polling
- Performance → content strategy feedback loop
- A/B hook testing (generate 2 hooks, compare performance)
- Automated weekly performance reports via Telegram
- Content scoring model improvement (based on real performance data)

**Blocker:** Requires Phase 5 (published content with IDs to track).

---

## Long-Term Vision (Phase 7+)

- Multi-language support (beyond Tamil/English)
- Multi-account management (agency use case)
- Trend detection via social listening
- AI model fine-tuning on high-performing AIOS content
- Self-improving prompt library based on performance data

---

## Dependency Graph

```
Phase 1 (Infrastructure)
    └── Phase 2 (AI Supervisor)
            └── Phase 2.5 (Hardening) ← parallel with Phase 2 completion
                    └── Phase 3 (Creative Engine)
                            └── Phase 4 (Media Rendering)
                                    └── Phase 5 (Publishing)
                                            └── Phase 6 (Analytics)
```

---

## Architecture Evolution

| Phase | Workflows | DB Tables | Commands |
|-------|-----------|-----------|---------|
| After Phase 1 | 0 active | 14 | — |
| After Phase 2 | 6 | 14 | Natural language |
| After Phase 2.5 | 8 | 18 | Natural language |
| After Phase 3 | 20 | 25 | + /research /script /story /caption |
| After Phase 4 | ~27 | ~28 | + /render /renderstatus |
| After Phase 5 | ~33 | ~32 | + /publish /schedule |
| After Phase 6 | ~38 | ~36 | + /report /analytics |
