#!/usr/bin/env python3
"""
Script to update Twilio webhook configuration
Run this after you have your ngrok URL
"""
import os
import sys
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def update_twilio_webhooks(ngrok_url: str):
    """
    Update Twilio phone number webhooks with ngrok URL
    """
    # Get credentials from environment
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        print("ERROR: Missing Twilio credentials in .env file")
        return False
    
    if auth_token == "REPLACE_WITH_NEW_TOKEN_AFTER_REGENERATING":
        print("ERROR: You must update TWILIO_AUTH_TOKEN with your new token!")
        return False
    
    try:
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Find the phone number
        phone_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not phone_numbers:
            print(f"ERROR: Phone number {phone_number} not found in your account")
            return False
        
        phone_number_sid = phone_numbers[0].sid
        
        # Update the phone number configuration
        client.incoming_phone_numbers(phone_number_sid).update(
            voice_url=f"{ngrok_url}/api/webhooks/incoming-call",
            voice_method="POST",
            status_callback=f"{ngrok_url}/api/webhooks/call-status",
            status_callback_method="POST"
        )
        
        print(f"✅ Successfully updated Twilio webhooks!")
        print(f"   Voice URL: {ngrok_url}/api/webhooks/incoming-call")
        print(f"   Status Callback: {ngrok_url}/api/webhooks/call-status")
        
        # Update .env file
        update_env_file(ngrok_url)
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to update Twilio: {e}")
        return False

def update_env_file(ngrok_url: str):
    """
    Update .env file with ngrok URLs
    """
    # Extract domain from ngrok URL
    domain = ngrok_url.replace("https://", "").replace("http://", "")
    
    # Read current .env
    with open('.env', 'r') as f:
        lines = f.readlines()
    
    # Update relevant lines
    for i, line in enumerate(lines):
        if line.startswith('TWILIO_WEBHOOK_URL='):
            lines[i] = f'TWILIO_WEBHOOK_URL="{ngrok_url}"\n'
        elif line.startswith('TWILIO_STATUS_CALLBACK_URL='):
            lines[i] = f'TWILIO_STATUS_CALLBACK_URL="{ngrok_url}"\n'
        elif line.startswith('WEBSOCKET_HOST='):
            lines[i] = f'WEBSOCKET_HOST="{domain}"\n'
    
    # Write back
    with open('.env', 'w') as f:
        f.writelines(lines)
    
    print("\n✅ Updated .env file with ngrok URLs")

if __name__ == "__main__":
    print("Siphio Phone System - Twilio Configuration Updater")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        ngrok_url = sys.argv[1]
    else:
        ngrok_url = input("\nEnter your ngrok HTTPS URL (e.g., https://abc123.ngrok.io): ").strip()
    
    if not ngrok_url.startswith("https://"):
        print("ERROR: URL must start with https://")
        sys.exit(1)
    
    if update_twilio_webhooks(ngrok_url):
        print("\n🎉 Configuration complete!")
        print("\nNext steps:")
        print("1. Start your server: uvicorn app.main:app --reload")
        print("2. Make a test call to your Twilio number: +441615243042")
        print("3. Check the server logs for activity")
    else:
        print("\n❌ Configuration failed. Please check the errors above.")
