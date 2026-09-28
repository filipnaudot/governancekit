# Helper functions for acting as an agent against the GovernanceKit server.
# Usage (from the repo root):
#   source scenarios/agent.sh
#   load_model scenarios/support_agent.decl
#   start_trace
#   act view_account
#   end_trace

BASE="${BASE:-http://localhost:8000}"

_post() {
    curl -s -X POST "$BASE$1" -H "Content-Type: application/json" -d "${2:-{\}}"
}

_field() {
    python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"
}

_pretty() {
    python3 -m json.tool
}

# Upload a .decl file as a model and remember its id in $MODEL
load_model() {
    local body response
    body=$(python3 -c 'import json,sys; print(json.dumps({"decl": sys.stdin.read()}))' < "$1")
    response=$(_post /models "$body")
    echo "$response" | _pretty
    MODEL=$(echo "$response" | _field model_id) && echo "MODEL=$MODEL"
}

# Start a new trace (one agent run) on $MODEL and remember its id in $TRACE
start_trace() {
    local response
    response=$(_post /traces "{\"model_id\": \"$MODEL\"}")
    echo "$response" | _pretty
    TRACE=$(echo "$response" | _field trace_id) && echo "TRACE=$TRACE"
}

# Ask whether an activity is allowed right now (does not record anything)
check() {
    _post "/traces/$TRACE/check" "{\"activity\": \"$1\"}" | _pretty
}

# Record that an activity was performed
commit() {
    curl -s -o /dev/null -w "commit $1 -> HTTP %{http_code}\n" -X POST \
        "$BASE/traces/$TRACE/commit" -H "Content-Type: application/json" \
        -d "{\"activity\": \"$1\"}"
}

# Behave like a well-mannered agent: check first, only commit if allowed
act() {
    local decision
    decision=$(_post "/traces/$TRACE/check" "{\"activity\": \"$1\"}")
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
    _post "/traces/$TRACE/end" | _pretty
}
