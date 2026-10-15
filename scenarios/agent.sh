# Helper functions for acting as an admin or an agent against the GovernanceKit server.
# Usage (from the repo root):
#   source scenarios/agent.sh      # admin secret: $GK_ADMIN_SECRET or .env
#   login_admin
#   register_agent
#   login_agent
#   load_model scenarios/support_agent.decl
#   start_trace
#   act view_account               # check, and if allowed: begin, take $ACT_SECONDS and finish as completed
#   act issue_refund '{"amount": 20000}'  # activities, check and begin take an optional payload
#   act_when_allowed issue_refund  # like act, but checks again every second while the answer is wait
#   begin approve_refund           # begin only; leaves it running in $INSTANCE
#   running                        # activities that have begun but not finished
#   finish failed                  # finish $INSTANCE: completed (default), failed or aborted
#   end_trace                      # or: end_trace abort, to abort running activities
#   verdict                        # like end_trace, but prints one line
#   list_agents                    # admin: known agents
#   show_audit [TRACE_ID]          # admin: audit log, optionally for one trace
#
# Several agents (each registered and logged in under a name):
#   new_agent anna                 # admin: register "anna", log in, remember as $ANNA_ID/$ANNA_TOKEN
#   as_agent anna                  # act as anna from now on
#   add_to_trace erik              # admin: let erik work on $TRACE too
# To run agents at the same time, run each in a subshell in the background,
# ( as_agent erik; act ... ) &, and then wait. Set $TICKET to tell traces apart
# in the output.

BASE="${BASE:-http://localhost:8000}"
# How long act spends performing an allowed activity, so it can be seen running
# in the frontend. ACT_SECONDS=0 to finish at once.
ACT_SECONDS="${ACT_SECONDS:-5}"

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

# _event ACTIVITY [PAYLOAD_JSON] -> request body for check and begin
_event() {
    local payload="${2:-}"
    [ -n "$payload" ] || payload='{}'
    echo "{\"activity\": \"$1\", \"payload\": $payload}"
}

# Who is acting, for the output: [TICKET/agent name]
_tag() {
    echo "[${TICKET:+$TICKET/}${AGENT_NAME:-agent}]"
}

# _upper NAME -> NAME in upper case, for the $NAME_ID and $NAME_TOKEN variables
_upper() {
    echo "$1" | tr '[:lower:]' '[:upper:]'
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

# As admin: register an agent called NAME, log in as it, and remember its ID
# and token in $NAME_ID and $NAME_TOKEN (NAME in upper case), for as_agent
new_agent() {
    local var
    var=$(_upper "$1")
    register_agent "$1" >/dev/null
    login_agent >/dev/null
    printf -v "${var}_ID" '%s' "$AGENT_ID"
    printf -v "${var}_TOKEN" '%s' "$AGENT_TOKEN"
    echo "Agent $1: $AGENT_ID"
}

# Act as an agent created with new_agent: as_agent NAME
as_agent() {
    local id_var token_var
    id_var="$(_upper "$1")_ID"
    token_var="$(_upper "$1")_TOKEN"
    AGENT_NAME="$1"
    AGENT_ID="${!id_var}"
    AGENT_TOKEN="${!token_var}"
}

# As admin: let an agent created with new_agent work on $TRACE too
add_to_trace() {
    local id_var response
    id_var="$(_upper "$1")_ID"
    response=$(_post "$ADMIN_TOKEN" "/traces/$TRACE/agents" "{\"agent_id\": \"${!id_var}\"}")
    if echo "$response" | grep -q '"agent_ids"'; then
        echo "${TICKET:+[$TICKET] }Admin added $1 to the trace"
    else
        echo "${TICKET:+[$TICKET] }Admin could not add $1: $response"
    fi
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

# Ask whether an activity may begin right now (does not reserve anything):
# check ACTIVITY [PAYLOAD_JSON]
check() {
    _post "$AGENT_TOKEN" "/traces/$TRACE/check" "$(_event "$1" "${2:-}")" | _pretty
}

# Ask to begin an activity; if allowed, remember its instance id in $INSTANCE:
# begin ACTIVITY [PAYLOAD_JSON]
begin() {
    local response
    response=$(_post "$AGENT_TOKEN" "/traces/$TRACE/activities" "$(_event "$1" "${2:-}")")
    echo "$response" | _pretty
    INSTANCE=$(echo "$response" | _field instance_id)
}

# Report how an activity ended: finish [STATUS] [INSTANCE_ID]
# STATUS is completed (default), failed or aborted; INSTANCE_ID defaults to $INSTANCE
finish() {
    local status="${1:-completed}" instance="${2:-$INSTANCE}"
    curl -s -o /dev/null -w "$(_tag) finish $instance $status -> HTTP %{http_code}\n" -X POST \
        "$BASE/traces/$TRACE/activities/$instance/finish" \
        -H "Authorization: Bearer $AGENT_TOKEN" -H "Content-Type: application/json" \
        -d "{\"status\": \"$status\"}"
}

# List the activities that have begun but not finished
running() {
    _get "$AGENT_TOKEN" "/traces/$TRACE/activities" | _pretty
}

# _decision RESPONSE -> the decision in a check or begin response, or nothing
_decision() {
    echo "$1" | python3 -c "import json,sys; print(json.load(sys.stdin).get('decision', ''))"
}

# _report STEP ACTIVITY RESPONSE: print a check or begin decision on one line,
# and the constraints that don't allow it
_report() {
    local decision
    decision=$(_decision "$3")
    if [ -z "$decision" ]; then
        echo "$(_tag) $1 ERROR  $2: $3"
        return
    fi
    echo "$(_tag) $1 $(_upper "$decision")  $2"
    echo "$3" | python3 -c "import json,sys; [print('      blocked by ' + c) for c in json.load(sys.stdin)['blocking']]"
}

# _begin_and_perform ACTIVITY [PAYLOAD_JSON]: begin, and if allowed, perform
# and finish it. Begin can still say no if another agent got there first.
_begin_and_perform() {
    local response
    response=$(_post "$AGENT_TOKEN" "/traces/$TRACE/activities" "$(_event "$1" "${2:-}")")
    if [ "$(_decision "$response")" = "allowed" ]; then
        echo "$(_tag) BEGIN ALLOWED  $1 (performing for ${ACT_SECONDS}s)"
        sleep "$ACT_SECONDS"
        finish completed "$(echo "$response" | _field instance_id)"
    else
        _report BEGIN "$1" "$response"
    fi
}

# _check_quietly ACTIVITY [PAYLOAD_JSON] -> the check response
_check_quietly() {
    _post "$AGENT_TOKEN" "/traces/$TRACE/check" "$(_event "$1" "${2:-}")"
}

# Behave like a well-mannered agent: check first, and only if allowed,
# begin, perform and finish it: act ACTIVITY [PAYLOAD_JSON]
act() {
    local response
    response=$(_check_quietly "$1" "${2:-}")
    _report CHECK "$1" "$response"
    [ "$(_decision "$response")" = "allowed" ] && _begin_and_perform "$1" "${2:-}"
    return 0
}

# Like act, but while check answers wait, check again every second (at most
# $WAIT_TRIES times): act_when_allowed ACTIVITY [PAYLOAD_JSON]
act_when_allowed() {
    local response tries=0
    while :; do
        response=$(_check_quietly "$1" "${2:-}")
        _report CHECK "$1" "$response"
        [ "$(_decision "$response")" = "wait" ] || break
        tries=$((tries + 1))
        [ "$tries" -lt "${WAIT_TRIES:-30}" ] || return 0
        sleep 1
    done
    [ "$(_decision "$response")" = "allowed" ] && _begin_and_perform "$1" "${2:-}"
    return 0
}

# Finish the run and get the final verdict; pass "abort" to abort running activities
end_trace() {
    local query=""
    [ "${1:-}" = "abort" ] && query="?abort_running=true"
    _post "$AGENT_TOKEN" "/traces/$TRACE/end$query" | _pretty
}

# Like end_trace, but print the verdict on one line
verdict() {
    local query=""
    [ "${1:-}" = "abort" ] && query="?abort_running=true"
    _post "$AGENT_TOKEN" "/traces/$TRACE/end$query" | TAG="$(_tag)" python3 -c '
import json, os, sys

data = json.load(sys.stdin)
tag = os.environ["TAG"]
if "violations" not in data:
    print(tag + " END  error: " + str(data.get("detail", data)))
elif not data["violations"]:
    print(tag + " END  conformant")
else:
    print(tag + " END  VIOLATED")
    for violation in data["violations"]:
        print("      " + violation)
'
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
