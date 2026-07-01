import pytest

from example_package import SubscriptionBilling


def test_bill_customer_returns_successful_result() -> None:
    result = SubscriptionBilling().bill_customer("cus_123", 500)

    assert result.customer_id == "cus_123"
    assert result.amount_cents == 500
    assert result.charged is True


def test_bill_customer_rejects_empty_customer_id() -> None:
    with pytest.raises(ValueError, match="customer_id"):
        SubscriptionBilling().bill_customer("", 500)
