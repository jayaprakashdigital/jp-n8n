# AIOS — Feature Log

**Purpose:** Track feature additions, capability expansions, and new user-facing behaviors.
**Owner:** Platform Lead
**Update Rule:** Add an entry when a new capability is available to end users.

---

## Features by Phase

### Phase 3 Features — 2026-05-23

#### F3-01: Viral Research Command
**Command:** `/research <topic>`
**Example:** `/research morning skincare routine`
**Output:** Top 5 viral angles, trending hooks, audience psychology insights, recommended niche
**Backend:** RESEARCH__VIRAL_ENGINE__V1 + RESEARCH__AUDIENCE_PSYCHOLOGY__V1

#### F3-02: Script Generation Command
**Command:** `/script <topic>` or `/generate <topic>`
**Example:** `/script 5-minute morning workout`
**Output:** 3 attention hooks, full Tamil/English script (60-90s), virality score (0-100)
**Backend:** CREATIVE__SCRIPT_PIPELINE__V1 (hooks → script → score)

#### F3-03: Tamil Story Engine
**Command:** `/story <prompt>`
**Example:** `/story continue the village healer story`
**Output:** Next episode (500-800 words), maintains continuity with previous episodes
**Backend:** MEMORY__TAMIL_STORY_ENGINE__V1 (PostgreSQL story_progression memory)

#### F3-04: Caption Generator
**Command:** `/caption <topic>`
**Example:** `/caption morning routine video`
**Output:** Captions for Instagram, YouTube, TikTok — each with hashtags and CTA
**Backend:** CAPTION__GENERATOR__V1

---

### Phase 2 Features — 2026-05-23

#### F2-01: AI Conversational Interface
**Trigger:** Any plain text message
**Output:** Context-aware AI response (claude-3.5-haiku via OpenRouter)
**Backend:** TELEGRAM__SUPERVISOR__V2 + AI__OPENROUTER_GATEWAY__V1

#### F2-02: Session Memory
**Behavior:** Bot remembers conversation context per user across messages
**Backend:** MEMORY__SESSION_MANAGER__V1 (PostgreSQL JSONB)

#### F2-03: Approval Flow
**Trigger:** AI detects action requiring user confirmation
**Output:** Inline keyboard with Yes/No buttons; action executes on approval
**Backend:** APPROVAL__STATE_MANAGER__V1

#### F2-04: Rate Limiting
**Behavior:** Users limited to 10 messages per minute; friendly warning sent on exceeded limit
**Backend:** Rate limiting in supervisor (PostgreSQL rate_limits table)

---

### Phase 1 Features — 2026-05-22

#### F1-01: Telegram Bot Online
**Bot:** @N8ninsta_jp_bot
**Behavior:** Responds to any message (basic echo at Phase 1, AI at Phase 2+)

---

## Feature Roadmap (Planned)

| ID | Feature | Phase | Status |
|----|---------|-------|--------|
| F4-01 | /render — generate 9:16 video from script | 4 | Planned |
| F4-02 | /renderstatus — check render queue | 4 | Planned |
| F5-01 | /publish — post to Instagram Reels | 5 | Planned |
| F5-02 | /schedule — schedule post for peak time | 5 | Planned |
| F6-01 | /report — weekly performance analytics | 6 | Planned |
| F6-02 | A/B hook testing (auto-compare 2 hooks) | 6 | Planned |

---

## Feature Deprecation Log

_No features deprecated yet._

**Deprecation process:** Feature must be logged here 30 days before removal. Users must be notified via Telegram announcement.
