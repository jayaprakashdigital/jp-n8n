# Workflow Template

**Purpose:** Reference template for building new n8n subworkflows in AIOS.
**Owner:** Platform Lead
**Instructions:** Use this structure when writing a new builder function in a phase builder script.

---

## Naming Convention

```
<DOMAIN>__<NAME>__<VERSION>
```

| Domain | Usage |
|--------|-------|
| TELEGRAM | Telegram-facing workflows (supervisor, handlers) |
| AI | AI/LLM orchestration workflows |
| MEMORY | Persistent memory and storage workflows |
| RESEARCH | Research and data gathering workflows |
| SCRIPT | Scripting and content creation workflows |
| CAPTION | Caption and copy generation |
| CREATIVE | Multi-step creative pipelines |
| APPROVAL | Approval flow management |
| SYSTEM | Infrastructure workflows (error handler, recovery) |
| MEDIA | Phase 4+ media rendering |

**Versioning:** Always start at V1. Never edit in place — create V2 and deprecate V1.

---

## UUID Generation

All workflow IDs must be deterministic using the project UUID namespace:

```python
import uuid

_NS = uuid.UUID("12345678-1234-5678-1234-567812345678")

def _wid(k):
    return str(uuid.uuid5(_NS, f"aios/p3/{k}"))

# Example
WORKFLOW_ID = _wid("my_workflow_name")
```

**Never use `uuid.uuid4()`** — IDs must be stable across re-runs.

---

## Standard Subworkflow Structure

Every subworkflow must follow this pattern:

```python
def build_my_workflow():
    nid = lambda: str(uuid.uuid4())
    
    t  = trigger_node(nid())          # Execute Workflow Trigger (entry point)
    ai = or_node(nid(), "Call AI", [460, 300],
         '={{ JSON.stringify({...}) }}',
         model="anthropic/claude-3.5-haiku")
    p  = pg_node(nid(), "Save Result", [680, 300],
         '={{ "INSERT INTO..." }}')
    r  = node(nid(), "Return Result", "n8n-nodes-base.set", 3.4, [900, 300], {
        "mode": "manual",
        "duplicateItem": False,
        "assignments": {"assignments": [{
            "id": "out-01",
            "name": "result",
            "value": '={{ $json }}',
            "type": "object"
        }]}
    })
    
    nodes = [t, ai, p, r]
    edges = {
        "Execute Workflow Trigger": {"main": [[{"node": "Call AI", "type": "main", "index": 0}]]},
        "Call AI":                  {"main": [[{"node": "Save Result", "type": "main", "index": 0}]]},
        "Save Result":              {"main": [[{"node": "Return Result", "type": "main", "index": 0}]]},
    }
    
    return upsert_workflow(
        wf_id=WF["my_key"],
        name="DOMAIN__NAME__V1",
        nodes=nodes,
        edges=edges
    )
```

---

## Node Type Reference

| Node Type | Type String | Version | Use For |
|-----------|------------|---------|---------|
| Execute Workflow Trigger | `n8n-nodes-base.executeWorkflowTrigger` | 1 | Subworkflow entry |
| Execute Workflow | `n8n-nodes-base.executeWorkflow` | 1.2 | Call subworkflow |
| HTTP Request | `n8n-nodes-base.httpRequest` | 4.2 | OpenRouter API calls |
| PostgreSQL | `n8n-nodes-base.postgres` | 2 | DB queries |
| IF | `n8n-nodes-base.if` | 2 | Conditional routing |
| Set | `n8n-nodes-base.set` | 3.4 | Data transformation |
| Respond to Webhook | `n8n-nodes-base.respondToWebhook` | 1.1 | HTTP response |
| Webhook | `n8n-nodes-base.webhook` | 2 | HTTP entry point |

**Never invent node types** — only use types from this table or ones verified in existing workflows.

---

## OpenRouter Call Pattern

```python
def or_node(nid, name, pos, body_expr, model="anthropic/claude-3.5-haiku"):
    return node(nid, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Authorization", "value": f"Bearer {OR_KEY}"},
            {"name": "Content-Type",  "value": "application/json"},
            {"name": "HTTP-Referer",  "value": "https://n8n.srv1654276.hstgr.cloud"},
            {"name": "X-Title",       "value": "AIOS"}
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": body_expr,
        "options": {"response": {"response": {"neverError": True}}}
    })
```

**Model selection:**
- `anthropic/claude-3.5-haiku` — speed tasks (research, captions, scoring)
- `anthropic/claude-3.5-sonnet` — quality tasks (scripts, stories)

---

## PostgreSQL Query Pattern

```python
def pg_node(nid, name, pos, query_expr):
    return node(nid, name, "n8n-nodes-base.postgres", 2, pos, {
        "operation": "executeQuery",
        "query": query_expr
    }, cred_id=PG_CRED_ID, cred_name="AIOS PostgreSQL")
```

**Always use `operation: "executeQuery"`** — never use other operations.

---

## AI Response Parsing Pattern

```javascript
// In a Set node after OpenRouter call:
const raw = $json.choices?.[0]?.message?.content || '{"error":"no response"}';
const jsonMatch = raw.match(/\{[\s\S]*\}/);
let parsed = {};
try {
    parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : {};
} catch(e) {
    parsed = { error: "parse_failed", raw: raw.slice(0, 200) };
}
return { json: { ...parsed } };
```

**Never use `JSON.parse()` directly on raw AI output** — always extract JSON block first.

---

## SQL Injection Prevention

```javascript
// In all Set nodes that build SQL with user input:
const safe = s => (s+'').replace(/'/g, "''");
const safeTopic = safe($json.topic || '');
const query = `INSERT INTO table (col) VALUES ('${safeTopic}')`;
```

**Always sanitize user-supplied text** before embedding in SQL strings.

---

## Required Output Fields

Every subworkflow must return a `result` field (or named output) that the calling workflow can use:

```javascript
// Return from every subworkflow
return {
    json: {
        result: "...",      // Main output
        source: "WORKFLOW_NAME",
        timestamp: new Date().toISOString()
    }
};
```
