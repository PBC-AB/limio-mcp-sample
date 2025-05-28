# Limio API MCP Server Implementation Guide

This guide provides all the necessary information for implementing a Model Context Protocol (MCP) server for the Limio API, based on our investigation and discoveries.

## Table of Contents
1. [OAuth Authentication](#oauth-authentication)
2. [Key API Discoveries](#key-api-discoveries)
3. [Customer and Subscription Search](#customer-and-subscription-search)
4. [MCP Server Proof of Concept](#mcp-server-proof-of-concept)
5. [Implementation Checklist](#implementation-checklist)

## OAuth Authentication

### Getting an Access Token

The Limio API uses OAuth 2.0 client credentials flow for authentication.

```python
import requests

def get_oauth_token(base_url, client_id, client_secret):
    """Get OAuth Bearer token using client credentials flow"""
    token_url = f"{base_url}/oauth2/token"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    response.raise_for_status()
    
    token_data = response.json()
    return token_data.get("access_token")
```

**Important Notes:**
- The token has a limited lifetime (check `expires_in` field)
- Store the token and reuse it until it expires
- The token scope observed: `api/subscription:sync catalog/read`

## Key API Discoveries

### 1. Events Endpoint Issue

**Problem**: The subscription-specific events endpoint returns empty results even when events exist.
- ❌ `/api/objects/limio/events/{subscription_id}/events` - Always returns `{"items":[],"unpackedItems":[]}`

**Root Cause**: Events don't have a top-level `subscription_id` field. The subscription reference is nested deep within the event structure at `data.event.subscriptions[].id`.

### 2. The Related Objects Solution

**Solution**: Use the related objects endpoint to get all data for a subscription, including events.
- ✅ `/api/objects/limio/subscription/{subscription_id}/related`

**Benefits of the Related Endpoint:**
- Returns ALL related objects in a single API call
- No pagination needed (returns everything)
- Includes multiple object types:
  - Events (with `record_type: "event"`)
  - Customer information
  - Orders
  - Payment methods
  - Addresses
  - Subscription offers
  - User entitlements

**Example Response Structure:**
```json
{
  "items": [
    {
      "record_type": "event",
      "id": "event-44b197ecba00bedf14d514abbb9ca89a",
      "data": {
        "type": "order.new",
        "message": "Order Received"
      },
      "status": "submitted",
      "created": "2025-05-27T18:09:47.233Z"
    },
    {
      "record_type": "customer",
      "id": "cus-886716de7dba964a9c74ffb7736ac9b3",
      "data": {
        "name": "John Doe",
        "email": "john@example.com"
      }
    }
    // ... more related objects
  ]
}
```

## Customer and Subscription Search

### Finding Customers

**Important Discovery**: The Limio API does not support server-side filtering for customers by email or name. Query parameters like `?email=...` return 400 errors.

**Solution**: Client-side filtering

### Finding Subscriptions

**Direct Lookup**: If you know the subscription ID, you can fetch it directly:
- ✅ `GET /api/objects/limio/subscription/{subscription_id}` - Works perfectly

**Search Limitations**: 
- ❌ Cannot search subscriptions by ID, reference, or any other field
- ❌ Query parameters like `?reference=...` or `?q=...` return 400 errors
- ❌ Must find subscriptions through customer relationships

**Solution**: Always go through customers to find subscriptions
```python
def find_customer_by_email(access_token, base_url, email):
    """Find a customer by email (requires client-side search)"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    url = f"{base_url}/api/objects/limio/customers"
    all_customers = []
    query_more = None
    
    while True:
        params = {"limit": 100}
        if query_more:
            params["queryMore"] = query_more
            
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            # Search for customer by email
            for customer in items:
                customer_data = customer.get('data', {})
                if customer_data.get('email') == email:
                    return customer
            
            # Handle pagination
            query_more = data.get('queryMore')
            if not query_more:
                break
    
    return None
```

### Getting Customer Subscriptions

Once you have a customer ID, use the related objects endpoint:

```python
def get_customer_subscriptions(access_token, base_url, customer_id):
    """Get all subscriptions for a customer"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    url = f"{base_url}/api/objects/limio/customer/{customer_id}/related"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        
        # Filter for subscriptions
        subscriptions = [item for item in items if item.get('record_type') == 'subscription']
        return subscriptions
    
    return []
```

### Getting Subscription Details

For detailed subscription information including renewal dates:

```python
def get_subscription_details(access_token, base_url, subscription_id):
    """Get detailed subscription information"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    url = f"{base_url}/api/objects/limio/subscription/{subscription_id}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    
    return None
```

**Key Subscription Fields:**
- `status`: Current status (e.g., "active")
- `created`: Creation date
- `data.termEndDate`: When the current term ends
- `data.attributes.autoRenew`: Whether it auto-renews
- `data.termStartDate`: When the current term started

## MCP Server Proof of Concept

### Workflow Design

1. **User Identification**
   - User provides their email address
   - Server searches for customer by email
   - If multiple customers found, present options

2. **Subscription Selection**
   - Fetch all subscriptions for the customer
   - Present subscription list with key details (ID, status, product name)
   - User selects a subscription

3. **Subscription Context**
   - Load full subscription details
   - Load all related objects (events, orders, payment methods)
   - Cache this data for the session

4. **Query Handling**
   - Answer questions about subscription status
   - Show event history
   - Provide renewal information
   - Display payment method details

### MCP Tool Definitions

```yaml
tools:
  - name: identify_customer
    description: Find a customer by email address
    input_schema:
      type: object
      properties:
        email:
          type: string
          description: Customer email address
      required: [email]

  - name: list_subscriptions
    description: List all subscriptions for a customer
    input_schema:
      type: object
      properties:
        customer_id:
          type: string
          description: Customer ID
      required: [customer_id]

  - name: get_subscription_context
    description: Get full context for a subscription including all related objects
    input_schema:
      type: object
      properties:
        subscription_id:
          type: string
          description: Subscription ID
      required: [subscription_id]

  - name: query_subscription
    description: Answer questions about a subscription
    input_schema:
      type: object
      properties:
        subscription_id:
          type: string
          description: Subscription ID
        query_type:
          type: string
          enum: [status, renewal_date, events, payment_method, order_history]
      required: [subscription_id, query_type]
```

### Example Session Flow

```
User: "I'm john@example.com"

MCP Server:
1. Calls identify_customer(email="john@example.com")
2. Finds customer ID: cus-123456
3. Calls list_subscriptions(customer_id="cus-123456")
4. Returns: "I found 2 subscriptions for you:
   - Digital Monthly (sub-abc123) - Active
   - Premium Annual (sub-xyz789) - Cancelled"

User: "Tell me about the Digital Monthly subscription"

MCP Server:
1. Calls get_subscription_context(subscription_id="sub-abc123")
2. Caches all related objects
3. Returns: "Your Digital Monthly subscription is active. It started on Jan 1, 2025 
   and will renew on Feb 1, 2025. Auto-renewal is enabled."

User: "What happened to this subscription recently?"

MCP Server:
1. Filters cached events for recent activity
2. Returns: "Recent events:
   - Jan 15: Payment method updated
   - Jan 1: Subscription renewed
   - Dec 28: Renewal reminder sent"
```

## Implementation Checklist

### Required Configuration
- [ ] OAuth Client ID
- [ ] OAuth Client Secret
- [ ] Base URL (e.g., https://saas-dev.prod.limio.com)
- [ ] Token refresh logic

### Core Functions to Implement
- [ ] OAuth token management (get, store, refresh)
- [ ] Customer search by email
- [ ] Get customer subscriptions
- [ ] Get subscription details
- [ ] Get subscription related objects
- [ ] Parse and categorize related objects
- [ ] Cache management for session data

### Error Handling
- [ ] Handle 401 (unauthorized) - refresh token
- [ ] Handle 404 (not found) - graceful messages
- [ ] Handle 400 (bad request) - validate inputs
- [ ] Handle pagination for large result sets
- [ ] Rate limiting considerations

### Data Processing
- [ ] Extract renewal dates from subscription data
- [ ] Sort and filter events by date and type
- [ ] Format dates for user-friendly display
- [ ] Identify important subscription attributes

### Testing Considerations
- [ ] Test with customers having multiple subscriptions
- [ ] Test with cancelled/expired subscriptions
- [ ] Test with subscriptions having many events
- [ ] Test error scenarios (invalid email, etc.)

## Key Insights and Gotchas

1. **No Server-Side Search**: The API doesn't support filtering customers/subscriptions by email or name. You must fetch all and filter client-side.

2. **Events Architecture**: Events are not directly linked to subscriptions via a simple foreign key. Use the related objects endpoint instead of the events endpoint.

3. **Related Endpoint is Powerful**: The `/related` endpoint is your best friend - it returns comprehensive data in one call without pagination.

4. **Subscription Dates**: Key dates are in `data.termEndDate` and `data.termStartDate`, not at the root level.

5. **Status Information**: Subscription status is at the root level, but most detailed information is nested under the `data` field.

6. **Customer Identity**: The identity object from Auth0 contains the email and user info, but you need to map this to a Limio customer object to find subscriptions.

## Sample Implementation Snippet

```python
class LimioMCPServer:
    def __init__(self, client_id, client_secret, base_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.token = None
        self.session_cache = {}
    
    def ensure_token(self):
        """Ensure we have a valid token"""
        if not self.token:  # In production, check expiry
            self.token = get_oauth_token(self.base_url, self.client_id, self.client_secret)
    
    def identify_customer(self, email):
        """Find customer by email and cache their data"""
        self.ensure_token()
        customer = find_customer_by_email(self.token, self.base_url, email)
        
        if customer:
            self.session_cache['customer'] = customer
            self.session_cache['customer_id'] = customer.get('id')
            
            # Pre-load subscriptions
            subscriptions = get_customer_subscriptions(
                self.token, self.base_url, customer.get('id')
            )
            self.session_cache['subscriptions'] = subscriptions
            
            return {
                'found': True,
                'customer_id': customer.get('id'),
                'name': customer.get('data', {}).get('name'),
                'subscription_count': len(subscriptions)
            }
        
        return {'found': False}
    
    def get_subscription_context(self, subscription_id):
        """Load full context for a subscription"""
        self.ensure_token()
        
        # Get full subscription details
        subscription = get_subscription_details(self.token, self.base_url, subscription_id)
        
        # Get all related objects
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}/related"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            related_data = response.json()
            
            # Categorize related objects
            context = {
                'subscription': subscription,
                'events': [],
                'orders': [],
                'payment_methods': [],
                'customer': None
            }
            
            for item in related_data.get('items', []):
                record_type = item.get('record_type')
                if record_type == 'event':
                    context['events'].append(item)
                elif record_type == 'order':
                    context['orders'].append(item)
                elif record_type == 'payment_method':
                    context['payment_methods'].append(item)
                elif record_type == 'customer':
                    context['customer'] = item
            
            # Sort events by date
            context['events'].sort(key=lambda x: x.get('created', ''), reverse=True)
            
            self.session_cache[f'subscription_{subscription_id}'] = context
            return context
        
        return None
```

## Next Steps

1. Set up the MCP server framework
2. Implement the core functions listed above
3. Add comprehensive error handling
4. Create user-friendly response formatting
5. Test with various customer scenarios
6. Add caching to minimize API calls
7. Implement token refresh logic
8. Add logging for debugging