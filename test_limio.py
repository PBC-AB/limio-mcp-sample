#!/usr/bin/env python3
"""
Test script for the Limio MCP server
Tests with the provided customer ID: cus-a1b2c3d4e5f6789012345678901234ab
"""

import os
import json
from dotenv import load_dotenv
from limio_client import LimioClient

# Load environment variables
load_dotenv()

def test_limio_client():
    print("Testing Limio Client...\n")
    
    # Initialize client
    client = LimioClient()
    
    # Test customer ID provided
    test_customer_id = "cus-a1b2c3d4e5f6789012345678901234ab"
    
    print(f"1. Testing customer lookup for ID: {test_customer_id}")
    try:
        customer = client.find_customer_by_id(test_customer_id)
        if customer:
            print("   ✓ Customer found!")
            customer_data = customer.get('data', {})
            print(f"   Name: {customer_data.get('name', 'N/A')}")
            print(f"   Email: {customer_data.get('email', 'N/A')}")
            print(f"   Status: {customer.get('status', 'N/A')}")
        else:
            print("   ✗ Customer not found")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n2. Testing subscription retrieval")
    try:
        subscriptions = client.get_customer_subscriptions(test_customer_id)
        print(f"   ✓ Found {len(subscriptions)} subscription(s)")
        
        for i, sub in enumerate(subscriptions, 1):
            sub_data = sub.get('data', {})
            print(f"\n   Subscription {i}:")
            print(f"   - ID: {sub.get('id')}")
            print(f"   - Plan: {sub_data.get('name', 'Unknown')}")
            print(f"   - Status: {sub.get('status')}")
            print(f"   - Term End: {sub_data.get('termEndDate', 'N/A')}")
            
            # Test getting events for first subscription
            if i == 1:
                sub_id = sub.get('id')
                print(f"\n3. Testing events retrieval for subscription: {sub_id}")
                try:
                    events = client.get_subscription_events(sub_id, limit=5)
                    print(f"   ✓ Found {len(events)} recent event(s)")
                    
                    for j, event in enumerate(events[:3], 1):
                        event_data = event.get('data', {})
                        print(f"\n   Event {j}:")
                        print(f"   - Type: {event_data.get('type', 'Unknown')}")
                        print(f"   - Message: {event_data.get('message', 'N/A')}")
                        print(f"   - Date: {event.get('created', 'N/A')}")
                        print(f"   - Status: {event.get('status', 'N/A')}")
                except Exception as e:
                    print(f"   ✗ Error getting events: {e}")
                
                # Test getting full subscription details
                print(f"\n4. Testing full subscription details for: {sub_id}")
                try:
                    details = client.get_subscription_details(sub_id)
                    if details:
                        print("   ✓ Retrieved full subscription details")
                        data = details.get('data', {})
                        print(f"   - Auto-renew: {data.get('attributes', {}).get('autoRenew', False)}")
                        print(f"   - Term Start: {data.get('termStartDate', 'N/A')}")
                        
                        # Count related objects
                        related = details.get('_related', [])
                        events = [r for r in related if r.get('record_type') == 'event']
                        orders = [r for r in related if r.get('record_type') == 'order']
                        payment_methods = [r for r in related if r.get('record_type') == 'payment_method']
                        
                        print(f"\n   Related objects:")
                        print(f"   - Events: {len(events)}")
                        print(f"   - Orders: {len(orders)}")
                        print(f"   - Payment Methods: {len(payment_methods)}")
                    else:
                        print("   ✗ Could not retrieve subscription details")
                except Exception as e:
                    print(f"   ✗ Error getting details: {e}")
                    
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_limio_client()