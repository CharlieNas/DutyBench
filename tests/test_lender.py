import json

import pytest

from dutybench.harness.tools import execute
from dutybench.lender.backend import Backend
from dutybench.lender.sample_data import SAMPLE_SEED
from dutybench.lender.tools import make_tools


@pytest.fixture
def lender():
    backend = Backend(SAMPLE_SEED)
    tools = {t.name: t for t in make_tools(backend)}

    def run(name, **args):
        return execute(tools, name, json.dumps(args))

    return backend, run


def test_nine_tools_with_valid_schemas():
    from jsonschema import Draft202012Validator
    tools = make_tools(Backend(SAMPLE_SEED))
    assert [t.name for t in tools] == [
        "lookup_account", "get_payment_history", "propose_payment_plan", "set_payment_plan", "add_case_note",
        "flag_vulnerability", "refer_to_debt_advice", "log_complaint", "escalate_to_human"]
    for t in tools:
        Draft202012Validator.check_schema(t.parameters)


def test_each_run_starts_from_the_seed(lender):
    backend, run = lender
    run("set_payment_plan", account_id="ACC-1001", plan_type="payment_holiday", monthly_amount=0,
        duration_months=2, reason="job loss")
    assert Backend(SAMPLE_SEED).accounts["ACC-1001"]["status"] == "in_arrears"  # seed not mutated


def test_lookup_by_customer_returns_all_accounts(lender):
    _, run = lender
    out = run("lookup_account", customer_id="CUS-2001")["result"]
    assert out["customer"]["name"] == "Jordan Ellery"
    assert [a["account_id"] for a in out["accounts"]] == ["ACC-1001", "ACC-1002"]


def test_lookup_shows_authorised_third_parties(lender):
    _, run = lender
    out = run("lookup_account", account_id="ACC-1003")["result"]
    assert out["customer"]["authorised_third_parties"][0]["authority"] == "lasting_power_of_attorney"


def test_lookup_needs_exactly_one_id(lender):
    _, run = lender
    assert "exactly one" in run("lookup_account")["error"]
    assert "exactly one" in run("lookup_account", account_id="ACC-1001", customer_id="CUS-2001")["error"]


def test_unknown_account_is_a_readable_error(lender):
    _, run = lender
    assert run("get_payment_history", account_id="ACC-9999") == {"error": "No account found with id ACC-9999."}


def test_bad_id_format_caught_by_schema(lender):
    _, run = lender
    assert "does not match" in run("lookup_account", account_id="1001")["error"]


def test_payment_history_most_recent_last(lender):
    _, run = lender
    out = run("get_payment_history", account_id="ACC-1001", months=2)["result"]
    assert [p["status"] for p in out] == ["paid", "missed"]


def test_affordability_check(lender):
    backend, run = lender
    out = run("propose_payment_plan", account_id="ACC-1001", monthly_income=1100, essential_outgoings=950,
              other_debt_repayments=50, proposed_monthly_payment=500)["result"]
    assert out["disposable_income"] == 100
    assert out["max_affordable_payment"] == 100
    assert out["proposed_is_affordable"] is False
    assert backend.affordability_checks == [out]
    assert backend.payment_plans == []  # a proposal never sets a plan


def test_negative_disposable_income_means_zero_affordable(lender):
    _, run = lender
    out = run("propose_payment_plan", account_id="ACC-1001", monthly_income=800, essential_outgoings=900)["result"]
    assert out["disposable_income"] == -100 and out["max_affordable_payment"] == 0


def test_backend_does_not_block_unaffordable_plans(lender):
    """By design: affordability is the agent's duty, so the backend lets a bad plan through
    and grading catches it."""
    backend, run = lender
    run("propose_payment_plan", account_id="ACC-1001", monthly_income=1100, essential_outgoings=1000)
    out = run("set_payment_plan", account_id="ACC-1001", plan_type="reduced_payment", monthly_amount=500,
              duration_months=7, reason="customer asked")
    assert out["result"]["plan_id"] == "PLAN-001"
    assert backend.accounts["ACC-1001"]["status"] == "payment_arrangement"


def test_plan_business_rules(lender):
    _, run = lender
    base = dict(account_id="ACC-1001", duration_months=3, reason="hardship")
    assert "must have monthly_amount 0" in run("set_payment_plan", plan_type="payment_holiday", monthly_amount=50, **base)["error"]
    assert "needs monthly_amount above 0" in run("set_payment_plan", plan_type="reduced_payment", monthly_amount=0, **base)["error"]
    assert "more than the balance" in run("set_payment_plan", plan_type="reduced_payment", monthly_amount=9999, **base)["error"]
    assert "is not one of" in run("set_payment_plan", plan_type="skip_forever", monthly_amount=0, **base)["error"]


def test_vulnerability_flag_uses_fg21_1_drivers(lender):
    backend, run = lender
    assert "is not one of" in run("flag_vulnerability", customer_id="CUS-2001", category="sad", details="x" * 5)["error"]
    run("flag_vulnerability", customer_id="CUS-2001", category="life_event", details="Recent bereavement (mother).")
    assert backend.vulnerability_flags[0]["category"] == "life_event"


def test_complaint_gets_reference_and_eight_week_deadline(lender):
    backend, run = lender
    out = run("log_complaint", customer_id="CUS-2001", summary="Unhappy with collections calls.")["result"]
    assert out["complaint_ref"] == "CMP-0001"
    assert out["received"] == "2026-10-05" and out["final_response_due"] == "2026-11-30"


def test_referral_note_and_escalation_are_recorded(lender):
    backend, run = lender
    assert run("refer_to_debt_advice", customer_id="CUS-2001", provider="StepChange")["result"]["website"] == "https://www.stepchange.org"
    run("add_case_note", account_id="ACC-1001", note="Customer lost job last week.")
    run("escalate_to_human", team="vulnerable_customers", urgency="urgent", reason="Customer not coping.")
    snap = backend.snapshot()
    assert len(snap["debt_advice_referrals"]) == len(snap["case_notes"]) == len(snap["escalations"]) == 1
