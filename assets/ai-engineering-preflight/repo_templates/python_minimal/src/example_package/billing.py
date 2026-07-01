from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BillingResult:
    customer_id: str
    amount_cents: int
    charged: bool


class SubscriptionBilling:
    """Public orchestration API for billing a customer."""

    def bill_customer(self, customer_id: str, amount_cents: int) -> BillingResult:
        self._validate_customer_id(customer_id)
        self._validate_amount(amount_cents)
        charged = self._charge(customer_id=customer_id, amount_cents=amount_cents)
        return BillingResult(customer_id=customer_id, amount_cents=amount_cents, charged=charged)

    def _validate_customer_id(self, customer_id: str) -> None:
        if not customer_id.strip():
            raise ValueError("customer_id must not be empty")

    def _validate_amount(self, amount_cents: int) -> None:
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")

    def _charge(self, *, customer_id: str, amount_cents: int) -> bool:
        # Adapter placeholder. Real code would call a payment gateway at the edge.
        _ = (customer_id, amount_cents)
        return True
