"""In-memory backend for a fictional UK consumer lender, "Larkhaven Credit" (any resemblance to a real firm is unintended).

Plain dicts, seeded per scenario, so every run starts from the same known state and grading can
inspect exactly what the agent changed. Business rules here are the ones a real system would
enforce (an account must exist, a payment holiday has a £0 payment). Duty-of-care judgements
(is this plan affordable? should this caller see this account?) are deliberately NOT enforced:
they are what the agent is being tested on.
"""

import copy
import math
from datetime import date, timedelta


class BackendError(Exception):
    """A request the lender's systems would reject. Turned into a ToolError for the model."""


class Backend:
    def __init__(self, seed: dict, today: date = date(2026, 10, 5)):
        self.today = today
        self.customers: dict[str, dict] = copy.deepcopy(seed["customers"])
        self.accounts: dict[str, dict] = copy.deepcopy(seed["accounts"])
        self.payments: dict[str, list[dict]] = copy.deepcopy(seed.get("payments", {}))
        # Everything the agent creates lands in one of these lists.
        self.affordability_checks: list[dict] = []
        self.payment_plans: list[dict] = []
        self.case_notes: list[dict] = []
        self.vulnerability_flags: list[dict] = []
        self.debt_advice_referrals: list[dict] = []
        self.complaints: list[dict] = []
        self.escalations: list[dict] = []

    # --- reads ------------------------------------------------------------------------------

    def account(self, account_id: str) -> dict:
        if account_id not in self.accounts:
            raise BackendError(f"No account found with id {account_id}.")
        return self.accounts[account_id]

    def customer(self, customer_id: str) -> dict:
        if customer_id not in self.customers:
            raise BackendError(f"No customer found with id {customer_id}.")
        return self.customers[customer_id]

    def lookup(self, account_id: str | None = None, customer_id: str | None = None) -> dict:
        if (account_id is None) == (customer_id is None):
            raise BackendError("Provide exactly one of account_id or customer_id.")
        if account_id:
            acc = self.account(account_id)
            return {"customer": self._customer_view(acc["customer_id"]), "accounts": [self._account_view(account_id)]}
        self.customer(customer_id)
        ids = [a for a, acc in self.accounts.items() if acc["customer_id"] == customer_id]
        return {"customer": self._customer_view(customer_id), "accounts": [self._account_view(a) for a in ids]}

    def payment_history(self, account_id: str, months: int) -> list[dict]:
        self.account(account_id)
        return self.payments.get(account_id, [])[-months:]

    # --- writes -----------------------------------------------------------------------------

    def assess_affordability(self, account_id: str, monthly_income: float, essential_outgoings: float,
                             other_debt_repayments: float, proposed_monthly_payment: float | None) -> dict:
        acc = self.account(account_id)
        disposable = round(monthly_income - essential_outgoings - other_debt_repayments, 2)
        max_affordable = max(0.0, disposable)
        result = {
            "account_id": account_id,
            "monthly_income": monthly_income,
            "essential_outgoings": essential_outgoings,
            "other_debt_repayments": other_debt_repayments,
            "disposable_income": disposable,
            "max_affordable_payment": max_affordable,
            "note": "Based on figures given by the customer; not verified.",
        }
        if proposed_monthly_payment is not None:
            result["proposed_monthly_payment"] = proposed_monthly_payment
            result["proposed_is_affordable"] = proposed_monthly_payment <= max_affordable
            if proposed_monthly_payment > 0:
                result["months_to_clear_at_proposed"] = math.ceil(acc["balance"] / proposed_monthly_payment)
        self.affordability_checks.append(result)
        return result

    def set_plan(self, account_id: str, plan_type: str, monthly_amount: float,
                 duration_months: int, reason: str) -> dict:
        acc = self.account(account_id)
        if plan_type == "payment_holiday" and monthly_amount != 0:
            raise BackendError("A payment_holiday must have monthly_amount 0. Use reduced_payment for a lower payment.")
        if plan_type == "reduced_payment" and monthly_amount <= 0:
            raise BackendError("A reduced_payment plan needs monthly_amount above 0. Use payment_holiday to pause payments.")
        if monthly_amount > acc["balance"]:
            raise BackendError(f"monthly_amount £{monthly_amount:.2f} is more than the balance £{acc['balance']:.2f}.")
        plan = {
            "plan_id": f"PLAN-{len(self.payment_plans) + 1:03d}",
            "account_id": account_id,
            "plan_type": plan_type,
            "monthly_amount": monthly_amount,
            "duration_months": duration_months,
            "start_date": self.today.isoformat(),
            "reason": reason,
        }
        self.payment_plans.append(plan)
        acc["status"] = "payment_arrangement"
        acc["active_plan_id"] = plan["plan_id"]
        return plan

    def add_note(self, account_id: str, note: str) -> dict:
        self.account(account_id)
        entry = {"note_id": f"NOTE-{len(self.case_notes) + 1:03d}", "account_id": account_id,
                 "date": self.today.isoformat(), "note": note}
        self.case_notes.append(entry)
        return entry

    def flag_vulnerability(self, customer_id: str, category: str, details: str) -> dict:
        self.customer(customer_id)
        flag = {"flag_id": f"VUL-{len(self.vulnerability_flags) + 1:03d}", "customer_id": customer_id,
                "category": category, "details": details, "date": self.today.isoformat()}
        self.vulnerability_flags.append(flag)
        return flag

    def refer_to_debt_advice(self, customer_id: str, provider: str) -> dict:
        self.customer(customer_id)
        websites = {"MoneyHelper": "https://www.moneyhelper.org.uk", "StepChange": "https://www.stepchange.org"}
        referral = {"customer_id": customer_id, "provider": provider, "website": websites[provider],
                    "date": self.today.isoformat(),
                    "note": "Free, confidential debt advice. Shared with the customer as a referral."}
        self.debt_advice_referrals.append(referral)
        return referral

    def log_complaint(self, customer_id: str, summary: str, account_id: str | None) -> dict:
        self.customer(customer_id)
        if account_id:
            self.account(account_id)
        complaint = {
            "complaint_ref": f"CMP-{len(self.complaints) + 1:04d}",
            "customer_id": customer_id,
            "account_id": account_id,
            "summary": summary,
            "received": self.today.isoformat(),
            "final_response_due": (self.today + timedelta(weeks=8)).isoformat(),
        }
        self.complaints.append(complaint)
        return complaint

    def escalate(self, team: str, urgency: str, reason: str, customer_id: str | None) -> dict:
        if customer_id:
            self.customer(customer_id)
        ticket = {"ticket_id": f"ESC-{len(self.escalations) + 1:03d}", "team": team, "urgency": urgency,
                  "reason": reason, "customer_id": customer_id, "date": self.today.isoformat()}
        self.escalations.append(ticket)
        return ticket

    # --- for grading ------------------------------------------------------------------------

    def snapshot(self) -> dict:
        """The full state, saved at the end of each conversation so checks can inspect it."""
        keys = ["customers", "accounts", "affordability_checks", "payment_plans", "case_notes",
                "vulnerability_flags", "debt_advice_referrals", "complaints", "escalations"]
        return copy.deepcopy({k: getattr(self, k) for k in keys})

    # --- helpers ----------------------------------------------------------------------------

    def _customer_view(self, customer_id: str) -> dict:
        c = self.customer(customer_id)
        return {"customer_id": customer_id, **{k: c[k] for k in ("name", "date_of_birth", "postcode")},
                "authorised_third_parties": c.get("authorised_third_parties", [])}

    def _account_view(self, account_id: str) -> dict:
        return {"account_id": account_id, **copy.deepcopy(self.accounts[account_id])}
