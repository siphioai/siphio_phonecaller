#!/usr/bin/env python3
"""
Quick test to verify server is ready for Twilio calls
"""
import asyncio
import aiohttp
import json
from datetime import datetime

async def test_server():
    """Test server endpoints"""
    base_url = "http://localhost:8000"
    ngrok_url = "https://79c9e80e881e.ngrok-free.app"
    
    print("Siphio Phone System - Server Readiness Test")
    print("=" * 50)
    print(f"Testing at: {datetime.now()}")
    print(f"Ngrok URL: {ngrok_url}")
    print()
    
    tests_passed = 0
    tests_total = 0
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Health endpoint
        print("1. Testing health endpoint...")
        tests_total += 1
        try:
            async with session.get(f"{base_url}/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✓ Health check passed: {data}")
                    tests_passed += 1
                else:
                    print(f"   ✗ Health check failed: Status {resp.status}")
        except Exception as e:
            print(f"   ✗ Health check failed: {e}")
        
        # Test 2: Webhook health
        print("\n2. Testing webhook health...")
        tests_total += 1
        try:
            async with session.get(f"{base_url}/api/webhooks/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✓ Webhook health passed: {data}")
                    tests_passed += 1
                else:
                    print(f"   ✗ Webhook health failed: Status {resp.status}")
        except Exception as e:
            print(f"   ✗ Webhook health failed: {e}")
        
        # Test 3: Check ngrok connectivity
        print("\n3. Testing ngrok connectivity...")
        tests_total += 1
        try:
            async with session.get(f"{ngrok_url}/health") as resp:
                if resp.status == 200:
                    print(f"   ✓ Ngrok tunnel is working!")
                    tests_passed += 1
                else:
                    print(f"   ✗ Ngrok tunnel returned status {resp.status}")
        except Exception as e:
            print(f"   ✗ Ngrok connectivity failed: {e}")
            print("   Make sure ngrok is running!")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("\n✅ SERVER IS READY FOR TWILIO CALLS!")
        print("\nNext steps:")
        print("1. Make sure ngrok is running")
        print("2. Update Twilio webhooks with: python update_twilio_config.py " + ngrok_url)
        print("3. Call your Twilio number: +441615243042")
    else:
        print("\n⚠️  Some tests failed. Please check:")
        print("1. Is the server running? (uvicorn app.main:app --reload)")
        print("2. Is ngrok running? (ngrok http 8000)")
        print("3. Check server logs for errors")

if __name__ == "__main__":
    asyncio.run(test_server())