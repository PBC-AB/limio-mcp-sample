# Limio API Structure Documentation

Based on exploration with test customer ID: `cus-a1b2c3d4e5f6789012345678901234ab`

## Key Data Locations

### Pricing Information
- **Location**: `subscription.data.price`
- **Fields**:
  - `amount`: The numeric price (e.g., 99 for $99)
  - `currency`: Currency code (e.g., "USD")
  - `summary.headline`: Display price HTML (e.g., "<p>$999 per location per year</p>")

**Note**: Orders in Limio do NOT contain pricing information, only tracking data.

### Subscription Structure
```json
{
  "id": "sub-xxx",
  "status": "active",
  "reference": "17H49B0T5BH8",
  "data": {
    "name": "Toro myTurf",
    "price": {
      "amount": 99,
      "currency": "USD",
      "summary": {
        "headline": "<p>$999 per location per year</p>"
      }
    },
    "termStartDate": "2025-05-27T18:09:44.736Z",
    "termEndDate": "2026-05-27",
    "attributes": {
      "autoRenew": false
    }
  }
}
```

### Payment Methods (Zuora Integration)
- **Location**: `payment_method.data.zuora.result`
- **Key Fields**:
  - `CreditCardType`: "Visa", "Mastercard", etc.
  - `CreditCardMaskNumber`: "************4242"
  - `CreditCardHolderName`: Cardholder name
  - `CreditCardExpirationMonth`: Numeric month
  - `CreditCardExpirationYear`: Four-digit year

### Related Objects Types
When calling `/api/objects/limio/subscription/{id}/related`:
- `customer`: Customer details
- `order`: Order records (no pricing)
- `subscription_offer`: Contains pricing duplicate
- `address`: Billing/shipping addresses
- `event`: Subscription events
- `identity`: External system identities
- `payment_method`: Payment methods

### Event Types
Common event types found:
- `order.new`: New order created
- `order.change_payment`: Payment method updated
- `order.change_address`: Address updated

## API Endpoints Used

1. **Customer Details**: `GET /api/objects/limio/customer/{customer_id}`
2. **Customer Subscriptions**: `GET /api/objects/limio/customer/{customer_id}/related`
3. **Subscription Details**: `GET /api/objects/limio/subscription/{subscription_id}`
4. **Subscription Related**: `GET /api/objects/limio/subscription/{subscription_id}/related`

## Implementation Notes

1. The `/related` endpoint returns ALL related objects without pagination
2. Subscription pricing is in the main subscription object, not in orders
3. Payment methods use Zuora integration with detailed card information
4. The display price may differ from the actual amount (e.g., $99 stored, $999 displayed)
5. Term dates determine renewal timing
6. Auto-renewal is controlled by `data.attributes.autoRenew`