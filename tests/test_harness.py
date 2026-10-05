import json

from dutybench.harness.agent import STEP_LIMIT_REPLY, Agent
from dutybench.harness.tools import Tool, ToolError, execute
from dutybench.harness.trace import Tracer
from tests.fakes import FakeLLM, call, reply


def get_balance(account_id: str) -> dict:
    if account_id != "ACC-1":
        raise ToolError(f"No account with id {account_id}.")
    return {"balance": 120.5}


BALANCE = Tool(
    name="get_balance",
    description="Get an account balance.",
    parameters={"type": "object", "properties": {"account_id": {"type": "string", "pattern": "^ACC-"}},
                "required": ["account_id"], "additionalProperties": False},
    fn=get_balance,
)


def make_agent(fake, tmp_path=None, **kw):
    tracer = Tracer(tmp_path / "trace.jsonl" if tmp_path else None)
    return Agent(model="fake", system_prompt="You are support.", tools=[BALANCE],
                 tracer=tracer, complete=fake, **kw)


# --- execute(): validation and errors returned to the model -------------------------------

def test_execute_valid_call():
    assert execute({"get_balance": BALANCE}, "get_balance", '{"account_id": "ACC-1"}') == {"result": {"balance": 120.5}}


def test_execute_unknown_tool_lists_available():
    out = execute({"get_balance": BALANCE}, "delete_everything", "{}")
    assert "Unknown tool 'delete_everything'" in out["error"] and "get_balance" in out["error"]


def test_execute_bad_json():
    assert "not valid JSON" in execute({"get_balance": BALANCE}, "get_balance", "{oops")["error"]


def test_execute_schema_errors_are_readable():
    out = execute({"get_balance": BALANCE}, "get_balance", '{"account_id": "X1", "extra": 1}')
    assert out["error"].startswith("Invalid arguments:")
    assert "account_id: 'X1' does not match '^ACC-'" in out["error"]
    assert "'extra' was unexpected" in out["error"]


def test_execute_missing_required():
    assert "'account_id' is a required property" in execute({"get_balance": BALANCE}, "get_balance", "{}")["error"]


def test_execute_business_error():
    assert execute({"get_balance": BALANCE}, "get_balance", '{"account_id": "ACC-9"}') == {"error": "No account with id ACC-9."}


# --- the loop -----------------------------------------------------------------------------

def test_plain_reply_without_tools():
    agent = make_agent(FakeLLM(reply("Hello! How can I help?")))
    assert agent.respond("hi") == "Hello! How can I help?"
    assert [m["role"] for m in agent.messages] == ["system", "user", "assistant"]


def test_tool_call_then_reply(tmp_path):
    fake = FakeLLM(call("get_balance", {"account_id": "ACC-1"}), reply("Your balance is £120.50."))
    agent = make_agent(fake, tmp_path)
    assert agent.respond("What's my balance?") == "Your balance is £120.50."

    # The second model call saw the tool result, linked to the right call id.
    tool_msg = fake.requests[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"]) == {"result": {"balance": 120.5}}

    # The trace has every step, in order, and is on disk as JSONL.
    types = [e["type"] for e in agent.tracer.events]
    assert types == ["customer_msg", "llm_call", "tool_call", "llm_call", "agent_reply"]
    lines = (tmp_path / "trace.jsonl").read_text().splitlines()
    assert [json.loads(l)["type"] for l in lines] == types
    assert agent.tracer.totals()["llm_calls"] == 2
    assert agent.tracer.totals()["cost_usd"] == 0.002


def test_model_recovers_from_invalid_arguments():
    fake = FakeLLM(call("get_balance", {"account_id": "123"}, id="c1"),
                   call("get_balance", {"account_id": "ACC-1"}, id="c2"),
                   reply("Your balance is £120.50."))
    agent = make_agent(fake)
    assert agent.respond("balance?") == "Your balance is £120.50."
    first_result = [e for e in agent.tracer.events if e["type"] == "tool_call"][0]["output"]
    assert "does not match" in first_result["error"]


def test_step_limit_hands_over_and_is_recorded():
    fake = FakeLLM(*[call("get_balance", {"account_id": "ACC-1"}, id=f"c{i}") for i in range(3)])
    agent = make_agent(fake, max_steps=3)
    assert agent.respond("balance?") == STEP_LIMIT_REPLY  # no text was said before the limit
    assert any(e["type"] == "step_limit" for e in agent.tracer.events)
    assert agent.tracer.events[-1] == {**agent.tracer.events[-1], "type": "agent_reply", "forced": True}


def test_policy_doc_goes_into_system_message():
    agent = make_agent(FakeLLM(), policy_doc="Always signpost MoneyHelper.")
    assert agent.messages[0]["content"].startswith("You are support.")
    assert "Always signpost MoneyHelper." in agent.messages[0]["content"]


def test_history_persists_across_turns():
    fake = FakeLLM(reply("Hi."), reply("Still here."))
    agent = make_agent(fake)
    agent.respond("one")
    agent.respond("two")
    assert [m.get("content") for m in fake.requests[1]][1:] == ["one", "Hi.", "two"]


def test_text_sent_alongside_tool_calls_is_part_of_the_reply():
    """Regression: DeepSeek writes to the customer in the same message as a tool call."""
    first = call("get_balance", {"account_id": "ACC-1"})
    first.text = "Sorry to hear that. Let me check your account."
    first.message["content"] = first.text
    agent = make_agent(FakeLLM(first, reply("Your balance is £120.50.")))
    assert agent.respond("balance?") == "Sorry to hear that. Let me check your account.\n\nYour balance is £120.50."
