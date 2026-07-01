#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CustomerId(String);

impl CustomerId {
    pub fn new(value: impl Into<String>) -> Result<Self, BillingError> {
        let value = value.into();
        if value.trim().is_empty() {
            return Err(BillingError::InvalidCustomerId);
        }
        Ok(Self(value))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AmountCents(u64);

impl AmountCents {
    pub fn new(value: u64) -> Result<Self, BillingError> {
        if value == 0 {
            return Err(BillingError::InvalidAmount);
        }
        Ok(Self(value))
    }

    pub fn value(self) -> u64 {
        self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BillingResult {
    pub charged: bool,
    pub amount: AmountCents,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BillingError {
    InvalidCustomerId,
    InvalidAmount,
}

pub struct SubscriptionBilling;

impl SubscriptionBilling {
    pub fn bill_customer(
        &self,
        customer_id: CustomerId,
        amount: AmountCents,
    ) -> Result<BillingResult, BillingError> {
        self.charge(&customer_id, amount)?;
        Ok(BillingResult {
            charged: true,
            amount,
        })
    }

    fn charge(&self, _customer_id: &CustomerId, _amount: AmountCents) -> Result<(), BillingError> {
        // Adapter placeholder. Real code would call a payment gateway at the edge.
        Ok(())
    }
}
