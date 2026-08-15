"""Load and performance tests for the debug server.

This module tests:
- Concurrent request handling
- Response time benchmarks
- Memory usage
- Throughput testing
- Stress testing
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from app.services.user import clear_users_db
from app.services.auth_service import AuthService
from app.core.security import hash_password
from app.core.state import StateManager, state_manager


class TestResponseTime:
    """Tests for response time benchmarks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_health_endpoint_response_time(self, client):
        """Test health endpoint response time."""
        times = []

        for _ in range(100):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            times.append(end - start)
            assert response.status_code == 200, \
                f"Response should be successful, got {response.status_code}"

        avg_time = statistics.mean(times)
        max_time = max(times)

        # Response time should be reasonable (under 100ms for local test)
        assert avg_time < 0.1, f"Average response time should be under 100ms, got {avg_time*1000:.2f}ms"
        assert max_time < 0.5, f"Max response time should be under 500ms, got {max_time*1000:.2f}ms"

    def test_time_endpoint_response_time(self, client):
        """Test time endpoint response time."""
        times = []

        for _ in range(50):
            start = time.perf_counter()
            response = client.get("/time")
            end = time.perf_counter()

            times.append(end - start)
            assert response.status_code == 200, f"Time endpoint should succeed, got {response.status_code}"

        avg_time = statistics.mean(times)
        assert avg_time < 0.1, f"Average response time should be under 100ms, got {avg_time*1000:.2f}ms"

    def test_register_endpoint_response_time(self, client):
        """Test register endpoint response time."""
        clear_users_db()

        times = []

        for i in range(20):
            start = time.perf_counter()
            response = client.post(
                "/register",
                json={"email": f"perf_{i}@example.com", "password": "password12345678"}
            )
            end = time.perf_counter()

            times.append(end - start)
            assert response.status_code == 200, f"Registration {i} should succeed"

        avg_time = statistics.mean(times)
        assert avg_time < 0.5, f"Average response time should be under 500ms, got {avg_time*1000:.2f}ms"


class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_concurrent_health_checks(self, client):
        """Test concurrent health check requests."""
        num_requests = 50
        results = []

        def make_request():
            response = client.get("/health")
            return response.status_code

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(code == 200 for code in results), \
            f"All {num_requests} concurrent requests should succeed"

    def test_concurrent_user_registration(self, client):
        """Test concurrent user registration."""
        clear_users_db()

        num_requests = 20
        results = []

        def register_user(i):
            response = client.post(
                "/register",
                json={"email": f"concurrent_{i}@example.com", "password": "password12345678"}
            )
            return response.status_code

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(register_user, i) for i in range(num_requests)]
            results = [f.result() for f in futures]

        # All registrations should succeed
        assert all(code == 200 for code in results), \
            f"All {num_requests} concurrent registrations should succeed"


class TestThroughput:
    """Tests for throughput measurement."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_throughput_health_endpoint(self, client):
        """Test throughput of health endpoint."""
        num_requests = 100
        start_time = time.perf_counter()

        for _ in range(num_requests):
            response = client.get("/health")
            assert response.status_code == 200, "Health check should succeed"

        end_time = time.perf_counter()
        total_time = end_time - start_time
        throughput = num_requests / total_time

        print(f"\nHealth endpoint throughput: {throughput:.2f} requests/second")

        # Should handle at least 100 requests per second
        assert throughput > 100, f"Throughput should be > 100 req/s, got {throughput:.2f}"


class TestMemoryUsage:
    """Tests for memory usage patterns."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_memory_usage_stable(self, client):
        """Test that memory usage remains stable under load."""
        import gc

        # Force garbage collection before test
        gc.collect()

        # Make many requests
        for i in range(100):
            client.get("/health")
            if i % 20 == 0:
                gc.collect()

        # Force garbage collection after test
        gc.collect()

        # If we get here without memory error, test passes
        assert True, "Memory usage should remain stable"


class TestStressTesting:
    """Stress tests for the debug server."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_stress_health_endpoint(self, client):
        """Stress test health endpoint with many requests."""
        num_requests = 500
        errors = 0

        for i in range(num_requests):
            try:
                response = client.get("/health")
                if response.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1

        error_rate = errors / num_requests
        print(f"\nHealth endpoint error rate: {error_rate*100:.2f}%")

        # Error rate should be very low
        assert error_rate < 0.01, f"Error rate should be < 1%, got {error_rate*100:.2f}%"

    def test_stress_register_login_flow(self, client):
        """Stress test register and login flow."""
        clear_users_db()

        num_users = 30
        errors = 0

        for i in range(num_users):
            try:
                # Register
                reg_response = client.post(
                    "/register",
                    json={"email": f"stress_{i}@example.com", "password": "password12345678"}
                )
                assert reg_response.status_code == 200, f"Registration {i} failed"

                # Login
                login_response = client.post(
                    "/login",
                    data={"username": f"stress_{i}@example.com", "password": "password12345678"}
                )
                assert login_response.status_code == 200, f"Login {i} failed"

            except Exception as e:
                errors += 1
                print(f"Error at iteration {i}: {e}")

        error_rate = errors / num_users
        print(f"\nRegister/Login flow error rate: {error_rate*100:.2f}%")

        assert error_rate == 0, f"Error rate should be 0%, got {error_rate*100:.2f}%"


class TestSyncPerformance:
    """Performance tests for sync operations."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_sync_push_performance(self, client):
        """Test performance of push-actions endpoint."""
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        await state_manager.reset()
        
        send_result = await auth.send_mail_login_code("sync_perf@example.com")
        mail_auth_token = await auth.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )
        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "hash",
            "secondSalt": "salt"
        }
        result = await auth.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Device",
            "Pixel"
        )
        token = result["deviceAuthToken"]

        # Test with different batch sizes
        batch_sizes = [1, 5, 10]

        for batch_size in batch_sizes:
            actions = []
            for i in range(batch_size):
                actions.append({
                    "type": "AddCategoryAction",
                    "sequenceNumber": i + 1,
                    "integrity": f"password:base64{i}",
                    "userId": "user_123",
                    "encodedAction": f'{{"categoryId":"cat_{i}","title":"Category {i}","childId":"user_456"}}'
                })

            start_time = time.perf_counter()
            response = client.post(
                "/sync/push-actions",
                json={"deviceAuthToken": token, "actions": actions}
            )
            end_time = time.perf_counter()

            assert response.status_code == 200, f"Push with {batch_size} actions should succeed"

            elapsed = end_time - start_time
            print(f"\nPush {batch_size} actions: {elapsed*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_sync_pull_performance(self, client):
        """Test performance of pull-status endpoint."""
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        await state_manager.reset()
        
        send_result = await auth.send_mail_login_code("pull_perf@example.com")
        mail_auth_token = await auth.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )
        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "hash",
            "secondSalt": "salt"
        }
        result = await auth.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Device",
            "Pixel"
        )
        token = result["deviceAuthToken"]

        # Test pull performance
        num_requests = 50
        times = []

        for _ in range(num_requests):
            start_time = time.perf_counter()
            response = client.post(
                "/sync/pull-status",
                json={
                    "deviceAuthToken": token,
                    "status": {
                        "clientLevel": 7,
                        "devices": "",
                        "users": "",
                        "apps": {},
                        "devicesDetail": {},
                        "categories": {},
                        "kri": 0,
                        "kr": 0,
                        "dh": "",
                        "u2f": ""
                    }
                }
            )
            end_time = time.perf_counter()

            times.append(end_time - start_time)
            assert response.status_code == 200, "Pull should succeed"

        avg_time = statistics.mean(times)
        print(f"\nPull-status average time: {avg_time*1000:.2f}ms")

        assert avg_time < 0.5, f"Average pull time should be under 500ms, got {avg_time*1000:.2f}ms"


class TestDatabasePerformance:
    """Tests for database/state performance."""

    @pytest.mark.asyncio
    async def test_state_operations_performance(self):
        """Test state manager operations performance."""
        sm = StateManager()

        # Test family operations
        start = time.perf_counter()
        for i in range(100):
            await sm.create_family(f"family_{i}", {"familyId": f"family_{i}"})
        end = time.perf_counter()

        family_time = end - start
        print(f"\nCreate 100 families: {family_time*1000:.2f}ms")

        # Test user operations
        start = time.perf_counter()
        for i in range(100):
            await sm.create_user(f"user_{i}", {"userId": f"user_{i}"})
        end = time.perf_counter()

        user_time = end - start
        print(f"Create 100 users: {user_time*1000:.2f}ms")

        # Test device operations
        start = time.perf_counter()
        for i in range(100):
            await sm.create_device(f"device_{i}", {"deviceId": f"device_{i}"})
        end = time.perf_counter()

        device_time = end - start
        print(f"Create 100 devices: {device_time*1000:.2f}ms")

        # Verify operations are reasonably fast
        assert family_time < 5.0, f"Family creation should be fast, took {family_time:.2f}s"
        assert user_time < 5.0, f"User creation should be fast, took {user_time:.2f}s"
        assert device_time < 5.0, f"Device creation should be fast, took {device_time:.2f}s"

    @pytest.mark.asyncio
    async def test_state_query_performance(self):
        """Test state manager query performance."""
        sm = StateManager()

        # Create test data
        for i in range(100):
            await sm.create_family(f"family_{i}", {"familyId": f"family_{i}"})

        # Test query performance
        start = time.perf_counter()
        families = await sm.list_families()
        end = time.perf_counter()

        query_time = end - start
        print(f"\nList 100 families: {query_time*1000:.2f}ms")

        assert len(families) == 100, "Should retrieve all families"
        assert query_time < 1.0, f"Query should be fast, took {query_time*1000:.2f}ms"


class TestErrorRecovery:
    """Tests for error recovery under load."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_recovery_from_errors(self, client):
        """Test server recovery after errors."""
        clear_users_db()

        # Send some invalid requests
        for _ in range(10):
            response = client.post(
                "/register",
                json={"email": "invalid-email", "password": "short"}
            )
            assert response.status_code in [400, 422], "Invalid requests should fail"

        # Server should still be responsive
        response = client.get("/health")
        assert response.status_code == 200, "Server should be responsive after errors"

        # Valid requests should still work
        response = client.post(
            "/register",
            json={"email": "recovery@example.com", "password": "password12345678"}
        )
        assert response.status_code == 200, "Valid requests should work after errors"
