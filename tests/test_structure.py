"""The core must work for any setting without being changed. Two tests hold it to that."""

import ast
import json
from pathlib import Path

from pydantic import BaseModel

from dutybench.core.eval.conversation import Conversation
from dutybench.core.eval.grade import grade
from dutybench.core.runner import run_episode
from dutybench.core.setting import Setting
from dutybench.core.simulator import END
from dutybench.core.tools import Tool, ToolError
from tests.fakes import FakeLLM, call, reply

CORE = Path(__file__).resolve().parent.parent / "dutybench" / "core"


def test_core_never_imports_a_setting():
    offenders = []
    for path in CORE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            offenders += [f"{path.relative_to(CORE)}: {n}" for n in names if n.startswith("dutybench.settings")]
    assert offenders == []


# --- a toy second setting: a library help desk with one tool ----------------------------------

class Library:
    def __init__(self, seed: dict):
        self.loans = dict(seed["loans"])
        self.renewals: list[str] = []

    def renew(self, book_id: str) -> dict:
        if book_id not in self.loans:
            raise ToolError(f"No loan for book {book_id}.")
        self.renewals.append(book_id)
        return {"book_id": book_id, "new_due_date": "2026-11-01"}

    def snapshot(self) -> dict:
        return {"loans": self.loans, "renewals": self.renewals}


class RenewArgs(BaseModel):
    book_id: str


def renew_tool(lib: Library) -> list[Tool]:
    return [Tool("renew_book", "Renew a borrowed book.", RenewArgs, lib.renew)]


def renewal_recorded(conv: Conversation, book_id: str):
    ok = book_id in conv.final_state["renewals"]
    return ok, f"renewals: {conv.final_state['renewals']}"


def make_toy_setting(tmp_path: Path) -> tuple[Setting, dict]:
    (tmp_path / "rules.md").write_text("### LIB-1\nRenew when asked.\n")
    scenario = {
        "id": "L01", "title": "Renew a book", "summary": "A reader wants to renew a book.",
        "session": {"reader": "R1"}, "seed": {"loans": {"B7": "R1"}}, "max_turns": 3,
        "customer": {"opening_message": "Can I renew B7?", "persona": "A reader.", "reveal": "Nothing hidden.",
                     "goal": "Renew the book."},
        "checks": [
            {"id": "renewed", "kind": "required", "rule": "LIB-1", "description": "Renews B7.",
             "check": "renewal_recorded", "args": {"book_id": "B7"}},
            {"id": "said_date", "kind": "required", "rule": "LIB-1", "description": "Gives the new date.",
             "check": "agent_says", "args": {"pattern": "1 November"}},  # a core check, reused as is
        ],
        "judge": ["polite"],
    }
    setting = Setting(
        name="library", agent_prompt="You help library readers.", customer_context="You are a library reader.",
        policy_doc="Renew books when asked.", session_line=lambda s: f"Reader {s['reader']}.",
        make_backend=Library, make_tools=renew_tool, scenario_dir=tmp_path, rules_file=tmp_path / "rules.md",
        checks={"renewal_recorded": renewal_recorded},
        judge_criteria={"polite": {"rule": "LIB-1", "question": "Polite?", "pass": "yes", "partial": "meh", "fail": "no"}},
    )
    return setting, scenario


def test_a_second_setting_runs_through_the_unchanged_core(tmp_path):
    setting, scenario = make_toy_setting(tmp_path)
    agent = FakeLLM(call("renew_book", {"book_id": "B7"}), reply("Done, it's now due on 1 November."), reply("Bye!"))
    customer = FakeLLM(reply(f"Thanks! {END}"))
    route = lambda model, messages, tools=None: (agent if model == "agent" else customer)(model, messages, tools)

    episode = run_episode(setting, scenario, "agent", complete=route, customer_model="customer", trace_dir=tmp_path)
    assert episode.status == "completed" and episode.final_state["renewals"] == ["B7"]
    assert "Reader R1." in agent.requests[0][0]["content"] and "library reader" in customer.requests[0][0]["content"]

    conv = Conversation.from_trace(Path(episode.trace_path))
    assert conv.setting == "library"
    judged = FakeLLM(reply(json.dumps({"polite": {"label": "pass", "reason": "r", "quote": "Done"}})))
    record = grade(conv, scenario, setting, use_judge=True, complete=judged)
    assert record["passed"] and [c["id"] for c in record["checks"]] == ["renewed", "said_date"]
