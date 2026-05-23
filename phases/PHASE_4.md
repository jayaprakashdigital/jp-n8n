# AIOS Phase 4 — Media Rendering Engine

**Status:** PLANNED
**Target Start:** 2026-06-01
**Phase Lead:** AIOS Team

---

## Objectives

- [ ] FFmpeg pipeline for 9:16 video generation (1080x1920)
- [ ] Image overlay system (background + text + branding)
- [ ] TTS (Text-to-Speech) integration for voiceover
- [ ] Background music mixer (low-volume, royalty-free)
- [ ] Render queue with job status tracking
- [ ] Telegram render progress notifications
- [ ] Generated video storage (local + optional S3)

---

## Planned Workflows

| Workflow | Purpose |
|----------|---------|
| MEDIA__FFMPEG_RENDERER__V1 | Core FFmpeg pipeline: text overlay → video |
| MEDIA__IMAGE_COMPOSITOR__V1 | Background image + branding layer |
| MEDIA__TTS_ENGINE__V1 | Text-to-speech voiceover generation |
| MEDIA__AUDIO_MIXER__V1 | Music + voiceover mixing |
| MEDIA__RENDER_QUEUE__V1 | Job queue with status and retry |
| MEDIA__PROGRESS_NOTIFIER__V1 | Telegram render status messages |
| TELEGRAM__HANDLER_V2__MEDIA | Extend P3 handler with /render command |

---

## Planned Telegram Commands

| Command | Purpose |
|---------|---------|
| `/render <script_id>` | Render a saved script to video |
| `/renderstatus` | Check queue status |
| `/renderpreview` | Get thumbnail preview before full render |

---

## New Tables (Planned)

```sql
CREATE TABLE render_jobs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    script_id INTEGER REFERENCES scripts(id),
    status VARCHAR(50) DEFAULT 'queued',
    progress INTEGER DEFAULT 0,
    output_path TEXT,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE render_assets (
    id SERIAL PRIMARY KEY,
    asset_type VARCHAR(50) NOT NULL,
    file_path TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE render_settings (
    user_id BIGINT PRIMARY KEY,
    resolution VARCHAR(20) DEFAULT '1080x1920',
    font_style VARCHAR(50) DEFAULT 'default',
    color_scheme VARCHAR(50) DEFAULT 'dark',
    watermark BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Infrastructure Requirements

- FFmpeg already installed (confirmed Phase 1: 1080x1920 capable)
- Local render directory: `/var/lib/docker/volumes/n8n_data/_data/renders/`
- Minimum 10GB free disk space for render artifacts
- Optional: S3 bucket for long-term video storage

---

## Technical Constraints

- FFmpeg runs as Execute Command node inside n8n — sandbox restrictions apply
- Max concurrent renders: 2 (CPU limitation on VPS)
- Estimated render time per 60s video: ~45-90 seconds
- n8n execution timeout must be raised to 300s for render workflows
- Videos stored for 7 days then auto-deleted (disk management)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| FFmpeg OOM on VPS | Limit resolution, segment renders, add memory guard |
| Execution timeout | Use async pattern: trigger render → poll status → notify |
| Disk space exhaustion | Cron job to purge renders older than 7 days |
| TTS rate limits | Queue with backoff, cache TTS output per text hash |

---

## Phase 4 Scope Boundary

Phase 4 produces **local video files only**.
Publishing to Instagram/YouTube is Phase 5+.

---

## Dependencies

- Phase 3 Creative Engine must be complete (scripts + hooks available)
- `scripts` table must have `topic` and `niche` columns (added Phase 3)
- FFmpeg binary at path accessible to n8n Docker container
