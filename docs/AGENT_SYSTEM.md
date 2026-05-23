# AIOS — Agent System

**Purpose:** Define how AI agents participate in AIOS development and operation.
**Owner:** AI Architecture Lead
**Update Rule:** Update when new agent roles are defined or agent rules change.

---

## Agent Types

### 1. Operational AI (Running in Production)
These are OpenRouter/Claude calls made during runtime by n8n workflows.

| Agent Role | Workflow | Model | Purpose |
|-----------|---------|-------|---------|
| Supervisor AI | TELEGRAM__SUPERVISOR__V2 | claude-3.5-haiku | Intent classification, conversation routing |
| Research Agent | RESEARCH__VIRAL_ENGINE__V1 | claude-3.5-haiku | Viral trend analysis |
| Psychology Agent | RESEARCH__AUDIENCE_PSYCHOLOGY__V1 | claude-3.5-haiku | Audience analysis |
| Hook Agent | SCRIPT__HOOK_OPTIMIZER__V1 | claude-3.5-haiku | Hook generation |
| Script Agent | SCRIPT__GENERATOR__V1 | claude-3.5-sonnet | Script writing |
| Story Agent | MEMORY__TAMIL_STORY_ENGINE__V1 | claude-3.5-sonnet | Tamil story generation |
| Caption Agent | CAPTION__GENERATOR__V1 | claude-3.5-haiku | Caption writing |
| Scorer Agent | AI__CONTENT_SCORER__V1 | claude-3.5-haiku | Quality scoring |

### 2. Development AI (Building the System)
AI agents that assist with building and modifying the AIOS platform (Claude Code, etc.)

See `agents/MASTER_AGENT_RULES.md` for rules governing development agents.

---

## Operational Agent Contracts

All operational agents communicate via structured JSON (enforced by system prompts):

```json
{
  "intent": "string — validated against VALID_INTENTS set",
  "reply": "string — max 4096 chars, Markdown OK",
  "show_buttons": false,
  "buttons": [],
  "session_update": {},
  "confidence": 0.9
}
```

**Validation:** If the AI returns malformed JSON, the system falls back to using the raw text content as the reply. A `parse_error` is logged but the user always gets a response.

---

## System Prompts

### Supervisor AI
```
You are AIOS Supervisor, an AI creative director for Instagram Reels and Tamil episodic content.
Role: understand user intent, route workflows, manage approvals, maintain context.
RESPOND ONLY IN EXACT JSON FORMAT.
Valid intents: general_chat|topic_suggestion|research_request|generate_script|
               approve|reject|regenerate|story_continuation|analytics_request|status_check|help
```

### Research Agent
```
You are a viral content research expert specializing in Instagram Reels.
Analyze trends, hooks, and viral patterns.
RESPOND ONLY IN VALID JSON, no markdown, no explanation outside JSON.
```

### Script Agent
```
You are an expert short-form video scriptwriter.
Write punchy, retention-optimized scripts.
RESPOND ONLY IN VALID JSON.
```

Full prompt library in `docs/PROMPT_LIBRARY.md`.

---

## Agent Memory Architecture

Agents have access to these memory systems:

| Memory Type | Storage | Scope |
|------------|---------|-------|
| Session memory | `sessions.session_data` JSONB | Per user, persistent |
| Story continuity | `tamil_story_memory` + `character_memory` | Global, accumulated |
| Research context | `viral_research` + `audience_patterns` | By niche, accumulated |
| Hook library | `hook_library` | By topic, accumulated |
| Script archive | `scripts` | All scripts, queryable |

---

## Agent Communication Rules

1. **JSON only:** All agents respond in structured JSON. No free-form text.
2. **Fail safe:** If agent returns invalid JSON, use fallback reply.
3. **No hallucination:** Agents use `content.match(/\{[\s\S]*\}/)` extraction to find the JSON block.
4. **Bounded replies:** All replies sliced to max 4096 chars before sending to Telegram.
5. **Temperature settings:** Haiku at 0.5–0.7, Sonnet at 0.7–0.8 for creative tasks; 0.3 for scoring.

---

**Future Extension:** Phase 6 — add a Feedback Agent that reads `replay_scores` and `analytics` to automatically tune prompt templates in the `prompts` table.
