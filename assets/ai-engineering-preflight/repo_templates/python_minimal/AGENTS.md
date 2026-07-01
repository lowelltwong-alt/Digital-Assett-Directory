# AGENTS.md

Follow the Python AI Engineering Preflight rules.

- Public API: `example_package.SubscriptionBilling.bill_customer()`.
- Internal helpers in `billing.py` are underscore-prefixed and must not be called externally.
- Tests should target public behavior unless a helper contains complex isolated logic.
- Run `python -m pytest` before reporting completion.
