# AIOS — Monitoring & Alerts

**Purpose:** Define what to monitor, alert thresholds, and how to respond.
**Owner:** Platform Reliability Lead
**Update Rule:** Add new metrics when new workflows or phases are deployed.

---

## Current Monitoring (Phase 3)

### Active Alerts
| Trigger | Alert Method | Who Gets It |
|---------|-------------|------------|
| Any workflow error | Telegram message | Admin (chat_id: 1241444951) |
| Pending approvals > 5 min old | Telegram reminder | User who made request |

### Manual Monitoring (check via SQL)

```sql
-- Workflow health: execution count in last hour
SELECT workflow_name, COUNT(*) as executions, 
       SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors
FROM execution_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY workflow_name ORDER BY executions DESC;

-- Rate limit hits in last 30 min
SELECT telegram_id, SUM(request_count) as total
FROM rate_limits
WHERE window_start > NOW() - INTERVAL '30 minutes'
GROUP BY telegram_id ORDER BY total DESC;

-- Pending approvals by age
SELECT telegram_id, content_preview, created_at, 
       EXTRACT(EPOCH FROM (NOW()-created_at))/60 as age_minutes
FROM pending_approvals WHERE status='pending' ORDER BY created_at;

-- Last 10 errors
SELECT workflow_name, error_message, created_at
FROM execution_logs WHERE status='error'
ORDER BY created_at DESC LIMIT 10;
```

---

## Alert Format

Admin Telegram alert (from SYSTEM__ERROR_HANDLER__V1):
```
⚠️ AIOS Error Alert

Workflow: {workflow_name}
Failed Node: {last_node}
Error: {error_message}
Time: {time}
```

---

## Phase 4 Monitoring Plan

Add `SYSTEM__HEALTH_CHECK__V1` (scheduled every 5 minutes):
- Check PostgreSQL connectivity
- Check n8n is responding
- Check last successful Telegram message < 1 hour ago
- Alert if any check fails

---

## Key Metrics to Watch

| Metric | Warning | Critical |
|--------|---------|---------|
| Error rate | >5% of executions | >20% |
| Pending approvals not resolved | >10 | >50 |
| Rate limit blocks | >20/hour | >100/hour |
| DB response time | >500ms | >2000ms |
| OpenRouter 429 errors | >2/hour | >10/hour |

---

**Future Extension:** Phase 4 — deploy Grafana + Prometheus for visual dashboards. Connect n8n execution logs to time-series metrics.
