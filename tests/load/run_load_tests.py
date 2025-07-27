#!/usr/bin/env python3
"""
Simple load test runner for concurrent call testing
Run this to verify the system can handle concurrent calls
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.load.test_concurrent_calls import simulate_concurrent_calls


async def main():
    """
    Run load tests with increasing concurrency
    """
    print("AI Phone Receptionist - Load Test Suite")
    print("=" * 50)
    
    # Test levels
    test_levels = [
        (5, "Basic Load"),
        (10, "Moderate Load"),
        (25, "Heavy Load"),
        (50, "Stress Test")
    ]
    
    for num_calls, test_name in test_levels:
        print(f"\n{test_name} Test ({num_calls} concurrent calls)")
        print("-" * 40)
        
        try:
            await simulate_concurrent_calls(num_calls)
        except Exception as e:
            print(f"Test failed: {e}")
            break
        
        # Wait between tests
        if num_calls < 50:
            print("\nWaiting 5 seconds before next test...")
            await asyncio.sleep(5)
    
    print("\nLoad testing complete!")


if __name__ == "__main__":
    # Check if server is running
    import httpx
    
    try:
        response = httpx.get("http://localhost:8000/health")
        if response.status_code != 200:
            print("ERROR: Server health check failed")
            sys.exit(1)
    except Exception:
        print("ERROR: Server is not running. Start with: uvicorn app.main:app")
        sys.exit(1)
    
    # Run load tests
    asyncio.run(main())
