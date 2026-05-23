# AIOS — Known Issues

**Purpose:** Track active known issues, limitations, and accepted tech debt.
**Owner:** Platform Lead
**Update Rule:** Add issues as discovered. Mark resolved with date. Never delete entries.

---

## Active Issues

### KI-001: rate_limits table grows indefinitely
- **Severity:** Low
- **Phase:** 2.5
- **Description:** `rate_limits` rows are never deleted. Each minute × each user = accumulating rows.
- **Impact:** Table will grow ~1440 rows/user/day. At 100 users = 144K rows/day.
- **Workaround:** Run manually: `DELETE FROM rate_limits WHERE window_start < NOW() - INTERVAL '2 minutes';`
- **Fix planned:** Phase 4 — add `SYSTEM__MAINTENANCE__V1` scheduled cleanup workflow.

### KI-002: execution_logs has no retention policy
- **Severity:** Low
- **Phase:** 2.5
- **Description:** All execution log rows are kept indefinitely.
- **Impact:** Table grows ~50 rows/day per active user.
- **Workaround:** Manual cleanup: `DELETE FROM execution_logs WHERE created_at < NOW() - INTERVAL '30 days';`
- **Fix planned:** Phase 4 — scheduled cleanup job.

### KI-003: OR_KEY embedded in workflow HTTP nodes
- **Severity:** Medium
- **Phase:** 2
- **Description:** OpenRouter API key is embedded as plaintext in n8n workflow JSON (inside SQLite). It is not exposed via the API but is visible in the n8n UI.
- **Impact:** Any admin with n8n UI access can see the API key.
- **Workaround:** Restrict n8n UI access to trusted admins only.
- **Fix planned:** Phase 4 — migrate to n8n credential (encrypted).

### KI-004: Tamil story episode_number not auto-incremented
- **Severity:** Low
- **Phase:** 3
- **Description:** `MEMORY__TAMIL_STORY_ENGINE__V1` always starts at episode 1 unless caller passes `episode_number`. There is no auto-detect of "next episode" from the DB.
- **Impact:** User must specify episode number manually or stories always start at 1.
- **Workaround:** Pass `episode_number` explicitly or check `SELECT MAX(episode_number) FROM tamil_story_memory`.
- **Fix planned:** Phase 3.1 — add DB query to auto-detect next episode.

### KI-005: executeWorkflow return value not validated
- **Severity:** Low
- **Phase:** 3
- **Description:** If a Phase 3 subworkflow (e.g., RESEARCH__VIRAL_ENGINE__V1) fails mid-way, the `executeWorkflow` caller in PHASE3__TELEGRAM_HANDLER__V1 receives partial or empty data. There is no error check on the returned JSON.
- **Impact:** Format Reply nodes may crash or return empty replies.
- **Workaround:** The Telegram handler's Format Reply nodes use `|| 'fallback'` defaults.
- **Fix planned:** Phase 3.1 — add data validation in Format Reply code nodes.

---

## Resolved Issues

| ID | Description | Resolved | Fix |
|----|-------------|---------|-----|
| KI-R001 | Telegram webhook path encoding issue with Telegram Trigger node | Phase 2 | Switched to standard Webhook node with simple path `aios-telegram-bot` |
| KI-R002 | Workflows stuck as "draft" after SQLite insertion | Phase 2 | Set both `versionId` AND `activeVersionId` + create `workflow_history` entry |
| KI-R003 | Both callback and message branches running simultaneously | Phase 2 | Added IF node `Route Branch` with `isCallback` condition |
| KI-R004 | Duplicate workflows on builder re-run | Phase 2 | Added name-based deduplication in `upsert_workflow()` |
| KI-R005 | `b.text.toLowerCase()` crash on undefined button | Phase 2 | Added `.filter(b => b && b.text)` before `.map()` |
| KI-R006 | Standalone `//` JS comment lines in Python strings | Phase 2.5 | All JS comments embedded within string literals |

---

**Warnings:**
- Do not mark an issue resolved unless you have verified the fix in production.
- Never delete issue entries — they are historical record.
