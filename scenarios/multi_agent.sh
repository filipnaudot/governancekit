#!/usr/bin/env bash
# Scenario 1: several agents work on one trace, a refund ticket, using the
# MP-DECLARE model in scenarios/mp.decl:
# - view_account needs a verify_identity by BankID or SMS in the last 10 minutes
# - a refund over 10000 needs a supervisor's approval, by someone other than
#   the one issuing it (four eyes)
# - every approved refund must be issued with the same amount within 48 hours
# - the ticket must be closed as resolved
#
# Anna starts the trace. Erik (supervisor) and Sara may only work on it once
# the admin has added them. Erik approves while Sara already tries to issue
# the refund: she is told to wait until his approval has finished.
#
# Every agent checks an activity first, and begins it only if the check allows
# it (see act in scenarios/agent.sh).
#
# Usage (server must be running, see ./rebuild.sh): ./scenarios/multi_agent.sh
# Follow it live in the frontend's Monitors tab.

set -eo pipefail

# Run from the repo root, so agent.sh finds .env
cd "$(dirname "$0")/.."
source scenarios/agent.sh

if ! curl -sf "$BASE/docs" >/dev/null; then
    echo "No server at $BASE. Start it with ./rebuild.sh" >&2
    exit 1
fi

step() { printf '\n==> %s\n' "$1"; }

step "Admin logs in, registers three agents and loads the model"
login_admin
new_agent anna
new_agent sara
new_agent erik
load_model scenarios/mp.decl >/dev/null
echo "MODEL=$MODEL"

step "Anna starts a trace for the ticket"
as_agent anna
start_trace >/dev/null
echo "TRACE=$TRACE"

step "Anna identifies the customer with a password, which is not enough to view the account"
act verify_identity '{"method": "password"}'
act view_account

step "Anna identifies the customer with BankID and views the account"
act verify_identity '{"method": "bankid"}'
act view_account

step "Anna tries to issue a refund of 20000 without an approval"
act issue_refund '{"amount": 20000, "resource": "anna"}'

step "Anna approves the refund herself, but she is not a supervisor"
act approve_refund '{"amount": 20000, "approver_role": "agent", "resource": "anna"}'
act issue_refund '{"amount": 20000, "resource": "anna"}'

step "Sara tries to issue the refund before the admin has added her to the trace"
as_agent sara
act issue_refund '{"amount": 20000, "resource": "sara"}'

step "Admin adds Erik (supervisor) and Sara to the trace"
add_to_trace erik
add_to_trace sara

step "At the same time: Erik approves the refund, and Sara tries to issue it"
(
    as_agent erik
    act approve_refund '{"amount": 20000, "approver_role": "supervisor", "resource": "erik"}'
) &
(
    as_agent sara
    sleep 1 # Erik's approval has begun but not finished
    act_when_allowed issue_refund '{"amount": 20000, "resource": "sara"}'
) &
wait

step "Anna closes the ticket as resolved and ends the trace"
as_agent anna
act close_ticket '{"status": "resolved"}'
verdict

step "Admin: audit log for this trace"
show_audit "$TRACE"
