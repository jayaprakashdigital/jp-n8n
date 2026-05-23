# AIOS — Database Schema

**Purpose:** Complete PostgreSQL schema reference for all 25 tables in `aios_db`.
**Owner:** Database Administrator / Backend Lead
**Update Rule:** Update this file BEFORE running any ALTER TABLE or CREATE TABLE migration. Never drop a table without a migration entry in `logs/MIGRATION_LOG.md`.

---

## Connection Details

```
Host:     aios-postgres (Docker container)
Port:     5432 (internal), not exposed externally
Database: aios_db
User:     aios_user
Encoding: UTF-8
```

n8n Credential ID: `a20cebf1b1c648`

---

## Table Inventory (25 tables)

### Group 1: Identity & Session

#### `users`
```sql
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username    VARCHAR(100),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
**Purpose:** One row per Telegram user. Created on first message.

#### `sessions`
```sql
CREATE TABLE sessions (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER UNIQUE REFERENCES users(id),
    session_data   JSONB NOT NULL DEFAULT '{}',
    active_workflow VARCHAR(100),
    current_status VARCHAR(50) DEFAULT 'active',
    message_count  INTEGER DEFAULT 0,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
**Purpose:** Per-user conversation state. Updated on every message. `session_data` stores AI context (last intent, preferences, workflow state).

---

### Group 2: Content Pipeline

#### `scripts`
```sql
CREATE TABLE scripts (
    id              SERIAL PRIMARY KEY,
    script_text     TEXT,
    script_type     VARCHAR(100),   -- 'reel', 'story', 'caption'
    approval_status VARCHAR(50),    -- 'pending', 'approved', 'rejected'
    topic           VARCHAR(300),   -- Added Phase 3
    niche           VARCHAR(100),   -- Added Phase 3
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `viral_research`
```sql
CREATE TABLE viral_research (
    id              SERIAL PRIMARY KEY,
    niche           VARCHAR(255),
    trend_summary   TEXT,
    retention_score INTEGER,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `prompts`
```sql
CREATE TABLE prompts (
    id          SERIAL PRIMARY KEY,
    prompt_text TEXT,
    prompt_type VARCHAR(100),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `content_queue`
```sql
CREATE TABLE content_queue (
    id          SERIAL PRIMARY KEY,
    content_type VARCHAR(50),
    content_data JSONB NOT NULL DEFAULT '{}',
    status      VARCHAR(20) DEFAULT 'pending',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### Group 3: Memory / Story

#### `tamil_story_memory`
```sql
CREATE TABLE tamil_story_memory (
    id               SERIAL PRIMARY KEY,
    episode_number   INTEGER,
    story_summary    TEXT,
    continuity_notes TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `character_memory`
```sql
CREATE TABLE character_memory (
    id               SERIAL PRIMARY KEY,
    character_name   VARCHAR(255),
    personality      TEXT,
    continuity_notes TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `story_progression` (Phase 3)
```sql
CREATE TABLE story_progression (
    id               SERIAL PRIMARY KEY,
    episode_number   INTEGER NOT NULL,
    theme            VARCHAR(200),
    story_content    TEXT NOT NULL,
    characters_used  JSONB NOT NULL DEFAULT '[]',
    continuity_notes TEXT,
    next_seeds       JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### Group 4: Hardening Layer (Phase 2.5)

#### `execution_logs`
```sql
CREATE TABLE execution_logs (
    id             SERIAL PRIMARY KEY,
    workflow_name  VARCHAR(100) NOT NULL,
    telegram_id    BIGINT,
    event_type     VARCHAR(50) NOT NULL DEFAULT 'message_processed',
    status         VARCHAR(20) NOT NULL DEFAULT 'success',
    duration_ms    INTEGER,
    error_message  TEXT,
    error_node     VARCHAR(100),
    metadata       JSONB NOT NULL DEFAULT '{}',
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- Indexes:
CREATE INDEX idx_exec_logs_tg ON execution_logs(telegram_id, created_at DESC);
CREATE INDEX idx_exec_logs_wf ON execution_logs(workflow_name, created_at DESC);
```

#### `rate_limits`
```sql
CREATE TABLE rate_limits (
    telegram_id   BIGINT NOT NULL,
    window_start  TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (telegram_id, window_start)
);
```
**Rule:** Max 10 requests per `window_start` (1-minute buckets). Enforced by supervisor.

#### `pending_approvals`
```sql
CREATE TABLE pending_approvals (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id),
    telegram_id      BIGINT NOT NULL,
    chat_id          BIGINT NOT NULL,
    workflow_context JSONB NOT NULL DEFAULT '{}',
    content_preview  TEXT,
    message_id       INTEGER,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|expired
    expires_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `workflow_versions`
```sql
CREATE TABLE workflow_versions (
    id             SERIAL PRIMARY KEY,
    workflow_name  VARCHAR(100) NOT NULL,
    version        VARCHAR(20) NOT NULL DEFAULT 'v1',
    n8n_id         VARCHAR(100),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    description    TEXT,
    deployed_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (workflow_name, version)
);
```

---

### Group 5: Phase 3 — Creative Engine

#### `hook_library`
```sql
CREATE TABLE hook_library (
    id          SERIAL PRIMARY KEY,
    topic       VARCHAR(300),
    niche       VARCHAR(100),
    hook_text   TEXT NOT NULL,
    hook_type   VARCHAR(50) DEFAULT 'attention',  -- attention|question|shock|story|stat
    score       INTEGER DEFAULT 0,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_hook_lib_niche ON hook_library(niche, created_at DESC);
```

#### `audience_patterns`
```sql
CREATE TABLE audience_patterns (
    id            SERIAL PRIMARY KEY,
    niche         VARCHAR(100) NOT NULL,
    demographics  VARCHAR(100) DEFAULT 'general',
    analysis_data JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_aud_pat_niche ON audience_patterns(niche, created_at DESC);
```

#### `successful_captions`
```sql
CREATE TABLE successful_captions (
    id                SERIAL PRIMARY KEY,
    topic             VARCHAR(300),
    niche             VARCHAR(100),
    platform          VARCHAR(50) DEFAULT 'instagram',
    caption_text      TEXT NOT NULL,
    hashtags          JSONB NOT NULL DEFAULT '[]',
    char_count        INTEGER DEFAULT 0,
    performance_score INTEGER DEFAULT 0,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_captions_niche ON successful_captions(niche, platform, created_at DESC);
```

#### `replay_scores`
```sql
CREATE TABLE replay_scores (
    id              SERIAL PRIMARY KEY,
    content_type    VARCHAR(50) DEFAULT 'script',
    niche           VARCHAR(100),
    content_preview TEXT,
    overall_score   INTEGER DEFAULT 0,
    hook_score      INTEGER DEFAULT 0,
    retention_score INTEGER DEFAULT 0,
    viral_score     INTEGER DEFAULT 0,
    clarity_score   INTEGER DEFAULT 0,
    suggestions     JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_replay_niche ON replay_scores(niche, overall_score DESC);
```

#### `emotional_scores`
```sql
CREATE TABLE emotional_scores (
    id                SERIAL PRIMARY KEY,
    content_ref       VARCHAR(100),
    content_type      VARCHAR(50) DEFAULT 'script',
    emotion_breakdown JSONB NOT NULL DEFAULT '{}',
    overall_score     INTEGER DEFAULT 0,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `pacing_feedback`
```sql
CREATE TABLE pacing_feedback (
    id            SERIAL PRIMARY KEY,
    content_type  VARCHAR(50),
    feedback_type VARCHAR(50) DEFAULT 'general',
    feedback_text TEXT,
    telegram_id   BIGINT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### Group 6: Media / Publishing (Phase 4+)

#### `generated_images`
```sql
CREATE TABLE generated_images (
    id          SERIAL PRIMARY KEY,
    script_id   INTEGER REFERENCES scripts(id),
    file_path   VARCHAR(500),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `generated_videos`
```sql
CREATE TABLE generated_videos (
    id          SERIAL PRIMARY KEY,
    script_id   INTEGER REFERENCES scripts(id),
    file_path   VARCHAR(500),
    duration    INTEGER,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `upload_history`
```sql
CREATE TABLE upload_history (
    id           SERIAL PRIMARY KEY,
    video_id     INTEGER REFERENCES generated_videos(id),
    platform     VARCHAR(50),
    post_id      VARCHAR(100),
    status       VARCHAR(20) DEFAULT 'pending',
    metadata     JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `analytics`
```sql
CREATE TABLE analytics (
    id          SERIAL PRIMARY KEY,
    post_id     VARCHAR(100),
    platform    VARCHAR(50),
    views       INTEGER DEFAULT 0,
    likes       INTEGER DEFAULT 0,
    shares      INTEGER DEFAULT 0,
    saves       INTEGER DEFAULT 0,
    metadata    JSONB NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `approvals` (legacy)
```sql
CREATE TABLE approvals (
    id          SERIAL PRIMARY KEY,
    content_id  INTEGER,
    status      VARCHAR(20),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `rejected_feedback`
```sql
CREATE TABLE rejected_feedback (
    id            SERIAL PRIMARY KEY,
    content_id    INTEGER,
    feedback_text TEXT,
    telegram_id   BIGINT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Migration Rules

1. **Never DROP a table or column** without a migration entry
2. **Always use `IF NOT EXISTS`** for CREATE TABLE
3. **Always use `ADD COLUMN IF NOT EXISTS`** for ALTER TABLE
4. **Document every migration** in `logs/MIGRATION_LOG.md`
5. **Test on backup** before running on production

## Backup Command

```bash
docker exec aios-postgres pg_dump -U aios_user aios_db > backups/$(date +%Y%m%d_%H%M%S)/aios_db.sql
```

---

**Warnings:**
- Never delete data from `sessions` or `users` without user request
- `execution_logs` grows fast — add a cleanup cron for rows > 30 days old (Phase 4 task)
- `rate_limits` rows are never cleaned up currently — add cleanup job

**Future Extension:** Add partitioning to `execution_logs` by month when row count exceeds 1M.
