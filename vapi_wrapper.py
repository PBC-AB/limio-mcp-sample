import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Limio API configuration
LIMIO_BASE_URL = os.getenv("BASE_URL", "https://api.example-saas.com")
LIMIO_CLIENT_ID = os.getenv("CLIENT_ID")
LIMIO_CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Token management
token_cache = {
    "access_token": None,
    "expires_at": None
}

class ToolCallRequest(BaseModel):
    toolCallId: str
    name: str
    parameters: Dict[str, Any]

async def get_limio_token():
    """Get or refresh Limio OAuth token"""
    # Check if we have a valid cached token
    if token_cache["access_token"] and token_cache["expires_at"]:
        if datetime.now() < token_cache["expires_at"]:
            return token_cache["access_token"]
    
    # Get new token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LIMIO_BASE_URL}/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": LIMIO_CLIENT_ID,
                "client_secret": LIMIO_CLIENT_SECRET
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to get Limio token")
        
        token_data = response.json()
        token_cache["access_token"] = token_data["access_token"]
        # Set expiry to 5 minutes before actual expiry for safety
        expires_in = token_data.get("expires_in", 3600)
        token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 300)
        
        logger.info("Got new Limio token")
        return token_cache["access_token"]

async def call_limio_api(endpoint: str, method: str = "GET") -> dict:
    """Make authenticated call to Limio API"""
    token = await get_limio_token()
    
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if method == "GET":
            response = await client.get(f"{LIMIO_BASE_URL}{endpoint}", headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code == 401:
            # Token expired, try once more with fresh token
            token_cache["access_token"] = None
            token = await get_limio_token()
            headers["Authorization"] = f"Bearer {token}"
            response = await client.get(f"{LIMIO_BASE_URL}{endpoint}", headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Limio API error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail=f"Limio API error: {response.status_code}")
        
        return response.json()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "vapi-limio-direct"}

@app.post("/get_customer_subscriptions")
async def get_customer_subscriptions(request: Request):
    """Get all subscriptions for a customer - handles VAPI format"""
    logger.info(f"=== /get_customer_subscriptions called ===")
    
    # Get the raw body
    body = await request.body()
    
    # Parse JSON
    try:
        json_body = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {"error": "Invalid JSON"}
    
    # VAPI sends everything wrapped in a "message" object
    message = json_body.get("message", {})
    
    # Extract the tool call ID and customer_id from VAPI's format
    tool_call_id = None
    customer_id = None
    
    # Get toolCallId from the first tool call
    tool_calls = message.get("toolCalls", [])
    if tool_calls:
        tool_call_id = tool_calls[0].get("id")
        # Get customer_id from the arguments
        arguments = tool_calls[0].get("function", {}).get("arguments", {})
        customer_id = arguments.get("customer_id")
    
    if not customer_id:
        logger.error("No customer_id found in request")
        return {
            "results": [{
                "toolCallId": tool_call_id or "error",
                "result": "Error: customer_id is required"
            }]
        }
    
    logger.info(f"Processing request for customer: {customer_id} with toolCallId: {tool_call_id}")
    
    try:
        # Get all related objects for the customer
        data = await call_limio_api(f"/api/objects/limio/customer/{customer_id}/related")
        
        # VAPI expects a specific response format with "results" array
        response = {
            "results": [{
                "toolCallId": tool_call_id,
                "result": json.dumps(data, indent=2)
            }]
        }
        
        logger.info(f"Returning successful response")
        return response
        
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        return {
            "results": [{
                "toolCallId": tool_call_id,
                "result": f"Error: {str(e)}"
            }]
        }

@app.post("/get_subscription_raw_data")
async def get_subscription_raw_data(request: Request):
    """Get raw subscription data - handles VAPI format"""
    logger.info(f"=== /get_subscription_raw_data called ===")
    
    # Get the raw body
    body = await request.body()
    
    # Parse JSON
    try:
        json_body = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {"error": "Invalid JSON"}
    
    # VAPI sends everything wrapped in a "message" object
    message = json_body.get("message", {})
    
    # Extract the tool call ID and subscription_id from VAPI's format
    tool_call_id = None
    subscription_id = None
    
    # Get toolCallId from the first tool call
    tool_calls = message.get("toolCalls", [])
    if tool_calls:
        tool_call_id = tool_calls[0].get("id")
        # Get subscription_id from the arguments
        arguments = tool_calls[0].get("function", {}).get("arguments", {})
        subscription_id = arguments.get("subscription_id")
    
    if not subscription_id:
        logger.error("No subscription_id found in request")
        return {
            "results": [{
                "toolCallId": tool_call_id or "error",
                "result": "Error: subscription_id is required"
            }]
        }
    
    logger.info(f"Processing request for subscription: {subscription_id} with toolCallId: {tool_call_id}")
    
    try:
        # Get subscription details
        subscription = await call_limio_api(f"/api/objects/limio/subscription/{subscription_id}")
        
        # Get all related objects
        related_data = await call_limio_api(f"/api/objects/limio/subscription/{subscription_id}/related")
        
        # Combine everything into one response
        raw_data = {
            "subscription": subscription,
            "related_objects": related_data.get('items', [])
        }
        
        # VAPI expects a specific response format with "results" array
        response = {
            "results": [{
                "toolCallId": tool_call_id,
                "result": json.dumps(raw_data, indent=2)
            }]
        }
        
        logger.info(f"Returning successful response")
        return response
        
    except Exception as e:
        logger.error(f"Error getting subscription raw data: {e}")
        return {
            "results": [{
                "toolCallId": tool_call_id,
                "result": f"Error: {str(e)}"
            }]
        }

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Direct VAPI to Limio Wrapper")
    print(f"Limio API: {LIMIO_BASE_URL}")
    print("No MCP, no complexity, just direct API calls!")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)