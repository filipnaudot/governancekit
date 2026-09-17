"""
TraceMonitor - runtime trace-level conformance checking.

Applies a MPDeclareModel on a trace.
"""

from core.mp_declare_model import MPDeclareModel


class TraceMonitor:
    def __init__(self, model: MPDeclareModel):
        self.model = model

    def handle_event(self, event):
        pass
