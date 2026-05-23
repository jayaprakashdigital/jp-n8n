# AIOS — Workflow Index

**Purpose:** Single reference for all 20 deployed n8n workflows — IDs, types, triggers, and purpose.
**Owner:** AIOS Platform Team
**Update Rule:** Update immediately when any workflow is added, modified, or deprecated. Never let this go stale.

---

## Active Workflows (20 total)

### Phase 2 — AI Supervisor Core

| # | Name | n8n ID | Trigger | Status |
|---|------|--------|---------|--------|
| 1 | `TELEGRAM__SUPERVISOR__V2` | `13473953-52ed-419e-93c0-78c0c91b0818` | Webhook POST `/webhook/aios-telegram-bot` | ACTIVE |
| 2 | `AI__OPENROUTER_GATEWAY__V1` | `8bc7451c-aaa9-4906-974b-e37140215262` | executeWorkflowTrigger | ACTIVE |
| 3 | `MEMORY__SESSION_MANAGER__V1` | `905c6145-e979-4a93-bc12-ad5f7c851c4b` | executeWorkflowTrigger | ACTIVE |
| 4 | `AI__INTENT_CLASSIFIER__V1` | `1ef6ed99-e1ba-4ef8-acc8-e6f6fe02fc3d` | executeWorkflowTrigger | ACTIVE |
| 5 | `APPROVAL__STATE_MANAGER__V1` | `91f3ead9-4c7d-4cfd-ba07-9d43062697ce` | Webhook POST `/webhook/aios-approval` | ACTIVE |
| 6 | `AI__WORKFLOW_ROUTER__V1` | `0ed293cc-2685-4d4d-a3fd-2c1a00601855` | executeWorkflowTrigger | ACTIVE |

### Phase 2.5 — Hardening Layer

| # | Name | n8n ID | Trigger | Status |
|---|------|--------|---------|--------|
| 7 | `SYSTEM__ERROR_HANDLER__V1` | `99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2` | errorTrigger (auto) | ACTIVE |
| 8 | `SYSTEM__APPROVAL_RECOVERY__V1` | `08a68b63-5e2d-4c6f-9d9e-c1bd0e69694f` | scheduleTrigger (every 5 min) | ACTIVE |

### Phase 3 — Creative Engine

| # | Name | n8n ID | Trigger | Status |
|---|------|--------|---------|--------|
| 9 | `RESEARCH__VIRAL_ENGINE__V1` | `fbdd5250-869e-51d6-b35d-55991ff24937` | executeWorkflowTrigger | ACTIVE |
| 10 | `RESEARCH__AUDIENCE_PSYCHOLOGY__V1` | `a23cbfac-21c6-5cd4-9fe3-978ed43f7250` | executeWorkflowTrigger | ACTIVE |
| 11 | `SCRIPT__HOOK_OPTIMIZER__V1` | `0e9cd37b-133c-5388-944a-f1f1302ec86d` | executeWorkflowTrigger | ACTIVE |
| 12 | `SCRIPT__GENERATOR__V1` | `ec217d3f-b547-5742-90ae-3131d15df173` | executeWorkflowTrigger | ACTIVE |
| 13 | `MEMORY__TAMIL_STORY_ENGINE__V1` | `a9aee250-116a-562c-9225-9c9a4f732eb9` | executeWorkflowTrigger | ACTIVE |
| 14 | `CAPTION__GENERATOR__V1` | `2bea7691-5d66-5c8f-a575-5d3fabcf7904` | executeWorkflowTrigger | ACTIVE |
| 15 | `AI__CONTENT_SCORER__V1` | `7c2fc159-1c75-51d5-95c0-dac9fd126656` | executeWorkflowTrigger | ACTIVE |
| 16 | `MEMORY__RESEARCH_CONTEXT__V1` | `1fe5fcb5-6761-5416-bfd9-e6d786947430` | executeWorkflowTrigger | ACTIVE |
| 17 | `CREATIVE__SCRIPT_PIPELINE__V1` | `7e6c168a-c01f-5b31-9f67-a605957d0243` | executeWorkflowTrigger | ACTIVE |
| 18 | `PHASE3__TELEGRAM_HANDLER__V1` | `28f26fd8-57ec-5e8e-8360-44c52a4cd627` | executeWorkflowTrigger | ACTIVE |

### External / Pre-existing

| # | Name | n8n ID | Trigger | Status |
|---|------|--------|---------|--------|
| 19 | `DB__WRITE_TEST__V1` | `c0dd6691-8149-45c7-ba7f-70158db62003` | Webhook GET | ACTIVE |
| 20 | `Daily 9AM Free Kids Video Creator to Telegram` | `1jXhN5qo7x2GxiBb` | scheduleTrigger | ACTIVE |

---

## Workflow Dependency Map

```
TELEGRAM__SUPERVISOR__V2
    └── PHASE3__TELEGRAM_HANDLER__V1
            ├── RESEARCH__VIRAL_ENGINE__V1
            ├── CREATIVE__SCRIPT_PIPELINE__V1
            │       ├── SCRIPT__HOOK_OPTIMIZER__V1
            │       ├── SCRIPT__GENERATOR__V1
            │       └── AI__CONTENT_SCORER__V1
            ├── MEMORY__TAMIL_STORY_ENGINE__V1
            └── CAPTION__GENERATOR__V1

SYSTEM__ERROR_HANDLER__V1 (wired to SUPERVISOR via errorWorkflow setting)
SYSTEM__APPROVAL_RECOVERY__V1 (runs independently on schedule)
```

---

## Workflow Node Count Reference

| Workflow | Node Count | Has DB | Has OpenRouter |
|----------|-----------|--------|---------------|
| TELEGRAM__SUPERVISOR__V2 | 24 | Yes | Yes |
| PHASE3__TELEGRAM_HANDLER__V1 | 16 | No | No |
| CREATIVE__SCRIPT_PIPELINE__V1 | 9 | Yes | No |
| SCRIPT__GENERATOR__V1 | 6 | Yes | Yes (sonnet) |
| MEMORY__TAMIL_STORY_ENGINE__V1 | 9 | Yes | Yes (sonnet) |
| RESEARCH__VIRAL_ENGINE__V1 | 6 | Yes | Yes (haiku) |
| SYSTEM__ERROR_HANDLER__V1 | 4 | Yes | No |
| Others | 5-6 | Yes | Yes (haiku) |

---

## Naming Convention

```
{DOMAIN}__{FUNCTION}__{VERSION}

Domain:     TELEGRAM | AI | MEMORY | SCRIPT | RESEARCH | CAPTION | SYSTEM | CREATIVE | PHASE3
Function:   SUPERVISOR | GENERATOR | ENGINE | CLASSIFIER | ROUTER | HANDLER | PIPELINE
Version:    V1 | V2 (increment on breaking changes only)
```

**Examples:**
- `RESEARCH__VIRAL_ENGINE__V1` — correct
- `viral_research_workflow` — incorrect (no domain prefix, no version)

---

## Adding a New Workflow

1. Add to the appropriate Python builder script (`phase4_builder.py`, etc.)
2. Use a deterministic fixed UUID (use `uuid5` with namespace)
3. Add entry to this index immediately
4. Register in `workflow_versions` PostgreSQL table
5. Update `CHANGELOG.md`

**WARNING:** Never create workflows through the n8n UI. Always use builder scripts to ensure reproducibility and the name-based deduplication logic runs correctly.

---

## Deprecated / Removed Workflows

| Name | Removed | Reason |
|------|---------|--------|
| `TELEGRAM__SUPERVISOR__V1` (original) | Phase 2 | Replaced by V2 with session memory |

---

**Future Extension:** Phase 4 will add `MEDIA__FFMPEG_RENDERER__V1`, `MEDIA__THUMBNAIL_GENERATOR__V1`. Phase 5 will add `PUBLISH__INSTAGRAM__V1`.
