# AIOS — Migration Log

**Purpose:** Record every database schema migration: what changed, when, and why.
**Owner:** Platform Lead
**Update Rule:** Add an entry for every `run_migration()` call in any builder script. Never delete.
**Format:** MIG-PHASE-NN

---

## Migration History

### MIG-01-01 — Phase 1 Initial Schema
**Date:** 2026-05-22
**Script:** phase1_builder.py
**Type:** CREATE TABLE (initial)

**Tables Created:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(100),
    first_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    user_id BIGINT PRIMARY KEY REFERENCES users(id),
    state JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scripts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    content TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS viral_research (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    topic VARCHAR(300),
    research_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_queue (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    content_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics (
    id SERIAL PRIMARY KEY,
    content_id INTEGER,
    platform VARCHAR(50),
    metric_type VARCHAR(50),
    value NUMERIC,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    workflow_name VARCHAR(100),
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generated_images (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    prompt TEXT,
    file_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generated_videos (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    script_id INTEGER REFERENCES scripts(id),
    file_path TEXT,
    status VARCHAR(50) DEFAULT 'queued',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tamil_story_memory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    story_arc VARCHAR(100),
    chapter INTEGER DEFAULT 1,
    state JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_memory (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES tamil_story_memory(id),
    character_name VARCHAR(100),
    traits JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS upload_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    platform VARCHAR(50),
    content_id INTEGER,
    upload_url TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rejected_feedback (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    content_type VARCHAR(50),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Result:** 14 tables created successfully.

---

### MIG-02-01 — Phase 2.5 Hardening Tables
**Date:** 2026-05-23
**Script:** phase25_builder.py
**Type:** CREATE TABLE (additive)

**Tables Created:**
```sql
CREATE TABLE IF NOT EXISTS execution_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    workflow_name VARCHAR(100),
    intent VARCHAR(100),
    status VARCHAR(50) DEFAULT 'success',
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rate_limits (
    user_id BIGINT PRIMARY KEY,
    request_count INTEGER DEFAULT 0,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    approval_type VARCHAR(100),
    payload JSONB NOT NULL DEFAULT '{}',
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_versions (
    workflow_id VARCHAR(100) PRIMARY KEY,
    workflow_name VARCHAR(200) NOT NULL,
    version INTEGER DEFAULT 1,
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Result:** 4 tables created. Total: 18 tables.

---

### MIG-03-01 — Phase 3 Creative Engine Tables
**Date:** 2026-05-23
**Script:** phase3_builder.py
**Type:** CREATE TABLE + ALTER TABLE (additive)

**Columns Added:**
```sql
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS topic VARCHAR(300);
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS niche VARCHAR(100);
```

**Tables Created:**
```sql
CREATE TABLE IF NOT EXISTS hook_library (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(300),
    niche VARCHAR(100),
    hook_text TEXT NOT NULL,
    hook_type VARCHAR(50) DEFAULT 'attention',
    score INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audience_patterns (
    id SERIAL PRIMARY KEY,
    niche VARCHAR(100),
    pattern_type VARCHAR(100),
    description TEXT,
    effectiveness_score INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS emotional_scores (
    id SERIAL PRIMARY KEY,
    content_id INTEGER,
    content_type VARCHAR(50),
    emotion VARCHAR(50),
    intensity INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS successful_captions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    topic VARCHAR(300),
    platform VARCHAR(50),
    caption_text TEXT NOT NULL,
    hashtags TEXT[],
    performance_score INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS story_progression (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    story_arc VARCHAR(100),
    episode INTEGER DEFAULT 1,
    chapter INTEGER DEFAULT 1,
    summary TEXT,
    characters JSONB NOT NULL DEFAULT '[]',
    state JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pacing_feedback (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES story_progression(id),
    episode INTEGER,
    pacing_score INTEGER,
    feedback TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS replay_scores (
    id SERIAL PRIMARY KEY,
    content_id INTEGER,
    content_type VARCHAR(50),
    predicted_replay_rate NUMERIC(5,2),
    virality_score INTEGER,
    engagement_score INTEGER,
    overall_score INTEGER,
    scoring_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Result:** 7 tables created, 2 columns added. Total: 25 tables.

---

## Migration Rules

1. **Always use `IF NOT EXISTS`** — migrations must be idempotent (safe to re-run)
2. **Never DROP or ALTER (destructive)** — only ADD columns or CREATE new tables
3. **Always log here** before running migration in production
4. **Always test in dev** before applying to production PostgreSQL
5. **Document rollback plan** for any migration that modifies existing column types
