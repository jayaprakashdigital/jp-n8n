# AIOS — Scaling Plan

**Purpose:** Define the scaling strategy as AIOS grows in users and content volume.
**Owner:** Architecture Lead
**Update Rule:** Review at each phase completion. This is a living plan, not a commitment.

---

## Current Capacity (Phase 3)

| Resource | Current | Bottleneck at |
|----------|---------|--------------|
| n8n workflows | 20 | ~200 (memory) |
| PostgreSQL | Single container | ~10K concurrent |
| Rate limit | 10 req/min per user | N/A |
| OpenRouter | Shared key, tier-1 | ~100 req/min |
| VPS | 4GB RAM | ~50 concurrent executions |

**Estimated current max users:** ~100 daily active Telegram users before performance degrades.

---

## Phase 4 Scaling (Media Rendering)

FFmpeg is CPU-intensive. Each video render blocks a CPU core.

**Mitigation:**
- Queue renders in `content_queue` table
- Process one at a time (sequential, not parallel)
- Off-peak scheduling (run renders at night via cron)

**Future:** Move renders to dedicated worker container with multiple CPU cores.

---

## Phase 5 Scaling (Publishing)

Instagram API has strict rate limits:
- 200 API calls per hour per access token
- 1 video upload per ~60 seconds (optimal)

**Strategy:**
- Upload queue in `upload_history` table
- Scheduler workflow: process 1 upload per 2 minutes
- Stagger publishing across time zones

---

## Phase 6 Scaling (Analytics)

`analytics` table will grow at ~10 rows per post per day.

**Mitigation:**
- Add created_at index from day 1
- Monthly aggregation jobs
- Partition table by month when > 1M rows

---

## Horizontal Scaling (Phase 6+)

When single VPS is not enough:

1. **Database:** Move PostgreSQL to managed DB (AWS RDS, Supabase, Neon)
2. **Rate limiting:** Replace PostgreSQL rate_limits with Redis
3. **n8n:** Deploy n8n cluster (n8n queue mode with Redis + PostgreSQL backend)
4. **Media:** Move FFmpeg to GPU-enabled cloud worker

---

**Warnings:**
- Do not scale prematurely. The current single-VPS architecture can handle typical creator workloads.
- Any database migration must go through `logs/MIGRATION_LOG.md` process.

**Future Extension:** This document becomes the architecture decision record (ADR) for each scaling choice.
