# Helper functions for acting as an agent against the GovernanceKit server.
# Usage (from the repo root):
#   source scenarios/agent.sh      # admin secret: $GK_ADMIN_SECRET or .env
#   login_admin
#   register_agent
#   load_model scenarios/support_agent.decl
#   start_trace
#   act view_account
#   end_trace

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

# Log in as admin with $GK_ADMIN_SECRET (read from .env if unset) and
# remember the token in $ADMIN_TOKEN
login_admin() {
    local secret="${GK_ADMIN_SECRET:-}"
    if [ -z "$secret" ] && [ -f .env ]; then
        secret=$(set -a; . ./.env; echo "$GK_ADMIN_SECRET")
    fi
    ADMIN_TOKEN=$(_login admin "$secret") && echo "Logged in as admin"
}

# Register a new agent (optional name), log in as it and remember its token in $AGENT_TOKEN
register_agent() {
    local response
    response=$(_post "$ADMIN_TOKEN" /agents "{\"agent_name\": \"${1:-scenario-agent}\"}")
    AGENT_ID=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin)['agent_info']['agent_id'])")
    echo "AGENT_ID=$AGENT_ID"
    AGENT_SECRET=$(echo "$response" | _field secret)
    AGENT_TOKEN=$(_login "$AGENT_ID" "$AGENT_SECRET") && echo "Logged in as agent"
}

# Upload a .decl file as a model and remember its id in $MODEL
load_model() {
    local body response
    body=$(python3 -c 'import json,sys; print(json.dumps({"decl": sys.stdin.read()}))' < "$1")
    response=$(_post "$ADMIN_TOKEN" /models "$body")
    echo "$response" | _pretty
    MODEL=$(echo "$response" | _field model_id) && echo "MODEL=$MODEL"
}

# Start a new trace (one agent run) on $MODEL for $AGENT_ID and remember its id in $TRACE
start_trace() {
    local response
    response=$(_post "$ADMIN_TOKEN" /traces \
        "{\"model_id\": \"$MODEL\", \"agent_id\": \"$AGENT_ID\"}")
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
    _post "$ADMIN_TOKEN" "/traces/$TRACE/end" | _pretty
}
