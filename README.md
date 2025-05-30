# Limio MCP Server

A Model Context Protocol (MCP) server for interacting with the Limio subscription management API.

## Overview

This MCP server provides tools for querying Limio customer subscriptions, subscription details, and events through a conversational interface.

## Features

- Get all subscriptions for a customer
- Get detailed subscription information including renewal dates
- Retrieve recent events for a subscription
- Automatic OAuth token management

## VAPI Wrapper Service

This repository also includes a VAPI wrapper service that can be run through ngrok for external access.

### Running the VAPI Wrapper

After completing the installation steps above, you can start the VAPI wrapper service using the provided script:

```bash
./start-vapi-wrapper.sh
```

This script will:
1. Load environment variables from your `.env` file
2. Start the VAPI wrapper Python service
3. Expose the service through ngrok with authentication

### Required Environment Variables

Add the following variables to your `.env` file for the VAPI wrapper:

```
NGROK_URL=your-ngrok-static-url-here
NGROK_AUTH_USER=your-auth-username
NGROK_AUTH_PASS=your-auth-password
```

- `NGROK_URL`: Your ngrok static URL (requires ngrok paid plan for static URLs)
- `NGROK_AUTH_USER`: Basic authentication username for securing the ngrok tunnel
- `NGROK_AUTH_PASS`: Basic authentication password for securing the ngrok tunnel

The service will be available on port 8000 and accessible through your configured ngrok URL with basic authentication.

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

You can configure the Limio API credentials in one of two ways:

### Option 1: Using .env file (Recommended for development)
Create a `.env` file in the project root:
```
BASE_URL=https://api.example-saas.com
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```

Then configure Claude Desktop with just the Python path:
```json
{
  "mcpServers": {
    "limio": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/limio-mcp-sample/server.py"]
    }
  }
}
```

### Option 2: Using Claude Desktop config only
Configure everything in `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "limio": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/limio-mcp-sample/server.py"],
      "env": {
        "BASE_URL": "https://api.example-saas.com",
        "CLIENT_ID": "your_client_id",
        "CLIENT_SECRET": "your_client_secret"
      }
    }
  }
}
```

## Available Tools

### get_customer_subscriptions
Get all subscriptions for a customer by their ID.

**Parameters:**
- `customer_id` (string, required): The Limio customer ID (e.g., cus-123456)

### get_subscription_details
Get detailed information about a specific subscription including renewal dates, order details with pricing, and payment methods.

**Parameters:**
- `subscription_id` (string, required): The subscription ID

**Returns:**
- Subscription status and dates
- Order details including amounts (if available)
- Payment method information
- Related object counts

### get_subscription_events
Get recent events for a subscription.

**Parameters:**
- `subscription_id` (string, required): The subscription ID
- `limit` (integer, optional): Number of events to return (default: 10)

### get_subscription_raw_data
Get raw subscription data including all related objects for debugging and exploration. Useful for discovering available fields and data structure.

**Parameters:**
- `subscription_id` (string, required): The subscription ID
- `object_type` (string, optional): Type of objects to show - "all", "orders", "events", or "payment_methods" (default: "all")

## Testing

Run the test script to verify the setup:
```bash
source venv/bin/activate
python test_limio.py
```

The test script uses the provided test customer ID: `cus-a1b2c3d4e5f6789012345678901234ab`

## Usage Example

Once configured in Claude Desktop, you can use commands like:

- "Using the Limio tools, get subscriptions for customer cus-a1b2c3d4e5f6789012345678901234ab"
- "Show me the details for subscription sub-x9y8z7w6v5u4321098765432109876ba"
- "What events happened recently on this subscription?"

## Project Structure

```
limio-mcp-sample/
├── server.py          # Main MCP server implementation
├── limio_client.py    # Limio API client wrapper
├── test_limio.py      # Test script
├── requirements.txt   # Python dependencies
├── .env              # Environment variables (create this)
└── README.md         # This file
```

## Development

The server uses the MCP Python SDK and implements three main tools for interacting with Limio's API. The implementation follows the simplified architecture outlined in the hackathon design document.

Key features:
- OAuth 2.0 authentication with automatic token refresh
- Efficient use of the related objects endpoint for comprehensive data retrieval
- Proper error handling and user-friendly output formatting

### Debugging

The server includes logging for debugging purposes:
- Logs are written to stderr, which Claude Desktop captures
- Log level is set to INFO by default
- Logs include API calls, responses, and error details
- View logs in Claude Desktop by checking the MCP server logs

To view logs in Claude Desktop:
1. Open Claude Desktop developer tools
2. Look for the Limio server logs
3. All debug output will appear there