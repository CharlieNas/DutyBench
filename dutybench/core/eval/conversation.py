"""A finished conversation, rebuilt from its trace file, in the shape the checks and judge need.

Grading reads only the trace. That keeps running and grading separate: a conversation can be
re-graded later (new checks, a different judge) without paying to run it again.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    args: dict
    output: dict
    turn: int  # the customer message number this call happened in response to

    @property
    def ok(self) -> bool:
        return "result" in self.output

    def __str__(self) -> str:
        return f"turn {self.turn}: {self.name}({json.dumps(self.args, ensure_ascii=False)})"


@dataclass
class Conversation:
    scenario_id: str
    model: str
    condition: str
    run: int
    status: str
    setting: str = "lending"  # traces from before settings existed are all lending
    turns: list[dict] = field(default_factory=list)  # [{"role": "customer" | "agent", "text": ...}]
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)

    @property
    def agent_text(self) -> str:
        return "\n\n".join(t["text"] for t in self.turns if t["role"] == "agent")

    @property
    def key(self) -> str:
        return f"{self.scenario_id}__{self.model}__{self.condition}__r{self.run}"

    def calls(self, name: str, where: dict | None = None, ok_only: bool = True) -> list[ToolCall]:
        """Tool calls to `name` whose arguments include everything in `where`."""
        return [c for c in self.tool_calls
                if c.name == name and (c.ok or not ok_only)
                and all(c.args.get(k) == v for k, v in (where or {}).items())]

    def transcript(self, with_tools: bool = False) -> str:
        lines, by_turn = [], {}
        for c in self.tool_calls:
            by_turn.setdefault(c.turn, []).append(c)
        n = 0
        for t in self.turns:
            if t["role"] == "customer":
                n += 1
                lines.append(f"CUSTOMER (message {n}): {t['text']}")
            else:
                if with_tools:
                    lines += [f"  [agent action: {c.name}({json.dumps(c.args, ensure_ascii=False)})"
                              f"{'' if c.ok else ' -> ERROR'}]" for c in by_turn.get(n, [])]
                lines.append(f"AGENT: {t['text']}")
        return "\n\n".join(lines)

    @classmethod
    def from_events(cls, events: list[dict]) -> "Conversation":
        start = next(e for e in events if e["type"] == "episode_start")
        end = next((e for e in events if e["type"] == "episode_end"), {})
        conv = cls(start["scenario_id"], start["model"], start["condition"], start["run"],
                   end.get("status", "incomplete"), setting=start.get("setting", "lending"),
                   final_state=end.get("final_state", {}),
                   totals=end.get("totals", {}))
        turn = 0
        for e in events:
            if e["type"] == "customer_msg":
                turn += 1
                conv.turns.append({"role": "customer", "text": e["text"]})
            elif e["type"] == "agent_reply":
                conv.turns.append({"role": "agent", "text": e["text"]})
            elif e["type"] == "tool_call":
                try:
                    args = json.loads(e["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                conv.tool_calls.append(ToolCall(e["name"], args if isinstance(args, dict) else {}, e["output"], turn))
        return conv

    @classmethod
    def from_trace(cls, path: Path) -> "Conversation":
        return cls.from_events([json.loads(line) for line in path.read_text().splitlines() if line.strip()])
