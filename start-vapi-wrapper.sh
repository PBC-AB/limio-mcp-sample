#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

echo "Starting services..."

# Start VAPI wrapper
python vapi_wrapper.py &
sleep 2

# Start ngrok
ngrok http --url="$NGROK_URL" --basic-auth="$NGROK_AUTH_USER:$NGROK_AUTH_PASS" 8000
