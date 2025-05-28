import asyncio
import json
import logging
import sys
from datetime import datetime
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from limio_client import LimioClient
from dotenv import load_dotenv

# Set up logging - only to stderr for Claude Desktop
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Initialize Limio client
limio = LimioClient()
logger.info("Limio client initialized")

# Create MCP server
server = Server("limio-server")
logger.info("MCP server created")

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
            description="Get detailed information about a specific subscription including order and payment details",
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
        ),
        types.Tool(
            name="get_subscription_raw_data",
            description="Get raw subscription data including all related objects for debugging/exploration",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "The subscription ID"
                    },
                    "object_type": {
                        "type": "string",
                        "description": "Type of objects to show (all, orders, events, payment_methods)",
                        "default": "all"
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
    
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        if name == "get_customer_subscriptions":
            customer_id = arguments.get("customer_id")
            logger.info(f"Getting subscriptions for customer: {customer_id}")
            
            # Try to get customer details first
            customer = limio.find_customer_by_id(customer_id)
            customer_name = "Unknown"
            if customer:
                customer_data = customer.get('data', {})
                customer_name = customer_data.get('name', customer_data.get('email', 'Unknown'))
                logger.debug(f"Customer found: {customer_name}")
            else:
                logger.warning(f"Customer details not found for ID: {customer_id}")
            
            subscriptions = limio.get_customer_subscriptions(customer_id)
            logger.info(f"Found {len(subscriptions)} subscriptions")
            
            if not subscriptions:
                return [types.TextContent(
                    type="text",
                    text=f"No subscriptions found for customer {customer_id}"
                )]
            
            # Format subscription list
            text = f"Customer: {customer_name}\n"
            text += f"Found {len(subscriptions)} subscription(s):\n\n"
            for i, sub in enumerate(subscriptions, 1):
                sub_data = sub.get('data', {})
                sub_name = sub_data.get('name', 'Unknown Plan')
                
                text += f"{i}. {sub_name}\n"
                text += f"   ID: {sub.get('id')}\n"
                text += f"   Status: {sub.get('status', 'unknown')}\n"
                text += f"   Reference: {sub.get('reference', sub.get('name', 'N/A'))}\n"
                
                # Add pricing if available
                price_info = sub_data.get('price', {})
                if price_info:
                    amount = price_info.get('amount', 0)
                    currency = price_info.get('currency', 'USD')
                    text += f"   Price: {currency} {amount}\n"
                
                # Add term dates if available
                term_end = sub_data.get('termEndDate')
                if term_end:
                    text += f"   Term ends: {term_end}\n"
                text += "\n"
            
            return [types.TextContent(type="text", text=text)]
        
        elif name == "get_subscription_details":
            subscription_id = arguments.get("subscription_id")
            logger.info(f"Getting details for subscription: {subscription_id}")
            
            try:
                details = limio.get_subscription_details(subscription_id)
                logger.info(f"Got subscription details: {details is not None}")
            except Exception as e:
                logger.error(f"Error getting subscription details: {str(e)}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=f"Error retrieving subscription details: {str(e)}"
                )]
            
            if not details:
                logger.warning(f"No details found for subscription: {subscription_id}")
                return [types.TextContent(
                    type="text",
                    text=f"Subscription {subscription_id} not found"
                )]
            
            # Format subscription details
            data = details.get('data', {})
            logger.info(f"Processing subscription data")
            
            text = f"Subscription Details:\n\n"
            text += f"ID: {details.get('id')}\n"
            text += f"Status: {details.get('status')}\n"
            
            # Handle plan name - might be in different locations
            plan_name = data.get('name') or data.get('planName') or data.get('productName') or 'Unknown'
            text += f"Plan: {plan_name}\n"
            
            text += f"Created: {details.get('created', 'N/A')}\n"
            
            # Term dates might not exist for all subscription types
            term_start = data.get('termStartDate')
            if term_start:
                text += f"Term Start Date: {term_start}\n"
            
            term_end = data.get('termEndDate')
            if term_end:
                text += f"Term End Date: {term_end}\n"
                # Calculate days until renewal if possible
                try:
                    from datetime import timezone
                    end_date = datetime.fromisoformat(term_end.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    days_left = (end_date - now).days
                    text += f"Days until renewal: {days_left}\n"
                except Exception as e:
                    logger.warning(f"Could not calculate days until renewal: {e}")
            
            # Auto-renew might be in different locations
            attributes = data.get('attributes', {})
            auto_renew = attributes.get('autoRenew', False)
            text += f"Auto-Renew: {auto_renew}\n"
            
            # Process related objects
            related = details.get('_related', [])
            events = [r for r in related if r.get('record_type') == 'event']
            orders = [r for r in related if r.get('record_type') == 'order']
            payment_methods = [r for r in related if r.get('record_type') == 'payment_method']
            
            text += f"\nRelated Objects Summary:\n"
            text += f"- Events: {len(events)}\n"
            text += f"- Orders: {len(orders)}\n"
            text += f"- Payment Methods: {len(payment_methods)}\n"
            
            # Get pricing from subscription data (the actual location)
            subscription_price = data.get('price', {})
            if subscription_price:
                price_amount = subscription_price.get('amount', 0)
                price_currency = subscription_price.get('currency', 'USD')
                price_headline = subscription_price.get('summary', {}).get('headline', '')
                
                text += f"\nPricing Information:\n"
                text += f"  Amount: {price_currency} {price_amount}\n"
                if price_headline:
                    text += f"  Display Price: {price_headline}\n"
            
            # Show order details if available (orders don't contain pricing in Limio)
            if orders:
                text += f"\nOrder History:\n"
                for order in orders:
                    order_data = order.get('data', {})
                    order_id = order.get('id', 'N/A')
                    order_name = order.get('name', 'N/A')
                    order_status = order.get('status', 'N/A')
                    order_created = order.get('created', 'N/A')
                    
                    text += f"\n  Order: {order_name}\n"
                    text += f"  ID: {order_id}\n"
                    text += f"  Status: {order_status}\n"
                    text += f"  Created: {order_created}\n"
                    
                    # Show tracking info if available
                    tracking = order_data.get('tracking', {})
                    if tracking.get('campaign'):
                        text += f"  Campaign: {tracking.get('campaign')}\n"
            
            # Show payment method details (Zuora integration)
            if payment_methods:
                text += f"\nPayment Methods:\n"
                for pm in payment_methods[:2]:  # Show max 2 payment methods
                    pm_data = pm.get('data', {})
                    pm_type = pm.get('type', 'zuora')
                    pm_status = pm.get('status', 'N/A')
                    pm_created = pm.get('created', 'N/A')
                    
                    # Get Zuora payment method details
                    zuora_data = pm_data.get('zuora', {}).get('result', {})
                    if zuora_data:
                        card_type = zuora_data.get('CreditCardType', 'Unknown')
                        card_mask = zuora_data.get('CreditCardMaskNumber', '')
                        card_holder = zuora_data.get('CreditCardHolderName', '')
                        exp_month = zuora_data.get('CreditCardExpirationMonth', '')
                        exp_year = zuora_data.get('CreditCardExpirationYear', '')
                        
                        text += f"  - {card_type} ending in {card_mask[-4:] if card_mask else 'XXXX'}\n"
                        text += f"    Holder: {card_holder}\n"
                        text += f"    Expires: {exp_month}/{exp_year}\n"
                        text += f"    Status: {pm_status}\n"
                        text += f"    Added: {pm_created[:10] if pm_created != 'N/A' else 'N/A'}\n"
                    else:
                        text += f"  - Type: {pm_type}\n"
                        text += f"    Status: {pm_status}\n"
            
            return [types.TextContent(type="text", text=text)]
        
        elif name == "get_subscription_events":
            subscription_id = arguments.get("subscription_id")
            limit = arguments.get("limit", 10)
            logger.info(f"Getting events for subscription: {subscription_id}, limit: {limit}")
            
            try:
                events = limio.get_subscription_events(subscription_id, limit)
                logger.info(f"Found {len(events)} events")
            except Exception as e:
                logger.error(f"Error getting subscription events: {str(e)}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=f"Error retrieving subscription events: {str(e)}"
                )]
            
            if not events:
                return [types.TextContent(
                    type="text",
                    text=f"No events found for subscription {subscription_id}"
                )]
            
            # Format events
            text = f"Recent Events (showing {len(events)} of {limit} requested):\n\n"
            for event in events:
                event_data = event.get('data', {})
                created = event.get('created', 'N/A')
                
                # Format date
                if created != 'N/A':
                    try:
                        event_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        date_str = event_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        date_str = created
                else:
                    date_str = 'N/A'
                
                text += f"• {date_str}\n"
                text += f"  Type: {event_data.get('type', 'unknown')}\n"
                text += f"  Message: {event_data.get('message', 'N/A')}\n"
                text += f"  Status: {event.get('status', 'N/A')}\n\n"
            
            return [types.TextContent(type="text", text=text)]
        
        elif name == "get_subscription_raw_data":
            subscription_id = arguments.get("subscription_id")
            object_type = arguments.get("object_type", "all")
            logger.info(f"Getting raw data for subscription: {subscription_id}, type: {object_type}")
            
            try:
                details = limio.get_subscription_details(subscription_id)
                if not details:
                    return [types.TextContent(
                        type="text",
                        text=f"Subscription {subscription_id} not found"
                    )]
                
                text = f"Raw Subscription Data (type: {object_type}):\n\n"
                
                # Show main subscription data
                if object_type == "all":
                    text += "=== SUBSCRIPTION DATA ===\n"
                    text += json.dumps(details.get('data', {}), indent=2)
                    text += "\n\n"
                
                # Get related objects
                related = details.get('_related', [])
                
                # Filter by type if requested
                if object_type == "orders":
                    related = [r for r in related if r.get('record_type') == 'order']
                elif object_type == "events":
                    related = [r for r in related if r.get('record_type') == 'event']
                elif object_type == "payment_methods":
                    related = [r for r in related if r.get('record_type') == 'payment_method']
                
                # Show related objects
                text += f"=== RELATED OBJECTS ({len(related)} items) ===\n\n"
                
                for i, obj in enumerate(related[:5]):  # Limit to first 5 to avoid too much output
                    text += f"--- Object {i+1} ---\n"
                    text += f"Type: {obj.get('record_type')}\n"
                    text += f"ID: {obj.get('id')}\n"
                    text += f"Status: {obj.get('status')}\n"
                    text += f"Created: {obj.get('created')}\n"
                    text += f"Data:\n{json.dumps(obj.get('data', {}), indent=2)}\n\n"
                
                if len(related) > 5:
                    text += f"... and {len(related) - 5} more objects\n"
                
                return [types.TextContent(type="text", text=text)]
                
            except Exception as e:
                logger.error(f"Error getting raw data: {str(e)}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=f"Error retrieving raw data: {str(e)}"
                )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

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