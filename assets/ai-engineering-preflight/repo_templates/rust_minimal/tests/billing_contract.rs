use rust_minimal_preflight_template::{AmountCents, CustomerId, SubscriptionBilling};

#[test]
fn bill_customer_returns_successful_result() {
    let customer_id = CustomerId::new("cus_123").expect("valid customer id");
    let amount = AmountCents::new(500).expect("valid amount");

    let result = SubscriptionBilling
        .bill_customer(customer_id, amount)
        .expect("billing succeeds");

    assert!(result.charged);
    assert_eq!(result.amount.value(), 500);
}
