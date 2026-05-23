# AIOS — Content Agent Rules

**Purpose:** Rules for AI agents working on creative content workflows: research, scripting, story, captions.
**Inherits From:** `agents/MASTER_AGENT_RULES.md`
**Owner:** Platform Lead

---

## Scope

This agent is responsible for:
- All Phase 3 creative subworkflows
- AI system prompts and user prompt templates
- OpenRouter model selection
- Content scoring and quality control
- Tamil story continuity and memory management

---

## Creative Workflow Architecture

### The Content Creation Pipeline
```
/research <topic>
    → RESEARCH__VIRAL_ENGINE__V1 (viral angles + trending hooks)
    → RESEARCH__AUDIENCE_PSYCHOLOGY__V1 (who watches + why)

/script <topic>
    → CREATIVE__SCRIPT_PIPELINE__V1
        ├── SCRIPT__HOOK_OPTIMIZER__V1 (3 hooks)
        ├── SCRIPT__GENERATOR__V1 (full script)
        └── AI__CONTENT_SCORER__V1 (0-100 score)

/story <prompt>
    → MEMORY__TAMIL_STORY_ENGINE__V1
        ├── Load story_progression from PostgreSQL
        ├── Generate next episode (with continuity)
        └── Save updated state back to PostgreSQL

/caption <topic>
    → CAPTION__GENERATOR__V1 (Instagram + YouTube + TikTok)
```

---

## AI Model Selection Rules

| Task Type | Model | Max Tokens | Temperature |
|-----------|-------|-----------|------------|
| Research (structured JSON) | claude-3.5-haiku | 1400 | 0.7 |
| Hook generation (creative) | claude-3.5-haiku | 1400 | 0.8 |
| Script generation (long-form) | claude-3.5-sonnet | 2000 | 0.75 |
| Tamil story (narrative) | claude-3.5-sonnet | 2000 | 0.8 |
| Caption generation | claude-3.5-haiku | 1400 | 0.7 |
| Scoring (analytical) | claude-3.5-haiku | 800 | 0.3 |

**Never use temperature > 0.9** — required by OpenRouter ToS and quality control.

---

## System Prompt Design Rules

1. **Always specify output format in the system prompt** — instruct AI to return JSON only
2. **Always include a fallback instruction** — "If you cannot complete the task, return `{\"error\": \"reason\"}`"
3. **Always specify language** — Tamil scripts must explicitly say "Write in Tamil script (not transliteration)"
4. **Max system prompt length**: 800 tokens (haiku) / 1200 tokens (sonnet)
5. **Never include user-provided text in system prompts** — user text goes in the user message only

### Standard System Prompt Template
```
You are an expert [role] for viral short-form video content.

Task: [specific task]

Output format (JSON only, no markdown wrapper):
{
  "field1": "description",
  "field2": ["array"],
  "field3": 0
}

Rules:
- [rule 1]
- [rule 2]

If unable to complete, return: {"error": "reason"}
```

---

## AI Response Parsing Rules

All AI responses must be parsed safely:

```javascript
const raw = $json.choices?.[0]?.message?.content || '{"error":"no response"}';
const jsonMatch = raw.match(/\{[\s\S]*\}/);
let parsed = {};
try {
    parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { error: "no_json_found" };
} catch(e) {
    parsed = { error: "parse_failed", raw: raw.slice(0, 200) };
}
```

**Rule: Never call `JSON.parse()` directly on raw AI output.** Extract JSON block with regex first.

---

## Tamil Story Memory Rules

The `story_progression` table is the source of truth for story state.

**Fields that must be preserved across episodes:**
- `story_arc` — the overall story arc name (never changes mid-arc)
- `episode` — always increments by 1
- `characters` — JSONB array of character names and last-known states
- `summary` — running summary of story so far (last 3 episodes max)

**Story prompt context must include:**
1. Current episode number
2. Characters and their last-known state
3. Running summary of previous episodes
4. Any unresolved plot threads

**Never generate episode N+2 before saving episode N+1** — story state is always sequential.

---

## Content Quality Rules

Minimum quality thresholds (enforced by AI__CONTENT_SCORER__V1):
- Virality score: ≥ 60 to pass
- Engagement score: ≥ 55 to pass
- Hook strength: ≥ 65 to pass

If a score is below threshold, the bot should suggest regenerating with a stronger angle — not silently serve low-quality content.

---

## Data Storage Rules

| Output | Table | Key Fields |
|--------|-------|-----------|
| Research results | viral_research | topic, research_data (JSONB) |
| Hooks | hook_library | topic, niche, hook_text, score |
| Scripts | scripts | user_id, content, topic, niche |
| Story episodes | story_progression | user_id, story_arc, episode, characters |
| Captions | successful_captions | topic, platform, caption_text, hashtags[] |
| Scores | replay_scores | content_id, virality_score, overall_score |

**All writes use `IF NOT EXISTS` or `ON CONFLICT DO UPDATE` patterns — never plain INSERT.**

---

## Forbidden in This Domain

- Generating violent, sexual, or politically sensitive content in prompts
- Storing raw message text from users in any table (privacy rule)
- Using `claude-3.5-sonnet` for tasks that don't require long-form generation (cost control)
- Skipping the content scorer for pipeline-generated scripts (quality control)
- Hardcoding story arc names — always derive from user input or last session state
