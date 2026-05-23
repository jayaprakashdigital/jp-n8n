#!/usr/bin/env python3
"""
AIOS Phase 2 — Workflow Builder
Creates all Phase 2 workflows directly in n8n SQLite database.

Workflows created:
  1. AI__OPENROUTER_GATEWAY__V1    (subworkflow: AI calls)
  2. MEMORY__SESSION_MANAGER__V1  (subworkflow: load/save session)
  3. AI__INTENT_CLASSIFIER__V1    (subworkflow: classify intent via AI)
  4. APPROVAL__STATE_MANAGER__V1  (webhook: handle inline button callbacks)
  5. AI__WORKFLOW_ROUTER__V1      (subworkflow: maps intent → action)
  6. TELEGRAM__SUPERVISOR__V2     (upgrades V1: full AI supervisor)
"""

import json, uuid, sqlite3, hashlib, os, base64
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad

# ─── Config ───────────────────────────────────────────────
DB_PATH = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID = "0YzGnVQ4VzNb3gOx"
SUPERVISOR_V1_ID = "13473953-52ed-419e-93c0-78c0c91b0818"
ENCRYPTION_KEY = "vdlIIW6ZObRWezflrgbWoR6LD05/7o+4"
SALTED_PREFIX = bytes.fromhex("53616c7465645f5f")
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OR_KEY = os.environ["OPENROUTER_API_KEY"]
TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"

# Pre-generate all workflow IDs for cross-references
IDS = {
    "openrouter_gateway": str(uuid.uuid4()),
    "session_manager":    str(uuid.uuid4()),
    "intent_classifier":  str(uuid.uuid4()),
    "approval_manager":   str(uuid.uuid4()),
    "workflow_router":    str(uuid.uuid4()),
    "supervisor_v2":      SUPERVISOR_V1_ID,  # upgrade in-place
}

print("Workflow IDs:")
for k, v in IDS.items():
    print(f"  {k}: {v}")


# ─── DB helpers ───────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_PATH)

def encrypt(plaintext):
    salt = os.urandom(8)
    key_bytes = ENCRYPTION_KEY.encode("latin-1")
    password = key_bytes + salt
    hash1 = __import__("hashlib").md5(password).digest()
    hash2 = __import__("hashlib").md5(hash1 + password).digest()
    iv = __import__("hashlib").md5(hash2 + password).digest()
    derived_key = hash1 + hash2
    cipher = AES.new(derived_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(SALTED_PREFIX + salt + encrypted).decode()

def upsert_workflow(wf_id, name, nodes, connections, settings=None, active=True, webhook_path=None, webhook_method="POST", webhook_node_name=None):
    db = get_db()
    cur = db.cursor()
    version_id = str(uuid.uuid4())
    nodes_str = json.dumps(nodes)
    conn_str = json.dumps(connections)
    settings_str = json.dumps(settings or {"executionOrder": "v1"})

    # Remove old entries (by id AND by name to avoid duplicates on re-runs)
    cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
    for (old_id,) in cur.fetchall():
        for tbl, col in [("webhook_entity","workflowId"), ("shared_workflow","workflowId"),
                         ("workflow_history","workflowId")]:
            cur.execute(f"DELETE FROM {tbl} WHERE {col}=?", (old_id,))
        cur.execute("DELETE FROM workflow_entity WHERE id=?", (old_id,))
    for tbl, col in [("webhook_entity","workflowId"), ("shared_workflow","workflowId"),
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
           VALUES (?, ?, 'AIOS Phase 2', ?, ?, ?, 0)""",
        (version_id, wf_id, nodes_str, conn_str, name)
    )
    cur.execute(
        "INSERT OR IGNORE INTO shared_workflow (workflowId, projectId, role) VALUES (?, ?, 'workflow:owner')",
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

# ─── Node builder helpers ──────────────────────────────────
def node(nid, name, ntype, version, pos, params, credentials=None, webhook_id=None):
    n = {"id": nid, "name": name, "type": ntype,
         "typeVersion": version, "position": pos, "parameters": params}
    if credentials:
        n["credentials"] = credentials
    if webhook_id:
        n["webhookId"] = webhook_id
    return n

def conn(src, dst, idx=0):
    return {src: {"main": [[{"node": dst, "type": "main", "index": idx}]]}}

def conns(*pairs):
    result = {}
    for src, dst in pairs:
        if src in result:
            result[src]["main"][0].append({"node": dst, "type": "main", "index": 0})
        else:
            result[src] = {"main": [[{"node": dst, "type": "main", "index": 0}]]}
    return result


# ══════════════════════════════════════════════════════════
# WORKFLOW 1: AI__OPENROUTER_GATEWAY__V1
# ══════════════════════════════════════════════════════════
def build_openrouter_gateway():
    wf_id = IDS["openrouter_gateway"]
    nodes = [
        node("or-trig-01", "Execute Workflow Trigger",
             "n8n-nodes-base.executeWorkflowTrigger", 1,
             [240, 300], {}),

        node("or-code-01", "Prepare Request",
             "n8n-nodes-base.code", 2, [460, 300], {
             "jsCode": (
                 "const input = $input.item.json;\n"
                 "const prompt = input.prompt || '';\n"
                 "const systemPrompt = input.system_prompt || 'You are a helpful AI assistant. Return only valid JSON.';\n"
                 "const model = input.model || 'anthropic/claude-3.5-haiku';\n"
                 "const schema = input.schema || null;\n\n"
                 "const messages = [\n"
                 "  { role: 'system', content: systemPrompt },\n"
                 "  { role: 'user', content: prompt }\n"
                 "];\n\n"
                 "if (input.history && Array.isArray(input.history)) {\n"
                 "  messages.splice(1, 0, ...input.history.slice(-6));\n"
                 "}\n\n"
                 "return [{ json: {\n"
                 "  model, messages,\n"
                 "  max_tokens: input.max_tokens || 1000,\n"
                 "  temperature: input.temperature || 0.3,\n"
                 "  original_input: input\n"
                 "} }];"
             )}),

        node("or-http-01", "Call OpenRouter",
             "n8n-nodes-base.httpRequest", 4.2, [680, 300], {
             "method": "POST",
             "url": OR_URL,
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": f"Bearer {OR_KEY}"},
                 {"name": "Content-Type",  "value": "application/json"},
                 {"name": "HTTP-Referer",  "value": "https://n8n.srv1654276.hstgr.cloud"},
                 {"name": "X-Title",       "value": "AIOS"}
             ]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ model: $json.model, messages: $json.messages, max_tokens: $json.max_tokens, temperature: $json.temperature }) }}",
             "options": {}}),

        node("or-code-02", "Parse Response",
             "n8n-nodes-base.code", 2, [900, 300], {
             "jsCode": (
                 "const response = $input.item.json;\n"
                 "const content = response?.choices?.[0]?.message?.content || '';\n"
                 "let parsed = null;\n"
                 "try {\n"
                 "  const jsonMatch = content.match(/\\{[\\s\\S]*\\}/);\n"
                 "  parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { raw: content };\n"
                 "} catch(e) {\n"
                 "  parsed = { raw: content, parse_error: e.message };\n"
                 "}\n"
                 "return [{ json: {\n"
                 "  success: true,\n"
                 "  content,\n"
                 "  parsed,\n"
                 "  model: response?.model,\n"
                 "  tokens: response?.usage\n"
                 "} }];"
             )})
    ]
    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prepare Request", "type": "main", "index": 0}]]},
        "Prepare Request":  {"main": [[{"node": "Call OpenRouter", "type": "main", "index": 0}]]},
        "Call OpenRouter":  {"main": [[{"node": "Parse Response", "type": "main", "index": 0}]]}
    }
    upsert_workflow(wf_id, "AI__OPENROUTER_GATEWAY__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════
# WORKFLOW 2: MEMORY__SESSION_MANAGER__V1
# ══════════════════════════════════════════════════════════
def build_session_manager():
    wf_id = IDS["session_manager"]
    nodes = [
        node("sm-trig-01", "Execute Workflow Trigger",
             "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {}),

        node("sm-code-01", "Prepare DB Query",
             "n8n-nodes-base.code", 2, [460, 300], {
             "jsCode": (
                 "const input = $input.item.json;\n"
                 "const action = input.action || 'load'; // load | save\n"
                 "const telegramId = input.telegram_id;\n"
                 "const sessionData = input.session_data || {};\n\n"
                 "if (action === 'load') {\n"
                 "  return [{ json: {\n"
                 "    action: 'load',\n"
                 "    query: `\n"
                 "      WITH upsert AS (\n"
                 "        INSERT INTO users (telegram_id, username)\n"
                 "        VALUES (${telegramId}, '${input.username || 'unknown'}')\n"
                 "        ON CONFLICT (telegram_id) DO UPDATE\n"
                 "        SET username = COALESCE(EXCLUDED.username, users.username)\n"
                 "        RETURNING id\n"
                 "      )\n"
                 "      SELECT u.id as user_id, u.telegram_id, u.username,\n"
                 "             s.session_data, s.active_workflow, s.message_count\n"
                 "      FROM upsert u\n"
                 "      LEFT JOIN sessions s ON s.user_id = u.id\n"
                 "      LIMIT 1\n"
                 "    `\n"
                 "  } }];\n"
                 "} else {\n"
                 "  const userId = input.user_id;\n"
                 "  const activeWf = sessionData.active_workflow || null;\n"
                 "  const msgCount = input.message_count || 0;\n"
                 "  return [{ json: {\n"
                 "    action: 'save',\n"
                 "    query: `\n"
                 "      INSERT INTO sessions (user_id, session_data, active_workflow, current_status, message_count)\n"
                 "      VALUES (${userId}, '${JSON.stringify(sessionData).replace(/'/g, \"''\")}', ${activeWf ? \"'\" + activeWf + \"'\" : 'NULL'}, 'active', ${msgCount})\n"
                 "      ON CONFLICT (user_id) DO UPDATE\n"
                 "      SET session_data = EXCLUDED.session_data,\n"
                 "          active_workflow = EXCLUDED.active_workflow,\n"
                 "          message_count = EXCLUDED.message_count,\n"
                 "          updated_at = NOW()\n"
                 "      RETURNING user_id, message_count\n"
                 "    `\n"
                 "  } }];\n"
                 "}"
             )}),

        node("sm-pg-01", "Execute DB Query",
             "n8n-nodes-base.postgres", 2, [680, 300], {
             "operation": "executeQuery",
             "query": "={{ $json.query }}",
             "options": {}
             }, credentials={"postgres": {"id": "a20cebf1b1c648", "name": "AIOS PostgreSQL"}}),

        node("sm-code-02", "Format Output",
             "n8n-nodes-base.code", 2, [900, 300], {
             "jsCode": (
                 "const rows = $input.all();\n"
                 "const row = rows[0]?.json || {};\n"
                 "let sessionData = {};\n"
                 "try {\n"
                 "  sessionData = typeof row.session_data === 'string'\n"
                 "    ? JSON.parse(row.session_data)\n"
                 "    : (row.session_data || {});\n"
                 "} catch(e) {}\n"
                 "return [{ json: {\n"
                 "  user_id: row.user_id,\n"
                 "  telegram_id: row.telegram_id,\n"
                 "  username: row.username,\n"
                 "  session_data: sessionData,\n"
                 "  active_workflow: row.active_workflow,\n"
                 "  message_count: row.message_count || 0\n"
                 "} }];"
             )})
    ]
    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prepare DB Query", "type": "main", "index": 0}]]},
        "Prepare DB Query":  {"main": [[{"node": "Execute DB Query", "type": "main", "index": 0}]]},
        "Execute DB Query":  {"main": [[{"node": "Format Output",   "type": "main", "index": 0}]]}
    }
    upsert_workflow(wf_id, "MEMORY__SESSION_MANAGER__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════
# WORKFLOW 3: AI__INTENT_CLASSIFIER__V1
# ══════════════════════════════════════════════════════════
def build_intent_classifier():
    wf_id = IDS["intent_classifier"]
    system_prompt = (
        "You are an intent classifier for an AI content creation system. "
        "Analyze the user message and return ONLY this JSON object with no other text:\\n"
        "{\\n"
        '  \\"intent\\": \\"one of: general_chat|topic_suggestion|research_request|generate_script|approve|reject|regenerate|story_continuation|analytics_request|status_check|help\\",\\n'
        '  \\"content_type\\": \\"viral_reel|youtube_short|tamil_story|null\\",\\n'
        '  \\"topic\\": \\"extracted topic or null\\",\\n'
        '  \\"needs_research\\": true/false,\\n'
        '  \\"requires_approval\\": false,\\n'
        '  \\"confidence\\": 0.0-1.0\\n'
        "}"
    )
    nodes = [
        node("ic-trig-01", "Execute Workflow Trigger",
             "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {}),

        node("ic-http-01", "Classify via OpenRouter",
             "n8n-nodes-base.httpRequest", 4.2, [460, 300], {
             "method": "POST",
             "url": OR_URL,
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": f"Bearer {OR_KEY}"},
                 {"name": "Content-Type",  "value": "application/json"}
             ]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": (
                 '={{ JSON.stringify({'
                 f'"model": "anthropic/claude-3.5-haiku",'
                 '"messages": ['
                 '{"role": "system", "content": "' + system_prompt + '"},'
                 '{"role": "user", "content": $json.text}'
                 '],'
                 '"max_tokens": 200,'
                 '"temperature": 0.1'
                 '}) }}'
             ),
             "options": {}}),

        node("ic-code-01", "Parse Intent",
             "n8n-nodes-base.code", 2, [680, 300], {
             "jsCode": (
                 "const response = $input.item.json;\n"
                 "const content = response?.choices?.[0]?.message?.content || '';\n"
                 "let intent = {\n"
                 "  intent: 'general_chat',\n"
                 "  content_type: null,\n"
                 "  topic: null,\n"
                 "  needs_research: false,\n"
                 "  requires_approval: false,\n"
                 "  confidence: 0.5\n"
                 "};\n"
                 "try {\n"
                 "  const match = content.match(/\\{[\\s\\S]*\\}/);\n"
                 "  if (match) intent = { ...intent, ...JSON.parse(match[0]) };\n"
                 "} catch(e) {}\n"
                 "return [{ json: intent }];"
             )})
    ]
    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Classify via OpenRouter", "type": "main", "index": 0}]]},
        "Classify via OpenRouter":  {"main": [[{"node": "Parse Intent", "type": "main", "index": 0}]]}
    }
    upsert_workflow(wf_id, "AI__INTENT_CLASSIFIER__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════
# WORKFLOW 4: APPROVAL__STATE_MANAGER__V1
# ══════════════════════════════════════════════════════════
def build_approval_manager():
    wf_id = IDS["approval_manager"]
    nodes = [
        node("am-wh-01", "Approval Webhook",
             "n8n-nodes-base.webhook", 2, [240, 300], {
             "httpMethod": "POST",
             "path": "aios-approval",
             "responseMode": "lastNode",
             "options": {}
             }, webhook_id="aios-approval"),

        node("am-code-01", "Parse Callback",
             "n8n-nodes-base.code", 2, [460, 300], {
             "jsCode": (
                 "const body = $input.item.json.body || $input.item.json;\n"
                 "const cq = body.callback_query;\n"
                 "if (!cq) return [{ json: { skip: true } }];\n\n"
                 "const data = cq.data || '';\n"
                 "const [action, assetId] = data.split(':');\n"
                 "return [{ json: {\n"
                 "  callback_id: cq.id,\n"
                 "  chat_id: cq.message.chat.id,\n"
                 "  from_id: cq.from.id,\n"
                 "  username: cq.from.username || cq.from.first_name,\n"
                 "  action,\n"
                 "  asset_id: assetId || null,\n"
                 "  raw_data: data,\n"
                 "  message_id: cq.message.message_id\n"
                 "} }];"
             )}),

        node("am-pg-01", "Save Approval",
             "n8n-nodes-base.postgres", 2, [680, 300], {
             "operation": "executeQuery",
             "query": (
                 "INSERT INTO approvals (asset_type, asset_id, user_feedback, status) "
                 "VALUES ('content', 0, '{{ $json.action }}', '{{ $json.action }}')"
             ),
             "options": {}
             }, credentials={"postgres": {"id": "a20cebf1b1c648", "name": "AIOS PostgreSQL"}}),

        node("am-http-01", "Answer Callback",
             "n8n-nodes-base.httpRequest", 4.2, [900, 300], {
             "method": "POST",
             "url": f"{TG_API}/answerCallbackQuery",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ callback_query_id: $("Parse Callback").item.json.callback_id, text: "Noted! " + $("Parse Callback").item.json.action }) }}',
             "options": {}}),

        node("am-code-02", "Build Confirm Reply",
             "n8n-nodes-base.code", 2, [1120, 300], {
             "jsCode": (
                 "const cb = $('Parse Callback').item.json;\n"
                 "const labels = {\n"
                 "  approve: '✅ Approved! Moving to next stage.',\n"
                 "  reject: '❌ Rejected. What should I change?',\n"
                 "  regenerate: '🔄 Regenerating... one moment.',\n"
                 "  darker: '🌑 Making it darker and more intense.',\n"
                 "  emotional: '💔 Adding more emotional depth.',\n"
                 "  faster: '⚡ Increasing the pacing.',\n"
                 "  cinematic: '🎬 Applying cinematic treatment.'\n"
                 "};\n"
                 "const reply = labels[cb.action] || `Action recorded: ${cb.action}`;\n"
                 "return [{ json: { chat_id: cb.chat_id, reply } }];"
             )}),

        node("am-http-02", "Send Confirmation",
             "n8n-nodes-base.httpRequest", 4.2, [1340, 300], {
             "method": "POST",
             "url": f"{TG_API}/sendMessage",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ chat_id: $json.chat_id, text: $json.reply, parse_mode: "Markdown" }) }}',
             "options": {}})
    ]
    connections = {
        "Approval Webhook": {"main": [[{"node": "Parse Callback", "type": "main", "index": 0}]]},
        "Parse Callback":   {"main": [[{"node": "Save Approval",  "type": "main", "index": 0}]]},
        "Save Approval":    {"main": [[{"node": "Answer Callback","type": "main", "index": 0}]]},
        "Answer Callback":  {"main": [[{"node": "Build Confirm Reply", "type": "main", "index": 0}]]},
        "Build Confirm Reply": {"main": [[{"node": "Send Confirmation", "type": "main", "index": 0}]]}
    }
    upsert_workflow(wf_id, "APPROVAL__STATE_MANAGER__V1", nodes, connections,
                    active=True, webhook_path="aios-approval",
                    webhook_method="POST", webhook_node_name="Approval Webhook")
    return wf_id


# ══════════════════════════════════════════════════════════
# WORKFLOW 5: AI__WORKFLOW_ROUTER__V1
# ══════════════════════════════════════════════════════════
def build_workflow_router():
    wf_id = IDS["workflow_router"]
    nodes = [
        node("wr-trig-01", "Execute Workflow Trigger",
             "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {}),

        node("wr-code-01", "Route Intent",
             "n8n-nodes-base.code", 2, [460, 300], {
             "jsCode": (
                 "const input = $input.item.json;\n"
                 "const intent = input.intent || 'general_chat';\n\n"
                 "const routes = {\n"
                 "  topic_suggestion:   { workflow: 'research', stage: 'research', next_prompt: 'Tell me your topic and I will research it for you.' },\n"
                 "  research_request:   { workflow: 'research', stage: 'research', next_prompt: 'Starting research...' },\n"
                 "  generate_script:    { workflow: 'script',   stage: 'script',   next_prompt: 'Generating script...' },\n"
                 "  approve:            { workflow: 'approval', stage: 'approved', next_prompt: 'Approved! Moving forward.' },\n"
                 "  reject:             { workflow: 'approval', stage: 'rejected', next_prompt: 'What should be changed?' },\n"
                 "  regenerate:         { workflow: 'approval', stage: 'regenerate', next_prompt: 'Regenerating...' },\n"
                 "  story_continuation: { workflow: 'tamil_story', stage: 'story', next_prompt: 'Continuing the Tamil story...' },\n"
                 "  analytics_request:  { workflow: 'analytics', stage: 'analytics', next_prompt: 'Loading analytics...' },\n"
                 "  status_check:       { workflow: 'system', stage: 'status', next_prompt: null },\n"
                 "  help:               { workflow: 'system', stage: 'help',   next_prompt: null },\n"
                 "  general_chat:       { workflow: 'chat',   stage: 'chat',   next_prompt: null }\n"
                 "};\n\n"
                 "const route = routes[intent] || routes.general_chat;\n"
                 "return [{ json: {\n"
                 "  intent,\n"
                 "  ...route,\n"
                 "  content_type: input.content_type,\n"
                 "  topic: input.topic,\n"
                 "  original_input: input\n"
                 "} }];"
             )})
    ]
    connections = {
        "Execute Workflow Trigger": {"main": [[{"node": "Route Intent", "type": "main", "index": 0}]]}
    }
    upsert_workflow(wf_id, "AI__WORKFLOW_ROUTER__V1", nodes, connections, active=True)
    return wf_id


# ══════════════════════════════════════════════════════════
# WORKFLOW 6: TELEGRAM__SUPERVISOR__V2 (upgrade V1 in-place)
# ══════════════════════════════════════════════════════════
def build_supervisor_v2():
    wf_id = SUPERVISOR_V1_ID

    # SUPERVISOR SYSTEM PROMPT
    system_prompt = (
        "You are AIOS Supervisor, an AI creative director for Instagram Reels and Tamil episodic content on a VPS automation system.\\n\\n"
        "Your role: understand user intent, route workflows, manage approvals, maintain context.\\n\\n"
        "RESPOND ONLY IN THIS EXACT JSON FORMAT (no markdown, no explanation):\\n"
        "{\\n"
        '  \\"intent\\": \\"[general_chat|topic_suggestion|research_request|generate_script|approve|reject|regenerate|story_continuation|analytics_request|status_check|help]\\",\\n'
        '  \\"reply\\": \\"[your Telegram message - use Markdown, keep under 300 chars unless showing a plan]\\",\\n'
        '  \\"show_buttons\\": false,\\n'
        '  \\"buttons\\": [],\\n'
        '  \\"session_update\\": {},\\n'
        '  \\"confidence\\": 0.9\\n'
        "}\\n\\n"
        "Rules:\\n"
        "- For content creation requests: confirm understanding and ask to proceed\\n"
        "- For approvals: show buttons [Approve, Reject, Regenerate, Darker, Emotional]\\n"
        "- For /start|/help|/status: respond with system info\\n"
        "- Tamil story requests: always acknowledge continuity\\n"
        "- Keep it professional and action-oriented"
    )

    nodes = [
        # ── Entry ──────────────────────────────────────────
        node("sv2-wh-01", "Telegram Webhook",
             "n8n-nodes-base.webhook", 2, [240, 300], {
             "httpMethod": "POST",
             "path": "aios-telegram-bot",
             "responseMode": "lastNode",
             "options": {}
             }, webhook_id="aios-telegram-bot"),

        # ── Extract message info ───────────────────────────
        node("sv2-code-01", "Extract Message",
             "n8n-nodes-base.code", 2, [460, 300], {
             "jsCode": (
                 "const body = $input.item.json.body || $input.item.json;\n"
                 "const msg = body.message;\n"
                 "const cq  = body.callback_query;\n"
                 "let chatId, fromId, username, text, isCallback = false, callbackId;\n"
                 "if (cq) {\n"
                 "  isCallback = true;\n"
                 "  chatId   = cq.message.chat.id;\n"
                 "  fromId   = cq.from.id;\n"
                 "  username = cq.from.username || cq.from.first_name || 'User';\n"
                 "  text     = cq.data || '';\n"
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

        # ── IF: route callback vs message ─────────────────
        node("sv2-if-01", "Route Branch",
             "n8n-nodes-base.if", 2, [680, 300], {
             "conditions": {
                 "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                 "conditions": [{
                     "id": "cond-isCallback",
                     "leftValue": "={{ $json.isCallback }}",
                     "rightValue": True,
                     "operator": {"type": "boolean", "operation": "equals"}
                 }],
                 "combinator": "and"
             }}),

        # ── Branch: callback query (inline buttons) ────────
        node("sv2-code-02", "Handle Callback",
             "n8n-nodes-base.code", 2, [900, 160], {
             "jsCode": (
                 "const d = $input.item.json;\n"
                 "const [action, assetId] = d.text.split(':');\n"
                 "const labels = {\n"
                 "  approve:'✅ Approved! Moving to next stage...',\n"
                 "  reject:'❌ Got it. What should I improve?',\n"
                 "  regenerate:'🔄 Regenerating...',\n"
                 "  darker:'🌑 Making it darker and more intense.',\n"
                 "  emotional:'💔 Adding emotional depth.',\n"
                 "  faster:'⚡ Speeding up the pacing.',\n"
                 "  cinematic:'🎬 Applying cinematic style.'\n"
                 "};\n"
                 "return [{ json: {\n"
                 "  isCallback: true,\n"
                 "  chat_id: d.chatId,\n"
                 "  callback_id: d.callbackId,\n"
                 "  reply: labels[action] || `Recorded: ${action}`,\n"
                 "  action, asset_id: assetId\n"
                 "} }];"
             )}),

        # ── Answer callback query ──────────────────────────
        node("sv2-http-cb-01", "Answer Callback Query",
             "n8n-nodes-base.httpRequest", 4.2, [1120, 160], {
             "method": "POST",
             "url": f"{TG_API}/answerCallbackQuery",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ callback_query_id: $json.callback_id, text: "✓" }) }}',
             "options": {}}),

        # ── Save approval state ────────────────────────────
        node("sv2-pg-cb-01", "Save Approval",
             "n8n-nodes-base.postgres", 2, [1340, 160], {
             "operation": "executeQuery",
             "query": "INSERT INTO approvals (asset_type, asset_id, user_feedback, status) VALUES ('content', 0, '{{ $json.action }}', '{{ $json.action }}') RETURNING id",
             "options": {}
             }, credentials={"postgres": {"id": "a20cebf1b1c648", "name": "AIOS PostgreSQL"}}),

        # ── Send callback reply ────────────────────────────
        node("sv2-http-cb-02", "Send Callback Reply",
             "n8n-nodes-base.httpRequest", 4.2, [1560, 160], {
             "method": "POST",
             "url": f"{TG_API}/sendMessage",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": '={{ JSON.stringify({ chat_id: $("Handle Callback").item.json.chat_id, text: $("Handle Callback").item.json.reply, parse_mode: "Markdown" }) }}',
             "options": {}}),

        # ── Branch: regular message ────────────────────────
        node("sv2-pg-sess-01", "Load Session",
             "n8n-nodes-base.postgres", 2, [900, 440], {
             "operation": "executeQuery",
             "query": (
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
                 "RETURNING user_id, session_data::text, active_workflow, message_count"
             ),
             "options": {}
             }, credentials={"postgres": {"id": "a20cebf1b1c648", "name": "AIOS PostgreSQL"}}),

        # ── Prepare AI request ─────────────────────────────
        node("sv2-code-03", "Prepare AI Context",
             "n8n-nodes-base.code", 2, [900, 440], {
             "jsCode": (
                 "const extract = $('Extract Message').item.json;\n"
                 "const sess = $input.item.json;\n"
                 "let sessionData = {};\n"
                 "try { sessionData = JSON.parse(sess.session_data || '{}'); } catch(e){}\n\n"
                 "const history = sessionData.history || [];\n"
                 "const systemPrompt = `" + system_prompt + "`;\n\n"
                 "const context = `User: ${extract.username}\\nMessage count: ${sess.message_count}\\nActive workflow: ${sess.active_workflow || 'none'}\\nSession context: ${JSON.stringify(sessionData).slice(0,300)}`;\n\n"
                 "const fullPrompt = `${context}\\n\\nUser message: ${extract.text}`;\n\n"
                 "return [{ json: {\n"
                 "  system_prompt: systemPrompt,\n"
                 "  prompt: fullPrompt,\n"
                 "  model: 'anthropic/claude-3.5-haiku',\n"
                 "  max_tokens: 800,\n"
                 "  temperature: 0.4,\n"
                 "  chat_id: extract.chatId,\n"
                 "  from_id: extract.fromId,\n"
                 "  username: extract.username,\n"
                 "  user_id: sess.user_id,\n"
                 "  message_count: sess.message_count,\n"
                 "  session_data: sessionData,\n"
                 "  text: extract.text\n"
                 "} }];"
             )}),

        # ── Call OpenRouter (supervisor AI) ────────────────
        node("sv2-http-or-01", "Call Supervisor AI",
             "n8n-nodes-base.httpRequest", 4.2, [1120, 440], {
             "method": "POST",
             "url": OR_URL,
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

        # ── Parse AI response ──────────────────────────────
        node("sv2-code-04", "Parse AI Response",
             "n8n-nodes-base.code", 2, [1340, 440], {
             "jsCode": (
                 "const aiResp = $input.item.json;\n"
                 "const ctx    = $('Prepare AI Context').item.json;\n"
                 "const content = aiResp?.choices?.[0]?.message?.content || '';\n\n"
                 "let ai = { intent:'general_chat', reply:'I am ready.', show_buttons:false, buttons:[], session_update:{}, confidence:0.5 };\n"
                 "try {\n"
                 "  const m = content.match(/\\{[\\s\\S]*\\}/);\n"
                 "  if (m) ai = { ...ai, ...JSON.parse(m[0]) };\n"
                 "} catch(e) {\n"
                 "  ai.reply = content.slice(0, 400) || 'Processing...';\n"
                 "}\n\n"
                 "// Build Telegram reply_markup if buttons requested\n"
                 "let replyMarkup = null;\n"
                 "if (ai.show_buttons && ai.buttons && ai.buttons.length > 0) {\n"
                 "  replyMarkup = { inline_keyboard: [ai.buttons.filter(b => b && b.text).map(b => ({ text: b.text, callback_data: b.callback_data || b.text.toLowerCase() }))] };\n"
                 "  if (replyMarkup.inline_keyboard[0].length === 0) replyMarkup = null;\n"
                 "}\n\n"
                 "// Default approval buttons for content approval\n"
                 "if (ai.intent === 'generate_script' && !replyMarkup) {\n"
                 "  replyMarkup = { inline_keyboard: [[\n"
                 "    { text: '✅ Approve', callback_data: 'approve' },\n"
                 "    { text: '❌ Reject',  callback_data: 'reject' },\n"
                 "    { text: '🔄 Regenerate', callback_data: 'regenerate' }\n"
                 "  ]] };\n"
                 "}\n\n"
                 "return [{ json: {\n"
                 "  chat_id: ctx.chat_id,\n"
                 "  reply: ai.reply,\n"
                 "  intent: ai.intent,\n"
                 "  reply_markup: replyMarkup,\n"
                 "  session_update: ai.session_update || {},\n"
                 "  user_id: ctx.user_id,\n"
                 "  session_data: ctx.session_data,\n"
                 "  message_count: ctx.message_count,\n"
                 "  confidence: ai.confidence\n"
                 "} }];"
             )}),

        # ── Save session ───────────────────────────────────
        node("sv2-pg-sess-02", "Save Session",
             "n8n-nodes-base.postgres", 2, [1560, 440], {
             "operation": "executeQuery",
             "query": (
                 "UPDATE sessions\n"
                 "SET session_data = '{{ JSON.stringify({ ...($json.session_data || {}), ...($json.session_update || {}), last_intent: $json.intent, last_msg_at: new Date().toISOString() }).replace(/'/g, \"''\") }}'::jsonb,\n"
                 "    active_workflow = '{{ $json.intent }}',\n"
                 "    updated_at = NOW()\n"
                 "WHERE user_id = {{ $json.user_id }}"
             ),
             "options": {}
             }, credentials={"postgres": {"id": "a20cebf1b1c648", "name": "AIOS PostgreSQL"}}),

        # ── Send Telegram reply ────────────────────────────
        node("sv2-http-tg-01", "Send Reply",
             "n8n-nodes-base.httpRequest", 4.2, [1780, 440], {
             "method": "POST",
             "url": f"{TG_API}/sendMessage",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": (
                 '={{ JSON.stringify({'
                 ' chat_id: $("Parse AI Response").item.json.chat_id,'
                 ' text: $("Parse AI Response").item.json.reply,'
                 ' parse_mode: "Markdown",'
                 ' reply_markup: $("Parse AI Response").item.json.reply_markup || undefined'
                 '}) }}'
             ),
             "options": {}})
    ]

    connections = {
        # Entry
        "Telegram Webhook": {"main": [[{"node": "Extract Message", "type": "main", "index": 0}]]},
        # Route through IF node
        "Extract Message": {"main": [[{"node": "Route Branch", "type": "main", "index": 0}]]},
        # IF true (isCallback) → callback path; IF false → message path
        "Route Branch": {"main": [
            [{"node": "Handle Callback", "type": "main", "index": 0}],  # output 0 = true
            [{"node": "Load Session",    "type": "main", "index": 0}]   # output 1 = false
        ]},
        # Callback path
        "Handle Callback":       {"main": [[{"node": "Answer Callback Query", "type": "main", "index": 0}]]},
        "Answer Callback Query": {"main": [[{"node": "Save Approval",         "type": "main", "index": 0}]]},
        "Save Approval":         {"main": [[{"node": "Send Callback Reply",   "type": "main", "index": 0}]]},
        # Message path
        "Load Session":          {"main": [[{"node": "Prepare AI Context",  "type": "main", "index": 0}]]},
        "Prepare AI Context":    {"main": [[{"node": "Call Supervisor AI",  "type": "main", "index": 0}]]},
        "Call Supervisor AI":    {"main": [[{"node": "Parse AI Response",   "type": "main", "index": 0}]]},
        "Parse AI Response":     {"main": [[{"node": "Save Session",        "type": "main", "index": 0}]]},
        "Save Session":          {"main": [[{"node": "Send Reply",          "type": "main", "index": 0}]]},
    }

    upsert_workflow(wf_id, "TELEGRAM__SUPERVISOR__V2",
                    nodes, connections, active=True,
                    webhook_path="aios-telegram-bot",
                    webhook_method="POST",
                    webhook_node_name="Telegram Webhook")
    return wf_id


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n=== AIOS Phase 2 — Building Workflows ===\n")

    print("[1] AI__OPENROUTER_GATEWAY__V1")
    build_openrouter_gateway()

    print("[2] MEMORY__SESSION_MANAGER__V1")
    build_session_manager()

    print("[3] AI__INTENT_CLASSIFIER__V1")
    build_intent_classifier()

    print("[4] APPROVAL__STATE_MANAGER__V1")
    build_approval_manager()

    print("[5] AI__WORKFLOW_ROUTER__V1")
    build_workflow_router()

    print("[6] TELEGRAM__SUPERVISOR__V2 (upgrade)")
    build_supervisor_v2()

    print("\n=== All workflows built ===")
    print("Restart n8n: docker restart n8n-n8n-1")
