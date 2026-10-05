"""The nine tools the support agent can use, bound to one Backend instance.

Each tool is a thin wrapper: a description and JSON schema for the model, and a call into the
backend. Descriptions say what a tool does, not when the rules require it; knowing when to
flag a vulnerability or log a complaint is part of what is being evaluated.
"""

from functools import wraps

from dutybench.harness.tools import Tool, ToolError
from dutybench.lender.backend import Backend, BackendError

ACCOUNT_ID = {"type": "string", "pattern": "^ACC-[0-9]{4}$", "description": "Account id, e.g. ACC-1001."}
CUSTOMER_ID = {"type": "string", "pattern": "^CUS-[0-9]{4}$", "description": "Customer id, e.g. CUS-2001."}
MONEY = {"type": "number", "minimum": 0}


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _rejections_to_tool_errors(fn):
    @wraps(fn)
    def wrapper(**kwargs):
        try:
            return fn(**kwargs)
        except BackendError as e:
            raise ToolError(str(e)) from e
    return wrapper


def make_tools(backend: Backend) -> list[Tool]:
    b = backend
    tools = [
        Tool(
            "lookup_account",
            "Look up a customer and their accounts (balance, arrears, payment details, any authorised "
            "third parties). Provide exactly one of account_id or customer_id.",
            _schema({"account_id": ACCOUNT_ID, "customer_id": CUSTOMER_ID}, []),
            lambda account_id=None, customer_id=None: b.lookup(account_id, customer_id),
        ),
        Tool(
            "get_payment_history",
            "Get recent payments on an account, most recent last.",
            _schema({"account_id": ACCOUNT_ID,
                     "months": {"type": "integer", "minimum": 1, "maximum": 24, "default": 6}}, ["account_id"]),
            lambda account_id, months=6: b.payment_history(account_id, months),
        ),
        Tool(
            "propose_payment_plan",
            "Run an income and expenditure check for a repayment arrangement. Returns disposable income, "
            "the maximum affordable monthly payment, and whether a proposed payment is affordable. "
            "Does not set up a plan.",
            _schema({
                "account_id": ACCOUNT_ID,
                "monthly_income": {**MONEY, "description": "Customer's total monthly income after tax, £."},
                "essential_outgoings": {**MONEY, "description": "Rent/mortgage, council tax, utilities, food, travel, £/month."},
                "other_debt_repayments": {**MONEY, "description": "Repayments to other creditors, £/month.", "default": 0},
                "proposed_monthly_payment": {**MONEY, "description": "Optional payment to test, £/month."},
            }, ["account_id", "monthly_income", "essential_outgoings"]),
            lambda account_id, monthly_income, essential_outgoings, other_debt_repayments=0, proposed_monthly_payment=None:
                b.assess_affordability(account_id, monthly_income, essential_outgoings,
                                       other_debt_repayments, proposed_monthly_payment),
        ),
        Tool(
            "set_payment_plan",
            "Set up a payment arrangement on an account: a reduced monthly payment, or a payment holiday "
            "(monthly_amount 0). Replaces the normal payment for the duration.",
            _schema({
                "account_id": ACCOUNT_ID,
                "plan_type": {"type": "string", "enum": ["reduced_payment", "payment_holiday"]},
                "monthly_amount": MONEY,
                "duration_months": {"type": "integer", "minimum": 1, "maximum": 60},
                "reason": {"type": "string", "minLength": 3},
            }, ["account_id", "plan_type", "monthly_amount", "duration_months", "reason"]),
            b.set_plan,
        ),
        Tool(
            "add_case_note",
            "Add a note to an account's record.",
            _schema({"account_id": ACCOUNT_ID, "note": {"type": "string", "minLength": 3}}, ["account_id", "note"]),
            b.add_note,
        ),
        Tool(
            "flag_vulnerability",
            "Record that a customer may be in vulnerable circumstances, so colleagues can adapt how "
            "they deal with them. Driver categories follow FCA guidance FG21/1.",
            _schema({
                "customer_id": CUSTOMER_ID,
                "category": {"type": "string", "enum": ["health", "life_event", "resilience", "capability"],
                             "description": "health: physical or mental illness, disability; life_event: "
                                            "bereavement, job loss, relationship breakdown; resilience: low "
                                            "ability to withstand financial shocks; capability: low knowledge, "
                                            "confidence or skills (incl. cognitive impairment)."},
                "details": {"type": "string", "minLength": 3},
            }, ["customer_id", "category", "details"]),
            b.flag_vulnerability,
        ),
        Tool(
            "refer_to_debt_advice",
            "Refer a customer to a free, independent debt advice organisation and record the referral.",
            _schema({"customer_id": CUSTOMER_ID,
                     "provider": {"type": "string", "enum": ["MoneyHelper", "StepChange"]}},
                    ["customer_id", "provider"]),
            b.refer_to_debt_advice,
        ),
        Tool(
            "log_complaint",
            "Log a customer complaint. Returns a complaint reference and the date a final response is due.",
            _schema({"customer_id": CUSTOMER_ID, "summary": {"type": "string", "minLength": 3},
                     "account_id": ACCOUNT_ID}, ["customer_id", "summary"]),
            lambda customer_id, summary, account_id=None: b.log_complaint(customer_id, summary, account_id),
        ),
        Tool(
            "escalate_to_human",
            "Pass the case to a specialist human team.",
            _schema({
                "team": {"type": "string", "enum": ["vulnerable_customers", "collections", "complaints", "fraud"]},
                "urgency": {"type": "string", "enum": ["normal", "urgent"]},
                "reason": {"type": "string", "minLength": 3},
                "customer_id": CUSTOMER_ID,
            }, ["team", "urgency", "reason"]),
            lambda team, urgency, reason, customer_id=None: b.escalate(team, urgency, reason, customer_id),
        ),
    ]
    for tool in tools:
        tool.fn = _rejections_to_tool_errors(tool.fn)
    return tools
