# AIOS — Rate Limit Rules

**Purpose:** Define rate limiting implementation, thresholds, and tuning guidelines.
**Owner:** Platform Reliability Lead
**Update Rule:** Update when limits are changed or new rate limit dimensions added.

---

## Current Limits

| Dimension | Limit | Window | Enforcement |
|-----------|-------|--------|-------------|
| Telegram messages per user | 10 | 1 minute | PostgreSQL rate_limits table |
| OpenRouter API calls | Provider limit | Per-minute | Managed by OpenRouter |
| Telegram Bot API | 30 msgs/second | Global | Managed by Telegram |
| n8n executions | Unlimited | — | VPS resource bound |

---

## Implementation

### PostgreSQL-backed rate limiting

```sql
-- On every incoming message (in Check Rate Limit node):
INSERT INTO rate_limits (telegram_id, window_start, request_count)
VALUES ($telegram_id, DATE_TRUNC('minute', NOW()), 1)
ON CONFLICT (telegram_id, window_start)
DO UPDATE SET request_count = rate_limits.request_count + 1
RETURNING request_count,
          request_count > 10 AS is_blocked,
          CEIL(EXTRACT(EPOCH FROM
            (DATE_TRUNC('minute', NOW() + INTERVAL '1 minute') - NOW())))::INTEGER
          AS retry_after_secs;
```

### Rate gate response
When `is_blocked = true`:
```
⏳ Too fast! Max 10 messages/min. Retry in {retry_after_secs}s.
```

---

## Tuning the Limit

The limit is defined in builder scripts as `RATE_LIMIT = 10`. To change:

1. Update `RATE_LIMIT` constant in `phase25_builder.py` and `phase3_builder.py`
2. Re-run the supervisor build: `python3 scripts/phase25_builder.py` or `phase3_builder.py`
3. Restart n8n
4. Update this document

**Current value reasoning:** 10/min is generous for normal conversation but blocks bots and spam.

---

## Rate Limit Table Cleanup

The `rate_limits` table currently grows indefinitely. Rows older than 2 minutes are obsolete.

**Temporary cleanup (run manually):**
```sql
DELETE FROM rate_limits WHERE window_start < NOW() - INTERVAL '2 minutes';
```

**Phase 4 task:** Add a scheduled n8n workflow to run this cleanup every 30 minutes.

---

## OpenRouter Rate Limits

OpenRouter enforces its own limits per API key tier:
- Check current usage at: `https://openrouter.ai/account`
- If 429 errors appear, the error handler will notify admin via Telegram
- Mitigation: cache common research results in `viral_research` table before calling OR again

---

**Future Extension:** Phase 4 — add per-command rate limits (e.g., `/script` max 5/hour since it uses claude-3.5-sonnet). Add Redis for distributed rate limiting across multiple n8n instances.
