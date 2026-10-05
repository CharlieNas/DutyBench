import openai
import pytest

from dutybench.sim.customer import END
from dutybench.sim.runner import run_episode
from dutybench.sim.scenarios import load_scenarios
from tests.fakes import FakeLLM, call, reply


def router(agent: FakeLLM, customer: FakeLLM):
    """One `complete` function that sends each model's calls to its own scripted fake."""
    return lambda model, messages, tools=None: (agent if model == "agent" else customer)(model, messages, tools)


@pytest.fixture
def s08():
    return load_scenarios(["S08"])[0]


def test_both_scenarios_load():
    assert [s["id"] for s in load_scenarios(["S01", "S08"])] == ["S01", "S08"]


def test_episode_runs_until_customer_ends(s08, tmp_path):
    agent = FakeLLM(reply("I'm sorry to hear that. What happened?"),
                    call("log_complaint", {"customer_id": "CUS-2801", "summary": "Late fee and calls."}),
                    reply("Logged as CMP-0001."),
                    reply("You're welcome."))
    customer = FakeLLM(reply("I was charged a late fee I was told I wouldn't get."), reply(f"Thanks. {END}"))
    ep = run_episode(s08, "agent", complete=router(agent, customer), customer_model="customer", trace_dir=tmp_path)

    assert ep.status == "completed"
    assert [t["role"] for t in ep.transcript] == ["customer", "agent"] * 3
    assert ep.transcript[0]["text"] == "This is ridiculous. I want to make a complaint."
    assert ep.transcript[-2]["text"] == "Thanks."  # [END] stripped, final message still delivered
    assert ep.final_state["complaints"][0]["complaint_ref"] == "CMP-0001"
    assert ep.totals["agent"]["llm_calls"] == 4 and ep.totals["customer"]["llm_calls"] == 2
    assert (tmp_path / "S08__agent__baseline__r1.jsonl").exists()


def test_customer_sees_conversation_from_its_side(s08):
    agent = FakeLLM(reply("What happened?"))
    customer = FakeLLM(reply(END))
    run_episode(s08, "agent", complete=router(agent, customer), customer_model="customer")
    sent = customer.requests[0]
    assert sent[0]["role"] == "system" and "Sam Okafor" in sent[0]["content"]
    assert [m["role"] for m in sent[1:]] == ["assistant", "user"]  # own opening, then the agent
    assert "message 2 of at most 10" in sent[-1]["content"]


def test_grounded_condition_adds_policy_and_session_line(s08):
    agent = FakeLLM(reply("Hello."))
    run_episode(s08, "agent", condition="grounded", complete=router(agent, FakeLLM(reply(END))), customer_model="customer")
    system = agent.requests[0][0]["content"]
    assert "logged in as customer CUS-2801" in system
    assert "Financial Ombudsman Service" in system  # from policy_doc.md


def test_baseline_has_no_policy(s08):
    agent = FakeLLM(reply("Hello."))
    run_episode(s08, "agent", complete=router(agent, FakeLLM(reply(END))), customer_model="customer")
    assert "Financial Ombudsman" not in agent.requests[0][0]["content"]


def test_turn_limit(s08):
    s08 = {**s08, "max_turns": 2}
    agent = FakeLLM(reply("a"), reply("b"))
    customer = FakeLLM(reply("still unhappy"))
    ep = run_episode(s08, "agent", complete=router(agent, customer), customer_model="customer")
    assert ep.status == "max_turns" and len(ep.transcript) == 4


def test_api_failure_marks_episode_as_error_not_failure(s08):
    def broken(model, messages, tools=None):
        raise openai.APIConnectionError(request=None)
    ep = run_episode(s08, "agent", complete=broken, customer_model="customer")
    assert ep.status == "error" and "APIConnectionError" in ep.error


def test_our_own_bugs_are_not_swallowed(s08):
    def buggy(model, messages, tools=None):
        raise KeyError("bug in our code")
    with pytest.raises(KeyError):
        run_episode(s08, "agent", complete=buggy, customer_model="customer")
