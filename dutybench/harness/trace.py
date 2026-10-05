"""Append-only event log for one conversation, written as JSONL so a run can be inspected
step by step (or replayed in the demo) after the fact."""

import json
import time
from pathlib import Path
from typing import Callable


class Tracer:
    def __init__(self, path: Path | None = None, on_event: Callable[[dict], None] | None = None):
        self.events: list[dict] = []
        self.on_event = on_event  # e.g. the demo streams events to the browser
        self._file = None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file = path.open("w")

    def log(self, type: str, **data) -> dict:
        event = {"t": round(time.time(), 3), "type": type, **data}
        self.events.append(event)
        if self._file:
            self._file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self._file.flush()  # survive a crash mid-conversation
        if self.on_event:
            self.on_event(event)
        return event

    def totals(self, role: str | None = None) -> dict:
        """Token, cost and latency totals, optionally for one role ("agent", "customer", "judge")."""
        calls = [e for e in self.events if e["type"] == "llm_call" and role in (None, e.get("role"))]
        return {
            "llm_calls": len(calls),
            "input_tokens": sum(e["usage"]["input_tokens"] for e in calls),
            "cached_tokens": sum(e["usage"]["cached_tokens"] for e in calls),
            "output_tokens": sum(e["usage"]["output_tokens"] for e in calls),
            "cost_usd": round(sum(e["cost_usd"] for e in calls), 6),
            "llm_latency_s": round(sum(e["latency_s"] for e in calls), 3),
        }

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
