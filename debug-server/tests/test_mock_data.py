"""Unit tests for mock data generation.

This module tests the MockDataGenerator class and related functions:
- Device data generation
- Category data generation
- User data generation
- Action generation
- Response data generation
"""

import pytest
from datetime import datetime, timezone

from app.services.mock_data import MockDataGenerator
from app.services.sync_service import SyncService
from app.core.state import StateManager


class TestMockDataGenerator:
    """Tests for MockDataGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a MockDataGenerator instance for testing."""
        return MockDataGenerator(seed=42)

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    def test_generator_initialization(self, generator):
        """Test MockDataGenerator initialization."""
        assert generator is not None, "Generator should be initialized"
        assert generator.seed == 42, "Seed should be set correctly"

    def test_generate_device_id(self, generator):
        """Test device ID generation."""
        device_id = generator.generate_device_id()

        assert isinstance(device_id, str), "Device ID should be a string"
        assert len(device_id) > 0, "Device ID should not be empty"

    def test_generate_user_id(self, generator):
        """Test user ID generation."""
        user_id = generator.generate_user_id()

        assert isinstance(user_id, str), "User ID should be a string"
        assert len(user_id) > 0, "User ID should not be empty"

    def test_generate_category_id(self, generator):
        """Test category ID generation."""
        category_id = generator.generate_category_id()

        assert isinstance(category_id, str), "Category ID should be a string"
        assert len(category_id) > 0, "Category ID should not be empty"

    def test_generate_action_id(self, generator):
        """Test action ID generation."""
        action_id = generator.generate_action_id()

        assert isinstance(action_id, str), "Action ID should be a string"
        assert len(action_id) > 0, "Action ID should not be empty"

    def test_generate_unique_ids(self, generator):
        """Test that generated IDs are unique."""
        ids = set()
        for _ in range(100):
            device_id = generator.generate_device_id()
            assert device_id not in ids, "Device IDs should be unique"
            ids.add(device_id)

    def test_generate_device_data(self, generator):
        """Test device data generation."""
        device_data = generator.generate_device_data()

        assert isinstance(device_data, dict), "Device data should be a dictionary"
        assert "deviceId" in device_data, "Device data should contain deviceId"
        assert "deviceName" in device_data, "Device data should contain deviceName"
        assert "deviceModel" in device_data, "Device data should contain deviceModel"

    def test_generate_user_data(self, generator):
        """Test user data generation."""
        user_data = generator.generate_user_data()

        assert isinstance(user_data, dict), "User data should be a dictionary"
        assert "userId" in user_data, "User data should contain userId"
        assert "userName" in user_data, "User data should contain userName"

    def test_generate_category_data(self, generator):
        """Test category data generation."""
        category_data = generator.generate_category_data()

        assert isinstance(category_data, dict), "Category data should be a dictionary"
        assert "categoryId" in category_data, "Category data should contain categoryId"
        assert "title" in category_data, "Category data should contain title"

    def test_generate_app_data(self, generator):
        """Test app data generation."""
        app_data = generator.generate_app_data()

        assert isinstance(app_data, dict), "App data should be a dictionary"
        assert "packageName" in app_data, "App data should contain packageName"
        assert "appName" in app_data, "App data should contain appName"

    def test_generate_time_limit_rule(self, generator):
        """Test time limit rule generation."""
        rule = generator.generate_time_limit_rule(category_id="cat_123")

        assert isinstance(rule, dict), "Rule should be a dictionary"
        assert "categoryId" in rule, "Rule should contain categoryId"
        assert "day" in rule, "Rule should contain day"
        assert "startTime" in rule, "Rule should contain startTime"
        assert "endTime" in rule, "Rule should contain endTime"
        assert "maxTime" in rule, "Rule should contain maxTime"

        # Validate day range
        assert 0 <= rule["day"] <= 6, "Day should be between 0 and 6"

    def test_generate_sync_action(self, generator):
        """Test sync action generation."""
        action = generator.generate_sync_action(
            action_type="AddCategoryAction",
            user_id="user_123"
        )

        assert isinstance(action, dict), "Action should be a dictionary"
        assert "type" in action, "Action should contain type"
        assert "sequenceNumber" in action, "Action should contain sequenceNumber"
        assert "integrity" in action, "Action should contain integrity"
        assert "userId" in action, "Action should contain userId"
        assert "encodedAction" in action, "Action should contain encodedAction"

    def test_generate_multiple_actions(self, generator):
        """Test generation of multiple actions."""
        actions = generator.generate_actions(count=10)

        assert isinstance(actions, list), "Actions should be a list"
        assert len(actions) == 10, "Should generate 10 actions"

        for action in actions:
            assert "type" in action, "Each action should have a type"
            assert "sequenceNumber" in action, "Each action should have a sequenceNumber"

    def test_reproducible_generation(self, generator):
        """Test that same seed produces same data."""
        gen1 = MockDataGenerator(seed=123)
        gen2 = MockDataGenerator(seed=123)

        id1 = gen1.generate_device_id()
        id2 = gen2.generate_device_id()

        assert id1 == id2, "Same seed should produce same IDs"


class TestMockDataIntegration:
    """Integration tests for mock data with state management."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_store_and_retrieve_device(self, state_manager):
        """Test storing and retrieving device data."""
        generator = MockDataGenerator(seed=42)
        device_data = generator.generate_device_data()
        device_id = device_data["deviceId"]

        # Store device
        await state_manager.create_device(device_id, device_data)

        # Retrieve device
        retrieved = await state_manager.get_device(device_id)

        assert retrieved is not None, "Device should be retrieved"
        assert retrieved["deviceId"] == device_id, "Device ID should match"

    @pytest.mark.asyncio
    async def test_store_and_retrieve_user(self, state_manager):
        """Test storing and retrieving user data."""
        generator = MockDataGenerator(seed=42)
        user_data = generator.generate_user_data()
        user_id = user_data["userId"]

        # Store user
        await state_manager.create_user(user_id, user_data)

        # Retrieve user
        retrieved = await state_manager.get_user(user_id)

        assert retrieved is not None, "User should be retrieved"
        assert retrieved["userId"] == user_id, "User ID should match"

    @pytest.mark.asyncio
    async def test_store_and_retrieve_category(self, state_manager):
        """Test storing and retrieving category data."""
        generator = MockDataGenerator(seed=42)
        category_data = generator.generate_category_data()
        category_id = category_data["categoryId"]

        # Store category
        await state_manager.create_category(category_id, category_data)

        # Retrieve category
        retrieved = await state_manager.get_category(category_id)

        assert retrieved is not None, "Category should be retrieved"
        assert retrieved["categoryId"] == category_id, "Category ID should match"

    @pytest.mark.asyncio
    async def test_family_operations(self, state_manager):
        """Test family creation and retrieval."""
        generator = MockDataGenerator(seed=42)
        family = generator.generate_family()
        family_id = family["family_id"]

        # Create family
        await state_manager.create_family(family_id, family)

        # Retrieve family
        retrieved = await state_manager.get_family(family_id)

        assert retrieved is not None, "Family should be retrieved"
        assert retrieved["family_id"] == family_id, "Family ID should match"

    @pytest.mark.asyncio
    async def test_device_auth_token_operations(self, state_manager):
        """Test device auth token storage and retrieval."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_device_auth_token_data()
        token = token_data["token"]
        device_id = token_data["deviceId"]
        family_id = token_data["familyId"]

        # Store token
        await state_manager.store_device_auth_token(token, device_id, family_id)

        # Retrieve token
        retrieved = await state_manager.get_device_auth_token(token)

        assert retrieved is not None, "Token should be retrieved"
        assert retrieved["device_id"] == device_id, "Device ID should match"

    @pytest.mark.asyncio
    async def test_add_device_token_operations(self, state_manager):
        """Test add-device token storage and retrieval."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_add_device_token_data()
        token = token_data["token"]
        device_id = token_data["deviceId"]
        parent_id = token_data["parentId"]

        # Store token
        await state_manager.create_add_device_token(token, device_id, parent_id)

        # Retrieve token
        retrieved = await state_manager.get_add_device_token(token)

        assert retrieved is not None, "Token should be retrieved"
        assert retrieved["device_id"] == device_id, "Device ID should match"


class TestMockDataGenerationMethods:
    """Tests for specific mock data generation methods."""

    def test_generate_family_data(self):
        """Test family data generation."""
        generator = MockDataGenerator(seed=42)
        family_data = generator.generate_family_data()

        assert isinstance(family_data, dict), "Family data should be a dictionary"
        assert "devices" in family_data, "Family data should contain devices"
        assert "users" in family_data, "Family data should contain users"
        assert "apps" in family_data, "Family data should contain apps"
        assert "categoryBase" in family_data, "Family data should contain categoryBase"

    def test_generate_device_auth_token_data(self):
        """Test device auth token data generation."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_device_auth_token_data()

        assert isinstance(token_data, dict), "Token data should be a dictionary"
        assert "token" in token_data, "Token data should contain token"
        assert "familyId" in token_data, "Token data should contain familyId"
        assert "deviceId" in token_data, "Token data should contain deviceId"

    def test_generate_add_device_token_data(self):
        """Test add-device token data generation."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_add_device_token_data()

        assert isinstance(token_data, dict), "Token data should be a dictionary"
        assert "token" in token_data, "Token data should contain token"
        assert "parentId" in token_data, "Token data should contain parentId"

    def test_generate_mail_login_token_data(self):
        """Test mail login token data generation."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_mail_login_token_data()

        assert isinstance(token_data, dict), "Token data should be a dictionary"
        assert "token" in token_data, "Token data should contain token"
        assert "mail" in token_data, "Token data should contain mail"

    def test_generate_mail_auth_token_data(self):
        """Test mail auth token data generation."""
        generator = MockDataGenerator(seed=42)
        token_data = generator.generate_mail_auth_token_data()

        assert isinstance(token_data, dict), "Token data should be a dictionary"
        assert "token" in token_data, "Token data should contain token"
        assert "mailLoginToken" in token_data, "Token data should contain mailLoginToken"

    def test_generate_sync_status(self):
        """Test sync status generation."""
        generator = MockDataGenerator(seed=42)
        status = generator.generate_sync_status()

        assert isinstance(status, dict), "Sync status should be a dictionary"
        assert "clientLevel" in status, "Sync status should contain clientLevel"
        assert "devices" in status, "Sync status should contain devices"
        assert "users" in status, "Sync status should contain users"
        assert "apps" in status, "Sync status should contain apps"

    def test_generate_server_data_status(self):
        """Test server data status generation."""
        generator = MockDataGenerator(seed=42)
        status = generator.generate_server_data_status()

        assert isinstance(status, dict), "Server data status should be a dictionary"
        assert "devices" in status, "Server data status should contain devices"
        assert "users" in status, "Server data status should contain users"
        assert "apps" in status, "Server data status should contain apps"
        assert "categoryBase" in status, "Server data status should contain categoryBase"


class TestMockDataWithSyncService:
    """Tests for mock data integration with SyncService."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_sync_service_with_mock_data(self, state_manager):
        """Test SyncService with mock data."""
        generator = MockDataGenerator(seed=42)
        sync_service = SyncService(state_manager)

        # Generate mock actions
        actions = generator.generate_actions(count=5)

        # Verify actions are valid
        for action in actions:
            assert "type" in action, "Action should have type"
            assert "sequenceNumber" in action, "Action should have sequenceNumber"
            assert "integrity" in action, "Action should have integrity"

    @pytest.mark.asyncio
    async def test_push_pull_with_mock_data(self, state_manager):
        """Test push/pull operations with mock data."""
        generator = MockDataGenerator(seed=42)
        sync_service = SyncService(state_manager)

        # Create a family first
        family = generator.generate_family()
        family_id = family["family_id"]
        await state_manager.create_family(family_id, family)

        # Create a device auth token with the same family_id
        device_id = f"device_{generator._random_string(8)}"
        token = f"device_token_{generator._random_string(16)}"
        await state_manager.store_device_auth_token(token, device_id, family_id)

        # Generate mock actions
        actions = generator.generate_actions(count=3)

        # Push actions
        result = await sync_service.push_actions(
            token,
            actions
        )

        assert result is not None, "Push should return a result"
        assert "shouldDoFullSync" in result, "Result should contain shouldDoFullSync"

        # Pull status
        client_status = generator.generate_sync_status()
        pull_result = await sync_service.pull_status(
            token,
            client_status
        )

        assert pull_result is not None, "Pull should return a result"
        assert "devices" in pull_result, "Result should contain devices"
        assert "users" in pull_result, "Result should contain users"


class TestMockDataValidation:
    """Tests for mock data validation."""

    def test_device_data_validation(self):
        """Test that generated device data is valid."""
        generator = MockDataGenerator(seed=42)

        for _ in range(10):
            device_data = generator.generate_device_data()

            # Validate required fields
            assert "deviceId" in device_data
            assert "deviceName" in device_data
            assert "deviceModel" in device_data

            # Validate types
            assert isinstance(device_data["deviceId"], str)
            assert isinstance(device_data["deviceName"], str)
            assert isinstance(device_data["deviceModel"], str)

    def test_category_data_validation(self):
        """Test that generated category data is valid."""
        generator = MockDataGenerator(seed=42)

        for _ in range(10):
            category_data = generator.generate_category_data()

            # Validate required fields
            assert "categoryId" in category_data
            assert "title" in category_data

            # Validate types
            assert isinstance(category_data["categoryId"], str)
            assert isinstance(category_data["title"], str)

    def test_action_data_validation(self):
        """Test that generated action data is valid."""
        generator = MockDataGenerator(seed=42)

        for _ in range(10):
            action = generator.generate_sync_action(
                action_type="AddCategoryAction",
                user_id="user_123"
            )

            # Validate required fields
            assert "type" in action
            assert "sequenceNumber" in action
            assert "integrity" in action
            assert "userId" in action
            assert "encodedAction" in action

            # Validate types
            assert isinstance(action["type"], str)
            assert isinstance(action["sequenceNumber"], int)
            assert isinstance(action["integrity"], str)
            assert isinstance(action["userId"], str)
            assert isinstance(action["encodedAction"], str)

            # Validate sequence number is positive
            assert action["sequenceNumber"] > 0, "Sequence number should be positive"

            # Validate integrity format
            assert action["integrity"].startswith("password:"), \
                "Integrity should start with 'password:'"