import requests
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LimioClient:
    def __init__(self):
        self.base_url = os.getenv("BASE_URL", "https://api.example-saas.com")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.token = None
        self.token_expiry = None
        logger.info(f"LimioClient initialized with base_url: {self.base_url}")
    
    def _ensure_token(self):
        """Get OAuth token if needed"""
        if not self.token or (self.token_expiry and datetime.now() >= self.token_expiry):
            logger.info("Getting new OAuth token")
            token_url = f"{self.base_url}/oauth2/token"
            logger.debug(f"Token URL: {token_url}")
            
            try:
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
                token_data = response.json()
                self.token = token_data["access_token"]
                logger.info("OAuth token obtained successfully")
                
                # Store expiry time if provided
                if "expires_in" in token_data:
                    from datetime import timedelta
                    self.token_expiry = datetime.now() + timedelta(seconds=token_data["expires_in"])
                    logger.debug(f"Token expires at: {self.token_expiry}")
            except Exception as e:
                logger.error(f"Failed to get OAuth token: {str(e)}", exc_info=True)
                raise
    
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
        logger.info(f"Getting subscription details for: {subscription_id}")
        
        # Get subscription
        url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}"
        logger.info(f"Subscription URL: {url}")
        
        try:
            response = requests.get(url, headers=self._get_headers())
            logger.info(f"Subscription response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.warning(f"Failed to get subscription. Status: {response.status_code}, Response: {response.text}")
                return None
                
            subscription = response.json()
            logger.info(f"Subscription data retrieved successfully")
            
            # Get related objects
            url = f"{self.base_url}/api/objects/limio/subscription/{subscription_id}/related"
            logger.info(f"Related objects URL: {url}")
            
            response = requests.get(url, headers=self._get_headers())
            logger.info(f"Related objects response status: {response.status_code}")
            
            if response.status_code == 200:
                related = response.json()
                subscription['_related'] = related.get('items', [])
                logger.info(f"Added {len(related.get('items', []))} related objects to subscription")
            else:
                logger.warning(f"Failed to get related objects. Status: {response.status_code}")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error in get_subscription_details: {str(e)}", exc_info=True)
            raise
    
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
    
    def find_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """Get customer details by ID"""
        url = f"{self.base_url}/api/objects/limio/customer/{customer_id}"
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            return response.json()
        return None