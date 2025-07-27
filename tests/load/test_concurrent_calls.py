"""
Load test for concurrent call handling
Tests WebSocket connections and audio streaming under load
"""
import asyncio
import time
import statistics
from typing import List, Dict, Any
import json
import base64
import random

import pytest
import websockets
import aiohttp
from faker import Faker

fake = Faker()

# Test configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
CONCURRENT_CALLS = 10  # Start with 10, increase for stress testing
CALL_DURATION_SECONDS = 30
AUDIO_CHUNK_INTERVAL_MS = 20


class CallSimulator:
    """
    Simulates a phone call with WebSocket audio streaming
    """
    
    def __init__(self, call_id: int):
        self.call_id = call_id
        self.call_sid = f"CA{fake.uuid4()[:32]}"
        self.from_number = fake.phone_number()
        self.to_number = "+18005551234"
        self.stream_id = None
        self.websocket = None
        self.metrics = {
            "connection_time": 0,
            "first_response_time": 0,
            "audio_chunks_sent": 0,
            "responses_received": 0,
            "errors": [],
            "latencies": []
        }
    
    async def initiate_call(self, session: aiohttp.ClientSession) -> str:
        """
        Initiate call via webhook and get WebSocket URL
        """
        start_time = time.time()
        
        data = {
            "CallSid": self.call_sid,
            "From": self.from_number,
            "To": self.to_number,
            "CallStatus": "in-progress",
            "Direction": "inbound"
        }
        
        async with session.post(f"{BASE_URL}/api/webhooks/incoming-call", data=data) as response:
            if response.status != 200:
                raise Exception(f"Webhook failed: {response.status}")
            
            # Parse TwiML to extract stream URL
            twiml = await response.text()
            # Extract stream ID from TwiML (simplified parsing)
            import re
            match = re.search(r'url=".*/(\w+_\w+)"', twiml)
            if match:
                self.stream_id = match.group(1)
            else:
                raise Exception("Could not extract stream ID from TwiML")
        
        self.metrics["connection_time"] = time.time() - start_time
        return f"{WS_URL}/media-stream/{self.stream_id}"
    
    async def stream_audio(self):
        """
        Stream audio data via WebSocket
        """
        ws_url = await self.initiate_call(aiohttp.ClientSession())
        
        async with websockets.connect(ws_url) as websocket:
            self.websocket = websocket
            
            # Send start event
            await websocket.send(json.dumps({
                "event": "start",
                "start": {
                    "streamSid": f"SM{fake.uuid4()[:32]}",
                    "accountSid": "ACtest",
                    "callSid": self.call_sid
                }
            }))
            
            # Start concurrent tasks
            await asyncio.gather(
                self._send_audio_chunks(),
                self._receive_responses(),
                return_exceptions=True
            )
    
    async def _send_audio_chunks(self):
        """
        Send audio chunks at regular intervals
        """
        chunks_to_send = int(CALL_DURATION_SECONDS * 1000 / AUDIO_CHUNK_INTERVAL_MS)
        
        for i in range(chunks_to_send):
            if self.websocket.closed:
                break
            
            # Generate mock audio data (160 bytes for 20ms at 8kHz)
            audio_data = bytes([random.randint(0, 255) for _ in range(160)])
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "event": "media",
                "sequenceNumber": str(i),
                "media": {
                    "track": "inbound",
                    "chunk": str(i),
                    "timestamp": str(int(time.time() * 1000)),
                    "payload": encoded_audio
                }
            }
            
            start_time = time.time()
            await self.websocket.send(json.dumps(message))
            self.metrics["audio_chunks_sent"] += 1
            
            # Track first response latency
            if self.metrics["first_response_time"] == 0 and self.metrics["responses_received"] > 0:
                self.metrics["first_response_time"] = time.time() - start_time
            
            # Wait for next chunk interval
            await asyncio.sleep(AUDIO_CHUNK_INTERVAL_MS / 1000)
        
        # Send stop event
        await self.websocket.send(json.dumps({"event": "stop"}))
    
    async def _receive_responses(self):
        """
        Receive responses from the server
        """
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                if data.get("event") == "media":
                    self.metrics["responses_received"] += 1
                    # Could track audio response latency here
                
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.metrics["errors"].append(str(e))
    
    async def end_call(self, session: aiohttp.ClientSession):
        """
        Send call completion webhook
        """
        data = {
            "CallSid": self.call_sid,
            "CallStatus": "completed",
            "CallDuration": str(CALL_DURATION_SECONDS)
        }
        
        async with session.post(f"{BASE_URL}/api/webhooks/call-status", data=data) as response:
            if response.status != 200:
                self.metrics["errors"].append(f"Call status webhook failed: {response.status}")


async def simulate_concurrent_calls(num_calls: int) -> List[Dict[str, Any]]:
    """
    Simulate multiple concurrent calls
    """
    print(f"Starting load test with {num_calls} concurrent calls...")
    
    simulators = [CallSimulator(i) for i in range(num_calls)]
    
    # Start all calls concurrently
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # Initiate all calls
        tasks = [simulator.stream_audio() for simulator in simulators]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                simulators[i].metrics["errors"].append(str(result))
        
        # End all calls
        end_tasks = [simulator.end_call(session) for simulator in simulators]
        await asyncio.gather(*end_tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    # Collect metrics
    all_metrics = [sim.metrics for sim in simulators]
    
    # Calculate aggregate statistics
    successful_calls = sum(1 for m in all_metrics if not m["errors"])
    avg_connection_time = statistics.mean([m["connection_time"] for m in all_metrics if m["connection_time"] > 0])
    avg_chunks_sent = statistics.mean([m["audio_chunks_sent"] for m in all_metrics])
    
    print(f"\nLoad Test Results:")
    print(f"  Total calls: {num_calls}")
    print(f"  Successful calls: {successful_calls}")
    print(f"  Success rate: {successful_calls/num_calls*100:.1f}%")
    print(f"  Total duration: {total_time:.2f}s")
    print(f"  Avg connection time: {avg_connection_time*1000:.2f}ms")
    print(f"  Avg audio chunks sent: {avg_chunks_sent:.0f}")
    
    # Print errors if any
    errors = [m["errors"] for m in all_metrics if m["errors"]]
    if errors:
        print(f"\n  Errors encountered:")
        for error_list in errors[:5]:  # Show first 5
            for error in error_list:
                print(f"    - {error}")
    
    return all_metrics


@pytest.mark.asyncio
@pytest.mark.load
async def test_concurrent_calls_basic():
    """
    Test basic concurrent call handling
    """
    metrics = await simulate_concurrent_calls(5)
    
    # Assertions
    successful = sum(1 for m in metrics if not m["errors"])
    assert successful >= 4, f"At least 4 out of 5 calls should succeed, got {successful}"


@pytest.mark.asyncio
@pytest.mark.load
@pytest.mark.stress
async def test_concurrent_calls_stress():
    """
    Stress test with higher concurrency
    """
    metrics = await simulate_concurrent_calls(CONCURRENT_CALLS)
    
    # More lenient assertions for stress test
    successful = sum(1 for m in metrics if not m["errors"])
    success_rate = successful / CONCURRENT_CALLS
    assert success_rate >= 0.8, f"At least 80% success rate required, got {success_rate*100:.1f}%"


@pytest.mark.asyncio
@pytest.mark.load
async def test_websocket_limits():
    """
    Test WebSocket connection limits
    """
    # Try to exceed max connections
    num_calls = 60  # Assuming max is 50
    
    simulators = [CallSimulator(i) for i in range(num_calls)]
    session = aiohttp.ClientSession()
    
    # Initiate calls one by one to test limit
    successful_connections = 0
    rejected_connections = 0
    
    for simulator in simulators:
        try:
            ws_url = await simulator.initiate_call(session)
            # Try to connect
            async with websockets.connect(ws_url) as ws:
                successful_connections += 1
                await ws.close()
        except Exception as e:
            if "capacity" in str(e).lower():
                rejected_connections += 1
            else:
                print(f"Unexpected error: {e}")
    
    await session.close()
    
    print(f"\nConnection limit test:")
    print(f"  Successful connections: {successful_connections}")
    print(f"  Rejected connections: {rejected_connections}")
    
    # Should enforce connection limit
    assert rejected_connections > 0, "Server should reject connections when at capacity"
    assert successful_connections <= 50, "Should not exceed max concurrent connections"


if __name__ == "__main__":
    # Run basic load test
    asyncio.run(simulate_concurrent_calls(CONCURRENT_CALLS))
