# AIOS — API Contracts

**Purpose:** Define input/output contracts for all subworkflows called via executeWorkflow.
**Owner:** Integration Lead
**Update Rule:** Update when any subworkflow's input/output schema changes. Treat as a breaking change.

---

## Subworkflow I/O Contracts

All Phase 3 subworkflows are triggered via `executeWorkflow` node. Input = current item JSON. Output = last node's JSON.

---

### RESEARCH__VIRAL_ENGINE__V1

**Input:**
```json
{
  "niche": "string (required) — e.g. 'Tamil Nadu food traditions'",
  "trend_type": "string (optional, default: 'general')",
  "telegram_id": "number (optional, default: 0)"
}
```

**Output (from Parse Research node):**
```json
{
  "niche": "Tamil Nadu food traditions",
  "trends": [
    {"topic": "...", "hook": "...", "angle": "...", "why_viral": "..."}
  ],
  "best_hook": "string",
  "content_angles": ["angle1", "angle2", "angle3"],
  "trending_keywords": ["kw1", "kw2"],
  "parseOk": true
}
```

---

### SCRIPT__HOOK_OPTIMIZER__V1

**Input:**
```json
{
  "topic": "string (required)",
  "niche": "string (optional, default: 'general')",
  "target_audience": "string (optional, default: 'general')",
  "hook_count": "number (optional, default: 5, max: 8)",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "hooks": [
    {"text": "...", "type": "question|shock|story|stat", "score": 85, "why": "..."}
  ],
  "best_hook": "string",
  "rationale": "string"
}
```

---

### SCRIPT__GENERATOR__V1

**Input:**
```json
{
  "topic": "string (required)",
  "hook": "string (optional — first hook used if not provided)",
  "niche": "string (optional, default: 'general')",
  "duration_seconds": "number (optional, default: 60, max: 180)",
  "style": "string (optional, default: 'educational')",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "script": "full script text",
  "sections": [
    {"name": "Hook", "content": "...", "duration_s": 3}
  ],
  "word_count": 130,
  "estimated_duration": 60,
  "cta": "call to action text",
  "script_id": 42
}
```

---

### MEMORY__TAMIL_STORY_ENGINE__V1

**Input:**
```json
{
  "episode_number": "number (required, min: 1)",
  "theme": "string (optional, default: 'family drama')",
  "story_type": "string (optional, default: 'drama')",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "story_content": "full story text",
  "episode_summary": "150 char summary",
  "characters_used": ["character1", "character2"],
  "continuity_notes": "notes for next episode",
  "next_episode_seeds": ["seed idea 1", "seed idea 2"]
}
```

---

### CAPTION__GENERATOR__V1

**Input:**
```json
{
  "topic": "string (required)",
  "niche": "string (optional, default: 'general')",
  "platform": "string (optional, default: 'instagram')",
  "tone": "string (optional, default: 'motivational')",
  "hook": "string (optional — context for caption)",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "captions": [
    {"text": "...", "char_count": 150, "engagement_score": 85}
  ],
  "hashtags": ["#tag1", "#tag2"],
  "best_caption": "string"
}
```

---

### AI__CONTENT_SCORER__V1

**Input:**
```json
{
  "content": "string (required — text to score, max 3000 chars)",
  "content_type": "string (optional, default: 'script')",
  "niche": "string (optional, default: 'general')",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "overall_score": 85,
  "hook_score": 90,
  "retention_score": 80,
  "viral_score": 75,
  "clarity_score": 88,
  "suggestions": ["improve pacing in middle", "stronger CTA"],
  "verdict": "publish_ready|needs_work|reject"
}
```

---

### CREATIVE__SCRIPT_PIPELINE__V1

**Input:**
```json
{
  "topic": "string (required)",
  "niche": "string (optional, default: 'general')",
  "target_audience": "string (optional, default: 'general')",
  "duration_seconds": "number (optional, default: 60)",
  "style": "string (optional, default: 'educational')",
  "telegram_id": "number (optional)"
}
```

**Output:**
```json
{
  "topic": "morning workout motivation",
  "best_hook": "string",
  "all_hooks": [...],
  "script": "full script text",
  "sections": [...],
  "word_count": 130,
  "script_id": 42,
  "overall_score": 85,
  "hook_score": 90,
  "retention_score": 80,
  "viral_score": 75,
  "suggestions": [...],
  "verdict": "publish_ready",
  "pipeline": "CREATIVE__SCRIPT_PIPELINE__V1"
}
```

---

### MEMORY__RESEARCH_CONTEXT__V1

**Input:**
```json
{
  "action": "load|save (required)",
  "niche": "string (required)",
  "context_data": "object (required for save action)",
  "telegram_id": "number (optional)"
}
```

**Output (load):**
```json
{
  "action": "load",
  "niche": "Tamil Nadu food",
  "research_data": [
    {"niche": "...", "summary": "...", "metadata": {}, "created_at": "..."}
  ],
  "context_summary": "Found 3 research entries for Tamil Nadu food"
}
```

**Output (save):**
```json
{
  "action": "save",
  "niche": "Tamil Nadu food",
  "saved": true,
  "id": 42
}
```

---

## External API Contracts

### OpenRouter (POST)
```
URL: https://openrouter.ai/api/v1/chat/completions
Headers:
  Authorization: Bearer <OR_KEY>
  Content-Type: application/json
  HTTP-Referer: https://n8n.srv1654276.hstgr.cloud
  X-Title: AIOS

Body:
{
  "model": "anthropic/claude-3.5-haiku",
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "max_tokens": 1400,
  "temperature": 0.7
}

Response:
{
  "choices": [{"message": {"content": "...JSON string..."}}]
}
```

### Telegram Bot API (POST)
```
sendMessage:    POST https://api.telegram.org/bot<TOKEN>/sendMessage
answerCallback: POST https://api.telegram.org/bot<TOKEN>/answerCallbackQuery
setWebhook:     GET  https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>
```

---

**Warnings:**
- All subworkflow inputs are passed as the current item JSON — callers must shape data correctly before the executeWorkflow node
- If a subworkflow's last node has `continueOnFail=true`, the output may be a PostgreSQL error row — callers should check output validity

**Future Extension:** Phase 4 will add `MEDIA__FFMPEG_RENDERER__V1` accepting `{script_id, video_style, resolution}` and returning `{video_path, duration, file_size}`.
