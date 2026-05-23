#!/usr/bin/env python3
"""
AIOS Phase 3 — Creative Engine
8 research/scripting/story workflows + pipeline + P3 handler + supervisor update.
"""

import json, uuid, sqlite3, subprocess

DB_PATH          = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID       = "0YzGnVQ4VzNb3gOx"
SUPERVISOR_ID    = "13473953-52ed-419e-93c0-78c0c91b0818"
ERROR_HANDLER_ID = "99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2"
TG_TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API           = f"https://api.telegram.org/bot{TG_TOKEN}"
OR_URL           = "https://openrouter.ai/api/v1/chat/completions"
OR_KEY           = os.environ["OPENROUTER_API_KEY"]
PG_CRED_ID       = "a20cebf1b1c648"
ADMIN_CHAT_ID    = 1241444951
RATE_LIMIT       = 10

_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")

def _wid(k):
    return str(uuid.uuid5(_NS, f"aios/p3/{k}"))

WF = {
    "viral":    _wid("viral_engine"),
    "audpsych": _wid("audience_psych"),
    "hookopt":  _wid("hook_optimizer"),
    "scriptgen":_wid("script_generator"),
    "tamil":    _wid("tamil_story"),
    "caption":  _wid("caption_generator"),
    "scorer":   _wid("content_scorer"),
    "resctx":   _wid("research_context"),
    "pipeline": _wid("script_pipeline"),
    "p3hdlr":   _wid("p3_handler"),
}

# ── SQL Migration ──────────────────────────────────────────────────
MIGRATION_SQL = """
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS topic VARCHAR(300);
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS niche VARCHAR(100);

CREATE TABLE IF NOT EXISTS hook_library (
    id          SERIAL PRIMARY KEY,
    topic       VARCHAR(300),
    niche       VARCHAR(100),
    hook_text   TEXT NOT NULL,
    hook_type   VARCHAR(50) DEFAULT 'attention',
    score       INTEGER DEFAULT 0,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audience_patterns (
    id            SERIAL PRIMARY KEY,
    niche         VARCHAR(100) NOT NULL,
    demographics  VARCHAR(100) DEFAULT 'general',
    analysis_data JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS emotional_scores (
    id                SERIAL PRIMARY KEY,
    content_ref       VARCHAR(100),
    content_type      VARCHAR(50) DEFAULT 'script',
    emotion_breakdown JSONB NOT NULL DEFAULT '{}',
    overall_score     INTEGER DEFAULT 0,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS successful_captions (
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

CREATE TABLE IF NOT EXISTS story_progression (
    id               SERIAL PRIMARY KEY,
    episode_number   INTEGER NOT NULL,
    theme            VARCHAR(200),
    story_content    TEXT NOT NULL,
    characters_used  JSONB NOT NULL DEFAULT '[]',
    continuity_notes TEXT,
    next_seeds       JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pacing_feedback (
    id            SERIAL PRIMARY KEY,
    content_type  VARCHAR(50),
    feedback_type VARCHAR(50) DEFAULT 'general',
    feedback_text TEXT,
    telegram_id   BIGINT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS replay_scores (
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

CREATE INDEX IF NOT EXISTS idx_hook_lib_niche   ON hook_library(niche, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aud_pat_niche    ON audience_patterns(niche, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_story_ep         ON story_progression(episode_number DESC);
CREATE INDEX IF NOT EXISTS idx_captions_niche   ON successful_captions(niche, platform, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_replay_niche     ON replay_scores(niche, overall_score DESC);
"""


def run_migration():
    r = subprocess.run(
        ["docker", "exec", "-i", "aios-postgres", "psql", "-U", "aios_user", "-d", "aios_db"],
        input=MIGRATION_SQL.encode(), capture_output=True, timeout=30
    )
    if r.returncode == 0:
        print("  OK SQL migration")
    else:
        print(f"  ERR migration: {r.stderr.decode()[:300]}")
    return r.returncode == 0


# ── n8n DB helpers ─────────────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_PATH)


def upsert_workflow(wf_id, name, nodes, connections, settings=None,
                    active=True, webhook_path=None, webhook_method="POST",
                    webhook_node_name=None):
    db = get_db()
    cur = db.cursor()
    version_id   = str(uuid.uuid4())
    nodes_str    = json.dumps(nodes)
    conn_str     = json.dumps(connections)
    settings_str = json.dumps(settings or {"executionOrder": "v1"})

    cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
    for (old_id,) in cur.fetchall():
        for tbl, col in [("webhook_entity","workflowId"),
                         ("shared_workflow","workflowId"),
                         ("workflow_history","workflowId")]:
            cur.execute(f"DELETE FROM {tbl} WHERE {col}=?", (old_id,))
        cur.execute("DELETE FROM workflow_entity WHERE id=?", (old_id,))

    for tbl, col in [("webhook_entity","workflowId"),
                     ("shared_workflow","workflowId"),
                     ("workflow_history","workflowId")]:
        cur.execute(f"DELETE FROM {tbl} WHERE {col}=?", (wf_id,))
    cur.execute("DELETE FROM workflow_entity WHERE id=?", (wf_id,))

    cur.execute(
        """INSERT INTO workflow_entity
           (id, name, active, nodes, connections, settings, staticData, pinData,
            versionId, activeVersionId, triggerCount)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 0)""",
        (wf_id, name, 1 if active else 0, nodes_str, conn_str,
         settings_str, version_id, version_id)
    )
    cur.execute(
        """INSERT INTO workflow_history
           (versionId, workflowId, authors, nodes, connections, name, autosaved)
           VALUES (?, ?, 'AIOS Phase 3', ?, ?, ?, 0)""",
        (version_id, wf_id, nodes_str, conn_str, name)
    )
    cur.execute(
        "INSERT OR IGNORE INTO shared_workflow (workflowId, projectId, role) "
        "VALUES (?, ?, 'workflow:owner')",
        (wf_id, PROJECT_ID)
    )
    if webhook_path:
        cur.execute(
            """INSERT OR REPLACE INTO webhook_entity
               (workflowId, webhookPath, method, node, webhookId, pathLength)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (wf_id, webhook_path, webhook_method,
             webhook_node_name or "Webhook", webhook_path)
        )
    db.commit()
    db.close()
    print(f"  OK {name}")


def node(nid, name, ntype, version, pos, params,
         credentials=None, webhook_id=None, continue_on_fail=False):
    n = {"id": nid, "name": name, "type": ntype,
         "typeVersion": version, "position": pos, "parameters": params}
    if credentials:
        n["credentials"] = credentials
    if webhook_id:
        n["webhookId"] = webhook_id
    if continue_on_fail:
        n["continueOnFail"] = True
    return n


def pg_node(nid, name, pos, query, continue_on_fail=False):
    return node(nid, name, "n8n-nodes-base.postgres", 2, pos,
                {"operation": "executeQuery", "query": query, "options": {}},
                credentials={"postgres": {"id": PG_CRED_ID, "name": "AIOS PostgreSQL"}},
                continue_on_fail=continue_on_fail)


def http_post(nid, name, pos, url, json_body, never_error=False):
    opts = {"response": {"response": {"neverError": True}}} if never_error else {}
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST", "url": url,
        "sendBody": True, "specifyBody": "json",
        "jsonBody": json_body,
        "options": opts
    })


def or_node(nid, name, pos, body_expr, model="anthropic/claude-3.5-haiku"):
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST", "url": OR_URL,
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Authorization", "value": f"Bearer {OR_KEY}"},
            {"name": "Content-Type",  "value": "application/json"},
            {"name": "HTTP-Referer",  "value": "https://n8n.srv1654276.hstgr.cloud"},
            {"name": "X-Title",       "value": "AIOS"}
        ]},
        "sendBody": True, "specifyBody": "json",
        "jsonBody": body_expr,
        "options": {"response": {"response": {"neverError": True}}}
    })


def if_eq(nid, name, pos, left_expr, right_val, op_type="string"):
    return node(nid, name, "n8n-nodes-base.if", 2, pos, {
        "conditions": {
            "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "id": "cond-01",
                "leftValue":  left_expr,
                "rightValue": right_val,
                "operator": {"type": op_type, "operation": "equals"}
            }],
            "combinator": "and"
        }
    })


def if_bool(nid, name, pos, left_expr):
    return node(nid, name, "n8n-nodes-base.if", 2, pos, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
            "conditions": [{
                "id": "cond-01",
                "leftValue":  left_expr,
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "equals"}
            }],
            "combinator": "and"
        }
    })


def exec_wf(nid, name, pos, wf_id):
    return node(nid, name, "n8n-nodes-base.executeWorkflow", 1.2, pos, {
        "source": "database",
        "workflowId": {"__rl": True, "value": wf_id, "mode": "id"},
        "options": {"waitForSubWorkflow": True}
    })


def trigger_node(nid):
    return node(nid, "Execute Workflow Trigger",
                "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {})


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 1: RESEARCH__VIRAL_ENGINE__V1
# ══════════════════════════════════════════════════════════════════
def build_viral_engine():
    wf_id = WF["viral"]

    build_prompt_js = (
        "const d = $input.item.json;\n"
        "const niche = (d.niche || 'general').slice(0, 100);\n"
        "const trendType = d.trend_type || 'general';\n"
        "const sysPrompt = 'You are a viral content research expert for Instagram Reels. "
        "Respond ONLY in valid JSON, no markdown, no explanation outside JSON.';\n"
        "const userPrompt = `Analyze viral trends for niche: \"${niche}\" (type: ${trendType}).\\n"
        "Return exactly this JSON:\\n"
        "{\\n"
        "  \"niche\": \"${niche}\",\\n"
        "  \"trends\": [{\"topic\":\"...\",\"hook\":\"...\",\"angle\":\"...\",\"why_viral\":\"...\"}],\\n"
        "  \"best_hook\": \"...\",\\n"
        "  \"content_angles\": [\"angle1\",\"angle2\",\"angle3\"],\\n"
        "  \"trending_keywords\": [\"kw1\",\"kw2\",\"kw3\"]\\n"
        "}\\nProvide 5 trends. Focus on scroll-stopping hooks.`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 1400, temperature: 0.7\n"
        "};\n"
        "return [{ json: { payload, niche, telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Research Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { niche: ctx.niche, trends: [], best_hook: '', content_angles: [], trending_keywords: [] };\n"
        "let parseOk = false;\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (!m) throw new Error('no json');\n"
        "  const p = JSON.parse(m[0]);\n"
        "  result.niche = p.niche || ctx.niche;\n"
        "  result.trends = Array.isArray(p.trends) ? p.trends.slice(0,5) : [];\n"
        "  result.best_hook = p.best_hook || '';\n"
        "  result.content_angles = Array.isArray(p.content_angles) ? p.content_angles : [];\n"
        "  result.trending_keywords = Array.isArray(p.trending_keywords) ? p.trending_keywords : [];\n"
        "  parseOk = true;\n"
        "} catch(e) { result.best_hook = content.slice(0,200); }\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const trendsJson = safe(JSON.stringify(result));\n"
        "const hookSafe = safe(result.best_hook);\n"
        "const nicheSafe = safe(result.niche);\n"
        "const metaSafe = safe(JSON.stringify({parse_ok:parseOk,count:result.trends.length}));\n"
        "return [{ json: { ...result, trendsJson, hookSafe, nicheSafe, metaSafe,\n"
        "  telegram_id: ctx.telegram_id, parseOk } }];"
    )

    nodes = [
        trigger_node("ve-trig-01"),

        node("ve-code-01", "Build Research Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_prompt_js}),

        or_node("ve-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("ve-code-02", "Parse Research",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("ve-pg-01", "Save Research",
                [1120, 300],
                "INSERT INTO viral_research (niche, trend_summary, retention_score, metadata) "
                "VALUES ('{{ $json.nicheSafe }}', '{{ $json.hookSafe }}', 75, "
                "'{{ $json.metaSafe }}'::jsonb) RETURNING id"),

        pg_node("ve-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('RESEARCH__VIRAL_ENGINE__V1', {{ $json.telegram_id }}, "
                "'research_complete', 'success', '{{ $json.metaSafe }}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Research Prompt", "type": "main", "index": 0}]]},
        "Build Research Prompt":   {"main": [[{"node": "Call OpenRouter",        "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Research",         "type": "main", "index": 0}]]},
        "Parse Research":          {"main": [[{"node": "Save Research",          "type": "main", "index": 0}]]},
        "Save Research":           {"main": [[{"node": "Log Execution",          "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "RESEARCH__VIRAL_ENGINE__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 2: RESEARCH__AUDIENCE_PSYCHOLOGY__V1
# ══════════════════════════════════════════════════════════════════
def build_audience_psych():
    wf_id = WF["audpsych"]

    build_js = (
        "const d = $input.item.json;\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "const demo = d.demographics || 'general';\n"
        "const sysPrompt = 'You are an audience psychology expert. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Deep psychology analysis for \"${niche}\" audience (${demo}).\\n"
        "Return exactly:\\n"
        "{\\n"
        "  \"pain_points\": [\"p1\",\"p2\",\"p3\"],\\n"
        "  \"desires\": [\"d1\",\"d2\",\"d3\"],\\n"
        "  \"emotional_triggers\": [\"t1\",\"t2\",\"t3\"],\\n"
        "  \"language_patterns\": [\"l1\",\"l2\",\"l3\"],\\n"
        "  \"objections\": [\"o1\",\"o2\"],\\n"
        "  \"content_formats\": [\"f1\",\"f2\"]\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 1000, temperature: 0.5\n"
        "};\n"
        "return [{ json: { payload, niche, demo, telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Psych Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { pain_points:[], desires:[], emotional_triggers:[], "
        "language_patterns:[], objections:[], content_formats:[] };\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.pain_points = p.pain_points || [];\n"
        "    result.desires = p.desires || [];\n"
        "    result.emotional_triggers = p.emotional_triggers || [];\n"
        "    result.language_patterns = p.language_patterns || [];\n"
        "    result.objections = p.objections || [];\n"
        "    result.content_formats = p.content_formats || [];\n"
        "  }\n"
        "} catch(e) {}\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const dataSafe = safe(JSON.stringify(result));\n"
        "const nicheSafe = safe(ctx.niche);\n"
        "const demoSafe = safe(ctx.demo);\n"
        "return [{ json: { ...result, dataSafe, nicheSafe, demoSafe, telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("ap-trig-01"),

        node("ap-code-01", "Build Psych Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_js}),

        or_node("ap-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("ap-code-02", "Parse Psych Data",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("ap-pg-01", "Save Audience Pattern",
                [1120, 300],
                "INSERT INTO audience_patterns (niche, demographics, analysis_data) "
                "VALUES ('{{ $json.nicheSafe }}', '{{ $json.demoSafe }}', "
                "'{{ $json.dataSafe }}'::jsonb) RETURNING id"),

        pg_node("ap-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('RESEARCH__AUDIENCE_PSYCHOLOGY__V1', {{ $json.telegram_id }}, "
                "'psych_complete', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Psych Prompt", "type": "main", "index": 0}]]},
        "Build Psych Prompt":      {"main": [[{"node": "Call OpenRouter",     "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Psych Data",    "type": "main", "index": 0}]]},
        "Parse Psych Data":        {"main": [[{"node": "Save Audience Pattern","type": "main", "index": 0}]]},
        "Save Audience Pattern":   {"main": [[{"node": "Log Execution",       "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "RESEARCH__AUDIENCE_PSYCHOLOGY__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 3: SCRIPT__HOOK_OPTIMIZER__V1
# ══════════════════════════════════════════════════════════════════
def build_hook_optimizer():
    wf_id = WF["hookopt"]

    build_js = (
        "const d = $input.item.json;\n"
        "const topic = (d.topic || 'general').slice(0,200);\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "const audience = d.target_audience || 'general';\n"
        "const count = Math.min(d.hook_count || 5, 8);\n"
        "const sysPrompt = 'You are a viral hook writing expert. Create scroll-stopping hooks. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Create ${count} powerful hooks for: \"${topic}\"\\n"
        "Niche: ${niche} | Audience: ${audience}\\n"
        "Return exactly:\\n"
        "{\\n"
        "  \"hooks\": [{\"text\":\"...\",\"type\":\"question|shock|story|stat\",\"score\":85,\"why\":\"...\"}],\\n"
        "  \"best_hook\": \"...\",\\n"
        "  \"rationale\": \"...\"\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 1000, temperature: 0.8\n"
        "};\n"
        "return [{ json: { payload, topic, niche, telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Hook Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { hooks: [], best_hook: '', rationale: '' };\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.hooks = Array.isArray(p.hooks) ? p.hooks.slice(0,8) : [];\n"
        "    result.best_hook = p.best_hook || '';\n"
        "    result.rationale = p.rationale || '';\n"
        "  }\n"
        "} catch(e) { result.best_hook = content.slice(0,200); }\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const hookSafe = safe(result.best_hook);\n"
        "const topicSafe = safe(ctx.topic);\n"
        "const nicheSafe = safe(ctx.niche);\n"
        "const metaSafe = safe(JSON.stringify({hooks:result.hooks,rationale:result.rationale}));\n"
        "return [{ json: { ...result, hookSafe, topicSafe, nicheSafe, metaSafe,\n"
        "  telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("ho-trig-01"),

        node("ho-code-01", "Build Hook Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_js}),

        or_node("ho-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("ho-code-02", "Parse Hooks",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("ho-pg-01", "Save Best Hook",
                [1120, 300],
                "INSERT INTO hook_library (topic, niche, hook_text, hook_type, score, metadata) "
                "VALUES ('{{ $json.topicSafe }}', '{{ $json.nicheSafe }}', "
                "'{{ $json.hookSafe }}', 'optimized', 90, "
                "'{{ $json.metaSafe }}'::jsonb) RETURNING id"),

        pg_node("ho-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('SCRIPT__HOOK_OPTIMIZER__V1', {{ $json.telegram_id }}, "
                "'hooks_generated', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Hook Prompt", "type": "main", "index": 0}]]},
        "Build Hook Prompt":       {"main": [[{"node": "Call OpenRouter",    "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Hooks",        "type": "main", "index": 0}]]},
        "Parse Hooks":             {"main": [[{"node": "Save Best Hook",     "type": "main", "index": 0}]]},
        "Save Best Hook":          {"main": [[{"node": "Log Execution",      "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "SCRIPT__HOOK_OPTIMIZER__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 4: SCRIPT__GENERATOR__V1
# ══════════════════════════════════════════════════════════════════
def build_script_generator():
    wf_id = WF["scriptgen"]

    build_js = (
        "const d = $input.item.json;\n"
        "const topic = (d.topic || 'untitled').slice(0,200);\n"
        "const hook = (d.hook || '').slice(0,300);\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "const dur = Math.min(d.duration_seconds || 60, 180);\n"
        "const style = d.style || 'educational';\n"
        "const wpm = 130;\n"
        "const targetWords = Math.round(dur * wpm / 60);\n"
        "const sysPrompt = 'You are an expert short-form video scriptwriter. "
        "Write punchy, retention-optimized scripts. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Write a ${dur}s ${style} script (~${targetWords} words).\\n"
        "Topic: ${topic}\\nHook: ${hook || '(create a strong hook)'}\\nNiche: ${niche}\\n"
        "Return exactly:\\n"
        "{\\n"
        "  \"script\": \"full script text...\",\\n"
        "  \"sections\": [{\"name\":\"Hook\",\"content\":\"...\",\"duration_s\":3}],\\n"
        "  \"word_count\": ${targetWords},\\n"
        "  \"estimated_duration\": ${dur},\\n"
        "  \"cta\": \"call to action text\"\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-sonnet',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 2000, temperature: 0.7\n"
        "};\n"
        "return [{ json: { payload, topic, hook, niche, dur, telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Script Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { script:'', sections:[], word_count:0, estimated_duration:ctx.dur, cta:'' };\n"
        "let parseOk = false;\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.script = p.script || content.slice(0,3000);\n"
        "    result.sections = Array.isArray(p.sections) ? p.sections : [];\n"
        "    result.word_count = p.word_count || result.script.split(' ').length;\n"
        "    result.estimated_duration = p.estimated_duration || ctx.dur;\n"
        "    result.cta = p.cta || '';\n"
        "    parseOk = true;\n"
        "  }\n"
        "} catch(e) { result.script = content.slice(0,3000); }\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const scriptSafe = safe(result.script.slice(0,5000));\n"
        "const topicSafe = safe(ctx.topic);\n"
        "const nicheSafe = safe(ctx.niche);\n"
        "const metaSafe = safe(JSON.stringify({word_count:result.word_count,"
        "duration:result.estimated_duration,sections_count:result.sections.length,parse_ok:parseOk}));\n"
        "return [{ json: { ...result, scriptSafe, topicSafe, nicheSafe, metaSafe,\n"
        "  telegram_id: ctx.telegram_id, parseOk } }];"
    )

    nodes = [
        trigger_node("sg-trig-01"),

        node("sg-code-01", "Build Script Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_js}),

        or_node("sg-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("sg-code-02", "Parse Script",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("sg-pg-01", "Save Script",
                [1120, 300],
                "INSERT INTO scripts (script_text, script_type, approval_status, topic, niche, metadata) "
                "VALUES ('{{ $json.scriptSafe }}', 'reel', 'pending', "
                "'{{ $json.topicSafe }}', '{{ $json.nicheSafe }}', "
                "'{{ $json.metaSafe }}'::jsonb) RETURNING id"),

        pg_node("sg-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('SCRIPT__GENERATOR__V1', {{ $json.telegram_id }}, "
                "'script_generated', 'success', '{{ $json.metaSafe }}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Script Prompt", "type": "main", "index": 0}]]},
        "Build Script Prompt":     {"main": [[{"node": "Call OpenRouter",      "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Script",         "type": "main", "index": 0}]]},
        "Parse Script":            {"main": [[{"node": "Save Script",          "type": "main", "index": 0}]]},
        "Save Script":             {"main": [[{"node": "Log Execution",        "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "SCRIPT__GENERATOR__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 5: MEMORY__TAMIL_STORY_ENGINE__V1
# ══════════════════════════════════════════════════════════════════
def build_tamil_story():
    wf_id = WF["tamil"]

    load_js = (
        "const d = $input.item.json;\n"
        "const ep = Math.max(1, parseInt(d.episode_number) || 1);\n"
        "const theme = (d.theme || 'family drama').slice(0,100);\n"
        "return [{ json: { ep, theme, story_type: d.story_type || 'drama',\n"
        "  telegram_id: d.telegram_id || 0 } }];"
    )

    build_js = (
        "const d = $input.item.json;\n"
        "const items = $input.all();\n"
        "const storyRows = items.filter(i => i.json.episode_number !== undefined);\n"
        "const charRows  = items.filter(i => i.json.character_name !== undefined);\n"
        "const ctx = $('Prep Story Input').item.json;\n"
        "let prevSummary = 'No previous episodes.';\n"
        "let charContext = 'No established characters.';\n"
        "if (storyRows.length > 0) {\n"
        "  prevSummary = storyRows.map(r => `Ep ${r.json.episode_number}: ${r.json.story_summary}`).join('\\n');\n"
        "}\n"
        "if (charRows.length > 0) {\n"
        "  charContext = charRows.map(r => `${r.json.character_name}: ${r.json.personality}`).join('\\n');\n"
        "}\n"
        "const sysPrompt = 'You are a Tamil episodic storyteller. "
        "Write emotionally engaging, culturally authentic content. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Write Episode ${ctx.ep} of this Tamil ${ctx.story_type} story.\\n"
        "Theme: ${ctx.theme}\\n"
        "Previous episodes:\\n${prevSummary}\\n"
        "Characters:\\n${charContext}\\n"
        "Return exactly:\\n"
        "{\\n"
        "  \"story_content\": \"...\",\\n"
        "  \"episode_summary\": \"...\",\\n"
        "  \"characters_used\": [\"name1\",\"name2\"],\\n"
        "  \"continuity_notes\": \"...\",\\n"
        "  \"next_episode_seeds\": [\"seed1\",\"seed2\"]\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-sonnet',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 2000, temperature: 0.8\n"
        "};\n"
        "return [{ json: { payload, ep: ctx.ep, theme: ctx.theme,\n"
        "  story_type: ctx.story_type, telegram_id: ctx.telegram_id } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Story Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { story_content:'', episode_summary:'', characters_used:[],\n"
        "  continuity_notes:'', next_episode_seeds:[] };\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.story_content = p.story_content || content.slice(0,3000);\n"
        "    result.episode_summary = p.episode_summary || result.story_content.slice(0,300);\n"
        "    result.characters_used = Array.isArray(p.characters_used) ? p.characters_used : [];\n"
        "    result.continuity_notes = p.continuity_notes || '';\n"
        "    result.next_episode_seeds = Array.isArray(p.next_episode_seeds) ? p.next_episode_seeds : [];\n"
        "  }\n"
        "} catch(e) { result.story_content = content.slice(0,3000); }\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const storySafe = safe(result.story_content.slice(0,5000));\n"
        "const sumSafe = safe(result.episode_summary.slice(0,500));\n"
        "const contSafe = safe(result.continuity_notes.slice(0,1000));\n"
        "const charsSafe = safe(JSON.stringify(result.characters_used));\n"
        "const seedsSafe = safe(JSON.stringify(result.next_episode_seeds));\n"
        "const themeSafe = safe(ctx.theme);\n"
        "return [{ json: { ...result, storySafe, sumSafe, contSafe, charsSafe, seedsSafe,\n"
        "  themeSafe, ep: ctx.ep, telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("ts-trig-01"),

        node("ts-code-01", "Prep Story Input",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": load_js}),

        pg_node("ts-pg-01", "Load Story Memory",
                [680, 220],
                "SELECT episode_number, story_summary, continuity_notes "
                "FROM tamil_story_memory ORDER BY episode_number DESC LIMIT 3"),

        pg_node("ts-pg-02", "Load Characters",
                [680, 380],
                "SELECT character_name, personality, continuity_notes "
                "FROM character_memory ORDER BY created_at DESC LIMIT 5"),

        node("ts-code-02", "Build Story Prompt",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": build_js}),

        or_node("ts-http-01", "Call OpenRouter",
                [1120, 300], '={{ JSON.stringify($json.payload) }}'),

        node("ts-code-03", "Parse Story",
             "n8n-nodes-base.code", 2, [1340, 300], {"jsCode": parse_js}),

        pg_node("ts-pg-03", "Save Story Progression",
                [1560, 300],
                "INSERT INTO story_progression "
                "(episode_number, theme, story_content, characters_used, continuity_notes, next_seeds) "
                "VALUES ({{ $json.ep }}, '{{ $json.themeSafe }}', '{{ $json.storySafe }}', "
                "'{{ $json.charsSafe }}'::jsonb, '{{ $json.contSafe }}', "
                "'{{ $json.seedsSafe }}'::jsonb);\n"
                "INSERT INTO tamil_story_memory (episode_number, story_summary, continuity_notes, metadata) "
                "VALUES ({{ $json.ep }}, '{{ $json.sumSafe }}', '{{ $json.contSafe }}', "
                "'{\"source\":\"p3\"}'::jsonb) "
                "ON CONFLICT DO NOTHING"),

        pg_node("ts-pg-04", "Log Execution",
                [1780, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('MEMORY__TAMIL_STORY_ENGINE__V1', {{ $json.telegram_id }}, "
                "'story_generated', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prep Story Input", "type": "main", "index": 0}]]},
        "Prep Story Input": {"main": [[
            {"node": "Load Story Memory", "type": "main", "index": 0},
            {"node": "Load Characters",   "type": "main", "index": 0},
        ]]},
        "Load Story Memory": {"main": [[{"node": "Build Story Prompt", "type": "main", "index": 0}]]},
        "Load Characters":   {"main": [[{"node": "Build Story Prompt", "type": "main", "index": 0}]]},
        "Build Story Prompt": {"main": [[{"node": "Call OpenRouter",       "type": "main", "index": 0}]]},
        "Call OpenRouter":    {"main": [[{"node": "Parse Story",           "type": "main", "index": 0}]]},
        "Parse Story":        {"main": [[{"node": "Save Story Progression","type": "main", "index": 0}]]},
        "Save Story Progression": {"main": [[{"node": "Log Execution",    "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "MEMORY__TAMIL_STORY_ENGINE__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 6: CAPTION__GENERATOR__V1
# ══════════════════════════════════════════════════════════════════
def build_caption_generator():
    wf_id = WF["caption"]

    build_js = (
        "const d = $input.item.json;\n"
        "const topic = (d.topic || 'general').slice(0,200);\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "const platform = d.platform || 'instagram';\n"
        "const tone = d.tone || 'motivational';\n"
        "const hook = (d.hook || '').slice(0,200);\n"
        "const sysPrompt = 'You are a social media caption expert. Write high-engagement captions. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Write 3 captions for \"${topic}\" on ${platform}.\\n"
        "Niche: ${niche} | Tone: ${tone}${hook ? '\\nHook: ' + hook : ''}\\n"
        "Return exactly:\\n"
        "{\\n"
        "  \"captions\": [{\"text\":\"...\",\"char_count\":150,\"engagement_score\":85}],\\n"
        "  \"hashtags\": [\"#tag1\",\"#tag2\",\"#tag3\",\"#tag4\",\"#tag5\"],\\n"
        "  \"best_caption\": \"...\"\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 1000, temperature: 0.75\n"
        "};\n"
        "return [{ json: { payload, topic, niche, platform, telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Caption Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { captions: [], hashtags: [], best_caption: '' };\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.captions = Array.isArray(p.captions) ? p.captions.slice(0,5) : [];\n"
        "    result.hashtags = Array.isArray(p.hashtags) ? p.hashtags.slice(0,20) : [];\n"
        "    result.best_caption = p.best_caption || (result.captions[0] && result.captions[0].text) || content.slice(0,300);\n"
        "  }\n"
        "} catch(e) { result.best_caption = content.slice(0,300); }\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const bestSafe = safe(result.best_caption.slice(0,2000));\n"
        "const hashSafe = safe(JSON.stringify(result.hashtags));\n"
        "const topicSafe = safe(ctx.topic);\n"
        "const nicheSafe = safe(ctx.niche);\n"
        "const platformSafe = safe(ctx.platform);\n"
        "const charCount = result.best_caption.length;\n"
        "return [{ json: { ...result, bestSafe, hashSafe, topicSafe, nicheSafe,\n"
        "  platformSafe, charCount, telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("cg-trig-01"),

        node("cg-code-01", "Build Caption Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_js}),

        or_node("cg-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("cg-code-02", "Parse Captions",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("cg-pg-01", "Save Caption",
                [1120, 300],
                "INSERT INTO successful_captions "
                "(topic, niche, platform, caption_text, hashtags, char_count) "
                "VALUES ('{{ $json.topicSafe }}', '{{ $json.nicheSafe }}', "
                "'{{ $json.platformSafe }}', '{{ $json.bestSafe }}', "
                "'{{ $json.hashSafe }}'::jsonb, {{ $json.charCount }}) RETURNING id"),

        pg_node("cg-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('CAPTION__GENERATOR__V1', {{ $json.telegram_id }}, "
                "'caption_generated', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Caption Prompt", "type": "main", "index": 0}]]},
        "Build Caption Prompt":    {"main": [[{"node": "Call OpenRouter",       "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Captions",        "type": "main", "index": 0}]]},
        "Parse Captions":          {"main": [[{"node": "Save Caption",          "type": "main", "index": 0}]]},
        "Save Caption":            {"main": [[{"node": "Log Execution",         "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "CAPTION__GENERATOR__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 7: AI__CONTENT_SCORER__V1
# ══════════════════════════════════════════════════════════════════
def build_content_scorer():
    wf_id = WF["scorer"]

    build_js = (
        "const d = $input.item.json;\n"
        "const content = (d.content || '').slice(0, 3000);\n"
        "const ctype = d.content_type || 'script';\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "const sysPrompt = 'You are a content quality analyst for viral short-form video. "
        "Score content objectively. Respond ONLY in valid JSON.';\n"
        "const userPrompt = `Score this ${ctype} for the \"${niche}\" niche:\\n\"${content}\"\\n"
        "Score 0-100 for each. Return exactly:\\n"
        "{\\n"
        "  \"overall_score\": 85,\\n"
        "  \"hook_score\": 90,\\n"
        "  \"retention_score\": 80,\\n"
        "  \"viral_score\": 75,\\n"
        "  \"clarity_score\": 88,\\n"
        "  \"suggestions\": [\"improve X\",\"add Y\"],\\n"
        "  \"verdict\": \"publish_ready|needs_work|reject\"\\n"
        "}`;\n"
        "const payload = {\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  messages: [{role:'system',content:sysPrompt},{role:'user',content:userPrompt}],\n"
        "  max_tokens: 600, temperature: 0.3\n"
        "};\n"
        "return [{ json: { payload, content: content.slice(0,300), ctype, niche,\n"
        "  telegram_id: d.telegram_id || 0 } }];"
    )

    parse_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Build Scorer Prompt').item.json;\n"
        "const content = d?.choices?.[0]?.message?.content || '';\n"
        "let result = { overall_score:50, hook_score:50, retention_score:50,\n"
        "  viral_score:50, clarity_score:50, suggestions:[], verdict:'needs_work' };\n"
        "try {\n"
        "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (m) { const p = JSON.parse(m[0]);\n"
        "    result.overall_score = p.overall_score || 50;\n"
        "    result.hook_score = p.hook_score || 50;\n"
        "    result.retention_score = p.retention_score || 50;\n"
        "    result.viral_score = p.viral_score || 50;\n"
        "    result.clarity_score = p.clarity_score || 50;\n"
        "    result.suggestions = Array.isArray(p.suggestions) ? p.suggestions.slice(0,5) : [];\n"
        "    result.verdict = p.verdict || 'needs_work';\n"
        "  }\n"
        "} catch(e) {}\n"
        "const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "const prevSafe = safe(ctx.content.slice(0,200));\n"
        "const nicheSafe = safe(ctx.niche);\n"
        "const ctypeSafe = safe(ctx.ctype);\n"
        "const suggSafe = safe(JSON.stringify(result.suggestions));\n"
        "return [{ json: { ...result, prevSafe, nicheSafe, ctypeSafe, suggSafe,\n"
        "  telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("sc-trig-01"),

        node("sc-code-01", "Build Scorer Prompt",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": build_js}),

        or_node("sc-http-01", "Call OpenRouter",
                [680, 300], '={{ JSON.stringify($json.payload) }}'),

        node("sc-code-02", "Parse Score",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": parse_js}),

        pg_node("sc-pg-01", "Save Score",
                [1120, 300],
                "INSERT INTO replay_scores "
                "(content_type, niche, content_preview, overall_score, hook_score, "
                "retention_score, viral_score, clarity_score, suggestions) "
                "VALUES ('{{ $json.ctypeSafe }}', '{{ $json.nicheSafe }}', "
                "'{{ $json.prevSafe }}', {{ $json.overall_score }}, {{ $json.hook_score }}, "
                "{{ $json.retention_score }}, {{ $json.viral_score }}, {{ $json.clarity_score }}, "
                "'{{ $json.suggSafe }}'::jsonb) RETURNING id"),

        pg_node("sc-pg-02", "Log Execution",
                [1340, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('AI__CONTENT_SCORER__V1', {{ $json.telegram_id }}, "
                "'score_complete', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Build Scorer Prompt", "type": "main", "index": 0}]]},
        "Build Scorer Prompt":     {"main": [[{"node": "Call OpenRouter",      "type": "main", "index": 0}]]},
        "Call OpenRouter":         {"main": [[{"node": "Parse Score",          "type": "main", "index": 0}]]},
        "Parse Score":             {"main": [[{"node": "Save Score",           "type": "main", "index": 0}]]},
        "Save Score":              {"main": [[{"node": "Log Execution",        "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "AI__CONTENT_SCORER__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 8: MEMORY__RESEARCH_CONTEXT__V1
# ══════════════════════════════════════════════════════════════════
def build_research_context():
    wf_id = WF["resctx"]

    route_js = (
        "const d = $input.item.json;\n"
        "const action = (d.action || 'load').toLowerCase();\n"
        "const niche = (d.niche || 'general').slice(0,100);\n"
        "let query;\n"
        "if (action === 'save') {\n"
        "  const safe = s => (s+'').replace(/'/g,\"''\");\n"
        "  const dataSafe = safe(JSON.stringify(d.context_data || {}));\n"
        "  const nicheSafe = safe(niche);\n"
        "  query = `INSERT INTO viral_research (niche, trend_summary, retention_score, metadata) "
        "VALUES ('${nicheSafe}', 'context_save', 0, '${dataSafe}'::jsonb) RETURNING id`;\n"
        "} else {\n"
        "  const nicheSafe = niche.replace(/'/g,\"''\");\n"
        "  query = `SELECT niche, trend_summary, metadata, created_at FROM viral_research "
        "WHERE niche ILIKE '%${nicheSafe}%' ORDER BY created_at DESC LIMIT 5`;\n"
        "}\n"
        "return [{ json: { action, niche, query, telegram_id: d.telegram_id || 0 } }];"
    )

    fmt_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Route Action').item.json;\n"
        "const items = Array.isArray(d) ? d : [d];\n"
        "if (ctx.action === 'save') {\n"
        "  return [{ json: { action: 'save', niche: ctx.niche, saved: true,\n"
        "    id: d.id || null, telegram_id: ctx.telegram_id } }];\n"
        "}\n"
        "const research = items.map(i => ({\n"
        "  niche: i.json?.niche || i.niche,\n"
        "  summary: i.json?.trend_summary || i.trend_summary || '',\n"
        "  metadata: i.json?.metadata || i.metadata || {},\n"
        "  created_at: i.json?.created_at || i.created_at\n"
        "})).filter(r => r.summary);\n"
        "return [{ json: { action: 'load', niche: ctx.niche,\n"
        "  research_data: research,\n"
        "  context_summary: `Found ${research.length} research entries for ${ctx.niche}`,\n"
        "  telegram_id: ctx.telegram_id } }];"
    )

    nodes = [
        trigger_node("rc-trig-01"),

        node("rc-code-01", "Route Action",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": route_js}),

        pg_node("rc-pg-01", "Execute Query",
                [680, 300], "{{ $json.query }}"),

        node("rc-code-02", "Format Output",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": fmt_js}),

        pg_node("rc-pg-02", "Log Execution",
                [1120, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('MEMORY__RESEARCH_CONTEXT__V1', {{ $json.telegram_id }}, "
                "'context_access', 'success', '{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Route Action",   "type": "main", "index": 0}]]},
        "Route Action":            {"main": [[{"node": "Execute Query",   "type": "main", "index": 0}]]},
        "Execute Query":           {"main": [[{"node": "Format Output",   "type": "main", "index": 0}]]},
        "Format Output":           {"main": [[{"node": "Log Execution",   "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "MEMORY__RESEARCH_CONTEXT__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 9: CREATIVE__SCRIPT_PIPELINE__V1
# Chains: Hook Optimizer → Script Generator → Content Scorer
# ══════════════════════════════════════════════════════════════════
def build_script_pipeline():
    wf_id = WF["pipeline"]

    prep_hook_js = (
        "const d = $input.item.json;\n"
        "return [{ json: {\n"
        "  topic: d.topic || 'content',\n"
        "  niche: d.niche || 'general',\n"
        "  target_audience: d.target_audience || 'general',\n"
        "  hook_count: 5,\n"
        "  telegram_id: d.telegram_id || 0,\n"
        "  _orig: d\n"
        "} }];"
    )

    prep_script_js = (
        "const hookResult = $input.item.json;\n"
        "const orig = $('Prep Hook Input').item.json._orig || {};\n"
        "return [{ json: {\n"
        "  topic: orig.topic || 'content',\n"
        "  hook: hookResult.best_hook || (hookResult.hooks && hookResult.hooks[0] && hookResult.hooks[0].text) || '',\n"
        "  niche: orig.niche || 'general',\n"
        "  duration_seconds: orig.duration_seconds || 60,\n"
        "  style: orig.style || 'educational',\n"
        "  telegram_id: orig.telegram_id || 0,\n"
        "  _hooks: hookResult.hooks || [],\n"
        "  _best_hook: hookResult.best_hook || ''\n"
        "} }];"
    )

    prep_score_js = (
        "const scriptResult = $input.item.json;\n"
        "const orig = $('Prep Hook Input').item.json._orig || {};\n"
        "return [{ json: {\n"
        "  content: scriptResult.script || '',\n"
        "  content_type: 'script',\n"
        "  niche: orig.niche || 'general',\n"
        "  telegram_id: orig.telegram_id || 0,\n"
        "  _script: scriptResult.script || '',\n"
        "  _script_id: scriptResult.id || null,\n"
        "  _sections: scriptResult.sections || [],\n"
        "  _word_count: scriptResult.word_count || 0\n"
        "} }];"
    )

    compile_js = (
        "const scoreResult = $input.item.json;\n"
        "const hookNode = $('Run Hook Optimizer').item.json;\n"
        "const scriptNode = $('Run Script Generator').item.json;\n"
        "return [{ json: {\n"
        "  topic: $('Prep Hook Input').item.json._orig?.topic || 'content',\n"
        "  best_hook: scoreResult._best_hook || hookNode.best_hook || '',\n"
        "  all_hooks: hookNode.hooks || [],\n"
        "  script: scoreResult._script || '',\n"
        "  sections: scoreResult._sections || [],\n"
        "  word_count: scoreResult._word_count || 0,\n"
        "  script_id: scoreResult._script_id,\n"
        "  overall_score: scoreResult.overall_score || 0,\n"
        "  hook_score: scoreResult.hook_score || 0,\n"
        "  retention_score: scoreResult.retention_score || 0,\n"
        "  viral_score: scoreResult.viral_score || 0,\n"
        "  suggestions: scoreResult.suggestions || [],\n"
        "  verdict: scoreResult.verdict || 'needs_work',\n"
        "  pipeline: 'CREATIVE__SCRIPT_PIPELINE__V1'\n"
        "} }];"
    )

    nodes = [
        trigger_node("pl-trig-01"),

        node("pl-code-01", "Prep Hook Input",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": prep_hook_js}),

        exec_wf("pl-exec-01", "Run Hook Optimizer",
                [680, 300], WF["hookopt"]),

        node("pl-code-02", "Prep Script Input",
             "n8n-nodes-base.code", 2, [900, 300], {"jsCode": prep_script_js}),

        exec_wf("pl-exec-02", "Run Script Generator",
                [1120, 300], WF["scriptgen"]),

        node("pl-code-03", "Prep Score Input",
             "n8n-nodes-base.code", 2, [1340, 300], {"jsCode": prep_score_js}),

        exec_wf("pl-exec-03", "Run Content Scorer",
                [1560, 300], WF["scorer"]),

        node("pl-code-04", "Compile Pipeline Result",
             "n8n-nodes-base.code", 2, [1780, 300], {"jsCode": compile_js}),

        pg_node("pl-pg-01", "Log Pipeline",
                [2000, 300],
                "INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('CREATIVE__SCRIPT_PIPELINE__V1', 0, 'pipeline_complete', 'success', "
                "'{\"ok\":true}'::jsonb)",
                continue_on_fail=True),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prep Hook Input",          "type": "main", "index": 0}]]},
        "Prep Hook Input":          {"main": [[{"node": "Run Hook Optimizer",        "type": "main", "index": 0}]]},
        "Run Hook Optimizer":       {"main": [[{"node": "Prep Script Input",         "type": "main", "index": 0}]]},
        "Prep Script Input":        {"main": [[{"node": "Run Script Generator",      "type": "main", "index": 0}]]},
        "Run Script Generator":     {"main": [[{"node": "Prep Score Input",          "type": "main", "index": 0}]]},
        "Prep Score Input":         {"main": [[{"node": "Run Content Scorer",        "type": "main", "index": 0}]]},
        "Run Content Scorer":       {"main": [[{"node": "Compile Pipeline Result",   "type": "main", "index": 0}]]},
        "Compile Pipeline Result":  {"main": [[{"node": "Log Pipeline",              "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "CREATIVE__SCRIPT_PIPELINE__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 10: PHASE3__TELEGRAM_HANDLER__V1
# Routes P3 commands to the right subworkflow, formats Telegram reply.
# ══════════════════════════════════════════════════════════════════
def build_p3_handler():
    wf_id = WF["p3hdlr"]

    prep_research_js = (
        "const d = $input.item.json;\n"
        "return [{ json: {\n"
        "  niche: d.p3Topic || 'general content',\n"
        "  trend_type: 'general',\n"
        "  telegram_id: d.from_id || d.chat_id || 0\n"
        "} }];"
    )

    fmt_research_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Prep Research').item.json;\n"
        "const trends = d.trends || [];\n"
        "const bestHook = d.best_hook || 'No hook generated';\n"
        "const angles = d.content_angles || [];\n"
        "let txt = `\\ud83d\\udcca *Viral Research: ${d.niche || ctx.niche}*\\n\\n`;\n"
        "if (trends.length > 0) {\n"
        "  txt += '*Top Trends:*\\n';\n"
        "  trends.slice(0,4).forEach((t,i) => {\n"
        "    txt += `${i+1}. *${(t.topic||'').slice(0,60)}*\\n   Hook: _${(t.hook||'').slice(0,80)}_\\n`;\n"
        "  });\n"
        "}\n"
        "txt += `\\n\\ud83c\\udfaf *Best Hook:*\\n_${bestHook.slice(0,200)}_`;\n"
        "if (angles.length > 0) txt += `\\n\\n*Angles:* ${angles.slice(0,3).join(' | ')}`;\n"
        "const replyMarkup = { inline_keyboard: [[\n"
        "  { text: '\\ud83d\\udcdd Generate Script', callback_data: 'p3_script' },\n"
        "  { text: '\\ud83d\\udd04 New Research',    callback_data: 'p3_research' }\n"
        "]] };\n"
        "return [{ json: { reply: txt.slice(0,4000), reply_markup: replyMarkup,\n"
        "  command: 'research', topic: ctx.niche } }];"
    )

    prep_script_js = (
        "const d = $input.item.json;\n"
        "return [{ json: {\n"
        "  topic: d.p3Topic || 'viral content',\n"
        "  niche: 'general',\n"
        "  target_audience: 'general',\n"
        "  duration_seconds: 60,\n"
        "  telegram_id: d.from_id || d.chat_id || 0\n"
        "} }];"
    )

    fmt_script_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Prep Script').item.json;\n"
        "const script = d.script || '';\n"
        "const hook = d.best_hook || (d.all_hooks && d.all_hooks[0] && d.all_hooks[0].text) || '';\n"
        "const score = d.overall_score || 0;\n"
        "const verdict = d.verdict || 'needs_work';\n"
        "const wc = d.word_count || 0;\n"
        "let txt = `\\ud83d\\udcdd *Script Ready: ${ctx.topic || 'Content'}*\\n\\n`;\n"
        "if (hook) txt += `\\ud83c\\udfaf *Hook:* _${hook.slice(0,150)}_\\n\\n`;\n"
        "txt += `*Script Preview:*\\n${script.slice(0,600)}`;\n"
        "if (script.length > 600) txt += '...';\n"
        "txt += `\\n\\n\\ud83d\\udcca Score: ${score}/100 | Words: ${wc} | ${verdict.replace('_',' ')}`;\n"
        "const replyMarkup = { inline_keyboard: [[\n"
        "  { text: '\\u2705 Approve',      callback_data: 'approve' },\n"
        "  { text: '\\u274c Reject',       callback_data: 'reject' },\n"
        "  { text: '\\ud83d\\udd04 Regen', callback_data: 'regenerate' }\n"
        "]] };\n"
        "return [{ json: { reply: txt.slice(0,4000), reply_markup: replyMarkup,\n"
        "  command: 'script', topic: ctx.topic } }];"
    )

    prep_story_js = (
        "const d = $input.item.json;\n"
        "return [{ json: {\n"
        "  episode_number: 1,\n"
        "  theme: d.p3Topic || 'family drama',\n"
        "  story_type: 'drama',\n"
        "  telegram_id: d.from_id || d.chat_id || 0\n"
        "} }];"
    )

    fmt_story_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Prep Story').item.json;\n"
        "const story = d.story_content || '';\n"
        "const ep = d.ep || ctx.episode_number || 1;\n"
        "const seeds = d.next_episode_seeds || [];\n"
        "let txt = `\\ud83d\\udcda *Tamil Story \\u2014 Episode ${ep}*\\n\\n`;\n"
        "txt += story.slice(0,800);\n"
        "if (story.length > 800) txt += '...';\n"
        "if (seeds.length > 0) txt += `\\n\\n*Next:* _${seeds[0].slice(0,100)}_`;\n"
        "const replyMarkup = { inline_keyboard: [[\n"
        "  { text: '\\u27a1 Continue Story', callback_data: 'p3_story_continue' },\n"
        "  { text: '\\ud83c\\udf00 New Direction', callback_data: 'p3_story_new' }\n"
        "]] };\n"
        "return [{ json: { reply: txt.slice(0,4000), reply_markup: replyMarkup,\n"
        "  command: 'story', topic: ctx.theme } }];"
    )

    prep_caption_js = (
        "const d = $input.item.json;\n"
        "return [{ json: {\n"
        "  topic: d.p3Topic || 'content',\n"
        "  niche: 'general',\n"
        "  platform: 'instagram',\n"
        "  tone: 'motivational',\n"
        "  telegram_id: d.from_id || d.chat_id || 0\n"
        "} }];"
    )

    fmt_caption_js = (
        "const d = $input.item.json;\n"
        "const ctx = $('Prep Caption').item.json;\n"
        "const best = d.best_caption || '';\n"
        "const tags = d.hashtags || [];\n"
        "const captions = d.captions || [];\n"
        "let txt = `\\u270d *Captions for: ${ctx.topic}*\\n\\n`;\n"
        "txt += `*Best Caption:*\\n${best.slice(0,400)}`;\n"
        "if (tags.length > 0) txt += `\\n\\n*Hashtags:* ${tags.slice(0,8).join(' ')}`;\n"
        "if (captions.length > 1) txt += `\\n\\n_${captions.length} variations generated._`;\n"
        "const replyMarkup = { inline_keyboard: [[\n"
        "  { text: '\\u2705 Use This',       callback_data: 'approve' },\n"
        "  { text: '\\ud83d\\udd04 Generate More', callback_data: 'p3_caption_more' }\n"
        "]] };\n"
        "return [{ json: { reply: txt.slice(0,4000), reply_markup: replyMarkup,\n"
        "  command: 'caption', topic: ctx.topic } }];"
    )

    nodes = [
        trigger_node("ph-trig-01"),

        if_eq("ph-if-01", "Is Research?",  [460, 300],
              "={{ $json.p3Command }}", "research"),

        if_eq("ph-if-02", "Is Script?",    [680, 480],
              "={{ $json.p3Command }}", "script"),

        if_eq("ph-if-03", "Is Story?",     [900, 480],
              "={{ $json.p3Command }}", "story"),

        node("ph-code-01", "Prep Research",
             "n8n-nodes-base.code", 2, [680, 180], {"jsCode": prep_research_js}),

        exec_wf("ph-exec-01", "Run Viral Engine",
                [900, 180], WF["viral"]),

        node("ph-code-02", "Format Research Reply",
             "n8n-nodes-base.code", 2, [1120, 180], {"jsCode": fmt_research_js}),

        node("ph-code-03", "Prep Script",
             "n8n-nodes-base.code", 2, [1100, 300], {"jsCode": prep_script_js}),

        exec_wf("ph-exec-02", "Run Script Pipeline",
                [1320, 300], WF["pipeline"]),

        node("ph-code-04", "Format Script Reply",
             "n8n-nodes-base.code", 2, [1540, 300], {"jsCode": fmt_script_js}),

        node("ph-code-05", "Prep Story",
             "n8n-nodes-base.code", 2, [1100, 480], {"jsCode": prep_story_js}),

        exec_wf("ph-exec-03", "Run Tamil Story",
                [1320, 480], WF["tamil"]),

        node("ph-code-06", "Format Story Reply",
             "n8n-nodes-base.code", 2, [1540, 480], {"jsCode": fmt_story_js}),

        node("ph-code-07", "Prep Caption",
             "n8n-nodes-base.code", 2, [1100, 660], {"jsCode": prep_caption_js}),

        exec_wf("ph-exec-04", "Run Caption Generator",
                [1320, 660], WF["caption"]),

        node("ph-code-08", "Format Caption Reply",
             "n8n-nodes-base.code", 2, [1540, 660], {"jsCode": fmt_caption_js}),
    ]

    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Is Research?",      "type": "main", "index": 0}]]},
        "Is Research?": {"main": [
            [{"node": "Prep Research",   "type": "main", "index": 0}],
            [{"node": "Is Script?",      "type": "main", "index": 0}],
        ]},
        "Is Script?": {"main": [
            [{"node": "Prep Script",     "type": "main", "index": 0}],
            [{"node": "Is Story?",       "type": "main", "index": 0}],
        ]},
        "Is Story?": {"main": [
            [{"node": "Prep Story",      "type": "main", "index": 0}],
            [{"node": "Prep Caption",    "type": "main", "index": 0}],
        ]},
        "Prep Research":           {"main": [[{"node": "Run Viral Engine",        "type": "main", "index": 0}]]},
        "Run Viral Engine":        {"main": [[{"node": "Format Research Reply",   "type": "main", "index": 0}]]},
        "Prep Script":             {"main": [[{"node": "Run Script Pipeline",     "type": "main", "index": 0}]]},
        "Run Script Pipeline":     {"main": [[{"node": "Format Script Reply",     "type": "main", "index": 0}]]},
        "Prep Story":              {"main": [[{"node": "Run Tamil Story",         "type": "main", "index": 0}]]},
        "Run Tamil Story":         {"main": [[{"node": "Format Story Reply",      "type": "main", "index": 0}]]},
        "Prep Caption":            {"main": [[{"node": "Run Caption Generator",   "type": "main", "index": 0}]]},
        "Run Caption Generator":   {"main": [[{"node": "Format Caption Reply",    "type": "main", "index": 0}]]},
    }
    upsert_workflow(wf_id, "PHASE3__TELEGRAM_HANDLER__V1", nodes, connections)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 11: TELEGRAM__SUPERVISOR__V2 (Phase 3 update, same ID)
# Adds P3 command detection and routing to PHASE3__TELEGRAM_HANDLER__V1
# ══════════════════════════════════════════════════════════════════
def build_updated_supervisor():
    wf_id  = SUPERVISOR_ID
    err_id = ERROR_HANDLER_ID

    system_prompt = (
        "You are AIOS Supervisor, an AI creative director for Instagram Reels and Tamil episodic content.\\n\\n"
        "RESPOND ONLY IN THIS EXACT JSON FORMAT (no markdown, no explanation):\\n"
        "{\\n"
        '  \\"intent\\": \\"[general_chat|topic_suggestion|research_request|generate_script|approve|reject|regenerate|story_continuation|analytics_request|status_check|help]\\",\\n'
        '  \\"reply\\": \\"[your Telegram message — Markdown OK, max 300 chars]\\",\\n'
        '  \\"show_buttons\\": false,\\n'
        '  \\"buttons\\": [],\\n'
        '  \\"session_update\\": {},\\n'
        '  \\"confidence\\": 0.9\\n'
        "}\\n\\n"
        "Rules:\\n"
        "- For generate_script: set show_buttons=true with Approve/Reject/Regenerate\\n"
        "- For /start|/help|/status: respond with system info\\n"
        "- Tamil story: always acknowledge continuity\\n"
        "- Keep responses professional and action-oriented"
    )

    prep_ai_context_js = (
        "const extract = $('Extract Message').item.json;\n"
        "const sess    = $input.item.json;\n"
        "let sessionData = {};\n"
        "try { sessionData = JSON.parse(sess.session_data || '{}'); } catch(e){}\n\n"
        "const P3_CMDS = { '/research':'research', '/script':'script',\n"
        "  '/story':'story', '/caption':'caption', '/generate':'script' };\n"
        "const txt = extract.text || '';\n"
        "let isP3Command = false, p3Command = '', p3Topic = '';\n"
        "const cmdKey = Object.keys(P3_CMDS).find(c => txt.toLowerCase().startsWith(c.toLowerCase()));\n"
        "if (cmdKey) {\n"
        "  isP3Command = true;\n"
        "  p3Command = P3_CMDS[cmdKey];\n"
        "  p3Topic = txt.slice(cmdKey.length).trim();\n"
        "}\n\n"
        "const systemPrompt = `" + system_prompt + "`;\n\n"
        "const context = `User: ${extract.username}\\n"
        "Message #: ${sess.message_count}\\n"
        "Active workflow: ${sess.active_workflow || 'none'}\\n"
        "Session: ${JSON.stringify(sessionData).slice(0,200)}`;\n\n"
        "return [{ json: {\n"
        "  system_prompt: systemPrompt,\n"
        "  prompt: `${context}\\n\\nUser message: ${txt}`,\n"
        "  model: 'anthropic/claude-3.5-haiku',\n"
        "  max_tokens: 800,\n"
        "  temperature: 0.4,\n"
        "  chat_id:       extract.chatId,\n"
        "  from_id:       extract.fromId,\n"
        "  username:      extract.username,\n"
        "  user_id:       sess.user_id,\n"
        "  message_count: sess.message_count,\n"
        "  session_data:  sessionData,\n"
        "  text: txt,\n"
        "  isP3Command, p3Command, p3Topic\n"
        "} }];"
    )

    validate_parse_js = (
        "const aiResp = $input.item.json;\n"
        "const ctx    = $('Prepare AI Context').item.json;\n"
        "const content = aiResp?.choices?.[0]?.message?.content || '';\n\n"
        "const VALID_INTENTS = new Set([\n"
        "  'general_chat','topic_suggestion','research_request','generate_script',\n"
        "  'approve','reject','regenerate','story_continuation',\n"
        "  'analytics_request','status_check','help'\n"
        "]);\n\n"
        "let ai = { intent:'general_chat', reply:'', show_buttons:false,\n"
        "           buttons:[], session_update:{}, confidence:0.5 };\n"
        "let validationOk = false;\n"
        "let parseError   = null;\n\n"
        "try {\n"
        "  if (!content.trim()) throw new Error('Empty AI response');\n"
        "  const match = content.match(/\\{[\\s\\S]*\\}/);\n"
        "  if (!match) throw new Error('No JSON object in response');\n"
        "  const parsed = JSON.parse(match[0]);\n"
        "  if (typeof parsed.reply !== 'string' || parsed.reply.trim().length < 1)\n"
        "    throw new Error('reply field missing or empty');\n"
        "  ai.intent  = VALID_INTENTS.has(parsed.intent) ? parsed.intent : 'general_chat';\n"
        "  ai.reply   = parsed.reply.slice(0, 4096);\n"
        "  ai.show_buttons = Boolean(parsed.show_buttons);\n"
        "  ai.buttons = Array.isArray(parsed.buttons) ? parsed.buttons : [];\n"
        "  ai.session_update = (parsed.session_update && typeof parsed.session_update === 'object')\n"
        "    ? parsed.session_update : {};\n"
        "  ai.confidence = typeof parsed.confidence === 'number' ? parsed.confidence : 0.5;\n"
        "  validationOk = true;\n"
        "} catch(e) {\n"
        "  parseError = e.message;\n"
        "  if (content.trim().length > 0) {\n"
        "    ai.reply = content.replace(/```json?/g,'').replace(/```/g,'').trim().slice(0,400);\n"
        "  } else {\n"
        "    ai.reply = '\\ud83d\\udd04 Processing issue — please try again.';\n"
        "  }\n"
        "}\n\n"
        "let replyMarkup = null;\n"
        "if (ai.show_buttons && ai.buttons.length > 0) {\n"
        "  const valid = ai.buttons.filter(b => b && typeof b.text === 'string' && b.text.trim());\n"
        "  if (valid.length > 0) {\n"
        "    replyMarkup = { inline_keyboard: [valid.map(b => ({\n"
        "      text: b.text.trim().slice(0,64),\n"
        "      callback_data: (b.callback_data || b.text.toLowerCase().replace(/\\s+/g,'_')).slice(0,64)\n"
        "    }))] };\n"
        "  }\n"
        "}\n"
        "if (ai.intent === 'generate_script' && !replyMarkup) {\n"
        "  replyMarkup = { inline_keyboard: [[\n"
        "    { text: '\\u2705 Approve',    callback_data: 'approve' },\n"
        "    { text: '\\u274c Reject',     callback_data: 'reject' },\n"
        "    { text: '\\ud83d\\udd04 Regen', callback_data: 'regenerate' }\n"
        "  ]] };\n"
        "}\n\n"
        "return [{ json: {\n"
        "  chat_id:        ctx.chat_id,\n"
        "  user_id:        ctx.user_id,\n"
        "  session_data:   ctx.session_data,\n"
        "  message_count:  ctx.message_count,\n"
        "  reply:          ai.reply,\n"
        "  intent:         ai.intent,\n"
        "  reply_markup:   replyMarkup,\n"
        "  session_update: ai.session_update,\n"
        "  confidence:     ai.confidence,\n"
        "  validation_ok:  validationOk,\n"
        "  parse_error:    parseError,\n"
        "  has_buttons:    replyMarkup !== null\n"
        "} }];"
    )

    prepare_save_js = (
        "const d = $input.item.json;\n\n"
        "const newSession = {\n"
        "  ...(d.session_data || {}),\n"
        "  ...(d.session_update || {}),\n"
        "  last_intent: d.intent,\n"
        "  last_msg_at: new Date().toISOString()\n"
        "};\n"
        "const sessJson   = JSON.stringify(newSession).replace(/'/g, \"''\");\n"
        "const intentSafe = (d.intent || 'general_chat').replace(/'/g, \"''\");\n"
        "const metaJson   = JSON.stringify({\n"
        "  intent: d.intent,\n"
        "  confidence: d.confidence,\n"
        "  validation_ok: d.validation_ok,\n"
        "  has_buttons: d.has_buttons,\n"
        "  parse_error: d.parse_error || null\n"
        "}).replace(/'/g, \"''\");\n"
        "const preview = (d.reply || '').slice(0,200).replace(/'/g, \"''\");\n\n"
        "const pendingSQL = d.has_buttons\n"
        "  ? `INSERT INTO pending_approvals (user_id, telegram_id, chat_id, workflow_context, content_preview, status) VALUES (${d.user_id}, ${d.chat_id}, ${d.chat_id}, '${sessJson}'::jsonb, '${preview}', 'pending') ON CONFLICT DO NOTHING;`\n"
        "  : '';\n\n"
        "const saveSQL = `UPDATE sessions SET session_data = '${sessJson}'::jsonb, active_workflow = '${intentSafe}', updated_at = NOW() WHERE user_id = ${d.user_id}; ${pendingSQL}`;\n\n"
        "const logSQL = `INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) VALUES ('TELEGRAM__SUPERVISOR__V2', ${d.chat_id}, 'message_processed', '${d.validation_ok ? 'success' : 'fallback'}', '${metaJson}'::jsonb)`;\n\n"
        "return [{ json: { ...d, saveSQL, logSQL } }];"
    )

    prep_p3_save_js = (
        "const p3Result = $input.item.json;\n"
        "const ctx = $('Prepare AI Context').item.json;\n\n"
        "const reply = p3Result.reply || '\\u2753 Could not process. Please try again.';\n"
        "const replyMarkup = p3Result.reply_markup || null;\n"
        "const hasButtons = replyMarkup !== null;\n"
        "const p3Cmd = ctx.p3Command || 'p3';\n"
        "const p3Topic = (ctx.p3Topic || '').replace(/'/g, \"''\").slice(0,200);\n\n"
        "const newSession = {\n"
        "  ...(ctx.session_data || {}),\n"
        "  last_intent: 'p3_' + p3Cmd,\n"
        "  last_msg_at: new Date().toISOString()\n"
        "};\n"
        "const sessJson = JSON.stringify(newSession).replace(/'/g, \"''\");\n"
        "const intentSafe = ('p3_' + p3Cmd).replace(/'/g, \"''\");\n"
        "const metaJson = JSON.stringify({ p3_command: p3Cmd, p3_topic: ctx.p3Topic || '' }).replace(/'/g, \"''\");\n"
        "const preview = reply.slice(0,200).replace(/'/g, \"''\");\n\n"
        "const pendingSQL = hasButtons\n"
        "  ? `INSERT INTO pending_approvals (user_id, telegram_id, chat_id, workflow_context, content_preview, status) VALUES (${ctx.user_id}, ${ctx.chat_id}, ${ctx.chat_id}, '${sessJson}'::jsonb, '${preview}', 'pending') ON CONFLICT DO NOTHING;`\n"
        "  : '';\n\n"
        "const saveSQL = `UPDATE sessions SET session_data = '${sessJson}'::jsonb, active_workflow = '${intentSafe}', updated_at = NOW() WHERE user_id = ${ctx.user_id}; ${pendingSQL}`;\n\n"
        "const logSQL = `INSERT INTO execution_logs (workflow_name, telegram_id, event_type, status, metadata) VALUES ('TELEGRAM__SUPERVISOR__V2', ${ctx.chat_id}, 'p3_command', 'success', '${metaJson}'::jsonb)`;\n\n"
        "return [{ json: { chat_id: ctx.chat_id, user_id: ctx.user_id,\n"
        "  reply, reply_markup: replyMarkup, saveSQL, logSQL, has_buttons: hasButtons,\n"
        "  validation_ok: true } }];"
    )

    OR_KEY_LOCAL = OR_KEY
    nodes = [
        node("sv3-wh-01", "Telegram Webhook",
             "n8n-nodes-base.webhook", 2, [240, 300], {
             "httpMethod": "POST", "path": "aios-telegram-bot",
             "responseMode": "lastNode", "options": {}
             }, webhook_id="aios-telegram-bot"),

        node("sv3-code-01", "Extract Message",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": (
                 "const body = $input.item.json.body || $input.item.json;\n"
                 "const msg = body.message;\n"
                 "const cq  = body.callback_query;\n"
                 "let chatId, fromId, username, text, isCallback = false, callbackId;\n"
                 "if (cq) {\n"
                 "  isCallback = true;\n"
                 "  chatId     = cq.message.chat.id;\n"
                 "  fromId     = cq.from.id;\n"
                 "  username   = cq.from.username || cq.from.first_name || 'User';\n"
                 "  text       = cq.data || '';\n"
                 "  callbackId = cq.id;\n"
                 "} else if (msg) {\n"
                 "  chatId   = msg.chat.id;\n"
                 "  fromId   = msg.from.id;\n"
                 "  username = msg.from.username || msg.from.first_name || 'User';\n"
                 "  text     = msg.text || '';\n"
                 "} else {\n"
                 "  return [{ json: { skip: true, chatId: null } }];\n"
                 "}\n"
                 "return [{ json: { isCallback, callbackId, chatId, fromId, username, text } }];"
             )}),

        if_bool("sv3-if-01", "Route Branch", [680, 300],
                "={{ $json.isCallback }}"),

        node("sv3-code-02", "Handle Callback",
             "n8n-nodes-base.code", 2, [900, 120], {"jsCode": (
                 "const d = $input.item.json;\n"
                 "const [action, assetId] = d.text.split(':');\n"
                 "const labels = {\n"
                 "  approve:    '\\u2705 Approved! Moving to next stage.',\n"
                 "  reject:     '\\u274c Got it. What should I improve?',\n"
                 "  regenerate: '\\ud83d\\udd04 Regenerating...',\n"
                 "  darker:     '\\ud83c\\udf11 Making it darker.',\n"
                 "  emotional:  '\\ud83d\\udc94 Adding emotional depth.',\n"
                 "  faster:     '\\u26a1 Speeding up the pacing.'\n"
                 "};\n"
                 "return [{ json: {\n"
                 "  isCallback: true,\n"
                 "  chat_id:    d.chatId,\n"
                 "  callback_id: d.callbackId,\n"
                 "  reply:      labels[action] || `Recorded: ${action}`,\n"
                 "  action,\n"
                 "  asset_id:   assetId || null\n"
                 "} }];"
             )}),

        http_post("sv3-http-cb-01", "Answer Callback",
                  [1120, 120],
                  f"{TG_API}/answerCallbackQuery",
                  '={{ JSON.stringify({ callback_query_id: $json.callback_id, text: "\\u2713" }) }}'),

        pg_node("sv3-pg-cb-01", "Resolve Approval",
                [1340, 120],
                "UPDATE pending_approvals "
                "SET status = '{{ $json.action }}', updated_at = NOW() "
                "WHERE chat_id = {{ $json.chat_id }} AND status = 'pending';"
                "INSERT INTO execution_logs "
                "(workflow_name, telegram_id, event_type, status, metadata) "
                "VALUES ('TELEGRAM__SUPERVISOR__V2', {{ $json.chat_id }}, "
                "'callback', 'success', "
                "'{\"action\":\"{{ $json.action }}\"}'::jsonb)",
                continue_on_fail=True),

        http_post("sv3-http-cb-02", "Send Callback Reply",
                  [1560, 120],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $("Handle Callback").item.json.chat_id, '
                  'text: $("Handle Callback").item.json.reply, parse_mode: "Markdown" }) }}'),

        pg_node("sv3-pg-rl-01", "Check Rate Limit",
                [900, 480],
                f"INSERT INTO rate_limits (telegram_id, window_start, request_count) "
                f"VALUES ({{{{ $json.fromId }}}}, DATE_TRUNC('minute', NOW()), 1) "
                f"ON CONFLICT (telegram_id, window_start) "
                f"DO UPDATE SET request_count = rate_limits.request_count + 1 "
                f"RETURNING request_count, "
                f"request_count > {RATE_LIMIT} as is_blocked, "
                f"CEIL(EXTRACT(EPOCH FROM "
                f"(DATE_TRUNC('minute', NOW() + INTERVAL '1 minute') - NOW())))::INTEGER "
                f"as retry_after_secs"),

        if_bool("sv3-if-02", "Rate Gate", [1120, 480],
                "={{ $json.is_blocked }}"),

        http_post("sv3-http-rl-01", "Send Rate Warning",
                  [1340, 360],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $("Extract Message").item.json.chatId, '
                  'text: "\\u23f3 Too fast! Max ' + str(RATE_LIMIT) + ' messages/min. '
                  'Retry in " + $json.retry_after_secs + "s." }) }}',
                  never_error=True),

        pg_node("sv3-pg-sess-01", "Load Session",
                [1340, 600],
                "WITH u AS (\n"
                "  INSERT INTO users (telegram_id, username)\n"
                "  VALUES ({{ $('Extract Message').item.json.fromId }}, '{{ $('Extract Message').item.json.username }}')\n"
                "  ON CONFLICT (telegram_id) DO UPDATE\n"
                "  SET username = EXCLUDED.username\n"
                "  RETURNING id\n"
                ")\n"
                "INSERT INTO sessions (user_id, session_data, active_workflow, current_status, message_count)\n"
                "SELECT id, '{}', NULL, 'active', 0 FROM u\n"
                "ON CONFLICT (user_id) DO UPDATE\n"
                "SET message_count = sessions.message_count + 1,\n"
                "    updated_at = NOW()\n"
                "RETURNING user_id, session_data::text, active_workflow, message_count"),

        node("sv3-code-03", "Prepare AI Context",
             "n8n-nodes-base.code", 2, [1560, 600], {"jsCode": prep_ai_context_js}),

        if_bool("sv3-if-p3-01", "P3 Command Gate", [1780, 600],
                "={{ $json.isP3Command }}"),

        exec_wf("sv3-exec-p3-01", "Call P3 Handler",
                [2000, 750], WF["p3hdlr"]),

        node("sv3-code-p3-01", "Prep P3 Save Data",
             "n8n-nodes-base.code", 2, [2220, 750], {"jsCode": prep_p3_save_js}),

        node("sv3-http-or-01", "Call Supervisor AI",
             "n8n-nodes-base.httpRequest", 4.2, [2000, 480], {
             "method": "POST", "url": OR_URL,
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": f"Bearer {OR_KEY_LOCAL}"},
                 {"name": "Content-Type",  "value": "application/json"},
                 {"name": "HTTP-Referer",  "value": "https://n8n.srv1654276.hstgr.cloud"},
                 {"name": "X-Title",       "value": "AIOS Supervisor"}
             ]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ model: $json.model, messages: [{ role: "system", content: $json.system_prompt }, { role: "user", content: $json.prompt }], max_tokens: $json.max_tokens, temperature: $json.temperature }) }}',
             "options": {}}),

        node("sv3-code-04", "Validate & Parse",
             "n8n-nodes-base.code", 2, [2220, 480], {"jsCode": validate_parse_js}),

        node("sv3-code-05", "Prepare Save Data",
             "n8n-nodes-base.code", 2, [2440, 480], {"jsCode": prepare_save_js}),

        pg_node("sv3-pg-save-01", "Save Session",
                [2660, 560],
                "{{ $json.saveSQL }}"),

        pg_node("sv3-pg-log-01", "Log Execution",
                [2660, 680],
                "{{ $json.logSQL }}",
                continue_on_fail=True),

        http_post("sv3-http-tg-01", "Send Reply",
                  [2880, 560],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $json.chat_id, text: $json.reply, '
                  'parse_mode: "Markdown", reply_markup: $json.reply_markup || undefined }) }}'),

        node("sv3-resp-01", "Respond OK",
             "n8n-nodes-base.respondToWebhook", 1, [3100, 560], {
             "respondWith": "text", "responseBody": "OK"
             }),
    ]

    connections = {
        "Telegram Webhook": {"main": [[{"node": "Extract Message",  "type": "main", "index": 0}]]},
        "Extract Message":  {"main": [[{"node": "Route Branch",     "type": "main", "index": 0}]]},

        "Route Branch": {"main": [
            [{"node": "Handle Callback",  "type": "main", "index": 0}],
            [{"node": "Check Rate Limit", "type": "main", "index": 0}],
        ]},

        "Handle Callback":    {"main": [[{"node": "Answer Callback",    "type": "main", "index": 0}]]},
        "Answer Callback":    {"main": [[{"node": "Resolve Approval",   "type": "main", "index": 0}]]},
        "Resolve Approval":   {"main": [[{"node": "Send Callback Reply","type": "main", "index": 0}]]},

        "Check Rate Limit": {"main": [[{"node": "Rate Gate", "type": "main", "index": 0}]]},
        "Rate Gate": {"main": [
            [{"node": "Send Rate Warning", "type": "main", "index": 0}],
            [{"node": "Load Session",      "type": "main", "index": 0}],
        ]},

        "Load Session":       {"main": [[{"node": "Prepare AI Context", "type": "main", "index": 0}]]},
        "Prepare AI Context": {"main": [[{"node": "P3 Command Gate",    "type": "main", "index": 0}]]},

        "P3 Command Gate": {"main": [
            [{"node": "Call P3 Handler",   "type": "main", "index": 0}],
            [{"node": "Call Supervisor AI","type": "main", "index": 0}],
        ]},

        "Call P3 Handler":    {"main": [[{"node": "Prep P3 Save Data", "type": "main", "index": 0}]]},
        "Prep P3 Save Data":  {"main": [[
            {"node": "Save Session",  "type": "main", "index": 0},
            {"node": "Log Execution", "type": "main", "index": 0},
            {"node": "Send Reply",    "type": "main", "index": 0},
        ]]},

        "Call Supervisor AI": {"main": [[{"node": "Validate & Parse",  "type": "main", "index": 0}]]},
        "Validate & Parse":   {"main": [[{"node": "Prepare Save Data", "type": "main", "index": 0}]]},
        "Prepare Save Data":  {"main": [[
            {"node": "Save Session",  "type": "main", "index": 0},
            {"node": "Log Execution", "type": "main", "index": 0},
            {"node": "Send Reply",    "type": "main", "index": 0},
        ]]},

        "Send Reply": {"main": [[{"node": "Respond OK", "type": "main", "index": 0}]]},
    }

    settings = {
        "executionOrder": "v1",
        "errorWorkflow":   err_id,
    }

    upsert_workflow(wf_id, "TELEGRAM__SUPERVISOR__V2",
                    nodes, connections,
                    settings=settings, active=True,
                    webhook_path="aios-telegram-bot",
                    webhook_method="POST",
                    webhook_node_name="Telegram Webhook")
    return wf_id


# ══════════════════════════════════════════════════════════════════
# Registry update
# ══════════════════════════════════════════════════════════════════
REGISTRY_P3 = [
    ("RESEARCH__VIRAL_ENGINE__V1",       "v1", WF["viral"],    "Viral trend research via OpenRouter"),
    ("RESEARCH__AUDIENCE_PSYCHOLOGY__V1","v1", WF["audpsych"], "Audience psychology analysis"),
    ("SCRIPT__HOOK_OPTIMIZER__V1",       "v1", WF["hookopt"],  "Hook generation and optimization"),
    ("SCRIPT__GENERATOR__V1",            "v1", WF["scriptgen"],"Full script generation (claude-3.5-sonnet)"),
    ("MEMORY__TAMIL_STORY_ENGINE__V1",   "v1", WF["tamil"],    "Tamil episodic story with continuity"),
    ("CAPTION__GENERATOR__V1",           "v1", WF["caption"],  "Social media caption generation"),
    ("AI__CONTENT_SCORER__V1",           "v1", WF["scorer"],   "Content quality scoring 0-100"),
    ("MEMORY__RESEARCH_CONTEXT__V1",     "v1", WF["resctx"],   "Research context save/load"),
    ("CREATIVE__SCRIPT_PIPELINE__V1",    "v1", WF["pipeline"], "Hook+Script+Score chained pipeline"),
    ("PHASE3__TELEGRAM_HANDLER__V1",     "v1", WF["p3hdlr"],   "Routes P3 Telegram commands to subworkflows"),
    ("TELEGRAM__SUPERVISOR__V2",         "v2", SUPERVISOR_ID,  "Supervisor with P3 routing (Phase 3 update)"),
]


def populate_registry():
    rows = []
    for name, version, wf_id, desc in REGISTRY_P3:
        safe_desc = desc.replace("'", "''")
        n8n_id_sql = f"'{wf_id}'" if wf_id else "NULL"
        rows.append(
            f"('{name}', '{version}', {n8n_id_sql}, TRUE, '{safe_desc}', NOW(), NOW())"
        )
    sql = (
        "INSERT INTO workflow_versions "
        "(workflow_name, version, n8n_id, is_active, description, deployed_at, updated_at) VALUES\n"
        + ",\n".join(rows)
        + "\nON CONFLICT (workflow_name, version) DO UPDATE SET "
        "n8n_id = EXCLUDED.n8n_id, is_active = TRUE, "
        "description = EXCLUDED.description, updated_at = NOW();"
    )
    r = subprocess.run(
        ["docker", "exec", "-i", "aios-postgres", "psql", "-U", "aios_user", "-d", "aios_db"],
        input=sql.encode(), capture_output=True, timeout=10
    )
    if r.returncode == 0:
        print(f"  OK Registry: {len(REGISTRY_P3)} entries")
    else:
        print(f"  ERR Registry: {r.stderr.decode()[:200]}")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n=== AIOS Phase 3 — Creative Engine ===\n")
    print("Workflow IDs:")
    for k, v in WF.items():
        print(f"  {k}: {v}")
    print()

    print("[SQL] Running migration...")
    run_migration()

    print("\n[1] RESEARCH__VIRAL_ENGINE__V1")
    build_viral_engine()

    print("\n[2] RESEARCH__AUDIENCE_PSYCHOLOGY__V1")
    build_audience_psych()

    print("\n[3] SCRIPT__HOOK_OPTIMIZER__V1")
    build_hook_optimizer()

    print("\n[4] SCRIPT__GENERATOR__V1")
    build_script_generator()

    print("\n[5] MEMORY__TAMIL_STORY_ENGINE__V1")
    build_tamil_story()

    print("\n[6] CAPTION__GENERATOR__V1")
    build_caption_generator()

    print("\n[7] AI__CONTENT_SCORER__V1")
    build_content_scorer()

    print("\n[8] MEMORY__RESEARCH_CONTEXT__V1")
    build_research_context()

    print("\n[9] CREATIVE__SCRIPT_PIPELINE__V1")
    build_script_pipeline()

    print("\n[10] PHASE3__TELEGRAM_HANDLER__V1")
    build_p3_handler()

    print("\n[11] TELEGRAM__SUPERVISOR__V2 (Phase 3 update)")
    build_updated_supervisor()

    print("\n[Registry] Updating workflow_versions...")
    populate_registry()

    print("\n=== Phase 3 Complete ===")
    print("\nRestart n8n to activate new workflows:")
    print("  cd /docker/n8n && docker compose restart n8n")
    print("\nTest commands in Telegram:")
    print("  /research Tamil Nadu food traditions")
    print("  /script viral morning routine")
    print("  /story family drama episode 1")
    print("  /caption motivational fitness content")
