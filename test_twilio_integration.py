"""
Simple test script to verify Twilio integration
Run this to test the webhook endpoints
"""
import requests
import json
from datetime import datetime

# Base URL - change this to your ngrok URL when testing
BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_webhook_health():
    """Test webhook health endpoint"""
    print("Testing webhook health endpoint...")
    response = requests.get(f"{BASE_URL}/api/webhooks/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_incoming_call():
    """Simulate an incoming call webhook from Twilio"""
    print("Testing incoming call webhook...")
    
    # Simulate Twilio form data
    data = {
        "CallSid": f"CA{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "From": "+1234567890",
        "To": "+0987654321",
        "CallStatus": "in-progress",
        "Direction": "inbound",
        "AccountSid": "ACtest123456789"
    }
    
    # Note: In development, webhook validation is typically disabled
    response = requests.post(
        f"{BASE_URL}/api/webhooks/incoming-call",
        data=data
    )
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"TwiML Response:\n{response.text}")
    print()

def main():
    """Run all tests"""
    print("=== Siphio AI Phone System - Twilio Integration Test ===\n")
    
    try:
        test_health()
        test_webhook_health()
        test_incoming_call()
        
        print("\n✅ All tests completed!")
        print("\nNext steps:")
        print("1. Install ngrok: https://ngrok.com/download")
        print("2. Run ngrok: ngrok http 8000")
        print("3. Update your Twilio phone number webhook to: https://your-ngrok-url.ngrok.io/api/webhooks/incoming-call")
        print("4. Make a test call to your Twilio number")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the app is running:")
        print("   python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()