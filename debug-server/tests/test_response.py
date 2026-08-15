"""Unit tests for response models.

This module tests all Pydantic response models:
- User models (User, UserCreate, Token, TokenPayload)
- Auth models (TimeResponse, SendMailLoginCodeResponse, etc.)
- Sync models (ActionUploadRequest, ServerDataStatus, etc.)
- Parent models (CreateFamilyResponse, RemoveDeviceResponse, etc.)
- Child models (AddDeviceResponse, UpdatePrimaryDeviceResponse, etc.)
- Purchase models (CanDoPurchaseResponse, FinishPurchaseByGooglePlayResponse, etc.)
- Category models
- Device models
- Action models
"""

import pytest
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from app.models.user import User, UserCreate, Token, TokenPayload
from app.models.auth import (
    TimeResponse,
    SendMailLoginCodeResponse,
    SignInByMailCodeResponse,
    GetStatusByMailAddressResponse,
    CreateFamilyResponse,
    SignInIntoFamilyResponse,
    RecoverParentPasswordResponse,
)
from app.models.sync import (
    ActionUploadRequest,
    ActionUploadItem,
    ActionUploadResponse,
    ClientDataStatus,
    ServerDataStatus,
    PullStatusRequest,
    PullStatusResponse,
    ReportRemovedRequest,
    ReportRemovedResponse,
    IsDeviceRemovedRequest,
    IsDeviceRemovedResponse,
)
from app.models.parent import (
    CreateAddDeviceTokenResponse,
    RemoveDeviceResponse,
    LinkMailAddressResponse,
    CreateIdentityTokenResponse,
    DeleteAccountResponse,
)
from app.models.child import (
    AddDeviceResponse,
    UpdatePrimaryDeviceResponse,
    LogoutAtPrimaryDeviceResponse,
)
from app.models.purchase import (
    CanDoPurchaseResponse,
    FinishPurchaseByGooglePlayResponse,
)
from app.models.category import CategoryBaseData, CategoryAppAssignment, TimeLimitRule
from app.models.device import DeviceData, DeviceCreate, DeviceUpdate
from app.models.action import (
    AddCategoryAction,
    UpdateCategoryAction,
    DeleteCategoryAction,
    AddUsedTimeAction,
    AddRuleAction,
    DeleteRuleAction,
    TimeLimitRule,
    SetAppsAction,
)


class TestUserModels:
    """Tests for user-related models."""

    def test_user_create_validation(self):
        """Test UserCreate model validation."""
        user_create = UserCreate(email="test@example.com", password="password123")

        assert user_create.email == "test@example.com"
        assert user_create.password == "password123"

    def test_user_create_invalid_email(self):
        """Test UserCreate with invalid email."""
        with pytest.raises(ValidationError):
            UserCreate(email="invalid-email", password="password123")

    def test_user_create_short_password(self):
        """Test UserCreate with short password."""
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="short")

    def test_user_model(self):
        """Test User model."""
        user = User(id=1, email="test@example.com", is_active=True, created_at=datetime.now())

        assert user.id == 1
        assert user.email == "test@example.com"
        assert user.is_active is True

    def test_token_model(self):
        """Test Token model."""
        token = Token(access_token="token123", token_type="bearer")

        assert token.access_token == "token123"
        assert token.token_type == "bearer"

    def test_token_payload_model(self):
        """Test TokenPayload model."""
        payload = TokenPayload(sub="user123", device_id="device456")

        assert payload.sub == "user123"
        assert payload.device_id == "device456"


class TestAuthModels:
    """Tests for authentication-related models."""

    def test_time_response(self):
        """Test TimeResponse model."""
        response = TimeResponse(ms=1234567890)

        assert response.ms == 1234567890

    def test_send_mail_login_code_response(self):
        """Test SendMailLoginCodeResponse model."""
        response = SendMailLoginCodeResponse(
            status="ok",
            mailLoginToken="token123",
            mailServerBlacklisted=False,
            mailAddressNotWhitelisted=False
        )

        assert response.status == "ok"
        assert response.mailLoginToken == "token123"
        assert response.mailServerBlacklisted is False
        assert response.mailAddressNotWhitelisted is False

    def test_sign_in_by_mail_code_response(self):
        """Test SignInByMailCodeResponse model."""
        response = SignInByMailCodeResponse(
            status="ok",
            mailAuthToken="auth_token_123"
        )

        assert response.status == "ok"
        assert response.mailAuthToken == "auth_token_123"

    def test_get_status_by_mail_address_response(self):
        """Test GetStatusByMailAddressResponse model."""
        response = GetStatusByMailAddressResponse(
            status="ok",
            mail="test@example.com",
            familyStatus="new",
            canCreateFamily=True,
            alwaysPro=False
        )

        assert response.status == "ok"
        assert response.mail == "test@example.com"
        assert response.canCreateFamily is True
        assert response.alwaysPro is False

    def test_create_family_response(self):
        """Test CreateFamilyResponse model."""
        response = CreateFamilyResponse(
            status="ok",
            deviceAuthToken="device_token_123",
            ownDeviceId="device_456",
            data={
                "devices": {},
                "users": {},
                "apps": [],
                "categories": []
            }
        )

        assert response.status == "ok"
        assert response.deviceAuthToken == "device_token_123"
        assert response.ownDeviceId == "device_456"

    def test_sign_in_into_family_response(self):
        """Test SignInIntoFamilyResponse model."""
        response = SignInIntoFamilyResponse(
            status="ok",
            deviceAuthToken="device_token_123",
            ownDeviceId="device_456"
        )

        assert response.status == "ok"
        assert response.deviceAuthToken == "device_token_123"

    def test_recover_parent_password_response(self):
        """Test RecoverParentPasswordResponse model."""
        response = RecoverParentPasswordResponse(
            status="ok",
            message="Password recovered successfully"
        )

        assert response.status == "ok"


class TestSyncModels:
    """Tests for sync-related models."""

    def test_action_upload_item(self):
        """Test ActionUploadItem model."""
        item = ActionUploadItem(
            type="AddCategoryAction",
            sequenceNumber=1,
            integrity="password:base64encoded",
            userId="user_123",
            encodedAction='{"categoryId":"cat_123"}'
        )

        assert item.type == "AddCategoryAction"
        assert item.sequenceNumber == 1
        assert item.integrity == "password:base64encoded"
        assert item.userId == "user_123"

    def test_action_upload_request(self):
        """Test ActionUploadRequest model."""
        request = ActionUploadRequest(
            deviceAuthToken="token_123",
            actions=[
                ActionUploadItem(
                    type="AddCategoryAction",
                    sequenceNumber=1,
                    integrity="password:base64encoded",
                    userId="user_123",
                    encodedAction='{"categoryId":"cat_123"}'
                )
            ]
        )

        assert request.deviceAuthToken == "token_123"
        assert len(request.actions) == 1

    def test_action_upload_response(self):
        """Test ActionUploadResponse model."""
        response = ActionUploadResponse(
            status="ok",
            shouldDoFullSync=False
        )

        assert response.status == "ok"
        assert response.shouldDoFullSync is False

    def test_client_data_status(self):
        """Test ClientDataStatus model."""
        status = ClientDataStatus(
            clientLevel=7,
            devices="v1",
            users="v1",
            apps={},
            devicesDetail={},
            categories={},
            kri=0,
            kr=0,
            dh="v1",
            u2f="v1"
        )

        assert status.clientLevel == 7
        assert status.devices == "v1"

    def test_server_data_status(self):
        """Test ServerDataStatus model."""
        status = ServerDataStatus(
            devices={"v": "v1", "data": {}},
            users={"v": "v1", "data": {}},
            apps=[],
            categories=[],
            fullVersion=0,
            message="",
            apiLevel=1
        )

        assert status.devices["v"] == "v1"
        assert status.fullVersion == 0

    def test_pull_status_request(self):
        """Test PullStatusRequest model."""
        request = PullStatusRequest(
            deviceAuthToken="token_123",
            status=ClientDataStatus(
                clientLevel=7,
                devices="v1",
                users="v1",
                apps={},
                devicesDetail={},
                categories={},
                kri=0,
                kr=0,
                dh="v1",
                u2f="v1"
            )
        )

        assert request.deviceAuthToken == "token_123"

    def test_pull_status_response(self):
        """Test PullStatusResponse model."""
        response = PullStatusResponse(
            status="ok",
            data={
                "devices": {"v": "v1", "data": {}},
                "users": {"v": "v1", "data": {}},
                "apps": [],
                "categories": [],
                "fullVersion": 0,
                "message": "",
                "apiLevel": 1
            }
        )

        assert response.status == "ok"
        assert response.data["devices"]["v"] == "v1"

    def test_report_removed_request(self):
        """Test ReportRemovedRequest model."""
        request = ReportRemovedRequest(deviceAuthToken="token_123")

        assert request.deviceAuthToken == "token_123"

    def test_report_removed_response(self):
        """Test ReportRemovedResponse model."""
        response = ReportRemovedResponse(status="ok")

        assert response.status == "ok"

    def test_is_device_removed_request(self):
        """Test IsDeviceRemovedRequest model."""
        request = IsDeviceRemovedRequest(deviceAuthToken="token_123")

        assert request.deviceAuthToken == "token_123"

    def test_is_device_removed_response(self):
        """Test IsDeviceRemovedResponse model."""
        response = IsDeviceRemovedResponse(
            status="ok",
            isDeviceRemoved=True
        )

        assert response.status == "ok"
        assert response.isDeviceRemoved is True


class TestParentModels:
    """Tests for parent-related models."""

    def test_create_add_device_token_response(self):
        """Test CreateAddDeviceTokenResponse model."""
        response = CreateAddDeviceTokenResponse(
            status="ok",
            token="token_123",
            deviceId="device_456"
        )

        assert response.status == "ok"
        assert response.token == "token_123"
        assert response.deviceId == "device_456"

    def test_remove_device_response(self):
        """Test RemoveDeviceResponse model."""
        response = RemoveDeviceResponse(status="ok")

        assert response.status == "ok"

    def test_link_mail_address_response(self):
        """Test LinkMailAddressResponse model."""
        response = LinkMailAddressResponse(status="ok")

        assert response.status == "ok"

    def test_create_identity_token_response(self):
        """Test CreateIdentityTokenResponse model."""
        response = CreateIdentityTokenResponse(
            status="ok",
            identityToken="identity_123"
        )

        assert response.status == "ok"
        assert response.identityToken == "identity_123"

    def test_delete_account_response(self):
        """Test DeleteAccountResponse model."""
        response = DeleteAccountResponse(status="ok")

        assert response.status == "ok"


class TestChildModels:
    """Tests for child-related models."""

    def test_add_device_response(self):
        """Test AddDeviceResponse model."""
        response = AddDeviceResponse(
            status="ok",
            ownDeviceId="device_123",
            deviceAuthToken="auth_token_456"
        )

        assert response.status == "ok"
        assert response.ownDeviceId == "device_123"

    def test_update_primary_device_response(self):
        """Test UpdatePrimaryDeviceResponse model."""
        response = UpdatePrimaryDeviceResponse(status="ok")

        assert response.status == "ok"

    def test_logout_at_primary_device_response(self):
        """Test LogoutAtPrimaryDeviceResponse model."""
        response = LogoutAtPrimaryDeviceResponse(status="ok")

        assert response.status == "ok"


class TestPurchaseModels:
    """Tests for purchase-related models."""

    def test_can_do_purchase_response(self):
        """Test CanDoPurchaseResponse model."""
        response = CanDoPurchaseResponse(
            status="ok",
            canDoPurchase=True
        )

        assert response.status == "ok"
        assert response.canDoPurchase is True

    def test_can_do_purchase_response_not_available(self):
        """Test CanDoPurchaseResponse when purchase not available."""
        response = CanDoPurchaseResponse(
            status="ok",
            canDoPurchase=False
        )

        assert response.canDoPurchase is False

    def test_finish_purchase_by_google_play_response(self):
        """Test FinishPurchaseByGooglePlayResponse model."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=365)

        response = FinishPurchaseByGooglePlayResponse(
            status="ok",
            fullVersionUntil=future
        )

        assert response.status == "ok"
        assert response.fullVersionUntil is not None


class TestCategoryModels:
    """Tests for category-related models."""

    def test_category_base_data_model(self):
        """Test CategoryBaseData model."""
        category = CategoryBaseData(
            categoryId="cat_123",
            childId="user_456",
            title="Games",
            blockedTimes="0",
            extraTime=0,
            extraTimeDay=0,
            tempBlocked=False,
            tempBlockTime=0,
            version="1",
            parentCategoryId=None,
            blockAllNotifications=False,
            timeWarnings=0,
            sort=0,
            networks=[],
            flags=0,
            blockNotificationDelay=0,
            atw=[0, 0, 0, 0, 0, 0, 0]
        )

        assert category.categoryId == "cat_123"
        assert category.title == "Games"
        assert category.childId == "user_456"

    def test_category_app_assignment_model(self):
        """Test CategoryAppAssignment model."""
        category_app = CategoryAppAssignment(
            categoryId="cat_123",
            apps=["com.game1", "com.game2"],
            version="1"
        )

        assert category_app.categoryId == "cat_123"
        assert len(category_app.apps) == 2

    def test_time_limit_rule_model(self):
        """Test TimeLimitRule model."""
        rule = TimeLimitRule(
            categoryId="cat_123",
            day=1,
            startTime=0,
            endTime=86400000,
            maxTime=3600000
        )

        assert rule.categoryId == "cat_123"
        assert rule.day == 1
        assert rule.maxTime == 3600000


class TestDeviceModels:
    """Tests for device-related models."""

    def test_device_data_model(self):
        """Test DeviceData model."""
        device = DeviceData(
            deviceId="device_123",
            name="Test Device",
            model="Pixel 7",
            addedAt=1234567890000,
            currentUserId="user_123"
        )

        assert device.deviceId == "device_123"
        assert device.name == "Test Device"
        assert device.model == "Pixel 7"

    def test_device_create_model(self):
        """Test DeviceCreate model."""
        device = DeviceCreate(
            deviceId="device_123",
            name="Test Device",
            model="Pixel 7"
        )

        assert device.deviceId == "device_123"
        assert device.name == "Test Device"
        assert device.model == "Pixel 7"

    def test_device_update_model(self):
        """Test DeviceUpdate model."""
        device = DeviceUpdate(
            name="Updated Device",
            model="Pixel 8"
        )

        assert device.name == "Updated Device"
        assert device.model == "Pixel 8"


class TestActionModels:
    """Tests for action-related models."""

    def test_add_category_action(self):
        """Test AddCategoryAction model."""
        action = AddCategoryAction(
            categoryId="cat_123",
            title="Games",
            childId="user_456"
        )

        assert action.categoryId == "cat_123"
        assert action.title == "Games"
        assert action.childId == "user_456"

    def test_update_category_action(self):
        """Test UpdateCategoryAction model."""
        action = UpdateCategoryAction(
            categoryId="cat_123",
            title="Updated Title",
            tempBlocked=True,
            tempBlockTime=3600000
        )

        assert action.categoryId == "cat_123"
        assert action.title == "Updated Title"
        assert action.tempBlocked is True

    def test_delete_category_action(self):
        """Test DeleteCategoryAction model."""
        action = DeleteCategoryAction(categoryId="cat_123")

        assert action.categoryId == "cat_123"

    def test_add_used_time_action(self):
        """Test AddUsedTimeAction model."""
        action = AddUsedTimeAction(
            categoryId="cat_123",
            usedTime=3600000,
            date="2024-01-15"
        )

        assert action.categoryId == "cat_123"
        assert action.usedTime == 3600000
        assert action.date == "2024-01-15"

    def test_add_rule_action(self):
        """Test AddRuleAction model."""
        action = AddRuleAction(
            categoryId="cat_123",
            day=1,
            startTime=0,
            endTime=86400000,
            maxTime=3600000
        )

        assert action.categoryId == "cat_123"
        assert action.day == 1
        assert action.maxTime == 3600000

    def test_delete_rule_action(self):
        """Test DeleteRuleAction model."""
        action = DeleteRuleAction(
            categoryId="cat_123",
            day=1
        )

        assert action.categoryId == "cat_123"
        assert action.day == 1

    def test_time_limit_rule(self):
        """Test TimeLimitRule model."""
        rule = TimeLimitRule(
            categoryId="cat_123",
            day=1,
            startTime=0,
            endTime=86400000,
            maxTime=3600000
        )

        assert rule.categoryId == "cat_123"
        assert rule.day == 1

    def test_set_apps_action(self):
        """Test SetAppsAction model."""
        action = SetAppsAction(
            deviceId="device_123",
            apps=["com.app1", "com.app2"]
        )

        assert action.deviceId == "device_123"
        assert len(action.apps) == 2

    def test_action_validation_day_range(self):
        """Test that day validation works for actions."""
        with pytest.raises(ValidationError):
            AddRuleAction(
                categoryId="cat_123",
                day=7,  # Invalid: should be 0-6
                startTime=0,
                endTime=86400000,
                maxTime=3600000
            )


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_user_create_json(self):
        """Test UserCreate JSON serialization."""
        user_create = UserCreate(email="test@example.com", password="password123")
        json_data = user_create.model_dump()

        assert json_data["email"] == "test@example.com"
        assert json_data["password"] == "password123"

    def test_action_upload_item_json(self):
        """Test ActionUploadItem JSON serialization."""
        item = ActionUploadItem(
            type="AddCategoryAction",
            sequenceNumber=1,
            integrity="password:base64encoded",
            userId="user_123",
            encodedAction='{"categoryId":"cat_123"}'
        )
        json_data = item.model_dump()

        assert json_data["type"] == "AddCategoryAction"
        assert json_data["sequenceNumber"] == 1

    def test_server_data_status_json(self):
        """Test ServerDataStatus JSON serialization."""
        status = ServerDataStatus(
            devices={"v": "v1", "data": {}},
            users={"v": "v1", "data": {}},
            apps=[],
            categories=[],
            fullVersion=0,
            message="",
            apiLevel=1
        )
        json_data = status.model_dump()

        assert json_data["devices"]["v"] == "v1"
        assert json_data["fullVersion"] == 0

    def test_model_from_json(self):
        """Test model creation from JSON data."""
        data = {
            "type": "AddCategoryAction",
            "sequenceNumber": 1,
            "integrity": "password:base64encoded",
            "userId": "user_123",
            "encodedAction": '{"categoryId":"cat_123"}'
        }

        item = ActionUploadItem(**data)

        assert item.type == "AddCategoryAction"
        assert item.sequenceNumber == 1
