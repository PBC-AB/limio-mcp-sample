"""
Limio MCP Server Proof of Concept

This demonstrates how an MCP server would interact with the Limio API
to provide a conversational interface for subscription management.
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LimioMCPServer:
    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.base_url = os.getenv("BASE_URL", "https://saas-dev.prod.limio.com")
        self.token = None
        self.session_data = {
            'customer': None,
            'subscriptions': [],
            'current_subscription': None,
            'subscription_context': {}
        }
    
    def get_oauth_token(self):
        """Get OAuth Bearer token"""
        token_url = f"{self.base_url}/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        self.token = response.json().get("access_token")
    
    def ensure_auth(self):
        """Ensure we have a valid token"""
        if not self.token:
            self.get_oauth_token()
    
    def identify_customer(self, email):
        """Find and identify a customer by email"""
        self.ensure_auth()
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Get customers and search for email
        url = f"{self.base_url}/api/objects/limio/customers"
        response = requests.get(url, headers=headers, params={"limit": 100})
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            for customer in items:
                customer_data = customer.get('data', {})
                if customer_data.get('email') == email:
                    self.session_data['customer'] = customer
                    
                    # Get subscriptions for this customer
                    customer_id = customer.get('id')
                    self._load_customer_subscriptions(customer_id)
                    
                    return {
                        'success': True,
                        'message': f"Welcome {customer_data.get('name', email)}! I found {len(self.session_data['subscriptions'])} subscription(s) for you.",
                        'subscriptions': self._format_subscription_list()
                    }
        
        return {
            'success': False,
            'message': f"I couldn't find a customer with email {email}."
        }
    
    def _load_customer_subscriptions(self, customer_id):
        """Load all subscriptions for a customer"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/api/objects/limio/customer/{customer_id}/related"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            self.session_data['subscriptions'] = [
                item for item in items if item.get('record_type') == 'subscription'
            ]
    
    def _format_subscription_list(self):
        """Format subscriptions for display"""
        subs = []
        for i, sub in enumerate(self.session_data['subscriptions']):
            sub_data = sub.get('data', {})
            offer_name = sub_data.get('name', 'Unknown Plan')
            status = sub.get('status', 'unknown')
            sub_id = sub.get('id', '')
            
            subs.append({
                'index': i + 1,
                'id': sub_id,
                'name': offer_name,
                'status': status,
                'reference': sub.get('reference', sub.get('name', ''))
            })
        
        return subs
    
    def select_subscription(self, index):
        """Select a subscription by index"""
        if 0 <= index - 1 < len(self.session_data['subscriptions']):
            subscription = self.session_data['subscriptions'][index - 1]
            subscription_id = subscription.get('id')
            
            # Load full context for this subscription
            self._load_subscription_context(subscription_id)
            self.session_data['current_subscription'] = subscription_id
            
            return {
                'success': True,
                'message': self._generate_subscription_summary(subscription_id)
            }
        
        return {
            'success': False,
            'message': "Invalid subscription number. Please choose from the list."
        }
    
    def _load_subscription_context(self, subscription_id):
        """Load full context for a subscription"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Get full subscription details
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            full_sub = response.json()
        else:
            full_sub = None
        
        # Get related objects
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}/related"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            context = {
                'full_subscription': full_sub,
                'events': [],
                'orders': [],
                'payment_methods': [],
                'addresses': []
            }
            
            for item in items:
                record_type = item.get('record_type')
                if record_type == 'event':
                    context['events'].append(item)
                elif record_type == 'order':
                    context['orders'].append(item)
                elif record_type == 'payment_method':
                    context['payment_methods'].append(item)
                elif record_type == 'address':
                    context['addresses'].append(item)
            
            # Sort events by date
            context['events'].sort(key=lambda x: x.get('created', ''), reverse=True)
            
            self.session_data['subscription_context'][subscription_id] = context
    
    def _generate_subscription_summary(self, subscription_id):
        """Generate a summary of the subscription"""
        context = self.session_data['subscription_context'].get(subscription_id, {})
        full_sub = context.get('full_subscription', {})
        
        if not full_sub:
            return "Unable to load subscription details."
        
        data = full_sub.get('data', {})
        
        # Extract key information
        status = full_sub.get('status', 'unknown')
        created = full_sub.get('created', '')
        term_end = data.get('termEndDate', 'Not specified')
        auto_renew = data.get('attributes', {}).get('autoRenew', False)
        offer_name = data.get('name', 'Unknown Plan')
        
        # Format dates
        if created:
            created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
            created_str = created_date.strftime("%B %d, %Y")
        else:
            created_str = "Unknown"
        
        # Build summary
        summary = f"**{offer_name}**\n\n"
        summary += f"Status: {status.capitalize()}\n"
        summary += f"Started: {created_str}\n"
        summary += f"Current term ends: {term_end}\n"
        summary += f"Auto-renewal: {'Enabled' if auto_renew else 'Disabled'}\n"
        
        # Add recent events
        events = context.get('events', [])
        if events:
            summary += f"\nRecent activity ({len(events)} events total):\n"
            for event in events[:3]:  # Show last 3 events
                event_type = event.get('data', {}).get('type', 'unknown')
                event_date = event.get('created', '')
                if event_date:
                    event_dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                    event_str = event_dt.strftime("%b %d")
                    summary += f"- {event_str}: {event_type}\n"
        
        return summary
    
    def answer_question(self, question_type):
        """Answer specific questions about the current subscription"""
        if not self.session_data['current_subscription']:
            return "Please select a subscription first."
        
        sub_id = self.session_data['current_subscription']
        context = self.session_data['subscription_context'].get(sub_id, {})
        full_sub = context.get('full_subscription', {})
        
        if question_type == 'events':
            events = context.get('events', [])
            if not events:
                return "No events found for this subscription."
            
            response = f"Event history ({len(events)} total events):\n\n"
            for event in events:
                event_data = event.get('data', {})
                event_type = event_data.get('type', 'unknown')
                message = event_data.get('message', '')
                created = event.get('created', '')
                status = event.get('status', '')
                
                if created:
                    event_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    date_str = event_dt.strftime("%Y-%m-%d %H:%M")
                    response += f"{date_str}: {event_type} - {message} (Status: {status})\n"
            
            return response
        
        elif question_type == 'payment':
            payment_methods = context.get('payment_methods', [])
            if not payment_methods:
                return "No payment methods found for this subscription."
            
            response = "Payment methods:\n\n"
            for pm in payment_methods:
                pm_data = pm.get('data', {})
                pm_type = pm_data.get('type', 'unknown')
                status = pm.get('status', 'unknown')
                response += f"- {pm_type} (Status: {status})\n"
            
            return response
        
        elif question_type == 'renewal':
            data = full_sub.get('data', {})
            term_end = data.get('termEndDate', 'Not specified')
            auto_renew = data.get('attributes', {}).get('autoRenew', False)
            
            response = f"Renewal information:\n\n"
            response += f"Current term ends: {term_end}\n"
            response += f"Auto-renewal: {'Enabled' if auto_renew else 'Disabled'}\n"
            
            if term_end and term_end != 'Not specified':
                # Calculate days until renewal
                try:
                    end_date = datetime.fromisoformat(term_end.replace('Z', '+00:00'))
                    days_left = (end_date - datetime.now()).days
                    response += f"Days until renewal: {days_left}\n"
                except:
                    pass
            
            return response
        
        return "I don't understand that question type."


def demo_session():
    """Demonstrate an MCP session"""
    server = LimioMCPServer()
    
    print("=== Limio MCP Server Demo ===\n")
    
    # Step 1: Identify customer
    print("User: I'm amaury+27051908@limio.com\n")
    
    result = server.identify_customer("amaury+27051908@limio.com")
    print(f"Assistant: {result['message']}")
    
    if result['success'] and result['subscriptions']:
        print("\nYour subscriptions:")
        for sub in result['subscriptions']:
            print(f"{sub['index']}. {sub['name']} ({sub['reference']}) - {sub['status']}")
    
    # Step 2: Select a subscription
    print("\nUser: Tell me about subscription 1\n")
    
    result = server.select_subscription(1)
    print(f"Assistant: {result['message']}")
    
    # Step 3: Ask about events
    print("\nUser: What events happened on this subscription?\n")
    
    response = server.answer_question('events')
    print(f"Assistant: {response}")
    
    # Step 4: Ask about renewal
    print("\nUser: When does it renew?\n")
    
    response = server.answer_question('renewal')
    print(f"Assistant: {response}")


if __name__ == "__main__":
    demo_session()