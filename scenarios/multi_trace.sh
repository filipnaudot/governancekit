#!/usr/bin/env bash
# Scenario 2: three refund tickets are handled at the same time, each as its
# own trace with several agents, using the model in scenarios/mp.decl (see
# scenarios/multi_agent.sh for its rules). Erik is the supervisor on all of
# them, so one agent works on several traces at once.
#
# A  Anna and Erik follow the rules: conformant.
# B  Sara and Erik. Erik approves the refund and then tries to issue it
#    himself, which the four-eyes rule denies. The approved refund is never
#    issued: violated when the trace ends.
# C  Anna, Sara and Erik. Erik approves 30000, but Sara issues 25000: allowed
#    when it begins, but violated when the trace ends, since no refund of the
#    approved amount was issued.
#
# Every agent checks an activity first, and begins it only if the check allows
# it (see act in scenarios/agent.sh).
#
# Usage (server must be running: docker compose up --build): ./scenarios/multi_trace.sh
# Follow it live in the frontend's Monitors tab.

set -eo pipefail

# Run from the repo root, so agent.sh finds .env
cd "$(dirname "$0")/.."
source scenarios/agent.sh

if ! curl -sf "$BASE/docs" >/dev/null; then
    echo "No server at $BASE. Start it with: docker compose up --build" >&2
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

step "Each ticket gets a trace, and the admin adds the agents that work on it"
TICKET=A
as_agent anna
start_trace >/dev/null
TRACE_A=$TRACE
add_to_trace erik

TICKET=B
as_agent sara
start_trace >/dev/null
TRACE_B=$TRACE
add_to_trace erik

TICKET=C
as_agent anna
start_trace >/dev/null
TRACE_C=$TRACE
add_to_trace sara
add_to_trace erik

ticket_a() {
    TICKET=A
    TRACE=$TRACE_A
    as_agent anna
    act verify_identity '{"method": "sms"}'
    act view_account
    as_agent erik
    act approve_refund '{"amount": 15000, "approver_role": "supervisor", "resource": "erik"}'
    as_agent anna
    act issue_refund '{"amount": 15000, "resource": "anna"}'
    act close_ticket '{"status": "resolved"}'
    verdict
}

ticket_b() {
    TICKET=B
    TRACE=$TRACE_B
    as_agent sara
    act verify_identity '{"method": "bankid"}'
    act view_account
    as_agent erik
    act approve_refund '{"amount": 20000, "approver_role": "supervisor", "resource": "erik"}'
    act issue_refund '{"amount": 20000, "resource": "erik"}'
    as_agent sara
    act close_ticket '{"status": "resolved"}'
    verdict
}

ticket_c() {
    TICKET=C
    TRACE=$TRACE_C
    as_agent anna
    act verify_identity '{"method": "bankid"}'
    as_agent sara
    act view_account
    as_agent erik
    act approve_refund '{"amount": 30000, "approver_role": "supervisor", "resource": "erik"}'
    as_agent sara
    act issue_refund '{"amount": 25000, "resource": "sara"}'
    as_agent anna
    act close_ticket '{"status": "resolved"}'
    verdict
}

step "The three tickets are worked on at the same time"
ticket_a &
sleep 1
ticket_b &
sleep 1
ticket_c &
wait

for ticket in A B C; do
    trace_var="TRACE_$ticket"
    step "Admin: audit log for ticket $ticket"
    show_audit "${!trace_var}"
done
