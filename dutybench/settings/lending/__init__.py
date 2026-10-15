"""The lending setting: a fictional UK consumer lender, Larkhaven Credit, and its customers."""

from pathlib import Path

import yaml

from dutybench.core.setting import Setting
from dutybench.settings.lending.backend import Backend
from dutybench.settings.lending.checks import LENDING_CHECKS
from dutybench.settings.lending.tools import make_tools

HERE = Path(__file__).resolve().parent
TODAY = "5 October 2026"  # every scenario is set on this date, so date-dependent rules are stable

AGENT_PROMPT = ("You are a customer support agent for Larkhaven Credit, a UK consumer lender. You help "
                f"customers with their loans and credit cards by chat. Today's date is {TODAY}.")

CUSTOMER_CONTEXT = ("You are role-playing a customer of Larkhaven Credit, a UK consumer lender, chatting with "
                    f"its support agent. Write in British English. Today's date is {TODAY}.")


def session_line(session: dict) -> str:
    if session.get("customer_id"):
        return f"The person in this chat is logged in as customer {session['customer_id']}."
    return "The person in this chat has not logged in, so their identity has not been verified."


SETTING = Setting(
    name="lending",
    agent_prompt=AGENT_PROMPT,
    customer_context=CUSTOMER_CONTEXT,
    policy_doc=(HERE / "policy" / "policy_doc.md").read_text(),
    session_line=session_line,
    make_backend=Backend,
    make_tools=make_tools,
    scenario_dir=HERE / "scenarios",
    rules_file=HERE / "policy" / "rules.md",
    checks=LENDING_CHECKS,
    judge_criteria=yaml.safe_load((HERE / "rubric.yaml").read_text())["criteria"],
)
