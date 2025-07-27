#!/usr/bin/env python3
"""
Test the Twilio webhook endpoint directly
"""
import requests
import xml.etree.ElementTree as ET

def test_webhook():
    """Test the incoming call webhook"""
    url = "http://localhost:8000/api/webhooks/incoming-call"
    
    # Simulate Twilio webhook data
    data = {
        'CallSid': 'CA_TEST_123456789',
        'AccountSid': 'AC_TEST_ACCOUNT_SID',
        'From': '+447777777777',
        'To': '+441615243042',
        'CallStatus': 'ringing',
        'Direction': 'inbound',
        'ApiVersion': '2010-04-01'
    }
    
    print("Testing Twilio webhook endpoint...")
    print(f"URL: {url}")
    print(f"Data: {data}")
    print()
    
    try:
        response = requests.post(url, data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.headers.get('Content-Type', 'Not specified')}")
        print()
        
        if response.status_code == 200:
            print("Response (TwiML):")
            print("-" * 50)
            print(response.text)
            print("-" * 50)
            
            # Try to parse the TwiML
            try:
                root = ET.fromstring(response.text)
                print("\nParsed TwiML structure:")
                for elem in root.iter():
                    print(f"  {elem.tag}: {elem.text if elem.text else elem.attrib}")
            except Exception as e:
                print(f"\nError parsing TwiML: {e}")
        else:
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to server!")
        print("Make sure the FastAPI server is running on port 8000")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_webhook()