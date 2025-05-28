# Limio MCP Server - Hackathon Quick Start Guide

## Overview

This guide provides a streamlined approach for building a Limio MCP server for the hackathon, focusing on simplicity and rapid development.

## Recommended Approach: Python with MCP SDK

### Why Python?
- Quick setup and minimal boilerplate
- Excellent HTTP libraries (requests)
- Easy JSON handling
- Your existing code is already in Python

### Recommended MCP Template

Use the **MCP Python SDK** with the **server template**:

```bash
# Install the MCP Python SDK
pip install mcp

# Or use the quickstart template
git clone https://github.com/modelcontextprotocol/python-sdk
cd python-sdk/examples
```

## Simplified Architecture for Hackathon

### Core Tools (Simplified from Original)

```python
tools = [
    Tool(
        name="get_customer_subscriptions",
        description="Get all subscriptions for a customer by their ID",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The Limio customer ID (e.g., cus-123456)"
                }
            },
            "required": ["customer_id"]
        }
    ),
    Tool(
        name="get_subscription_details",
        description="Get detailed information about a specific subscription",
        inputSchema={
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "The subscription ID to get details for"
                }
            },
            "required": ["subscription_id"]
        }
    ),
    Tool(
        name="get_subscription_events",
        description="Get recent events for a subscription",
        inputSchema={
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "The subscription ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of events to return",
                    "default": 10
                }
            },
            "required": ["subscription_id"]
        }
    )
]
```

## Quick Implementation Template

### 1. Project Structure
```
limio-mcp-server/
├── server.py          # Main MCP server
├── limio_client.py    # Limio API wrapper
├── .env              # Environment variables
├── requirements.txt   # Dependencies
└── README.md         # Quick start guide
```

### 2. Requirements.txt
```
mcp>=0.1.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### 3. Simplified Limio Client (limio_client.py)
```python
import requests
import os
from typing import Dict, List, Optional

class LimioClient:
    def __init__(self):
        self.base_url = os.getenv("LIMIO_BASE_URL", "https://saas-dev.prod.limio.com")
        self.client_id = os.getenv("LIMIO_CLIENT_ID")
        self.client_secret = os.getenv("LIMIO_CLIENT_SECRET")
        self.token = None
    
    def _ensure_token(self):
        """Get OAuth token if needed"""
        if not self.token:
            token_url = f"{self.base_url}/oauth2/token"
            response = requests.post(
                token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            self.token = response.json()["access_token"]
    
    def _get_headers(self):
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def get_customer_subscriptions(self, customer_id: str) -> List[Dict]:
        """Get all subscriptions for a customer"""
        url = f"{self.base_url}/api/objects/limio/customer/{customer_id}/related"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            items = response.json().get('items', [])
            return [item for item in items if item.get('record_type') == 'subscription']
        return []
    
    def get_subscription_details(self, subscription_id: str) -> Optional[Dict]:
        """Get full subscription details including related objects"""
        # Get subscription
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code != 200:
            return None
            
        subscription = response.json()
        
        # Get related objects
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}/related"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            related = response.json()
            subscription['_related'] = related.get('items', [])
        
        return subscription
    
    def get_subscription_events(self, subscription_id: str, limit: int = 10) -> List[Dict]:
        """Get events for a subscription from related objects"""
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}/related"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            items = response.json().get('items', [])
            events = [item for item in items if item.get('record_type') == 'event']
            # Sort by created date descending
            events.sort(key=lambda x: x.get('created', ''), reverse=True)
            return events[:limit]
        return []
```

### 4. MCP Server (server.py)
```python
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from limio_client import LimioClient

# Initialize Limio client
limio = LimioClient()

# Create MCP server
server = Server("limio-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_customer_subscriptions",
            description="Get all subscriptions for a customer by their ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The Limio customer ID (e.g., cus-123456)"
                    }
                },
                "required": ["customer_id"]
            }
        ),
        types.Tool(
            name="get_subscription_details",
            description="Get detailed information about a specific subscription",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "The subscription ID"
                    }
                },
                "required": ["subscription_id"]
            }
        ),
        types.Tool(
            name="get_subscription_events",
            description="Get recent events for a subscription",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "The subscription ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of events to return",
                        "default": 10
                    }
                },
                "required": ["subscription_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    
    if name == "get_customer_subscriptions":
        customer_id = arguments.get("customer_id")
        subscriptions = limio.get_customer_subscriptions(customer_id)
        
        if not subscriptions:
            return [types.TextContent(
                type="text",
                text=f"No subscriptions found for customer {customer_id}"
            )]
        
        # Format subscription list
        text = f"Found {len(subscriptions)} subscription(s):\n\n"
        for i, sub in enumerate(subscriptions, 1):
            sub_data = sub.get('data', {})
            text += f"{i}. {sub_data.get('name', 'Unknown Plan')}\n"
            text += f"   ID: {sub.get('id')}\n"
            text += f"   Status: {sub.get('status', 'unknown')}\n"
            text += f"   Reference: {sub.get('reference', 'N/A')}\n\n"
        
        return [types.TextContent(type="text", text=text)]
    
    elif name == "get_subscription_details":
        subscription_id = arguments.get("subscription_id")
        details = limio.get_subscription_details(subscription_id)
        
        if not details:
            return [types.TextContent(
                type="text",
                text=f"Subscription {subscription_id} not found"
            )]
        
        # Format subscription details
        data = details.get('data', {})
        text = f"Subscription Details:\n\n"
        text += f"ID: {details.get('id')}\n"
        text += f"Status: {details.get('status')}\n"
        text += f"Plan: {data.get('name', 'Unknown')}\n"
        text += f"Created: {details.get('created', 'N/A')}\n"
        text += f"Term End Date: {data.get('termEndDate', 'N/A')}\n"
        text += f"Auto-Renew: {data.get('attributes', {}).get('autoRenew', False)}\n"
        
        # Count related objects
        related = details.get('_related', [])
        events = [r for r in related if r.get('record_type') == 'event']
        text += f"\nRelated Objects:\n"
        text += f"- Events: {len(events)}\n"
        
        return [types.TextContent(type="text", text=text)]
    
    elif name == "get_subscription_events":
        subscription_id = arguments.get("subscription_id")
        limit = arguments.get("limit", 10)
        events = limio.get_subscription_events(subscription_id, limit)
        
        if not events:
            return [types.TextContent(
                type="text",
                text=f"No events found for subscription {subscription_id}"
            )]
        
        # Format events
        text = f"Recent Events (showing {len(events)} of {limit} requested):\n\n"
        for event in events:
            event_data = event.get('data', {})
            text += f"• {event.get('created', 'N/A')}\n"
            text += f"  Type: {event_data.get('type', 'unknown')}\n"
            text += f"  Message: {event_data.get('message', 'N/A')}\n"
            text += f"  Status: {event.get('status', 'N/A')}\n\n"
        
        return [types.TextContent(type="text", text=text)]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="limio-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 5. .env File
```
LIMIO_CLIENT_ID=your_client_id_here
LIMIO_CLIENT_SECRET=your_client_secret_here
LIMIO_BASE_URL=https://saas-dev.prod.limio.com
```

## Hackathon Usage Flow

1. **User provides customer ID**
   ```
   User: "My customer ID is cus-886716de7dba964a9c74ffb7736ac9b3"
   ```

2. **Assistant lists subscriptions**
   ```
   Assistant: [calls get_customer_subscriptions]
   "I found 2 subscriptions for you:
   1. Digital Monthly (sub-abc123) - Active
   2. Premium Annual (sub-xyz789) - Cancelled"
   ```

3. **User asks for details**
   ```
   User: "Tell me about sub-abc123"
   Assistant: [calls get_subscription_details]
   "Your Digital Monthly subscription is active, renews on Feb 1, 2025..."
   ```

4. **User asks for events**
   ```
   User: "What happened recently?"
   Assistant: [calls get_subscription_events]
   "Recent events: Payment updated, Subscription renewed..."
   ```

## Quick Start Instructions

1. **Clone and setup**
   ```bash
   mkdir limio-mcp-server
   cd limio-mcp-server
   pip install mcp requests python-dotenv
   ```

2. **Create the files above**

3. **Configure Claude Desktop**
   Add to `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "limio": {
         "command": "python",
         "args": ["/path/to/limio-mcp-server/server.py"],
         "env": {
           "LIMIO_CLIENT_ID": "your_client_id",
           "LIMIO_CLIENT_SECRET": "your_client_secret"
         }
       }
     }
   }
   ```

4. **Test it!**
   - Restart Claude Desktop
   - Ask: "Using the Limio tools, get subscriptions for customer cus-886716de7dba964a9c74ffb7736ac9b3"

## Extension Ideas for Hackathon

- Add a tool to search for customers by email (with pagination)
- Add payment method details extraction
- Create a summary tool that combines all data
- Add date formatting and "days until renewal" calculations
- Add webhook event simulation

## Troubleshooting

- **No tools showing**: Check Claude Desktop logs, ensure Python path is correct
- **Authentication errors**: Verify client credentials in .env
- **Empty results**: Check customer ID format, ensure it exists
- **Token expiry**: Current implementation gets new token each time (simple but not optimal)

## Resources

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Documentation](https://modelcontextprotocol.io/docs)
- Original Limio implementation guide (see attached documents)