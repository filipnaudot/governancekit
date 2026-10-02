# Helper functions for acting as an admin or an agent against the GovernanceKit server.
# Usage (from the repo root):
#   source scenarios/agent.sh      # admin secret: $GK_ADMIN_SECRET or .env
#   login_admin
#   register_agent
#   login_agent
#   load_model scenarios/support_agent.decl
#   start_trace
#   act view_account
#   end_trace
#   list_agents                    # admin: known agents
#   show_audit [TRACE_ID]          # admin: audit log, optionally for one trace

BASE="${BASE:-http://localhost:8000}"

# _post TOKEN PATH [JSON]
_post() {
    curl -s -X POST "$BASE$2" -H "Authorization: Bearer $1" \
        -H "Content-Type: application/json" -d "${3:-{\}}"
}

# _login ID SECRET -> prints an access token
_login() {
    curl -s -X POST "$BASE/token" --data-urlencode "username=$1" \
        --data-urlencode "password=$2" | _field access_token
}

_field() {
    python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"
}

_pretty() {
    python3 -m json.tool
}

# _get TOKEN PATH
_get() {
    curl -s "$BASE$2" -H "Authorization: Bearer $1"
}

# Log in as admin with $GK_ADMIN_SECRET (read from .env if unset) and
# remember the token in $ADMIN_TOKEN
login_admin() {
    local secret="${GK_ADMIN_SECRET:-}"
    if [ -z "$secret" ] && [ -f .env ]; then
        secret=$(set -a; . ./.env; echo "$GK_ADMIN_SECRET")
    fi
    ADMIN_TOKEN=$(_login admin "$secret") && echo "Logged in as admin"
}

# As admin: register a new agent (optional name) and remember its
# credentials in $AGENT_ID and $AGENT_SECRET. Does not log in as the agent.
register_agent() {
    local response
    response=$(_post "$ADMIN_TOKEN" /agents "{\"agent_name\": \"${1:-scenario-agent}\"}")
    AGENT_ID=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin)['agent_info']['agent_id'])")
    echo "AGENT_ID=$AGENT_ID"
    AGENT_SECRET=$(echo "$response" | _field secret)
}

# As agent: log in with $AGENT_ID and $AGENT_SECRET (or the ID and secret
# given as arguments) and remember the token in $AGENT_TOKEN
login_agent() {
    AGENT_ID="${1:-$AGENT_ID}"
    AGENT_SECRET="${2:-$AGENT_SECRET}"
    AGENT_TOKEN=$(_login "$AGENT_ID" "$AGENT_SECRET") && echo "Logged in as agent $AGENT_ID"
}

# Upload a .decl file as a model and remember its id in $MODEL
load_model() {
    local body response
    body=$(python3 -c 'import json,sys; print(json.dumps({"decl": sys.stdin.read()}))' < "$1")
    response=$(_post "$ADMIN_TOKEN" /models "$body")
    echo "$response" | _pretty
    MODEL=$(echo "$response" | _field model_id) && echo "MODEL=$MODEL"
}

# Start a new trace (one agent run) on $MODEL as the agent and remember its id in $TRACE
start_trace() {
    local response
    response=$(_post "$AGENT_TOKEN" /traces "{\"model_id\": \"$MODEL\"}")
    echo "$response" | _pretty
    TRACE=$(echo "$response" | _field trace_id) && echo "TRACE=$TRACE"
}

# Ask whether an activity is allowed right now (does not record anything)
check() {
    _post "$AGENT_TOKEN" "/traces/$TRACE/check" "{\"activity\": \"$1\"}" | _pretty
}

# Record that an activity was performed
commit() {
    curl -s -o /dev/null -w "commit $1 -> HTTP %{http_code}\n" -X POST \
        "$BASE/traces/$TRACE/commit" -H "Authorization: Bearer $AGENT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"activity\": \"$1\"}"
}

# Behave like a well-mannered agent: check first, only commit if allowed
act() {
    local decision
    decision=$(_post "$AGENT_TOKEN" "/traces/$TRACE/check" "{\"activity\": \"$1\"}")
    if [ "$(echo "$decision" | _field allowed)" = "True" ]; then
        echo "ALLOWED  $1"
        commit "$1"
    else
        echo "BLOCKED  $1"
        echo "$decision" | _pretty
    fi
}

# Finish the run and get the final verdict
end_trace() {
    _post "$AGENT_TOKEN" "/traces/$TRACE/end" | _pretty
}

# --- Admin: inspect the server ---

# Print the agents the server knows about
list_agents() {
    _get "$ADMIN_TOKEN" /agents | python3 -c '
import json, sys

data = json.load(sys.stdin)
if "agents" not in data:
    sys.exit("Error: " + str(data.get("detail", data)) + " (try login_admin)")
print(str(len(data["agents"])) + " known agent(s)")
for agent in data["agents"]:
    print("  " + agent["agent_id"] + "  " + agent["agent_name"])
'
}

# Print the audit log as a table; pass a trace ID to show only that trace
show_audit() {
    AUDIT_JSON=$(_get "$ADMIN_TOKEN" /audit) \
    AGENTS_JSON=$(_get "$ADMIN_TOKEN" /agents) \
    TRACE_FILTER="${1:-}" \
    python3 -c '
import json, os, sys

audit = json.loads(os.environ["AUDIT_JSON"])
if "auditLog" not in audit:
    sys.exit("Error: " + str(audit.get("detail", audit)) + " (try login_admin)")
agents = json.loads(os.environ["AGENTS_JSON"]).get("agents", [])
names = {a["agent_id"]: a["agent_name"] for a in agents}
trace = os.environ["TRACE_FILTER"]
entries = [e for e in audit["auditLog"] if not trace or e["trace_id"] == trace]

def result(e):
    if e["action"] == "check":
        verdict = "ALLOWED" if e["allowed"] else "BLOCKED"
        return verdict + "".join("  " + v for v in e["violations"])
    if e["action"] == "end_trace":
        return "conformant" if not e["violations"] else "VIOLATED  " + "  ".join(e["violations"])
    return ""

row = "{:<12}  {:<16}  {:<8}  {:<11}  {:<16}  {}"
print(row.format("TIME", "AGENT", "TRACE", "ACTION", "ACTIVITY", "RESULT"))
for e in entries:
    print(row.format(
        e["received_at"][11:23],
        names.get(e["agent_id"], e["agent_id"][:8])[:16],
        e["trace_id"][:8],
        e["action"],
        e["activity"] or "",
        result(e),
    ))
print(str(len(entries)) + " entr" + ("y" if len(entries) == 1 else "ies"))
'
}
