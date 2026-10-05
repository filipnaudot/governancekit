# Helper functions for acting as an admin or an agent against the GovernanceKit server.
# Usage (from the repo root):
#   source scenarios/agent.sh      # admin secret: $GK_ADMIN_SECRET or .env
#   login_admin
#   register_agent
#   login_agent
#   load_model scenarios/support_agent.decl
#   start_trace
#   act view_account               # begin, and finish as completed if allowed
#   begin approve_refund           # begin only; leaves it running in $INSTANCE
#   running                        # activities that have begun but not finished
#   finish failed                  # finish $INSTANCE: completed (default), failed or aborted
#   end_trace                      # or: end_trace abort, to abort running activities
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

# Ask whether an activity may begin right now (does not reserve anything)
check() {
    _post "$AGENT_TOKEN" "/traces/$TRACE/check" "{\"activity\": \"$1\"}" | _pretty
}

# Ask to begin an activity; if allowed, remember its instance id in $INSTANCE
begin() {
    local response
    response=$(_post "$AGENT_TOKEN" "/traces/$TRACE/activities" "{\"activity\": \"$1\"}")
    echo "$response" | _pretty
    INSTANCE=$(echo "$response" | _field instance_id)
}

# Report how an activity ended: finish [STATUS] [INSTANCE_ID]
# STATUS is completed (default), failed or aborted; INSTANCE_ID defaults to $INSTANCE
finish() {
    local status="${1:-completed}" instance="${2:-$INSTANCE}"
    curl -s -o /dev/null -w "finish $instance $status -> HTTP %{http_code}\n" -X POST \
        "$BASE/traces/$TRACE/activities/$instance/finish" \
        -H "Authorization: Bearer $AGENT_TOKEN" -H "Content-Type: application/json" \
        -d "{\"status\": \"$status\"}"
}

# List the activities that have begun but not finished
running() {
    _get "$AGENT_TOKEN" "/traces/$TRACE/activities" | _pretty
}

# Behave like a well-mannered agent: begin, and if allowed, perform and finish it
act() {
    local response decision
    response=$(_post "$AGENT_TOKEN" "/traces/$TRACE/activities" "{\"activity\": \"$1\"}")
    decision=$(echo "$response" | _field decision)
    if [ "$decision" = "allowed" ]; then
        echo "ALLOWED  $1"
        finish completed "$(echo "$response" | _field instance_id)"
    else
        echo "$(echo "$decision" | tr '[:lower:]' '[:upper:]')  $1"
        echo "$response" | _pretty
    fi
}

# Finish the run and get the final verdict; pass "abort" to abort running activities
end_trace() {
    local query=""
    [ "${1:-}" = "abort" ] && query="?abort_running=true"
    _post "$AGENT_TOKEN" "/traces/$TRACE/end$query" | _pretty
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
    if e["action"] in ("check", "begin"):
        return e["decision"].upper() + "".join("  " + v for v in e["violations"])
    if e["action"] == "finish":
        return e["status"]
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
