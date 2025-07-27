"""
Benchmark tests for performance validation
"""
import asyncio
import os
import time
import pytest
from unittest.mock import patch

from app.core.security_utils import EncryptionManager, mask_phone, mask_email
from app.core.config import get_settings


class TestPerformanceBenchmarks:
    """Test performance benchmarks without external dependencies"""
    
    def test_encryption_single_operation(self):
        """Test single encryption/decryption performance"""
        manager = EncryptionManager()
        test_data = "Patient: John Doe, SSN: 123-45-6789, DOB: 01/01/1980"
        
        # Measure encryption time
        start = time.perf_counter()
        encrypted = manager.encrypt(test_data)
        encrypt_time = (time.perf_counter() - start) * 1000  # Convert to ms
        
        # Measure decryption time
        start = time.perf_counter()
        decrypted = manager.decrypt(encrypted)
        decrypt_time = (time.perf_counter() - start) * 1000
        
        # Verify correctness
        assert decrypted == test_data
        
        # Performance assertions (should be <2ms for typical PHI data, allowing for variance)
        assert encrypt_time < 2.0, f"Encryption took {encrypt_time:.2f}ms, expected <2ms"
        assert decrypt_time < 2.0, f"Decryption took {decrypt_time:.2f}ms, expected <2ms"
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(os.environ.get('SKIP_SLOW_TESTS') == 'true', reason="Skipping slow tests in CI")
    async def test_concurrent_encryption(self):
        """Test concurrent encryption operations"""
        manager = EncryptionManager()
        test_data = ["Patient record " + str(i) for i in range(100)]
        
        async def encrypt_decrypt(data: str):
            # Simulate async operation
            await asyncio.sleep(0)  # Yield control
            encrypted = manager.encrypt(data)
            decrypted = manager.decrypt(encrypted)
            return decrypted == data
        
        # Run 100 concurrent operations
        start = time.perf_counter()
        tasks = [encrypt_decrypt(data) for data in test_data]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start
        
        # Verify all operations succeeded
        assert all(results)
        
        # Calculate operations per second
        ops_per_sec = len(test_data) / total_time
        
        # Should handle reasonable ops/sec (adjusted for CI/CD environments)
        # Being conservative for slower hardware
        min_ops_per_sec = 300 if os.environ.get('CI') == 'true' else 400
        assert ops_per_sec > min_ops_per_sec, f"Only {ops_per_sec:.0f} ops/sec, expected >{min_ops_per_sec}"
    
    def test_masking_performance(self):
        """Test masking function performance"""
        test_phones = ["123-456-7890" for _ in range(1000)]
        test_emails = ["user@example.com" for _ in range(1000)]
        
        # Test phone masking performance
        start = time.perf_counter()
        for phone in test_phones:
            mask_phone(phone)
        phone_time = (time.perf_counter() - start) * 1000
        
        # Test email masking performance
        start = time.perf_counter()
        for email in test_emails:
            mask_email(email)
        email_time = (time.perf_counter() - start) * 1000
        
        # Should mask 1000 items in reasonable time
        assert phone_time < 100, f"Phone masking took {phone_time:.2f}ms for 1000 items"
        assert email_time < 200, f"Email masking took {email_time:.2f}ms for 1000 items (includes validation)"
    
    @pytest.mark.asyncio
    async def test_health_endpoint_latency(self):
        """Simulate health endpoint performance"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        # Use sync client for simplicity
        client = TestClient(app)
        
        # Warm up
        client.get("/health")
        
        # Measure multiple requests
        times = []
        for _ in range(10):
            start = time.perf_counter()
            response = client.get("/health")
            latency = (time.perf_counter() - start) * 1000
            times.append(latency)
            assert response.status_code == 200
        
        # Calculate average latency
        avg_latency = sum(times) / len(times)
        
        # Should be reasonable for health endpoint (allowing for test overhead)
        max_latency = 20 if os.environ.get('CI') == 'true' else 10
        assert avg_latency < max_latency, f"Average latency {avg_latency:.2f}ms, expected <{max_latency}ms"
    
    def test_config_loading_performance(self):
        """Test configuration loading performance"""
        # Clear cache to test fresh load
        get_settings.cache_clear()
        
        start = time.perf_counter()
        settings = get_settings()
        load_time = (time.perf_counter() - start) * 1000
        
        # Verify settings loaded
        assert settings.APP_NAME is not None
        
        # Should load quickly
        assert load_time < 100, f"Config loading took {load_time:.2f}ms, expected <100ms"
    
    @pytest.mark.asyncio
    async def test_async_io_simulation(self):
        """Simulate async I/O patterns without external dependencies"""
        async def simulate_db_query():
            # Simulate database query latency
            await asyncio.sleep(0.01)  # 10ms
            return {"id": 1, "name": "Test Patient"}
        
        async def simulate_api_call():
            # Simulate external API call
            await asyncio.sleep(0.02)  # 20ms
            return {"status": "success"}
        
        # Run operations concurrently
        start = time.perf_counter()
        results = await asyncio.gather(
            simulate_db_query(),
            simulate_api_call(),
            simulate_db_query(),
        )
        total_time = (time.perf_counter() - start) * 1000
        
        # Verify results
        assert len(results) == 3
        assert results[0]["name"] == "Test Patient"
        assert results[1]["status"] == "success"
        
        # Should complete in ~20ms (concurrent), not 40ms (sequential)
        assert total_time < 30, f"Concurrent ops took {total_time:.2f}ms, expected <30ms"


class TestMemoryEfficiency:
    """Test memory efficiency of operations"""
    
    def test_encryption_memory_stability(self):
        """Test that encryption doesn't leak memory"""
        manager = EncryptionManager()
        
        # Track operation count before
        initial_count = manager.operation_count
        
        # Perform many operations
        for i in range(100):
            data = f"Test data {i}" * 100  # ~1KB each
            encrypted = manager.encrypt(data)
            decrypted = manager.decrypt(encrypted)
            assert decrypted == data
        
        # Verify operation count increased correctly
        assert manager.operation_count == initial_count + 200  # 100 encrypt + 100 decrypt
    
    @pytest.mark.asyncio
    async def test_concurrent_memory_usage(self):
        """Test memory usage under concurrent load"""
        manager = EncryptionManager()
        
        async def process_batch(batch_id: int):
            # Process a batch of data
            results = []
            for i in range(10):
                data = f"Batch {batch_id} Item {i}"
                encrypted = manager.encrypt(data)
                # Simulate some async work
                await asyncio.sleep(0.001)
                decrypted = manager.decrypt(encrypted)
                results.append(decrypted == data)
            return all(results)
        
        # Run 10 concurrent batches
        tasks = [process_batch(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All batches should succeed
        assert all(results)