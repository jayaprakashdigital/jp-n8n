#!/usr/bin/env python3
"""
Phase 4 Builder — Media Rendering Engine
Deploy: python3 scripts/phase4_builder.py
"""
import sqlite3, json, uuid, subprocess, sys, time, os

DB_PATH          = "/var/lib/docker/volumes/n8n_data/_data/database.sqlite"
PROJECT_ID       = "0YzGnVQ4VzNb3gOx"
ERROR_HANDLER_ID = "99d7c9f8-c45c-46ff-9d5b-7df67c15ebf2"
TG_TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
PG_CRED_ID       = "a20cebf1b1c648"
ADMIN_CHAT_ID    = 1241444951
TG_URL           = f"https://api.telegram.org/bot{TG_TOKEN}"
RENDERS_PATH     = "/files/renders"
FONT_TAMIL       = "/usr/local/share/fonts/NotoSansTamil-Regular.ttf"
FONT_LATIN       = "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"
TTS_HELPER       = "/usr/local/lib/aios/tts_helper.js"
SENDVID_HELPER   = "/usr/local/lib/aios/send_video_helper.js"

# --- supervisor & p3 handler IDs (for updates) ---
SUPERVISOR_ID   = "13473953-52ed-419e-93c0-78c0c91b0818"
P3_HANDLER_ID   = str(uuid.uuid5(uuid.UUID("12345678-1234-5678-1234-567812345678"),
                                  "aios/p3/p3_handler"))

_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
def _wid(k): return str(uuid.uuid5(_NS, f"aios/p4/{k}"))

WF = {
    "tts":      _wid("tts_engine"),
    "ffmpeg":   _wid("ffmpeg_renderer"),
    "pipeline": _wid("render_pipeline"),
    "p4hdlr":   _wid("p4_handler"),
}

# ─── HELPERS ────────────────────────────────────────────────────────────────

def node(nid, name, ntype, ver, pos, params, cred_id=None, cred_name=None, cfail=False):
    n = {"id": nid, "name": name, "type": ntype, "typeVersion": ver,
         "position": pos, "parameters": params}
    if cred_id:
        n["credentials"] = {"postgres": {"id": cred_id, "name": cred_name}}
    if cfail:
        n["continueOnFail"] = True
    return n

def trigger(nid):
    return node(nid, "Execute Workflow Trigger",
                "n8n-nodes-base.executeWorkflowTrigger", 1, [240, 300], {})

def pg(nid, name, pos, query_expr, cfail=False):
    return node(nid, name, "n8n-nodes-base.postgres", 2, pos,
                {"operation": "executeQuery", "query": query_expr},
                PG_CRED_ID, "AIOS PostgreSQL", cfail)

def code(nid, name, pos, js):
    return node(nid, name, "n8n-nodes-base.code", 2, pos,
                {"jsCode": js, "mode": "runOnceForAllItems"})

def setn(nid, name, pos, assignments):
    return node(nid, name, "n8n-nodes-base.set", 3.4, pos,
                {"mode": "manual", "duplicateItem": False,
                 "assignments": {"assignments": assignments}})

def cmd(nid, name, pos, command_expr, cfail=True):
    return node(nid, name, "n8n-nodes-base.executeCommand", 1, pos,
                {"command": command_expr}, cfail=cfail)

def exec_wf(nid, name, pos, wf_id, wait=True):
    return node(nid, name, "n8n-nodes-base.executeWorkflow", 1.2, pos, {
        "source": "database",
        "workflowId": {"__rl": True, "value": wf_id, "mode": "id"},
        "options": {"waitForSubWorkflow": wait}
    })

def http_post(nid, name, pos, url_expr, body_expr, cfail=False):
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST", "url": url_expr,
        "sendBody": True, "specifyBody": "json",
        "jsonBody": body_expr,
        "options": {"response": {"response": {"neverError": True}}}
    }, cfail=cfail)

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

# ─── WORKFLOW 1 — TTS ENGINE ─────────────────────────────────────────────────

def build_tts_engine():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())
    bc  = code(nid(), "Prepare TTS Command", [460, 300], f"""
const text = ($json.script_text || '').trim();
const renderId = $json.render_id || 'r_' + Date.now();
const audioPath = '{RENDERS_PATH}/audio/' + renderId + '.mp3';
const isTamil = /[\\u0B80-\\u0BFF]/.test(text);
const lang = isTamil ? 'ta' : 'en';
const safe = s => s.replace(/'/g, "'\\\\''");
const ttsCmd = "node {TTS_HELPER} '" + safe(text) + "' " + lang + " " + audioPath;
return [{{ json: {{ tts_cmd: ttsCmd, audio_path: audioPath, render_id: renderId, lang }} }}];
""")
    rc  = cmd(nid(), "Run TTS", [680, 300],
              '={{ $json.tts_cmd }}', cfail=True)
    pv  = cmd(nid(), "Verify Audio", [900, 300],
              '={{ "ffprobe -v quiet -show_entries format=duration -of csv=p=0 " + $("Prepare TTS Command").item.json.audio_path }}',
              cfail=True)
    rt  = code(nid(), "Return Audio Result", [1120, 300], f"""
const raw = ($json.stdout || '').trim();
const duration = parseFloat(raw) || 0;
const audioPath = $('Prepare TTS Command').item.json.audio_path;
const renderId = $('Prepare TTS Command').item.json.render_id;
const ttsOut = $('Run TTS').item.json;
const success = duration > 0 || (ttsOut.exitCode === 0);
return [{{ json: {{ success, audio_path: audioPath, duration_sec: duration, render_id: renderId }} }}];
""")
    nodes = [t, bc, rc, pv, rt]
    edges = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prepare TTS Command",  "type": "main", "index": 0}]]},
        "Prepare TTS Command":      {"main": [[{"node": "Run TTS",              "type": "main", "index": 0}]]},
        "Run TTS":                  {"main": [[{"node": "Verify Audio",         "type": "main", "index": 0}]]},
        "Verify Audio":             {"main": [[{"node": "Return Audio Result",  "type": "main", "index": 0}]]},
    }
    upsert_workflow(WF["tts"], "MEDIA__TTS_ENGINE__V1", nodes, edges)

# ─── WORKFLOW 2 — FFMPEG RENDERER ────────────────────────────────────────────

def build_ffmpeg_renderer():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())
    pp  = code(nid(), "Prepare Render", [460, 300], f"""
const renderId  = $json.render_id || 'r_' + Date.now();
const audioPath = $json.audio_path || '{RENDERS_PATH}/audio/' + renderId + '.mp3';
const rawText   = ($json.display_text || $json.script_text || '').trim();
const isTamil   = /[\\u0B80-\\u0BFF]/.test(rawText);
const font      = isTamil ? '{FONT_TAMIL}' : '{FONT_LATIN}';
const textPath  = '/tmp/' + renderId + '_text.txt';
const videoPath = '{RENDERS_PATH}/finals/' + renderId + '.mp4';
const displayText = rawText.slice(0, 300);
const writeCmd = "node -e \\"require('fs').writeFileSync('" + textPath + "', process.env.DISPLAY_TEXT)\\"";
return [{{ json: {{
  render_id: renderId, audio_path: audioPath, font,
  text_path: textPath, video_path: videoPath,
  display_text: displayText, write_cmd: writeCmd,
  is_tamil: isTamil
}} }}];
""")
    wt  = cmd(nid(), "Write Text File", [680, 300],
              '={{ $json.write_cmd }}', cfail=False)
    rf  = code(nid(), "Build FFmpeg Command", [900, 300], f"""
const p = $('Prepare Render').item.json;
const videoPath = p.video_path;
const audioPath = p.audio_path;
const font      = p.font;
const textPath  = p.text_path;
const drawtext  = [
  'fontfile=' + font,
  'textfile=' + textPath,
  'fontcolor=white',
  'fontsize=48',
  'x=(w-text_w)/2',
  'y=(h-text_h)/2',
  'line_spacing=22',
  'fix_bounds=1',
  'borderw=3',
  'bordercolor=0x0f3460@0.85'
].join(':');
const watermark = [
  'fontfile={FONT_LATIN}',
  'text=AIOS',
  'fontcolor=white@0.25',
  'fontsize=28',
  'x=(w-text_w)/2',
  'y=h-60'
].join(':');
const vf = 'drawtext=' + drawtext + ',drawtext=' + watermark;
const ffCmd = [
  'ffmpeg -y',
  '-f lavfi -i "color=c=#0f3460:s=1080x1920:r=25"',
  '-i ' + audioPath,
  '-vf "' + vf + '"',
  '-c:v libx264 -preset ultrafast -crf 22',
  '-c:a aac -b:a 128k',
  '-pix_fmt yuv420p',
  '-shortest -t 120',
  videoPath
].join(' ');
return [{{ json: {{ ffmpeg_cmd: ffCmd, video_path: videoPath, render_id: p.render_id }} }}];
""")
    rv  = cmd(nid(), "Run FFmpeg", [1120, 300],
              '={{ $json.ffmpeg_cmd }}', cfail=False)
    ct  = cmd(nid(), "Cleanup Text File", [1340, 300],
              '={{ "rm -f " + $("Prepare Render").item.json.text_path }}', cfail=True)
    rt  = code(nid(), "Return Video Result", [1560, 300], f"""
const videoPath = $('Build FFmpeg Command').item.json.video_path;
const renderId  = $('Build FFmpeg Command').item.json.render_id;
const exitCode  = parseInt($('Run FFmpeg').item.json.exitCode || 0);
const stderr    = $('Run FFmpeg').item.json.stderr || '';
const success   = exitCode === 0 && !stderr.includes('Error');
return [{{ json: {{ success, video_path: videoPath, render_id: renderId, exit_code: exitCode }} }}];
""")
    nodes = [t, pp, wt, rf, rv, ct, rt]
    edges = {
        "Execute Workflow Trigger": {"main": [[{"node": "Prepare Render",       "type": "main", "index": 0}]]},
        "Prepare Render":           {"main": [[{"node": "Write Text File",      "type": "main", "index": 0}]]},
        "Write Text File":          {"main": [[{"node": "Build FFmpeg Command", "type": "main", "index": 0}]]},
        "Build FFmpeg Command":     {"main": [[{"node": "Run FFmpeg",           "type": "main", "index": 0}]]},
        "Run FFmpeg":               {"main": [[{"node": "Cleanup Text File",    "type": "main", "index": 0}]]},
        "Cleanup Text File":        {"main": [[{"node": "Return Video Result",  "type": "main", "index": 0}]]},
    }
    upsert_workflow(WF["ffmpeg"], "MEDIA__FFMPEG_RENDERER__V1", nodes, edges)

# ─── WORKFLOW 3 — RENDER PIPELINE (ASYNC) ────────────────────────────────────

def build_render_pipeline():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())

    # Notify start
    ns  = http_post(nid(), "Notify Rendering Start", [460, 300],
        f'={TG_URL}/sendMessage',
        '={{ JSON.stringify({ chat_id: $json.chat_id, text: "🎬 *Rendering your video...*\\nGenerating voiceover and compositing. This takes ~60 seconds. Will send it directly when ready!", parse_mode: "Markdown" }) }}',
        cfail=True)

    # Acquire render lock
    al  = exec_wf(nid(), "Acquire Lock", [680, 300],
        str(uuid.uuid5(uuid.UUID("12345678-1234-5678-1234-567812345678"),
                       "aios/p35/render_locks")))

    # TTS
    tts = exec_wf(nid(), "Generate Audio", [900, 300], WF["tts"])

    # FFmpeg render
    ffr = exec_wf(nid(), "Render Video", [1120, 300], WF["ffmpeg"])

    # Send video to Telegram
    sv  = cmd(nid(), "Send Video to Telegram", [1340, 300],
        '={{ "node ' + SENDVID_HELPER + ' " + $("Execute Workflow Trigger").item.json.chat_id + ' + '" " + $("Render Video").item.json.video_path + " " + "' + TG_TOKEN + '" + " \\"✅ *Your AIOS video is ready!*\\"" }}',
        cfail=True)

    # Release lock + cleanup
    rl  = exec_wf(nid(), "Release Lock", [1560, 300],
        str(uuid.uuid5(uuid.UUID("12345678-1234-5678-1234-567812345678"),
                       "aios/p35/render_locks")))

    dl  = cmd(nid(), "Delete Temp Audio", [1780, 300],
        '={{ "rm -f " + $("Generate Audio").item.json.audio_path }}', cfail=True)

    # Update DB job status
    uq  = pg(nid(), "Mark Job Complete", [2000, 300],
        '={{ "UPDATE render_queue SET status=\'done\',completed_at=NOW() WHERE render_id=\'" + $("Execute Workflow Trigger").item.json.render_id.replace(/\'/g,"\'\'") + "\'" }}',
        cfail=True)

    nodes = [t, ns, al, tts, ffr, sv, rl, dl, uq]
    edges = {
        "Execute Workflow Trigger": {"main": [[{"node": "Notify Rendering Start","type": "main", "index": 0}]]},
        "Notify Rendering Start":   {"main": [[{"node": "Acquire Lock",          "type": "main", "index": 0}]]},
        "Acquire Lock":             {"main": [[{"node": "Generate Audio",        "type": "main", "index": 0}]]},
        "Generate Audio":           {"main": [[{"node": "Render Video",          "type": "main", "index": 0}]]},
        "Render Video":             {"main": [[{"node": "Send Video to Telegram","type": "main", "index": 0}]]},
        "Send Video to Telegram":   {"main": [[{"node": "Release Lock",          "type": "main", "index": 0}]]},
        "Release Lock":             {"main": [[{"node": "Delete Temp Audio",     "type": "main", "index": 0}]]},
        "Delete Temp Audio":        {"main": [[{"node": "Mark Job Complete",     "type": "main", "index": 0}]]},
    }
    upsert_workflow(WF["pipeline"], "MEDIA__RENDER_PIPELINE__V1", nodes, edges)

# ─── WORKFLOW 4 — PHASE 4 TELEGRAM HANDLER (SYNC) ────────────────────────────

def build_p4_handler():
    nid = lambda: str(uuid.uuid4())
    t   = trigger(nid())

    gs  = pg(nid(), "Get Latest Script", [460, 300],
        '={{ "SELECT id,content,topic,niche FROM scripts WHERE user_id=" + parseInt($json.user_id||0) + " ORDER BY created_at DESC LIMIT 1" }}')

    pj  = code(nid(), "Prepare Render Job", [680, 300], f"""
const scripts = $input.all();
const script  = scripts[0]?.json;
const trig    = $('Execute Workflow Trigger').item.json;
const userId  = trig.user_id || 0;
const chatId  = trig.chat_id || 0;
const safe    = s => (s+'').replace(/'/g,"''");
if (!script || !script.content) {{
  return [{{ json: {{
    has_script: false,
    reply: "❌ No script found. Use */script <topic>* first to generate a script, then */render* to create your video.",
    render_id: null, chat_id: chatId
  }} }}];
}}
const renderId = 'r_' + userId + '_' + Date.now();
const displayText = (script.content||'').slice(0, 300);
const insertQuery = "INSERT INTO render_queue (render_id,user_id,script_id,status) VALUES ('" + safe(renderId) + "'," + userId + "," + (script.id||0) + ",'queued') ON CONFLICT(render_id) DO NOTHING";
return [{{ json: {{
  has_script: true,
  render_id: renderId,
  script_id: script.id,
  script_text: script.content,
  display_text: displayText,
  topic: script.topic || '',
  user_id: userId,
  chat_id: chatId,
  insert_query: insertQuery,
  reply: "⏳ *Render queued!*\\nGenerating your *" + (script.topic||'video') + "* video...\\nI'll send it directly when ready 🎬"
}} }}];
""")

    iq  = pg(nid(), "Insert Queue Job", [900, 300],
        '={{ $json.insert_query }}', cfail=True)

    # Fire-and-forget: launch pipeline without waiting
    ap  = exec_wf(nid(), "Fire Render Pipeline", [1120, 300],
        WF["pipeline"], wait=False)

    rt  = setn(nid(), "Return Reply", [1340, 300], [
        {"id": "r1", "name": "reply",      "value": '={{ $("Prepare Render Job").item.json.reply }}',   "type": "string"},
        {"id": "r2", "name": "chat_id",    "value": '={{ $("Prepare Render Job").item.json.chat_id }}', "type": "number"},
        {"id": "r3", "name": "render_id",  "value": '={{ $("Prepare Render Job").item.json.render_id }}', "type": "string"},
    ])

    nodes = [t, gs, pj, iq, ap, rt]
    edges = {
        "Execute Workflow Trigger": {"main": [[{"node": "Get Latest Script",   "type": "main", "index": 0}]]},
        "Get Latest Script":        {"main": [[{"node": "Prepare Render Job",  "type": "main", "index": 0}]]},
        "Prepare Render Job":       {"main": [[{"node": "Insert Queue Job",    "type": "main", "index": 0}]]},
        "Insert Queue Job":         {"main": [[{"node": "Fire Render Pipeline","type": "main", "index": 0}]]},
        "Fire Render Pipeline":     {"main": [[{"node": "Return Reply",        "type": "main", "index": 0}]]},
    }
    upsert_workflow(WF["p4hdlr"], "PHASE4__TELEGRAM_HANDLER__V1", nodes, edges)

# ─── UPDATE P3 HANDLER — add /render route ───────────────────────────────────

def update_p3_handler():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT nodes, connections FROM workflow_entity WHERE id=?", (P3_HANDLER_ID,))
    row = cur.fetchone()
    if not row:
        print("  ✗ P3 handler not found, skipping")
        con.close()
        return

    nodes = json.loads(row[0])
    edges = json.loads(row[1])

    # Find the "Is Story?" node to insert after it
    story_node = next((n for n in nodes if n["name"] == "Is Story?"), None)
    render_node = next((n for n in nodes if n["name"] == "Is Render?"), None)

    if render_node:
        print("  ✓ PHASE3__TELEGRAM_HANDLER__V1 (already has Is Render?)")
        con.close()
        return

    nid = lambda: str(uuid.uuid4())

    # New "Is Render?" IF node
    is_render = {
        "id": nid(), "name": "Is Render?",
        "type": "n8n-nodes-base.if", "typeVersion": 2,
        "position": [1120, 300],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{"id": "cr1", "leftValue": '={{ $json.p3Command }}',
                                "rightValue": "render",
                                "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and"
            }
        }
    }

    # Call P4 handler node
    call_p4 = {
        "id": nid(), "name": "Call P4 Handler",
        "type": "n8n-nodes-base.executeWorkflow", "typeVersion": 1.2,
        "position": [1340, 200],
        "parameters": {
            "source": "database",
            "workflowId": {"__rl": True, "value": WF["p4hdlr"], "mode": "id"},
            "options": {"waitForSubWorkflow": True}
        }
    }

    # Prep Caption node (the previous default fallback)
    prep_caption = next((n for n in nodes if n["name"] == "Prep Caption"), None)
    prep_caption_pos = prep_caption["position"] if prep_caption else [1340, 400]
    # Move Prep Caption lower to make room
    if prep_caption:
        prep_caption["position"] = [1340, 420]

    nodes.append(is_render)
    nodes.append(call_p4)

    # Re-wire: old "Is Story?" false branch → new "Is Render?"
    # Old: Is Story? false → Prep Caption
    # New: Is Story? false → Is Render? true → Call P4 Handler
    #                         Is Render? false → Prep Caption
    if story_node and "Is Story?" in edges:
        edges["Is Story?"]["main"][1] = [{"node": "Is Render?", "type": "main", "index": 0}]

    edges["Is Render?"] = {
        "main": [
            [{"node": "Call P4 Handler", "type": "main", "index": 0}],
            [{"node": "Prep Caption",    "type": "main", "index": 0}],
        ]
    }

    # Find existing "Exec Caption" or "Format Caption" to wire Call P4 Handler output
    format_nodes = [n["name"] for n in nodes if "Format" in n["name"]]
    # Call P4 Handler → Format Research (reuse same format/return as other handlers)
    format_research = next((n for n in nodes if n["name"] == "Format Research"), None)
    if format_research:
        edges["Call P4 Handler"] = {"main": [[{"node": "Format Research", "type": "main", "index": 0}]]}

    now_ms = int(time.time() * 1000)
    cur.execute("""
        UPDATE workflow_entity SET nodes=?, connections=?, updatedAt=?, versionId=?
        WHERE id=?
    """, (json.dumps(nodes), json.dumps(edges), now_ms, P3_HANDLER_ID, P3_HANDLER_ID))
    con.commit()
    con.close()
    print("  ✓ PHASE3__TELEGRAM_HANDLER__V1 (added Is Render? → P4 handler)")

# ─── UPDATE SUPERVISOR — add /render detection ───────────────────────────────

def update_supervisor():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT nodes FROM workflow_entity WHERE id=?", (SUPERVISOR_ID,))
    row = cur.fetchone()
    if not row:
        print("  ✗ Supervisor not found")
        con.close()
        return

    nodes = json.loads(row[0])
    pac_node = next((n for n in nodes if n["name"] == "Prepare AI Context"), None)
    if not pac_node:
        print("  ✗ 'Prepare AI Context' node not found")
        con.close()
        return

    js = pac_node["parameters"].get("jsCode", "")
    if "/render" in js:
        print("  ✓ TELEGRAM__SUPERVISOR__V2 (already has /render)")
        con.close()
        return

    # Add /render to P3_CMDS
    js = js.replace(
        "'/generate':'script'",
        "'/generate':'script', '/render':'render'"
    )
    pac_node["parameters"]["jsCode"] = js

    now_ms = int(time.time() * 1000)
    cur.execute("UPDATE workflow_entity SET nodes=?, updatedAt=?, versionId=? WHERE id=?",
                (json.dumps(nodes), now_ms, SUPERVISOR_ID, SUPERVISOR_ID))
    con.commit()
    con.close()
    print("  ✓ TELEGRAM__SUPERVISOR__V2 (/render detection added)")

# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("AIOS Phase 4 — Media Rendering Engine")
    print("=" * 50)

    print("\n[1] Deploying 4 media workflows...")
    build_tts_engine()
    build_ffmpeg_renderer()
    build_render_pipeline()
    build_p4_handler()

    print("\n[2] Updating existing workflows...")
    update_p3_handler()
    update_supervisor()

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
    print(f"  ✓ {total} total active workflows")
    print("\nPhase 4 Workflow IDs:")
    for k, v in WF.items():
        print(f"  {k:10} {v}")
    print("\n✅ Phase 4 complete — Media Rendering Engine live")
    print("   Test: send /render in Telegram")

if __name__ == "__main__":
    main()
