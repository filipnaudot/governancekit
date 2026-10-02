#!/usr/bin/env bash
# Demo: one agent works through a refund ticket, then the admin inspects the
# known agents and the audit log.
# Usage (server must be running, see ./rebuild.sh): ./scenarios/demo.sh
#
# Afterwards, inspect the server yourself from the terminal:
#   source scenarios/agent.sh
#   login_admin
#   list_agents
#   show_audit

set -eo pipefail

# Run from the repo root, so agent.sh finds .env
cd "$(dirname "$0")/.."
source scenarios/agent.sh

if ! curl -sf "$BASE/docs" >/dev/null; then
    echo "No server at $BASE. Start it with ./rebuild.sh" >&2
    exit 1
fi

step() { printf '\n==> %s\n' "$1"; }

step "Admin logs in, registers an agent and loads the model"
login_admin
register_agent demo-agent
load_model scenarios/support_agent.decl >/dev/null
echo "MODEL=$MODEL"

step "Agent logs in with the credentials it got from the admin, and starts a trace"
login_agent
start_trace >/dev/null
echo "TRACE=$TRACE"

step "Agent checks view_account before verifying the customer's identity"
check view_account

step "Agent verifies the identity, then views the account"
act verify_identity
act view_account

step "Agent checks issue_refund before the refund is approved"
check issue_refund

step "Agent gets the refund approved, issues it and closes the ticket"
act approve_refund
act issue_refund
commit close_ticket

step "Agent ends the trace"
end_trace

step "Admin: known agents"
list_agents

step "Admin: audit log for this trace"
show_audit "$TRACE"
