"""A small synthetic book of customers, used by tests, the live check and the demo's free-chat mode.
Scenarios define their own seeds in the same shape. All names and figures are invented; postcodes
use the non-existent area "TE" so none can match a real address."""

SAMPLE_SEED = {
    "customers": {
        "CUS-2001": {"name": "Jordan Ellery", "date_of_birth": "1988-03-14", "postcode": "TE1 4QP",
                     "authorised_third_parties": []},
        "CUS-2002": {"name": "Morgan Hale", "date_of_birth": "1951-11-02", "postcode": "TE7 2LD",
                     "authorised_third_parties": [
                         {"name": "Sam Hale", "relationship": "son", "authority": "lasting_power_of_attorney"}]},
    },
    "accounts": {
        "ACC-1001": {"customer_id": "CUS-2001", "product": "personal_loan", "balance": 3482.17,
                     "monthly_payment": 186.40, "arrears": 186.40, "missed_payments": 1, "status": "in_arrears",
                     "apr": 14.9, "next_payment_date": "2026-10-28", "direct_debit_day": 28},
        "ACC-1002": {"customer_id": "CUS-2001", "product": "credit_card", "balance": 912.53, "credit_limit": 1500.0,
                     "monthly_payment": 27.38, "arrears": 0.0, "missed_payments": 0, "status": "up_to_date",
                     "apr": 29.9, "next_payment_date": "2026-10-19", "direct_debit_day": 19},
        "ACC-1003": {"customer_id": "CUS-2002", "product": "personal_loan", "balance": 5127.64,
                     "monthly_payment": 241.15, "arrears": 0.0, "missed_payments": 0, "status": "up_to_date",
                     "apr": 11.4, "next_payment_date": "2026-10-12", "direct_debit_day": 12},
    },
    "payments": {
        "ACC-1001": [
            {"date": "2026-06-28", "amount": 186.40, "status": "paid"},
            {"date": "2026-07-28", "amount": 186.40, "status": "paid"},
            {"date": "2026-08-28", "amount": 186.40, "status": "paid"},
            {"date": "2026-09-28", "amount": 0.0, "status": "missed"},
        ],
        "ACC-1002": [
            {"date": "2026-08-19", "amount": 27.38, "status": "paid"},
            {"date": "2026-09-19", "amount": 50.00, "status": "paid"},
        ],
        "ACC-1003": [
            {"date": "2026-08-12", "amount": 241.15, "status": "paid"},
            {"date": "2026-09-12", "amount": 241.15, "status": "paid"},
        ],
    },
}
