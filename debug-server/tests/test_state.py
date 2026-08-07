"""Unit tests for state management.

This module tests the StateManager class and its methods:
- Family management
- User management
- Device management
- Category management
- Token management
- Sync version management
- Connection management
"""

import pytest
import asyncio

from app.core.state import StateManager


class TestStateManagerInitialization:
    """Tests for StateManager initialization."""

    def test_state_manager_creation(self):
        """Test StateManager can be created."""
        sm = StateManager()
        assert sm is not None, "StateManager should be created"

    def test_state_manager_context_manager(self):
        """Test StateManager as context manager."""
        async def test():
            async with StateManager() as sm:
                assert sm is not None, "StateManager should be available in context"

        asyncio.run(test())


class TestFamilyManagement:
    """Tests for family management operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_create_family(self, state_manager):
        """Test family creation."""
        family_id = "family_123"
        family_data = {
            "familyId": family_id,
            "mail": "parent@example.com",
            "parentId": "parent_456"
        }

        await state_manager.create_family(family_id, family_data)

        retrieved = await state_manager.get_family(family_id)
        assert retrieved is not None, "Family should be created"
        assert retrieved["familyId"] == family_id, "Family ID should match"

    @pytest.mark.asyncio
    async def test_get_nonexistent_family(self, state_manager):
        """Test retrieving non-existent family."""
        retrieved = await state_manager.get_family("nonexistent_family")
        assert retrieved is None, "Non-existent family should return None"

    @pytest.mark.asyncio
    async def test_update_family(self, state_manager):
        """Test family update."""
        family_id = "family_123"
        family_data = {
            "familyId": family_id,
            "mail": "parent@example.com"
        }

        await state_manager.create_family(family_id, family_data)

        updated_data = {"mail": "updated@example.com"}
        result = await state_manager.update_family(family_id, updated_data)

        assert result is True, "Update should succeed"

        retrieved = await state_manager.get_family(family_id)
        assert retrieved["mail"] == "updated@example.com", "Mail should be updated"

    @pytest.mark.asyncio
    async def test_delete_family(self, state_manager):
        """Test family deletion."""
        family_id = "family_123"
        family_data = {"familyId": family_id, "mail": "parent@example.com"}

        await state_manager.create_family(family_id, family_data)

        result = await state_manager.delete_family(family_id)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_family(family_id)
        assert retrieved is None, "Family should be deleted"

    @pytest.mark.asyncio
    async def test_list_families(self, state_manager):
        """Test listing all families."""
        family_ids = ["family_1", "family_2", "family_3"]

        for fid in family_ids:
            await state_manager.create_family(fid, {"familyId": fid})

        listed = await state_manager.list_families()
        assert len(listed) == 3, "Should list all families"
        assert set(listed) == set(family_ids), "All family IDs should be present"

    @pytest.mark.asyncio
    async def test_get_family_by_mail(self, state_manager):
        """Test retrieving family by mail address."""
        family_id = "family_123"
        family_data = {
            "familyId": family_id,
            "mail": "parent@example.com"
        }

        await state_manager.create_family(family_id, family_data)

        retrieved = await state_manager.get_family_by_mail("parent@example.com")
        assert retrieved is not None, "Family should be found by mail"
        assert retrieved["familyId"] == family_id, "Family ID should match"


class TestUserManagement:
    """Tests for user management operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_create_user(self, state_manager):
        """Test user creation."""
        user_id = "user_123"
        user_data = {
            "userId": user_id,
            "userName": "Test User",
            "email": "user@example.com"
        }

        await state_manager.create_user(user_id, user_data)

        retrieved = await state_manager.get_user(user_id)
        assert retrieved is not None, "User should be created"
        assert retrieved["userId"] == user_id, "User ID should match"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, state_manager):
        """Test retrieving non-existent user."""
        retrieved = await state_manager.get_user("nonexistent_user")
        assert retrieved is None, "Non-existent user should return None"

    @pytest.mark.asyncio
    async def test_update_user(self, state_manager):
        """Test user update."""
        user_id = "user_123"
        user_data = {"userId": user_id, "userName": "Original Name"}

        await state_manager.create_user(user_id, user_data)

        updated_data = {"userName": "Updated Name"}
        result = await state_manager.update_user(user_id, updated_data)

        assert result is True, "Update should succeed"

        retrieved = await state_manager.get_user(user_id)
        assert retrieved["userName"] == "Updated Name", "Name should be updated"

    @pytest.mark.asyncio
    async def test_delete_user(self, state_manager):
        """Test user deletion."""
        user_id = "user_123"
        user_data = {"userId": user_id, "userName": "Test User"}

        await state_manager.create_user(user_id, user_data)

        result = await state_manager.delete_user(user_id)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_user(user_id)
        assert retrieved is None, "User should be deleted"

    @pytest.mark.asyncio
    async def test_get_users_by_family(self, state_manager):
        """Test retrieving users by family."""
        family_id = "family_123"

        user_ids = ["user_1", "user_2", "user_3"]
        for uid in user_ids:
            await state_manager.create_user(uid, {"userId": uid, "family_id": family_id})

        users = await state_manager.get_users_by_family(family_id)
        assert len(users) == 3, "Should retrieve all family users"


class TestDeviceManagement:
    """Tests for device management operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_create_device(self, state_manager):
        """Test device creation."""
        device_id = "device_123"
        device_data = {
            "deviceId": device_id,
            "deviceName": "Test Device",
            "deviceModel": "Pixel 7"
        }

        await state_manager.create_device(device_id, device_data)

        retrieved = await state_manager.get_device(device_id)
        assert retrieved is not None, "Device should be created"
        assert retrieved["deviceId"] == device_id, "Device ID should match"

    @pytest.mark.asyncio
    async def test_get_nonexistent_device(self, state_manager):
        """Test retrieving non-existent device."""
        retrieved = await state_manager.get_device("nonexistent_device")
        assert retrieved is None, "Non-existent device should return None"

    @pytest.mark.asyncio
    async def test_update_device(self, state_manager):
        """Test device update."""
        device_id = "device_123"
        device_data = {"deviceId": device_id, "deviceName": "Original Name"}

        await state_manager.create_device(device_id, device_data)

        updated_data = {"deviceName": "Updated Name"}
        result = await state_manager.update_device(device_id, updated_data)

        assert result is True, "Update should succeed"

        retrieved = await state_manager.get_device(device_id)
        assert retrieved["deviceName"] == "Updated Name", "Name should be updated"

    @pytest.mark.asyncio
    async def test_delete_device(self, state_manager):
        """Test device deletion."""
        device_id = "device_123"
        device_data = {"deviceId": device_id, "deviceName": "Test Device"}

        await state_manager.create_device(device_id, device_data)

        result = await state_manager.delete_device(device_id)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_device(device_id)
        assert retrieved is None, "Device should be deleted"

    @pytest.mark.asyncio
    async def test_get_devices_by_family(self, state_manager):
        """Test retrieving devices by family."""
        family_id = "family_123"

        device_ids = ["device_1", "device_2", "device_3"]
        for did in device_ids:
            await state_manager.create_device(did, {"deviceId": did, "family_id": family_id})

        devices = await state_manager.get_devices_by_family(family_id)
        assert len(devices) == 3, "Should retrieve all family devices"


class TestCategoryManagement:
    """Tests for category management operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_create_category(self, state_manager):
        """Test category creation."""
        category_id = "category_123"
        category_data = {
            "categoryId": category_id,
            "title": "Games",
            "apps": ["com.game1", "com.game2"]
        }

        await state_manager.create_category(category_id, category_data)

        retrieved = await state_manager.get_category(category_id)
        assert retrieved is not None, "Category should be created"
        assert retrieved["categoryId"] == category_id, "Category ID should match"

    @pytest.mark.asyncio
    async def test_get_nonexistent_category(self, state_manager):
        """Test retrieving non-existent category."""
        retrieved = await state_manager.get_category("nonexistent_category")
        assert retrieved is None, "Non-existent category should return None"

    @pytest.mark.asyncio
    async def test_update_category(self, state_manager):
        """Test category update."""
        category_id = "category_123"
        category_data = {"categoryId": category_id, "title": "Original Title"}

        await state_manager.create_category(category_id, category_data)

        updated_data = {"title": "Updated Title"}
        result = await state_manager.update_category(category_id, updated_data)

        assert result is True, "Update should succeed"

        retrieved = await state_manager.get_category(category_id)
        assert retrieved["title"] == "Updated Title", "Title should be updated"

    @pytest.mark.asyncio
    async def test_delete_category(self, state_manager):
        """Test category deletion."""
        category_id = "category_123"
        category_data = {"categoryId": category_id, "title": "Test Category"}

        await state_manager.create_category(category_id, category_data)

        result = await state_manager.delete_category(category_id)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_category(category_id)
        assert retrieved is None, "Category should be deleted"

    @pytest.mark.asyncio
    async def test_get_categories_by_user(self, state_manager):
        """Test retrieving categories by user."""
        user_id = "user_123"

        category_ids = ["cat_1", "cat_2", "cat_3"]
        for cid in category_ids:
            await state_manager.create_category(cid, {"categoryId": cid, "child_id": user_id})

        categories = await state_manager.get_categories_by_user(user_id)
        assert len(categories) == 3, "Should retrieve all user categories"


class TestTokenManagement:
    """Tests for token management operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_store_and_get_mail_login_token(self, state_manager):
        """Test mail login token storage and retrieval."""
        token = "mail_login_token_123"
        token_data = {
            "token": token,
            "mail": "test@example.com",
            "code": "123456",
            "expires_at": None
        }

        await state_manager.store_mail_login_token(
            token=token,
            mail=token_data["mail"],
            code=token_data["code"],
            expires_at=token_data.get("expires_at")
        )

        retrieved = await state_manager.get_mail_login_token(token)
        assert retrieved is not None, "Token should be retrieved"
        assert retrieved["mail"] == "test@example.com", "Mail should match"

    @pytest.mark.asyncio
    async def test_delete_mail_login_token(self, state_manager):
        """Test mail login token deletion."""
        token = "mail_login_token_123"

        await state_manager.store_mail_login_token(
            token=token,
            mail="test@example.com",
            code="123456"
        )

        result = await state_manager.delete_mail_login_token(token)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_mail_login_token(token)
        assert retrieved is None, "Token should be deleted"

    @pytest.mark.asyncio
    async def test_store_and_get_device_auth_token(self, state_manager):
        """Test device auth token storage and retrieval."""
        token = "device_auth_token_123"
        token_data = {
            "token": token,
            "familyId": "family_123",
            "deviceId": "device_456"
        }

        await state_manager.store_device_auth_token(
            token=token,
            device_id=token_data["deviceId"],
            family_id=token_data["familyId"]
        )

        retrieved = await state_manager.get_device_auth_token(token)
        assert retrieved is not None, "Token should be retrieved"
        assert retrieved["device_id"] == "device_456", "Device ID should match"

    @pytest.mark.asyncio
    async def test_store_and_get_add_device_token(self, state_manager):
        """Test add-device token storage and retrieval."""
        token = "add_device_token_123"
        token_data = {
            "token": token,
            "parentId": "parent_456"
        }

        await state_manager.create_add_device_token(
            token=token,
            device_id="device_123",
            parent_id=token_data["parentId"]
        )

        retrieved = await state_manager.get_add_device_token(token)
        assert retrieved is not None, "Token should be retrieved"
        assert retrieved["parent_id"] == "parent_456", "Parent ID should match"


class TestPendingActions:
    """Tests for pending actions management."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_add_pending_action(self, state_manager):
        """Test adding pending action."""
        action = {
            "type": "AddCategoryAction",
            "sequenceNumber": 1,
            "integrity": "password:base64encoded",
            "userId": "user_123",
            "encodedAction": '{"categoryId":"cat_123"}'
        }

        seq_num = await state_manager.add_pending_action(action)

        assert isinstance(seq_num, int), "Should return sequence number"
        assert seq_num > 0, "Sequence number should be positive"

    @pytest.mark.asyncio
    async def test_get_pending_action(self, state_manager):
        """Test retrieving pending action."""
        action = {
            "type": "AddCategoryAction",
            "sequenceNumber": 1,
            "integrity": "password:base64encoded",
            "userId": "user_123",
            "encodedAction": '{"categoryId":"cat_123"}'
        }

        seq_num = await state_manager.add_pending_action(action)

        retrieved = await state_manager.get_pending_action(seq_num)
        assert retrieved is not None, "Action should be retrieved"
        assert retrieved["type"] == "AddCategoryAction", "Action type should match"

    @pytest.mark.asyncio
    async def test_delete_pending_action(self, state_manager):
        """Test deleting pending action."""
        action = {
            "type": "AddCategoryAction",
            "sequenceNumber": 1,
            "integrity": "password:base64encoded",
            "userId": "user_123",
            "encodedAction": '{"categoryId":"cat_123"}'
        }

        seq_num = await state_manager.add_pending_action(action)

        result = await state_manager.delete_pending_action(seq_num)
        assert result is True, "Deletion should succeed"

        retrieved = await state_manager.get_pending_action(seq_num)
        assert retrieved is None, "Action should be deleted"

    @pytest.mark.asyncio
    async def test_get_pending_actions(self, state_manager):
        """Test retrieving multiple pending actions."""
        for i in range(5):
            action = {
                "type": "AddCategoryAction",
                "sequenceNumber": i + 1,
                "integrity": f"password:base64{i}",
                "userId": "user_123",
                "encodedAction": f'{{"categoryId":"cat_{i}"}}'
            }
            await state_manager.add_pending_action(action)

        actions = await state_manager.get_pending_actions(limit=10)
        assert len(actions) == 5, "Should retrieve all pending actions"

    @pytest.mark.asyncio
    async def test_clear_pending_actions(self, state_manager):
        """Test clearing all pending actions."""
        for i in range(5):
            action = {
                "type": "AddCategoryAction",
                "sequenceNumber": i + 1,
                "integrity": "password:base64",
                "userId": "user_123",
                "encodedAction": '{"categoryId":"cat"}'
            }
            await state_manager.add_pending_action(action)

        await state_manager.clear_pending_actions()

        actions = await state_manager.get_pending_actions()
        assert len(actions) == 0, "All actions should be cleared"


class TestSyncVersionManagement:
    """Tests for sync version management."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_set_and_get_sync_version(self, state_manager):
        """Test setting and getting sync version."""
        entity_type = "devices"
        version = "v1"

        await state_manager.set_sync_version(entity_type, version)

        retrieved = await state_manager.get_sync_version(entity_type)
        assert retrieved == version, "Version should match"

    @pytest.mark.asyncio
    async def test_increment_sync_version(self, state_manager):
        """Test incrementing sync version."""
        entity_type = "users"

        version1 = await state_manager.increment_sync_version(entity_type)
        version2 = await state_manager.increment_sync_version(entity_type)

        assert version1 != version2, "Versions should be different"
        assert version2 > version1, "Version should increment"


class TestAppsManagement:
    """Tests for apps management."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_set_apps(self, state_manager):
        """Test setting apps for a device."""
        device_id = "device_123"
        apps = ["com.app1", "com.app2", "com.app3"]

        await state_manager.set_apps(device_id, apps)

        retrieved = await state_manager.get_apps(device_id)
        assert retrieved == apps, "Apps should match"

    @pytest.mark.asyncio
    async def test_get_apps_nonexistent_device(self, state_manager):
        """Test getting apps for non-existent device."""
        apps = await state_manager.get_apps("nonexistent_device")
        assert apps == [], "Should return empty list for non-existent device"


class TestConnectionManagement:
    """Tests for connection management."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_add_connection(self, state_manager):
        """Test adding connection."""
        connection_id = "connection_123"

        await state_manager.add_connection(connection_id)

        connections = await state_manager.get_active_connections()
        assert connection_id in connections, "Connection should be added"

    @pytest.mark.asyncio
    async def test_remove_connection(self, state_manager):
        """Test removing connection."""
        connection_id = "connection_123"

        await state_manager.add_connection(connection_id)
        await state_manager.remove_connection(connection_id)

        connections = await state_manager.get_active_connections()
        assert connection_id not in connections, "Connection should be removed"

    @pytest.mark.asyncio
    async def test_get_active_connections(self, state_manager):
        """Test getting all active connections."""
        connection_ids = ["conn_1", "conn_2", "conn_3"]

        for cid in connection_ids:
            await state_manager.add_connection(cid)

        connections = await state_manager.get_active_connections()
        assert len(connections) == 3, "Should have 3 active connections"


class TestStateManagerReset:
    """Tests for StateManager reset functionality."""

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    async def test_reset_clears_all_data(self, state_manager):
        """Test that reset clears all data."""
        # Add some data
        await state_manager.create_family("family_1", {"familyId": "family_1"})
        await state_manager.create_user("user_1", {"userId": "user_1"})
        await state_manager.create_device("device_1", {"deviceId": "device_1"})

        # Reset
        await state_manager.reset()

        # Verify all data is cleared
        assert await state_manager.get_family("family_1") is None
        assert await state_manager.get_user("user_1") is None
        assert await state_manager.get_device("device_1") is None
        assert await state_manager.list_families() == []