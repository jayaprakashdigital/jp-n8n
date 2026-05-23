#!/usr/bin/env python3
"""
AIOS Phase 2.5 — Hardening Layer
1. Execution Logging   — execution_logs table, logged on every message
2. Error Handler       — SYSTEM__ERROR_HANDLER__V1 (errorTrigger → DB → Telegram)
3. JSON Validation     — schema-checked parse in Validate & Parse node
4. Rate Limiting       — rate_limits table, 10 req/min per user
5. Approval Recovery   — SYSTEM__APPROVAL_RECOVERY__V1 (scheduled, re-sends pending)
6. Workflow Registry   — workflow_versions table, populated on deploy
"""

import json, uuid, sqlite3, os, base64, hashlib, subprocess
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

# ── Config ────────────────────────────────────────────────────────
DB_PATH      = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID   = "0YzGnVQ4VzNb3gOx"
SUPERVISOR_ID = "13473953-52ed-419e-93c0-78c0c91b0818"
ENCRYPTION_KEY = "vdlIIW6ZObRWezflrgbWoR6LD05/7o+4"
SALTED_PREFIX  = bytes.fromhex("53616c7465645f5f")
TG_TOKEN     = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API       = f"https://api.telegram.org/bot{TG_TOKEN}"
OR_URL       = "https://openrouter.ai/api/v1/chat/completions"
OR_KEY       = os.environ["OPENROUTER_API_KEY"]
PG_CRED_ID   = "a20cebf1b1c648"
ADMIN_CHAT_ID = 1241444951
RATE_LIMIT   = 10   # requests per minute

IDS = {
    "error_handler":     str(uuid.uuid4()),
    "approval_recovery": str(uuid.uuid4()),
    "supervisor":        SUPERVISOR_ID,
}

print("Phase 2.5 Workflow IDs:")
for k, v in IDS.items():
    print(f"  {k}: {v}")


# ── SQL Migration ─────────────────────────────────────────────────
MIGRATION_SQL = """
-- 1. Execution logging
CREATE TABLE IF NOT EXISTS execution_logs (
    id             SERIAL PRIMARY KEY,
    workflow_name  VARCHAR(100) NOT NULL,
    telegram_id    BIGINT,
    event_type     VARCHAR(50)  NOT NULL DEFAULT 'message_processed',
    status         VARCHAR(20)  NOT NULL DEFAULT 'success',
    duration_ms    INTEGER,
    error_message  TEXT,
    error_node     VARCHAR(100),
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Rate limiting (per-minute window, one row per user per minute)
CREATE TABLE IF NOT EXISTS rate_limits (
    telegram_id   BIGINT        NOT NULL,
    window_start  TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER       NOT NULL DEFAULT 1,
    PRIMARY KEY (telegram_id, window_start)
);

-- 3. Pending approvals (approval state recovery after restart)
CREATE TABLE IF NOT EXISTS pending_approvals (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id),
    telegram_id      BIGINT  NOT NULL,
    chat_id          BIGINT  NOT NULL,
    workflow_context JSONB   NOT NULL DEFAULT '{}',
    content_preview  TEXT,
    message_id       INTEGER,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    expires_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Workflow version registry
CREATE TABLE IF NOT EXISTS workflow_versions (
    id             SERIAL PRIMARY KEY,
    workflow_name  VARCHAR(100) NOT NULL,
    version        VARCHAR(20)  NOT NULL DEFAULT 'v1',
    n8n_id         VARCHAR(100),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    description    TEXT,
    deployed_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (workflow_name, version)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exec_logs_tg   ON execution_logs(telegram_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_logs_wf   ON execution_logs(workflow_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rl_window      ON rate_limits(telegram_id, window_start);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_approvals(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_wf_ver_active  ON workflow_versions(workflow_name, is_active);
"""


def run_migration():
    cmd = ["docker", "exec", "-i", "aios-postgres",
           "psql", "-U", "aios_user", "-d", "aios_db"]
    r = subprocess.run(cmd, input=MIGRATION_SQL.encode(), capture_output=True, timeout=30)
    if r.returncode == 0:
        print("  ✓ SQL migration complete")
    else:
        print(f"  ✗ Migration stderr: {r.stderr.decode()[:300]}")
    return r.returncode == 0


# ── n8n DB helpers ────────────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_PATH)


def upsert_workflow(wf_id, name, nodes, connections, settings=None,
                    active=True, webhook_path=None, webhook_method="POST",
                    webhook_node_name=None):
    db = get_db()
    cur = db.cursor()
    version_id  = str(uuid.uuid4())
    nodes_str   = json.dumps(nodes)
    conn_str    = json.dumps(connections)
    settings_str = json.dumps(settings or {"executionOrder": "v1"})

    # Delete by id AND by name (prevents duplicates on re-runs)
    cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
    for (old_id,) in cur.fetchall():
        for tbl, col in [("webhook_entity", "workflowId"),
                         ("shared_workflow", "workflowId"),
                         ("workflow_history", "workflowId")]:
            cur.execute(f"DELETE FROM {tbl} WHERE {col}=?", (old_id,))
        cur.execute("DELETE FROM workflow_entity WHERE id=?", (old_id,))

    for tbl, col in [("webhook_entity", "workflowId"),
                     ("shared_workflow", "workflowId"),
                     ("workflow_history", "workflowId")]:
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
           VALUES (?, ?, 'AIOS Phase 2.5', ?, ?, ?, 0)""",
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
    print(f"  ✓ {name}")


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


def pg_node(nid, name, pos, query, cred_id=PG_CRED_ID,
            continue_on_fail=False):
    return node(nid, name, "n8n-nodes-base.postgres", 2, pos,
                {"operation": "executeQuery", "query": query, "options": {}},
                credentials={"postgres": {"id": cred_id, "name": "AIOS PostgreSQL"}},
                continue_on_fail=continue_on_fail)


def http_post(nid, name, pos, url, json_body, never_error=False):
    opts = {"response": {"response": {"neverError": True}}} if never_error else {}
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST", "url": url,
        "sendBody": True, "specifyBody": "json",
        "jsonBody": json_body,
        "options": opts
    })


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 1: SYSTEM__ERROR_HANDLER__V1
# Triggered automatically when any workflow with errorWorkflow=this fails.
# ══════════════════════════════════════════════════════════════════
def build_error_handler():
    wf_id = IDS["error_handler"]

    nodes = [
        node("eh-trig-01", "Error Trigger",
             "n8n-nodes-base.errorTrigger", 1, [240, 300], {}),

        node("eh-code-01", "Extract Error Info",
             "n8n-nodes-base.code", 2, [460, 300], {"jsCode": (
                 "const d = $input.item.json;\n"
                 "const wfName = d.workflow?.name || 'Unknown';\n"
                 "const execId = d.execution?.id || '';\n"
                 "const error  = d.execution?.error || {};\n"
                 "const lastNode = d.execution?.lastNodeExecuted || 'unknown';\n"
                 "const msg = (error.message || 'Unknown error').slice(0, 300);\n"
                 "const safeMsg  = msg.replace(/'/g, \"''\");\n"
                 "const safeName = wfName.replace(/'/g, \"''\");\n"
                 "const safeNode = lastNode.replace(/'/g, \"''\");\n"
                 "const metaJson = JSON.stringify({ execution_id: execId, stack: (error.stack || '').slice(0,200) }).replace(/'/g, \"''\");\n"
                 "return [{ json: {\n"
                 "  workflow_name: wfName,\n"
                 "  execution_id: execId,\n"
                 "  last_node: lastNode,\n"
                 "  error_message: msg,\n"
                 "  safe_name: safeName,\n"
                 "  safe_msg: safeMsg,\n"
                 "  safe_node: safeNode,\n"
                 "  meta_json: metaJson,\n"
                 "  alert: `⚠️ AIOS Error Alert\\n\\nWorkflow: ${wfName}\\nFailed Node: ${lastNode}\\nError: ${msg}\\nTime: ${new Date().toLocaleTimeString()}`\n"
                 "} }];"
             )}),

        pg_node("eh-pg-01", "Log Error to DB",
                [680, 300],
                "INSERT INTO execution_logs "
                "(workflow_name, event_type, status, error_message, error_node, metadata) "
                "VALUES ("
                "'{{ $json.safe_name }}', 'error', 'error', "
                "'{{ $json.safe_msg }}', "
                "'{{ $json.safe_node }}', "
                "'{{ $json.meta_json }}'::jsonb"
                ")",
                continue_on_fail=True),

        http_post("eh-http-01", "Notify Admin",
                  [900, 300],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: ' + str(ADMIN_CHAT_ID) + ', text: $("Extract Error Info").item.json.alert }) }}',
                  never_error=True),
    ]

    connections = {
        "Error Trigger":      {"main": [[{"node": "Extract Error Info", "type": "main", "index": 0}]]},
        "Extract Error Info": {"main": [[{"node": "Log Error to DB",    "type": "main", "index": 0}]]},
        "Log Error to DB":    {"main": [[{"node": "Notify Admin",       "type": "main", "index": 0}]]},
    }

    upsert_workflow(wf_id, "SYSTEM__ERROR_HANDLER__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 2: SYSTEM__APPROVAL_RECOVERY__V1
# Runs every 5 min: re-sends pending approval reminders, expires stale ones.
# ══════════════════════════════════════════════════════════════════
def build_approval_recovery():
    wf_id = IDS["approval_recovery"]

    nodes = [
        node("ar-sched-01", "Every 5 Minutes",
             "n8n-nodes-base.scheduleTrigger", 1.2, [240, 300],
             {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}}),

        # Expire stale approvals (older than 24 hours)
        pg_node("ar-pg-01", "Expire Stale Approvals",
                [460, 420],
                "UPDATE pending_approvals "
                "SET status = 'expired', updated_at = NOW() "
                "WHERE status = 'pending' AND expires_at < NOW()",
                continue_on_fail=True),

        # Fetch approvals that are pending > 5 min but not yet expired
        pg_node("ar-pg-02", "Get Pending Approvals",
                [460, 300],
                "SELECT id, telegram_id, chat_id, content_preview, created_at "
                "FROM pending_approvals "
                "WHERE status = 'pending' "
                "  AND expires_at > NOW() "
                "  AND created_at < NOW() - INTERVAL '5 minutes' "
                "ORDER BY created_at ASC LIMIT 10"),

        node("ar-code-01", "Build Reminders",
             "n8n-nodes-base.code", 2, [680, 300], {"jsCode": (
                 "const items = $input.all();\n"
                 "const valid = items.filter(i => i.json && i.json.id);\n"
                 "if (valid.length === 0) return [];\n"
                 "return valid.map(item => ({\n"
                 "  json: {\n"
                 "    chat_id: item.json.chat_id,\n"
                 "    text: `🔔 Pending Approval Reminder\\n\\nYou have content waiting for your review since ${new Date(item.json.created_at).toLocaleTimeString()}.\\n\\n${item.json.content_preview ? '_Preview:_ ' + item.json.content_preview.slice(0,150) : ''}\\n\\nReply to this bot to continue.`\n"
                 "  }\n"
                 "}));"
             )}),

        http_post("ar-http-01", "Send Reminders",
                  [900, 300],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $json.chat_id, text: $json.text }) }}',
                  never_error=True),
    ]

    connections = {
        "Every 5 Minutes":     {"main": [[
            {"node": "Get Pending Approvals",  "type": "main", "index": 0},
            {"node": "Expire Stale Approvals", "type": "main", "index": 0},
        ]]},
        "Get Pending Approvals": {"main": [[{"node": "Build Reminders", "type": "main", "index": 0}]]},
        "Build Reminders":       {"main": [[{"node": "Send Reminders",  "type": "main", "index": 0}]]},
    }

    upsert_workflow(wf_id, "SYSTEM__APPROVAL_RECOVERY__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════════════
# WORKFLOW 3: TELEGRAM__SUPERVISOR__V2 (hardened rebuild)
# Adds: rate limiting, JSON validation, execution logging,
#       pending approval tracking, error workflow wiring.
# ══════════════════════════════════════════════════════════════════
def build_hardened_supervisor():
    wf_id  = SUPERVISOR_ID
    err_id = IDS["error_handler"]

    system_prompt = (
        "You are AIOS Supervisor, an AI creative director for Instagram Reels and Tamil episodic content on a VPS automation system.\\n\\n"
        "Your role: understand user intent, route workflows, manage approvals, maintain context.\\n\\n"
        "RESPOND ONLY IN THIS EXACT JSON FORMAT (no markdown, no explanation):\\n"
        "{\\n"
        '  \\"intent\\": \\"[general_chat|topic_suggestion|research_request|generate_script|approve|reject|regenerate|story_continuation|analytics_request|status_check|help]\\",\\n'
        '  \\"reply\\": \\"[your Telegram message — Markdown OK, max 300 chars unless showing a plan]\\",\\n'
        '  \\"show_buttons\\": false,\\n'
        '  \\"buttons\\": [],\\n'
        '  \\"session_update\\": {},\\n'
        '  \\"confidence\\": 0.9\\n'
        "}\\n\\n"
        "Rules:\\n"
        "- For content creation requests: confirm, ask to proceed\\n"
        "- For generate_script: set show_buttons=true with Approve/Reject/Regenerate\\n"
        "- For /start|/help|/status: respond with system info\\n"
        "- Tamil story: always acknowledge continuity\\n"
        "- Keep responses professional and action-oriented"
    )

    validate_parse_js = (
        # ── Parse & validate AI JSON response ──────────────────
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
        # Build safe SQL strings in JS, passed to Postgres node
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

    # ── Nodes list ──────────────────────────────────────────────
    nodes = [

        # ── Entry ────────────────────────────────────────────
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

        # ── Route: callback vs message ───────────────────────
        node("sv3-if-01", "Route Branch",
             "n8n-nodes-base.if", 2, [680, 300], {
             "conditions": {
                 "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                 "conditions": [{
                     "id": "cond-isCallback",
                     "leftValue":  "={{ $json.isCallback }}",
                     "rightValue": True,
                     "operator": {"type": "boolean", "operation": "equals"}
                 }],
                 "combinator": "and"
             }}),

        # ── Callback path ────────────────────────────────────
        node("sv3-code-02", "Handle Callback",
             "n8n-nodes-base.code", 2, [900, 120], {"jsCode": (
                 "const d = $input.item.json;\n"
                 "const [action, assetId] = d.text.split(':');\n"
                 "const labels = {\n"
                 "  approve:    '\\u2705 Approved! Moving to next stage.',\n"
                 "  reject:     '\\u274c Got it. What should I improve?',\n"
                 "  regenerate: '\\ud83d\\udd04 Regenerating...',\n"
                 "  darker:     '\\ud83c\\udf11 Making it darker and more intense.',\n"
                 "  emotional:  '\\ud83d\\udc94 Adding emotional depth.',\n"
                 "  faster:     '\\u26a1 Speeding up the pacing.',\n"
                 "  cinematic:  '\\ud83c\\udfa5 Applying cinematic style.'\n"
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

        # Resolve pending approval + log callback
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
                  '={{ JSON.stringify({ chat_id: $("Handle Callback").item.json.chat_id, text: $("Handle Callback").item.json.reply, parse_mode: "Markdown" }) }}'),

        # ── Message path: rate limit ─────────────────────────
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

        node("sv3-if-02", "Rate Gate",
             "n8n-nodes-base.if", 2, [1120, 480], {
             "conditions": {
                 "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                 "conditions": [{
                     "id": "cond-rate",
                     "leftValue":  "={{ $json.is_blocked }}",
                     "rightValue": True,
                     "operator": {"type": "boolean", "operation": "equals"}
                 }],
                 "combinator": "and"
             }}),

        # Rate limited → warn user, stop here
        http_post("sv3-http-rl-01", "Send Rate Warning",
                  [1340, 360],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $("Extract Message").item.json.chatId, text: "\\u23f3 Slow down! Max ' + str(RATE_LIMIT) + ' messages per minute. Try again in " + $json.retry_after_secs + " seconds." }) }}',
                  never_error=True),

        # ── Message path: session + AI ───────────────────────
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
             "n8n-nodes-base.code", 2, [1560, 600], {"jsCode": (
                 "const extract = $('Extract Message').item.json;\n"
                 "const sess    = $input.item.json;\n"
                 "let sessionData = {};\n"
                 "try { sessionData = JSON.parse(sess.session_data || '{}'); } catch(e){}\n\n"
                 "const systemPrompt = `" + system_prompt + "`;\n\n"
                 "const context = `User: ${extract.username}\\n"
                 "Message #: ${sess.message_count}\\n"
                 "Active workflow: ${sess.active_workflow || 'none'}\\n"
                 "Session: ${JSON.stringify(sessionData).slice(0,200)}`;\n\n"
                 "return [{ json: {\n"
                 "  system_prompt: systemPrompt,\n"
                 "  prompt: `${context}\\n\\nUser message: ${extract.text}`,\n"
                 "  model: 'anthropic/claude-3.5-haiku',\n"
                 "  max_tokens: 800,\n"
                 "  temperature: 0.4,\n"
                 "  chat_id:       extract.chatId,\n"
                 "  from_id:       extract.fromId,\n"
                 "  username:      extract.username,\n"
                 "  user_id:       sess.user_id,\n"
                 "  message_count: sess.message_count,\n"
                 "  session_data:  sessionData,\n"
                 "  text:          extract.text\n"
                 "} }];"
             )}),

        node("sv3-http-or-01", "Call Supervisor AI",
             "n8n-nodes-base.httpRequest", 4.2, [1780, 600], {
             "method": "POST", "url": OR_URL,
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": f"Bearer {OR_KEY}"},
                 {"name": "Content-Type",  "value": "application/json"},
                 {"name": "HTTP-Referer",  "value": "https://n8n.srv1654276.hstgr.cloud"},
                 {"name": "X-Title",       "value": "AIOS Supervisor"}
             ]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ model: $json.model, messages: [{ role: "system", content: $json.system_prompt }, { role: "user", content: $json.prompt }], max_tokens: $json.max_tokens, temperature: $json.temperature }) }}',
             "options": {}}),

        # Enhanced parse with full JSON validation
        node("sv3-code-04", "Validate & Parse",
             "n8n-nodes-base.code", 2, [2000, 600], {"jsCode": validate_parse_js}),

        # Prepare safe SQL strings
        node("sv3-code-05", "Prepare Save Data",
             "n8n-nodes-base.code", 2, [2220, 600], {"jsCode": prepare_save_js}),

        # Save session + optionally track pending approval
        pg_node("sv3-pg-save-01", "Save Session",
                [2440, 600],
                "{{ $json.saveSQL }}"),

        # Log execution (non-critical, don't block on failure)
        pg_node("sv3-pg-log-01", "Log Execution",
                [2440, 720],
                "{{ $json.logSQL }}",
                continue_on_fail=True),

        # Send reply to Telegram
        http_post("sv3-http-tg-01", "Send Reply",
                  [2660, 600],
                  f"{TG_API}/sendMessage",
                  '={{ JSON.stringify({ chat_id: $("Validate & Parse").item.json.chat_id, text: $("Validate & Parse").item.json.reply, parse_mode: "Markdown", reply_markup: $("Validate & Parse").item.json.reply_markup || undefined }) }}'),
    ]

    connections = {
        "Telegram Webhook": {"main": [[{"node": "Extract Message", "type": "main", "index": 0}]]},
        "Extract Message":  {"main": [[{"node": "Route Branch",    "type": "main", "index": 0}]]},

        # IF true (callback) / false (message)
        "Route Branch": {"main": [
            [{"node": "Handle Callback",   "type": "main", "index": 0}],  # 0 = true
            [{"node": "Check Rate Limit",  "type": "main", "index": 0}]   # 1 = false
        ]},

        # Callback path
        "Handle Callback":    {"main": [[{"node": "Answer Callback",    "type": "main", "index": 0}]]},
        "Answer Callback":    {"main": [[{"node": "Resolve Approval",   "type": "main", "index": 0}]]},
        "Resolve Approval":   {"main": [[{"node": "Send Callback Reply","type": "main", "index": 0}]]},

        # Rate gate
        "Check Rate Limit": {"main": [[{"node": "Rate Gate", "type": "main", "index": 0}]]},
        "Rate Gate": {"main": [
            [{"node": "Send Rate Warning", "type": "main", "index": 0}],  # 0 = true (blocked)
            [{"node": "Load Session",      "type": "main", "index": 0}]   # 1 = false (allowed)
        ]},

        # Message path
        "Load Session":       {"main": [[{"node": "Prepare AI Context", "type": "main", "index": 0}]]},
        "Prepare AI Context": {"main": [[{"node": "Call Supervisor AI", "type": "main", "index": 0}]]},
        "Call Supervisor AI": {"main": [[{"node": "Validate & Parse",   "type": "main", "index": 0}]]},
        "Validate & Parse":   {"main": [[{"node": "Prepare Save Data",  "type": "main", "index": 0}]]},
        "Prepare Save Data":  {"main": [[
            {"node": "Save Session",   "type": "main", "index": 0},
            {"node": "Log Execution",  "type": "main", "index": 0},
        ]]},
        "Save Session":       {"main": [[{"node": "Send Reply", "type": "main", "index": 0}]]},
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
# Populate workflow_versions table
# ══════════════════════════════════════════════════════════════════
REGISTRY = [
    ("TELEGRAM__SUPERVISOR__V2",     "v2", SUPERVISOR_ID,             "AI supervisor with hardening layer"),
    ("SYSTEM__ERROR_HANDLER__V1",    "v1", IDS["error_handler"],      "Central error capture and Telegram alert"),
    ("SYSTEM__APPROVAL_RECOVERY__V1","v1", IDS["approval_recovery"],  "Scheduled pending approval reminders"),
    ("AI__OPENROUTER_GATEWAY__V1",   "v1", None,                      "Reusable OpenRouter HTTP subworkflow"),
    ("MEMORY__SESSION_MANAGER__V1",  "v1", None,                      "PostgreSQL session load/save subworkflow"),
    ("AI__INTENT_CLASSIFIER__V1",    "v1", None,                      "AI intent classification subworkflow"),
    ("APPROVAL__STATE_MANAGER__V1",  "v1", None,                      "Approval state machine subworkflow"),
    ("AI__WORKFLOW_ROUTER__V1",      "v1", None,                      "Intent-to-workflow routing table"),
]


def populate_registry():
    cmd_base = ["docker", "exec", "-i", "aios-postgres",
                "psql", "-U", "aios_user", "-d", "aios_db"]
    rows = []
    for name, version, wf_id, desc in REGISTRY:
        safe_desc = desc.replace("'", "''")
        n8n_id_sql = f"'{wf_id}'" if wf_id else "NULL"
        rows.append(
            f"('{name}', '{version}', {n8n_id_sql}, TRUE, '{safe_desc}', NOW(), NOW())"
        )
    sql = (
        "INSERT INTO workflow_versions (workflow_name, version, n8n_id, is_active, description, deployed_at, updated_at) VALUES\n"
        + ",\n".join(rows)
        + "\nON CONFLICT (workflow_name, version) DO UPDATE SET "
        "n8n_id = EXCLUDED.n8n_id, is_active = TRUE, "
        "description = EXCLUDED.description, updated_at = NOW();"
    )
    r = subprocess.run(cmd_base, input=sql.encode(), capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f"  ✓ Workflow registry: {len(REGISTRY)} entries")
    else:
        print(f"  ✗ Registry error: {r.stderr.decode()[:200]}")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n=== AIOS Phase 2.5 — Hardening Layer ===\n")

    print("[SQL] Running migration...")
    run_migration()

    print("\n[1] SYSTEM__ERROR_HANDLER__V1")
    build_error_handler()

    print("\n[2] SYSTEM__APPROVAL_RECOVERY__V1")
    build_approval_recovery()

    print("\n[3] TELEGRAM__SUPERVISOR__V2 (hardened rebuild)")
    build_hardened_supervisor()

    print("\n[4] Workflow Version Registry")
    populate_registry()

    print("\n=== Phase 2.5 complete ===")
    print("Restart n8n: docker restart n8n-n8n-1")
