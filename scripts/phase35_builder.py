#!/usr/bin/env python3
"""
Phase 3.5 Builder — Media Infrastructure Hardening Layer
Deploy: python3 scripts/phase35_builder.py
"""
import sqlite3, json, uuid, subprocess, sys, time

DB_PATH          = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID       = "0YzGnVQ4VzNb3gOx"
ERROR_HANDLER_ID = "99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2"
TG_TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
PG_CRED_ID       = "a20cebf1b1c648"
ADMIN_CHAT_ID    = 1241444951
TG_URL           = f"https://api.telegram.org/bot{TG_TOKEN}"
RENDERS_PATH     = "/files/renders"

_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
def _wid(k): return str(uuid.uuid5(_NS, f"aios/p35/{k}"))

WF = {
    "asset_ver":   _wid("asset_versioning"),
    "render_lock": _wid("render_locks"),
    "sub_val":     _wid("subtitle_validator"),
    "storage_mgr": _wid("storage_manager"),
    "queue_ctrl":  _wid("queue_controller"),
    "media_val":   _wid("media_validator"),
    "rdr_timeout": _wid("render_timeout"),
    "asset_rec":   _wid("asset_recovery"),
    "prev_cache":  _wid("preview_cache"),
    "disk_clean":  _wid("disk_cleanup"),
}

# ─── HELPERS ────────────────────────────────────────────────────────────────

def node(nid, name, ntype, ver, pos, params, cred_id=None, cred_name=None,
         continue_on_fail=False):
    n = {"id": nid, "name": name, "type": ntype, "typeVersion": ver,
         "position": pos, "parameters": params}
    if cred_id:
        n["credentials"] = {"postgres": {"id": cred_id, "name": cred_name}}
    if continue_on_fail:
        n["continueOnFail"] = True
    return n

def trigger(nid):
    return node(nid, "Execute Workflow Trigger",
                "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {})

def pg(nid, name, pos, query_expr, cfail=False):
    return node(nid, name, "n8n-nodes-base.postgres", 2, pos,
                {"operation": "executeQuery", "query": query_expr},
                PG_CRED_ID, "AIOS PostgreSQL", continue_on_fail=cfail)

def code(nid, name, pos, js):
    return node(nid, name, "n8n-nodes-base.code", 2, pos,
                {"jsCode": js, "mode": "runOnceForAllItems"})

def setn(nid, name, pos, assignments):
    return node(nid, name, "n8n-nodes-base.set", 3.4, pos,
                {"mode": "manual", "duplicateItem": False,
                 "assignments": {"assignments": assignments}})

def cmd(nid, name, pos, command_expr, cfail=True):
    return node(nid, name, "n8n-nodes-base.executeCommand", 1, pos,
                {"command": command_expr}, continue_on_fail=cfail)

def tg_alert(nid, name, pos):
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST",
        "url": f"{TG_URL}/sendMessage",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ chat_id: ' + str(ADMIN_CHAT_ID) + ', text: $json.alert_text || "⚠️ AIOS System Alert", parse_mode: "Markdown" }) }}',
        "options": {"response": {"response": {"neverError": True}}}
    })

def edge(src, dst, branch=0):
    return {src: {"main": [[{"node": dst, "type": "main", "index": branch}]]}}

def merge_edges(*edge_dicts):
    result = {}
    for d in edge_dicts:
        for k, v in d.items():
            if k in result:
                result[k]["main"].extend(v["main"])
            else:
                result[k] = v
    return result

def upsert_workflow(wf_id, name, nodes, edges, active=True):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id FROM workflow_entity WHERE name=? AND id!=?", (name, wf_id))
    for (old_id,) in cur.fetchall():
        for tbl in ["workflow_entity", "workflow_history", "shared_workflow"]:
            try:
                cur.execute(f"DELETE FROM {tbl} WHERE id=? OR workflowId=?",
                            (old_id, old_id))
            except Exception:
                pass
    now_ms = int(time.time() * 1000)
    settings = {"executionOrder": "v1", "errorWorkflow": ERROR_HANDLER_ID,
                "saveManualExecutions": True}
    cur.execute("""
        INSERT INTO workflow_entity
          (id,name,active,nodes,connections,createdAt,updatedAt,settings,staticData,pinData,versionId,triggerCount)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          name=excluded.name,active=excluded.active,nodes=excluded.nodes,
          connections=excluded.connections,updatedAt=excluded.updatedAt,
          settings=excluded.settings,versionId=excluded.versionId
    """, (wf_id, name, 1 if active else 0,
          json.dumps(nodes), json.dumps(edges),
          now_ms, now_ms, json.dumps(settings), "null", "{}", wf_id, 0))
    cur.execute("""
        INSERT OR REPLACE INTO workflow_history
          (versionId,workflowId,authors,createdAt,updatedAt,nodes,connections)
        VALUES (?,?,?,?,?,?,?)
    """, (wf_id, wf_id, "AIOS Builder", now_ms, now_ms,
          json.dumps(nodes), json.dumps(edges)))
    cur.execute("""
        INSERT OR IGNORE INTO shared_workflow
          (workflowId,projectId,role,createdAt,updatedAt)
        VALUES (?,?,?,?,?)
    """, (wf_id, PROJECT_ID, "workflow:owner", now_ms, now_ms))
    con.commit()
    con.close()
    print(f"  ✓ {name}")

# ─── SQL MIGRATION ──────────────────────────────────────────────────────────

def run_migration():
    print("\n[1] Running SQL migration...")
    stmts = [
        """CREATE TABLE IF NOT EXISTS render_locks (
            id SERIAL PRIMARY KEY,
            render_id VARCHAR(100) UNIQUE NOT NULL,
            user_id BIGINT,
            acquired_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '15 minutes')
        )""",
        """CREATE TABLE IF NOT EXISTS render_queue (
            id SERIAL PRIMARY KEY,
            render_id VARCHAR(100) UNIQUE NOT NULL,
            user_id BIGINT,
            script_id INTEGER,
            priority INTEGER DEFAULT 5,
            status VARCHAR(50) DEFAULT 'queued',
            queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS render_versions (
            id SERIAL PRIMARY KEY,
            asset_id VARCHAR(100) NOT NULL,
            asset_type VARCHAR(50) NOT NULL,
            version_number INTEGER DEFAULT 1,
            file_path TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            is_original BOOLEAN DEFAULT FALSE,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS preview_cache (
            id SERIAL PRIMARY KEY,
            cache_key VARCHAR(200) UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            asset_type VARCHAR(50),
            metadata JSONB NOT NULL DEFAULT '{}',
            expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours'),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS storage_alerts (
            id SERIAL PRIMARY KEY,
            disk_percent INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL,
            freed_mb INTEGER DEFAULT 0,
            alert_sent BOOLEAN DEFAULT FALSE,
            recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS render_timeouts (
            id SERIAL PRIMARY KEY,
            render_id VARCHAR(100) NOT NULL,
            user_id BIGINT,
            timeout_minutes INTEGER DEFAULT 10,
            detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            resolved BOOLEAN DEFAULT FALSE,
            resolved_at TIMESTAMP WITH TIME ZONE
        )""",
        """CREATE TABLE IF NOT EXISTS corrupted_assets (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            render_id VARCHAR(100),
            corruption_type VARCHAR(100),
            details JSONB NOT NULL DEFAULT '{}',
            detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            quarantined BOOLEAN DEFAULT FALSE
        )""",
        """CREATE TABLE IF NOT EXISTS recovery_events (
            id SERIAL PRIMARY KEY,
            render_id VARCHAR(100),
            user_id BIGINT,
            event_type VARCHAR(100) NOT NULL,
            before_state JSONB NOT NULL DEFAULT '{}',
            after_state JSONB NOT NULL DEFAULT '{}',
            success BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )"""
    ]
    for stmt in stmts:
        result = subprocess.run(
            ["docker", "exec", "aios-postgres", "psql",
             "-U", "aios_user", "-d", "aios_db", "-c", stmt],
            capture_output=True, text=True
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"  ✗ Migration error: {result.stderr[:200]}")
            sys.exit(1)
    print("  ✓ 8 tables created")

# ─── WORKFLOW 1 — ASSET VERSIONING ──────────────────────────────────────────

def build_asset_versioning():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    gv = pg(nid(), "Get Current Version", [460, 300],
        '={{ "SELECT COALESCE(MAX(version_number),0) AS max_ver FROM render_versions WHERE asset_id=\'" + ($json.asset_id||"").replace(/\'/g,"\'\'") + "\'" }}')
    cv = code(nid(), "Calculate New Version", [680, 300], """
const items = $input.all();
const maxVer = parseInt(items[0]?.json?.max_ver || 0);
const newVer = maxVer + 1;
const assetId = $('Execute Workflow Trigger').item.json.asset_id || '';
const assetType = $('Execute Workflow Trigger').item.json.asset_type || 'render';
const filePath = $('Execute Workflow Trigger').item.json.file_path || '';
const userId = $('Execute Workflow Trigger').item.json.user_id || 0;
const safe = s => (s+'').replace(/'/g,"''");
const isOriginal = newVer === 1;
const query = "INSERT INTO render_versions (asset_id,asset_type,version_number,file_path,is_active,is_original) VALUES ('" + safe(assetId) + "','" + safe(assetType) + "'," + newVer + ",'" + safe(filePath) + "',true," + isOriginal + ") RETURNING id,version_number";
return [{ json: { query, asset_id: assetId, version_number: newVer, file_path: filePath, asset_type: assetType } }];
""")
    sv = pg(nid(), "Save Version", [900, 300],
        '={{ $json.query }}')
    rt = setn(nid(), "Return Version", [1120, 300], [
        {"id": "r1", "name": "version_id",     "value": '={{ $json.id }}',             "type": "number"},
        {"id": "r2", "name": "version_number", "value": '={{ $json.version_number }}', "type": "number"},
        {"id": "r3", "name": "asset_id",       "value": '={{ $("Calculate New Version").item.json.asset_id }}', "type": "string"},
        {"id": "r4", "name": "file_path",      "value": '={{ $("Calculate New Version").item.json.file_path }}', "type": "string"},
        {"id": "r5", "name": "asset_type",     "value": '={{ $("Calculate New Version").item.json.asset_type }}', "type": "string"},
    ])
    nodes = [t, gv, cv, sv, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Get Current Version", "type": "main", "index": 0}]]},
             "Get Current Version":      {"main": [[{"node": "Calculate New Version","type": "main", "index": 0}]]},
             "Calculate New Version":    {"main": [[{"node": "Save Version",         "type": "main", "index": 0}]]},
             "Save Version":             {"main": [[{"node": "Return Version",        "type": "main", "index": 0}]]}}
    upsert_workflow(WF["asset_ver"], "SYSTEM__ASSET_VERSIONING__V1", nodes, edges)

# ─── WORKFLOW 2 — RENDER LOCK SYSTEM ────────────────────────────────────────

def build_render_locks():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())
    bq  = code(nid(), "Build Lock Query", [460, 300], """
const action = $json.action || 'acquire';
const renderId = ($json.render_id||'').replace(/'/g,"''");
const userId = parseInt($json.user_id||0);
let query = '', result_action = action;
if (action === 'acquire') {
  query = "INSERT INTO render_locks (render_id,user_id) VALUES ('" + renderId + "'," + userId + ") ON CONFLICT(render_id) DO NOTHING RETURNING id,render_id";
} else if (action === 'release') {
  query = "DELETE FROM render_locks WHERE render_id='" + renderId + "' RETURNING render_id";
} else {
  query = "DELETE FROM render_locks WHERE expires_at < NOW() RETURNING render_id";
}
return [{ json: { query, action: result_action, render_id: renderId } }];
""")
    rq  = pg(nid(), "Execute Lock Query", [680, 300], '={{ $json.query }}', cfail=True)
    rt  = code(nid(), "Return Lock Result", [900, 300], """
const action = $('Build Lock Query').item.json.action;
const render_id = $('Build Lock Query').item.json.render_id;
const rows = $input.all();
let success = rows.length > 0;
let message = '';
if (action === 'acquire') {
  message = success ? 'Lock acquired' : 'Already locked';
} else if (action === 'release') {
  message = success ? 'Lock released' : 'Lock not found';
} else {
  message = 'Cleaned ' + rows.length + ' stale locks';
}
return [{ json: { success, action, render_id, message } }];
""")
    nodes = [t, bq, rq, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Build Lock Query",   "type": "main", "index": 0}]]},
             "Build Lock Query":         {"main": [[{"node": "Execute Lock Query", "type": "main", "index": 0}]]},
             "Execute Lock Query":       {"main": [[{"node": "Return Lock Result", "type": "main", "index": 0}]]}}
    upsert_workflow(WF["render_lock"], "SYSTEM__RENDER_LOCKS__V1", nodes, edges)

# ─── WORKFLOW 3 — SUBTITLE SYNC VALIDATOR ───────────────────────────────────

def build_subtitle_validator():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    vl = code(nid(), "Validate Subtitles", [460, 300], """
const subs = $json.subtitles || [];
const renderId = $json.render_id || '';
const errors = [];
let prevEnd = 0;
for (let i = 0; i < subs.length; i++) {
  const s = subs[i];
  if (typeof s.start !== 'number' || typeof s.end !== 'number') {
    errors.push('Sub ' + i + ': start/end must be numbers');
    continue;
  }
  if (s.start < 0 || s.end < 0) {
    errors.push('Sub ' + i + ': negative timestamp');
  }
  if (s.end <= s.start) {
    errors.push('Sub ' + i + ': end must be after start');
  }
  if (s.start < prevEnd) {
    errors.push('Sub ' + i + ': overlaps previous subtitle');
  }
  const dur = s.end - s.start;
  if (dur < 0.5) {
    errors.push('Sub ' + i + ': duration < 0.5s (unreadable on mobile)');
  }
  if (dur > 7) {
    errors.push('Sub ' + i + ': duration > 7s (too long)');
  }
  const text = (s.text||'').trim();
  if (!text) {
    errors.push('Sub ' + i + ': empty text');
  }
  try { decodeURIComponent(encodeURIComponent(text)); } catch(e) {
    errors.push('Sub ' + i + ': not valid UTF-8');
  }
  prevEnd = s.end;
}
const valid = errors.length === 0;
const safe = s => (s+'').replace(/'/g,"''");
const query = valid
  ? "SELECT 1"
  : "INSERT INTO corrupted_assets (file_path,corruption_type,details) VALUES ('subtitle_" + safe(renderId) + "','subtitle_validation','" + safe(JSON.stringify({errors,render_id:renderId})) + "')";
return [{ json: { valid, errors, render_id: renderId, subtitle_count: subs.length, query } }];
""")
    sv = pg(nid(), "Save Validation Result", [680, 300], '={{ $json.query }}', cfail=True)
    rt = setn(nid(), "Return Result", [900, 300], [
        {"id": "r1", "name": "valid",          "value": '={{ $("Validate Subtitles").item.json.valid }}',          "type": "boolean"},
        {"id": "r2", "name": "errors",         "value": '={{ $("Validate Subtitles").item.json.errors }}',         "type": "array"},
        {"id": "r3", "name": "render_id",      "value": '={{ $("Validate Subtitles").item.json.render_id }}',      "type": "string"},
        {"id": "r4", "name": "subtitle_count", "value": '={{ $("Validate Subtitles").item.json.subtitle_count }}', "type": "number"},
    ])
    nodes = [t, vl, sv, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Validate Subtitles",      "type": "main", "index": 0}]]},
             "Validate Subtitles":       {"main": [[{"node": "Save Validation Result",  "type": "main", "index": 0}]]},
             "Save Validation Result":   {"main": [[{"node": "Return Result",           "type": "main", "index": 0}]]}}
    upsert_workflow(WF["sub_val"], "SYSTEM__SUBTITLE_VALIDATOR__V1", nodes, edges)

# ─── WORKFLOW 4 — STORAGE MANAGER ───────────────────────────────────────────

def build_storage_manager():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())
    dc  = cmd(nid(), "Check Disk", [460, 300],
        f"df -h {RENDERS_PATH} | tail -1 | awk '{{print $5}}' | tr -d '%'", cfail=True)
    pd  = code(nid(), "Parse Disk Usage", [680, 300], """
const raw = ($json.stdout || '').trim();
const pct = parseInt(raw) || 0;
const warn = parseInt($('Execute Workflow Trigger').item.json.threshold_warn || 80);
const emergency = parseInt($('Execute Workflow Trigger').item.json.threshold_emergency || 90);
let status = 'ok';
if (pct >= emergency) status = 'emergency';
else if (pct >= warn) status = 'warn';
const safe = s => (s+'').replace(/'/g,"''");
const alert_text = status !== 'ok'
  ? '*⚠️ AIOS Storage Alert*\\n' + (status==='emergency'?'🔴 EMERGENCY':'🟡 WARNING') + ': Disk at ' + pct + '%'
  : '';
return [{ json: { disk_percent: pct, status, warn_threshold: warn, emergency_threshold: emergency, alert_text,
  log_query: "INSERT INTO storage_alerts (disk_percent,status) VALUES (" + pct + ",'" + safe(status) + "')" } }];
""")
    ifg = node(nid(), "Needs Alert?", "n8n-nodes-base.if", 2, [900, 300], {
        "conditions": {"options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                       "conditions": [{"id": "c1", "leftValue": '={{ $json.status }}', "rightValue": "ok",
                                       "operator": {"type": "string", "operation": "notEquals"}}],
                       "combinator": "and"}})
    al  = tg_alert(nid(), "Send Storage Alert", [1120, 200])
    lg  = pg(nid(), "Log Storage Status", [1120, 400], '={{ $json.log_query }}', cfail=True)
    rt  = setn(nid(), "Return Status", [1340, 300], [
        {"id": "r1", "name": "disk_percent", "value": '={{ $("Parse Disk Usage").item.json.disk_percent }}', "type": "number"},
        {"id": "r2", "name": "status",       "value": '={{ $("Parse Disk Usage").item.json.status }}',       "type": "string"},
    ])
    nodes = [t, dc, pd, ifg, al, lg, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Check Disk",        "type": "main", "index": 0}]]},
             "Check Disk":               {"main": [[{"node": "Parse Disk Usage",  "type": "main", "index": 0}]]},
             "Parse Disk Usage":         {"main": [[{"node": "Needs Alert?",      "type": "main", "index": 0}]]},
             "Needs Alert?":             {"main": [[{"node": "Send Storage Alert","type": "main", "index": 0}],
                                                   [{"node": "Log Storage Status","type": "main", "index": 0}]]},
             "Send Storage Alert":       {"main": [[{"node": "Log Storage Status","type": "main", "index": 0}]]},
             "Log Storage Status":       {"main": [[{"node": "Return Status",     "type": "main", "index": 0}]]}}
    upsert_workflow(WF["storage_mgr"], "SYSTEM__STORAGE_MANAGER__V1", nodes, edges)

# ─── WORKFLOW 5 — QUEUE CONCURRENCY CONTROLLER ──────────────────────────────

def build_queue_controller():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    bq = code(nid(), "Build Queue Query", [460, 300], """
const action = $json.action || 'status';
const renderId = ($json.render_id||'unknown_'+Date.now()).replace(/'/g,"''");
const userId = parseInt($json.user_id||0);
const priority = parseInt($json.priority||5);
const maxConcurrent = parseInt($json.max_concurrent||2);
let query = '', countQuery = "SELECT COUNT(*) AS active FROM render_queue WHERE status='rendering'";
if (action === 'enqueue') {
  query = "INSERT INTO render_queue (render_id,user_id,priority) VALUES ('" + renderId + "'," + userId + "," + priority + ") ON CONFLICT(render_id) DO NOTHING RETURNING id,render_id";
} else if (action === 'dequeue') {
  query = "UPDATE render_queue SET status='rendering',started_at=NOW() WHERE id=(SELECT id FROM render_queue WHERE status='queued' ORDER BY priority DESC,queued_at ASC LIMIT 1) RETURNING id,render_id,user_id";
} else if (action === 'complete') {
  query = "UPDATE render_queue SET status='done',completed_at=NOW() WHERE render_id='" + renderId + "' RETURNING render_id";
} else if (action === 'fail') {
  const errMsg = ($json.error_message||'unknown error').replace(/'/g,"''");
  query = "UPDATE render_queue SET status='failed',completed_at=NOW(),error_message='" + errMsg + "' WHERE render_id='" + renderId + "' RETURNING render_id";
} else {
  query = countQuery;
}
return [{ json: { query, countQuery, action, render_id: renderId, max_concurrent: maxConcurrent } }];
""")
    ca = pg(nid(), "Count Active Renders", [680, 200], '={{ $json.countQuery }}')
    eq = pg(nid(), "Execute Queue Action", [680, 400], '={{ $json.query }}', cfail=True)
    rt = code(nid(), "Return Queue State", [900, 300], """
const action = $('Build Queue Query').item.json.action;
const maxConcurrent = $('Build Queue Query').item.json.max_concurrent;
const activeRows = $('Count Active Renders').all();
const active = parseInt(activeRows[0]?.json?.active || 0);
const can_start = active < maxConcurrent;
const actionRows = $('Execute Queue Action').all();
const success = actionRows.length > 0;
return [{ json: { success, action, active_renders: active, max_concurrent: maxConcurrent, can_start, queue_result: actionRows[0]?.json || {} } }];
""")
    nodes = [t, bq, ca, eq, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Build Queue Query",    "type": "main", "index": 0}]]},
             "Build Queue Query":        {"main": [[{"node": "Count Active Renders", "type": "main", "index": 0},
                                                    {"node": "Execute Queue Action", "type": "main", "index": 0}]]},
             "Count Active Renders":     {"main": [[{"node": "Return Queue State",   "type": "main", "index": 0}]]},
             "Execute Queue Action":     {"main": [[{"node": "Return Queue State",   "type": "main", "index": 0}]]}}
    upsert_workflow(WF["queue_ctrl"], "SYSTEM__QUEUE_CONTROLLER__V1", nodes, edges)

# ─── WORKFLOW 6 — MEDIA INTEGRITY VALIDATOR ─────────────────────────────────

def build_media_validator():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    fp = cmd(nid(), "Run ffprobe", [460, 300],
        '={{ "ffprobe -v quiet -print_format json -show_streams -show_format " + $json.file_path }}', cfail=True)
    pf = code(nid(), "Parse ffprobe Output", [680, 300], """
const renderId = $('Execute Workflow Trigger').item.json.render_id || '';
const filePath = $('Execute Workflow Trigger').item.json.file_path || '';
const safe = s => (s+'').replace(/'/g,"''");
let valid = false, errors = [], format = '', duration = 0, resolution = '', has_audio = false;
try {
  const raw = $json.stdout || '';
  const probe = JSON.parse(raw);
  const streams = probe.streams || [];
  const fmt = probe.format || {};
  duration = parseFloat(fmt.duration || 0);
  format = fmt.format_name || '';
  const videoStream = streams.find(s => s.codec_type === 'video');
  const audioStream = streams.find(s => s.codec_type === 'audio');
  has_audio = !!audioStream;
  if (videoStream) {
    resolution = videoStream.width + 'x' + videoStream.height;
  }
  if (!videoStream) errors.push('No video stream found');
  if (duration < 1) errors.push('Duration < 1 second');
  if (duration > 300) errors.push('Duration > 5 minutes');
  if (videoStream && videoStream.width !== 1080) errors.push('Width not 1080px');
  if (videoStream && videoStream.height !== 1920) errors.push('Height not 1920px');
  valid = errors.length === 0;
} catch(e) {
  errors.push('ffprobe parse failed: ' + e.message);
  valid = false;
}
let dbQuery = "SELECT 1";
if (!valid) {
  dbQuery = "INSERT INTO corrupted_assets (file_path,render_id,corruption_type,details) VALUES ('" + safe(filePath) + "','" + safe(renderId) + "','integrity_check','" + safe(JSON.stringify({errors})) + "')";
}
return [{ json: { valid, errors, format, duration, resolution, has_audio, render_id: renderId, file_path: filePath, db_query: dbQuery } }];
""")
    sv = pg(nid(), "Save Validation Result", [900, 300], '={{ $json.db_query }}', cfail=True)
    rt = setn(nid(), "Return Validation", [1120, 300], [
        {"id": "r1", "name": "valid",      "value": '={{ $("Parse ffprobe Output").item.json.valid }}',      "type": "boolean"},
        {"id": "r2", "name": "errors",     "value": '={{ $("Parse ffprobe Output").item.json.errors }}',     "type": "array"},
        {"id": "r3", "name": "duration",   "value": '={{ $("Parse ffprobe Output").item.json.duration }}',   "type": "number"},
        {"id": "r4", "name": "resolution", "value": '={{ $("Parse ffprobe Output").item.json.resolution }}', "type": "string"},
        {"id": "r5", "name": "has_audio",  "value": '={{ $("Parse ffprobe Output").item.json.has_audio }}',  "type": "boolean"},
    ])
    nodes = [t, fp, pf, sv, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Run ffprobe",            "type": "main", "index": 0}]]},
             "Run ffprobe":              {"main": [[{"node": "Parse ffprobe Output",    "type": "main", "index": 0}]]},
             "Parse ffprobe Output":     {"main": [[{"node": "Save Validation Result",  "type": "main", "index": 0}]]},
             "Save Validation Result":   {"main": [[{"node": "Return Validation",       "type": "main", "index": 0}]]}}
    upsert_workflow(WF["media_val"], "SYSTEM__MEDIA_VALIDATOR__V1", nodes, edges)

# ─── WORKFLOW 7 — RENDER TIMEOUT PROTECTION ─────────────────────────────────

def build_render_timeout():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    fs = pg(nid(), "Find Stale Renders", [460, 300],
        '={{ "SELECT render_id,user_id FROM render_queue WHERE status=\'rendering\' AND started_at < NOW() - INTERVAL \'" + ($json.timeout_minutes||10) + " minutes\'" }}')
    pr = code(nid(), "Prepare Timeout Actions", [680, 300], """
const items = $input.all();
const stale = items.filter(i => i.json && i.json.render_id);
if (stale.length === 0) {
  return [{ json: { timed_out_count: 0, render_ids: [], alert_text: '', update_query: 'SELECT 1' } }];
}
const ids = stale.map(i => "'" + i.json.render_id.replace(/'/g,"''") + "'").join(',');
const update_query = "UPDATE render_queue SET status='timeout',completed_at=NOW() WHERE render_id IN (" + ids + ")";
const lock_query = "DELETE FROM render_locks WHERE render_id IN (" + ids + ")";
const insert_query = stale.map(i => "INSERT INTO render_timeouts (render_id,user_id) VALUES ('" + i.json.render_id.replace(/'/g,"''") + "'," + (i.json.user_id||0) + ")").join('; ');
const alert_text = '*⚠️ AIOS Render Timeout*\\nDetected ' + stale.length + ' hung render(s):\\n' + stale.map(i => '`' + i.json.render_id + '`').join(', ');
return [{ json: { timed_out_count: stale.length, render_ids: stale.map(i=>i.json.render_id), alert_text, update_query, lock_query: lock_query, insert_query } }];
""")
    uq = pg(nid(), "Mark Jobs Timed Out",  [900, 200], '={{ $json.update_query }}', cfail=True)
    lq = pg(nid(), "Release Stale Locks",  [900, 300], '={{ $json.lock_query }}',   cfail=True)
    iq = pg(nid(), "Insert Timeout Events", [900, 400], '={{ $json.insert_query }}', cfail=True)
    al = tg_alert(nid(), "Alert Admin", [1120, 200])
    rt = setn(nid(), "Return Summary", [1340, 300], [
        {"id": "r1", "name": "timed_out_count", "value": '={{ $("Prepare Timeout Actions").item.json.timed_out_count }}', "type": "number"},
        {"id": "r2", "name": "render_ids",      "value": '={{ $("Prepare Timeout Actions").item.json.render_ids }}',      "type": "array"},
    ])
    nodes = [t, fs, pr, uq, lq, iq, al, rt]
    edges = {"Execute Workflow Trigger":  {"main": [[{"node": "Find Stale Renders",      "type": "main", "index": 0}]]},
             "Find Stale Renders":        {"main": [[{"node": "Prepare Timeout Actions", "type": "main", "index": 0}]]},
             "Prepare Timeout Actions":   {"main": [[{"node": "Mark Jobs Timed Out",     "type": "main", "index": 0},
                                                     {"node": "Release Stale Locks",     "type": "main", "index": 0},
                                                     {"node": "Insert Timeout Events",   "type": "main", "index": 0}]]},
             "Mark Jobs Timed Out":       {"main": [[{"node": "Alert Admin",             "type": "main", "index": 0}]]},
             "Release Stale Locks":       {"main": [[{"node": "Alert Admin",             "type": "main", "index": 0}]]},
             "Insert Timeout Events":     {"main": [[{"node": "Alert Admin",             "type": "main", "index": 0}]]},
             "Alert Admin":               {"main": [[{"node": "Return Summary",          "type": "main", "index": 0}]]}}
    upsert_workflow(WF["rdr_timeout"], "SYSTEM__RENDER_TIMEOUT__V1", nodes, edges)

# ─── WORKFLOW 8 — ASSET RECOVERY SYSTEM ─────────────────────────────────────

def build_asset_recovery():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    gi = pg(nid(), "Get Interrupted Renders", [460, 300],
        '={{ "SELECT render_id,user_id FROM render_queue WHERE status IN (\'rendering\',\'queued\') AND queued_at < NOW() - INTERVAL \'1 hour\'" + ($json.user_id ? " AND user_id=" + parseInt($json.user_id) : "") }}')
    cf = code(nid(), "Build File Check Commands", [680, 300], """
const items = $input.all();
const renders = items.filter(i => i.json && i.json.render_id);
if (renders.length === 0) {
  return [{ json: { check_cmd: 'echo "no_renders"', renders: [], recovery_queries: [] } }];
}
const paths = renders.map(r => '/files/renders/temp/' + r.json.render_id + '.mp4');
const check_cmd = 'for f in ' + paths.join(' ') + '; do [ -f "$f" ] && echo "FOUND:$f" || echo "MISSING:$f"; done';
const safe = s => (s+'').replace(/'/g,"''");
const recovery_queries = renders.map(r =>
  "INSERT INTO recovery_events (render_id,user_id,event_type,success) VALUES ('" +
  safe(r.json.render_id) + "'," + (r.json.user_id||0) + ",'interrupted_render_detected',false)"
);
return [{ json: { check_cmd, renders: renders.map(r=>r.json), recovery_queries } }];
""")
    fc = cmd(nid(), "Check Files Exist", [900, 300],
        '={{ $json.check_cmd }}', cfail=True)
    pr = code(nid(), "Categorize Recovery", [1120, 300], """
const fileOutput = ($json.stdout || '').trim().split('\\n');
const renders = $('Build File Check Commands').item.json.renders || [];
const recovered = [], missing = [];
fileOutput.forEach(line => {
  if (line.startsWith('FOUND:')) recovered.push(line.replace('FOUND:',''));
  else if (line.startsWith('MISSING:')) missing.push(line.replace('MISSING:',''));
});
const safe = s => (s+'').replace(/'/g,"''");
let updateQuery = 'SELECT 1';
if (recovered.length > 0) {
  const ids = recovered.map(p => "'" + safe(p.replace('/files/renders/temp/','').replace('.mp4','')) + "'").join(',');
  updateQuery = "UPDATE render_queue SET status='recoverable' WHERE render_id IN (" + ids + ")";
}
return [{ json: { recovered_count: recovered.length, missing_count: missing.length, recovered, missing, update_query: updateQuery } }];
""")
    uq = pg(nid(), "Mark Recoverable", [1340, 300], '={{ $json.update_query }}', cfail=True)
    rt = setn(nid(), "Return Recovery Report", [1560, 300], [
        {"id": "r1", "name": "recovered_count", "value": '={{ $("Categorize Recovery").item.json.recovered_count }}', "type": "number"},
        {"id": "r2", "name": "missing_count",   "value": '={{ $("Categorize Recovery").item.json.missing_count }}',   "type": "number"},
        {"id": "r3", "name": "recovered",       "value": '={{ $("Categorize Recovery").item.json.recovered }}',       "type": "array"},
    ])
    nodes = [t, gi, cf, fc, pr, uq, rt]
    edges = {"Execute Workflow Trigger":   {"main": [[{"node": "Get Interrupted Renders",   "type": "main", "index": 0}]]},
             "Get Interrupted Renders":    {"main": [[{"node": "Build File Check Commands", "type": "main", "index": 0}]]},
             "Build File Check Commands":  {"main": [[{"node": "Check Files Exist",         "type": "main", "index": 0}]]},
             "Check Files Exist":          {"main": [[{"node": "Categorize Recovery",       "type": "main", "index": 0}]]},
             "Categorize Recovery":        {"main": [[{"node": "Mark Recoverable",          "type": "main", "index": 0}]]},
             "Mark Recoverable":           {"main": [[{"node": "Return Recovery Report",    "type": "main", "index": 0}]]}}
    upsert_workflow(WF["asset_rec"], "SYSTEM__ASSET_RECOVERY__V1", nodes, edges)

# ─── WORKFLOW 9 — PREVIEW CACHE SYSTEM ──────────────────────────────────────

def build_preview_cache():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    bq = code(nid(), "Build Cache Query", [460, 300], """
const action = $json.action || 'retrieve';
const cacheKey = ($json.cache_key||'').replace(/'/g,"''");
const filePath = ($json.file_path||'').replace(/'/g,"''");
const assetType = ($json.asset_type||'preview').replace(/'/g,"''");
const metaStr = JSON.stringify($json.metadata||{}).replace(/'/g,"''");
let query = '', is_write = false;
if (action === 'store') {
  query = "INSERT INTO preview_cache (cache_key,file_path,asset_type,metadata) VALUES ('" + cacheKey + "','" + filePath + "','" + assetType + "','" + metaStr + "') ON CONFLICT(cache_key) DO UPDATE SET file_path=excluded.file_path,metadata=excluded.metadata,expires_at=NOW()+INTERVAL '24 hours' RETURNING id,cache_key,file_path";
  is_write = true;
} else if (action === 'invalidate') {
  query = "DELETE FROM preview_cache WHERE cache_key='" + cacheKey + "' RETURNING cache_key";
} else {
  query = "SELECT cache_key,file_path,asset_type,metadata FROM preview_cache WHERE cache_key='" + cacheKey + "' AND expires_at > NOW()";
}
return [{ json: { query, action, cache_key: cacheKey, is_write } }];
""")
    eq = pg(nid(), "Execute Cache Query", [680, 300], '={{ $json.query }}', cfail=True)
    rt = code(nid(), "Return Cache Result", [900, 300], """
const action = $('Build Cache Query').item.json.action;
const cache_key = $('Build Cache Query').item.json.cache_key;
const rows = $input.all();
const hit = rows.length > 0 && rows[0].json && rows[0].json.cache_key;
const result = hit ? rows[0].json : {};
return [{ json: { hit, action, cache_key, file_path: result.file_path||'', metadata: result.metadata||{} } }];
""")
    nodes = [t, bq, eq, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Build Cache Query",   "type": "main", "index": 0}]]},
             "Build Cache Query":        {"main": [[{"node": "Execute Cache Query", "type": "main", "index": 0}]]},
             "Execute Cache Query":      {"main": [[{"node": "Return Cache Result", "type": "main", "index": 0}]]}}
    upsert_workflow(WF["prev_cache"], "SYSTEM__PREVIEW_CACHE__V1", nodes, edges)

# ─── WORKFLOW 10 — DISK CLEANUP AUTOMATION ──────────────────────────────────

def build_disk_cleanup():
    nid = lambda: str(uuid.uuid4())
    t  = trigger(nid())
    ge = pg(nid(), "Get Expired Items", [460, 300],
        '={{ "SELECT id,file_path FROM preview_cache WHERE expires_at < NOW() LIMIT 100" }}')
    gc = pg(nid(), "Get Old Renders",  [460, 500],
        '={{ "SELECT r.id,r.render_id FROM render_queue r WHERE r.status IN (\'done\',\'failed\',\'timeout\') AND r.completed_at < NOW() - INTERVAL \'" + ($("Execute Workflow Trigger").item.json.max_age_hours||168) + " hours\' LIMIT 50" }}')
    bc = code(nid(), "Build Cleanup Commands", [680, 400], """
const dry_run = $('Execute Workflow Trigger').item.json.dry_run === true;
const expired = $('Get Expired Items').all().map(i => i.json).filter(i => i && i.file_path);
const old_renders = $('Get Old Renders').all().map(i => i.json).filter(i => i && i.render_id);
const files_to_delete = expired.map(i => i.file_path);
const render_paths = old_renders.map(i => '/files/renders/temp/' + i.render_id + '.mp4 /files/renders/previews/' + i.render_id + '.jpg');
const all_paths = [...files_to_delete, ...render_paths].join(' ');
const delete_cmd = dry_run ? 'echo "DRY_RUN: would delete ' + (expired.length + old_renders.length) + ' items"' : ('rm -f ' + all_paths + ' 2>/dev/null; echo "DELETED"');
const safe = s => (s+'').replace(/'/g,"''");
const expired_ids = expired.map(i=>i.id).filter(Boolean);
const render_ids = old_renders.map(i=>"'" + safe(i.render_id) + "'").filter(Boolean);
const db_cleanup_1 = expired_ids.length > 0 ? "DELETE FROM preview_cache WHERE id IN (" + expired_ids.join(',') + ")" : "SELECT 1";
const db_cleanup_2 = render_ids.length > 0 ? "DELETE FROM render_queue WHERE render_id IN (" + render_ids.join(',') + ") AND status IN ('done','failed','timeout')" : "SELECT 1";
return [{ json: { delete_cmd, db_cleanup_1, db_cleanup_2, dry_run, items_count: expired.length + old_renders.length } }];
""")
    fc = cmd(nid(), "Delete Files", [900, 300], '={{ $json.delete_cmd }}', cfail=True)
    d1 = pg(nid(), "Cleanup Cache DB",   [900, 400], '={{ $json.db_cleanup_1 }}', cfail=True)
    d2 = pg(nid(), "Cleanup Renders DB", [900, 500], '={{ $json.db_cleanup_2 }}', cfail=True)
    rt = setn(nid(), "Return Summary", [1120, 400], [
        {"id": "r1", "name": "items_cleaned", "value": '={{ $("Build Cleanup Commands").item.json.items_count }}', "type": "number"},
        {"id": "r2", "name": "dry_run",       "value": '={{ $("Build Cleanup Commands").item.json.dry_run }}',     "type": "boolean"},
    ])
    nodes = [t, ge, gc, bc, fc, d1, d2, rt]
    edges = {"Execute Workflow Trigger": {"main": [[{"node": "Get Expired Items",       "type": "main", "index": 0},
                                                    {"node": "Get Old Renders",         "type": "main", "index": 0}]]},
             "Get Expired Items":        {"main": [[{"node": "Build Cleanup Commands",  "type": "main", "index": 0}]]},
             "Get Old Renders":          {"main": [[{"node": "Build Cleanup Commands",  "type": "main", "index": 0}]]},
             "Build Cleanup Commands":   {"main": [[{"node": "Delete Files",            "type": "main", "index": 0},
                                                    {"node": "Cleanup Cache DB",        "type": "main", "index": 0},
                                                    {"node": "Cleanup Renders DB",      "type": "main", "index": 0}]]},
             "Delete Files":             {"main": [[{"node": "Return Summary",          "type": "main", "index": 0}]]},
             "Cleanup Cache DB":         {"main": [[{"node": "Return Summary",          "type": "main", "index": 0}]]},
             "Cleanup Renders DB":       {"main": [[{"node": "Return Summary",          "type": "main", "index": 0}]]}}
    upsert_workflow(WF["disk_clean"], "SYSTEM__DISK_CLEANUP__V1", nodes, edges)

# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("AIOS Phase 3.5 — Media Infrastructure Hardening")
    print("=" * 50)

    run_migration()

    print("\n[2] Deploying 10 infrastructure workflows...")
    build_asset_versioning()
    build_render_locks()
    build_subtitle_validator()
    build_storage_manager()
    build_queue_controller()
    build_media_validator()
    build_render_timeout()
    build_asset_recovery()
    build_preview_cache()
    build_disk_cleanup()

    print("\n[3] Restarting n8n...")
    subprocess.run(
        ["docker", "compose", "-f", "/docker/n8n/docker-compose.yml", "restart", "n8n"],
        check=True
    )
    print("  ✓ n8n restarted")

    print("\n[4] Verifying...")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM workflow_entity WHERE active=1")
    total = cur.fetchone()[0]
    con.close()
    result = subprocess.run(
        ["docker", "exec", "aios-postgres", "psql", "-U", "aios_user",
         "-d", "aios_db", "-c",
         "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"],
        capture_output=True, text=True
    )
    table_count = result.stdout.strip().split('\n')[2].strip() if result.returncode == 0 else "?"
    print(f"  ✓ {total} workflows active")
    print(f"  ✓ {table_count} database tables")
    print("\n✅ Phase 3.5 complete — Media Infrastructure Hardened")
    print("\nWorkflow IDs:")
    for k, v in WF.items():
        print(f"  {k:14} {v}")

if __name__ == "__main__":
    main()
