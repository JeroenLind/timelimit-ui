"""Authentication service for TimeLimit API.

This module provides authentication service logic for handling
email login codes, mail auth tokens, and device auth tokens.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.security import hash_password
from app.core.state import state_manager

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for TimeLimit API.
    
    Handles:
    - Email login code generation and validation
    - Mail auth token management
    - Device auth token management
    - Family creation and sign-in
    """
    
    def __init__(self, state: state_manager = None):
        """Initialize the auth service.
        
        Args:
            state: State manager instance. Uses global state_manager if not provided.
        """
        self.state = state or state_manager
    
    def _generate_code(self, length: int = 6) -> str:
        """Generate a random verification code.
        
        Args:
            length: Code length.
            
        Returns:
            Random numeric code.
        """
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    def _generate_token(self, length: int = 32) -> str:
        """Generate a random token.
        
        Args:
            length: Token length.
            
        Returns:
            Random alphanumeric token.
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def send_mail_login_code(
        self,
        mail: str,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Send email login code.
        
        Args:
            mail: Email address.
            locale: Locale for the code.
            
        Returns:
            Mail login token and status.
        """
        # Generate verification code
        code = self._generate_code()
        
        # Generate mail login token
        mail_login_token = self._generate_token()
        
        # Store the token
        await self.state.store_mail_login_token(
            token=mail_login_token,
            mail=mail,
            code=code,
        )
        
        logger.info(
            "Mail login code sent",
            extra={"mail": mail, "token": mail_login_token[:8] + "..."}
        )
        
        return {
            "mailLoginToken": mail_login_token,
            "mailServerBlacklisted": False,
            "mailAddressNotWhitelisted": False,
            "blockedForIntegrityReasons": False,
            "mailServerBlacklistedTemporarily": False,
        }
    
    async def sign_in_by_mail_code(
        self,
        mail_login_token: str,
        received_code: str
    ) -> Dict[str, Any]:
        """Sign in with email and code.
        
        Args:
            mail_login_token: Mail login token.
            received_code: Verification code received by email.
            
        Returns:
            Mail auth token.
        """
        # Get the stored token
        token_data = await self.state.get_mail_login_token(mail_login_token)
        if not token_data:
            raise ValueError("Invalid or expired mail login token")
        
        # Verify the code
        stored_code = token_data.get("code")
        if stored_code != received_code:
            logger.warning(
                "Invalid verification code",
                extra={"token": mail_login_token[:8] + "..."}
            )
            raise ValueError("Invalid verification code")
        
        # Get mail address
        mail = token_data.get("mail")
        
        # Generate mail auth token
        mail_auth_token = self._generate_token()
        
        # Store the mail auth token (family_id will be set when family is created)
        await self.state.store_mail_auth_token(
            token=mail_auth_token,
            mail=mail,
            family_id="",  # Will be updated when family is created
        )
        
        # Delete the mail login token (one-time use)
        await self.state.delete_mail_login_token(mail_login_token)
        
        logger.info(
            "Signed in by mail code",
            extra={"mail": mail, "token": mail_auth_token[:8] + "..."}
        )
        
        return {
            "mailAuthToken": mail_auth_token,
        }
    
    async def get_status_by_mail_address(
        self,
        mail_auth_token: str
    ) -> Dict[str, Any]:
        """Get family status by mail address.
        
        Args:
            mail_auth_token: Mail authentication token.
            
        Returns:
            Family status.
        """
        # Verify mail auth token
        token_data = await self.state.get_mail_auth_token(mail_auth_token)
        if not token_data:
            raise ValueError("Invalid mail auth token")
        
        mail = token_data.get("mail")
        
        # Check if family exists
        family = await self.state.get_family_by_mail(mail)
        
        if family:
            status = "existing"
            can_create_family = False
        else:
            status = "new"
            can_create_family = True
        
        logger.info(
            "Got status by mail address",
            extra={"mail": mail, "status": status}
        )
        
        return {
            "mail": mail,
            "status": status,
            "canCreateFamily": can_create_family,
            "alwaysPro": False,
        }
    
    async def create_family(
        self,
        mail_auth_token: str,
        parent_password: Dict[str, Any],
        device_name: str = "Parent Device",
        device_model: str = "Pixel 7"
    ) -> Dict[str, Any]:
        """Create a new family.
        
        Args:
            mail_auth_token: Mail authentication token.
            parent_password: Parent password data (hash, secondHash, secondSalt, encrypted).
            device_name: Device name.
            device_model: Device model.
            
        Returns:
            Device auth token and server data.
        """
        # Verify mail auth token
        token_data = await self.state.get_mail_auth_token(mail_auth_token)
        if not token_data:
            raise ValueError("Invalid mail auth token")
        
        mail = token_data.get("mail")
        
        # Generate family ID
        family_id = f"family_{secrets.token_hex(8)}"
        
        # Generate parent user ID
        parent_id = f"user_{secrets.token_hex(8)}"
        
        # Generate device ID
        device_id = f"device_{secrets.token_hex(8)}"
        
        # Generate device auth token
        device_auth_token = secrets.token_urlsafe(32)
        
        # Store family
        await self.state.create_family(family_id, {
            "family_id": family_id,
            "mail": mail,
            "parent_id": parent_id,
            "parent_password_second_hash": parent_password.get("secondHash", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Store parent user
        await self.state.create_user(parent_id, {
            "id": parent_id,
            "name": f"Parent_{secrets.token_hex(4)}",
            "password": parent_password.get("hash", ""),
            "secondPasswordSalt": parent_password.get("secondSalt", ""),
            "type": "parent",
            "timeZone": "Europe/Amsterdam",
            "disableLimitsUntil": 0,
            "mail": mail,
            "currentDevice": device_id,
            "categoryForNotAssignedApps": "",
            "relaxPrimaryDevice": True,
            "flags": 0,
            "limitLoginCategory": None,
            "preBlockDuration": 0,
            "family_id": family_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Store device
        await self.state.create_device(device_id, {
            "deviceId": device_id,
            "name": device_name,
            "model": device_model,
            "addedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            "currentUserId": parent_id,
            "currentProtectionLevel": "none",
            "highestProtectionLevel": "none",
            "currentAppVersion": 1,
            "highestAppVersion": 1,
            "publicKey": "",
            "platformType": "android",
            "platformLevel": 30,
            "familyId": family_id,
        })
        
        # Store device auth token
        await self.state.store_device_auth_token(
            token=device_auth_token,
            device_id=device_id,
            family_id=family_id,
        )
        
        # Update mail auth token with family_id
        await self.state.store_mail_auth_token(
            token=mail_auth_token,
            mail=mail,
            family_id=family_id,
        )
        
        # Generate server data
        server_data = await self._generate_server_data(family_id)
        
        logger.info(
            "Family created",
            extra={"family_id": family_id, "mail": mail, "device_id": device_id}
        )
        
        return {
            "deviceAuthToken": device_auth_token,
            "ownDeviceId": device_id,
            "data": server_data,
        }
    
    async def sign_in_into_family(
        self,
        mail_auth_token: str,
        parent_password_second_hash: str,
        device_name: str = "Parent Device",
        device_model: str = "Pixel 7"
    ) -> Dict[str, Any]:
        """Sign in to an existing family.
        
        Args:
            mail_auth_token: Mail authentication token.
            parent_password_second_hash: Second password hash for verification.
            device_name: Device name.
            device_model: Device model.
            
        Returns:
            Device auth token and server data.
        """
        # Verify mail auth token
        token_data = await self.state.get_mail_auth_token(mail_auth_token)
        if not token_data:
            raise ValueError("Invalid mail auth token")
        
        mail = token_data.get("mail")
        family_id = token_data.get("family_id")
        
        if not family_id:
            raise ValueError("Family not found for this mail")
        
        # Get family
        family = await self.state.get_family(family_id)
        if not family:
            raise ValueError("Family not found")
        
        # Get parent user
        parent_id = family.get("parent_id")
        parent_user = await self.state.get_user(parent_id)
        if not parent_user:
            raise ValueError("Parent user not found")
        
        # Verify second password hash
        stored_second_hash = parent_user.get("password", "")
        if stored_second_hash != parent_password_second_hash:
            raise ValueError("Invalid password")
        
        # Generate device ID
        device_id = f"device_{secrets.token_hex(8)}"
        
        # Generate device auth token
        device_auth_token = secrets.token_urlsafe(32)
        
        # Store device
        await self.state.create_device(device_id, {
            "deviceId": device_id,
            "name": device_name,
            "model": device_model,
            "addedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            "currentUserId": parent_id,
            "currentProtectionLevel": "none",
            "highestProtectionLevel": "none",
            "currentAppVersion": 1,
            "highestAppVersion": 1,
            "publicKey": "",
            "platformType": "android",
            "platformLevel": 30,
            "familyId": family_id,
        })
        
        # Store device auth token
        await self.state.store_device_auth_token(
            token=device_auth_token,
            device_id=device_id,
            family_id=family_id,
        )
        
        # Generate server data
        server_data = await self._generate_server_data(family_id)
        
        logger.info(
            "Signed in to family",
            extra={"family_id": family_id, "mail": mail, "device_id": device_id}
        )
        
        return {
            "deviceAuthToken": device_auth_token,
            "ownDeviceId": device_id,
            "data": server_data,
        }
    
    async def recover_parent_password(
        self,
        mail_auth_token: str,
        new_password: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover parent password.
        
        Args:
            mail_auth_token: Mail authentication token.
            new_password: New password data (hash, secondHash, secondSalt, encrypted).
            
        Returns:
            Status.
        """
        # Verify mail auth token
        token_data = await self.state.get_mail_auth_token(mail_auth_token)
        if not token_data:
            raise ValueError("Invalid mail auth token")
        
        mail = token_data.get("mail")
        family_id = token_data.get("family_id")
        
        if not family_id:
            raise ValueError("Family not found for this mail")
        
        # Get parent user
        family = await self.state.get_family(family_id)
        if not family:
            raise ValueError("Family not found")
        
        parent_id = family.get("parent_id")
        
        # Update parent password
        await self.state.update_user(parent_id, {
            "password": new_password.get("hash", ""),
            "secondPasswordSalt": new_password.get("secondSalt", ""),
        })
        
        logger.info(
            "Parent password recovered",
            extra={"mail": mail, "family_id": family_id}
        )
        
        return {"status": "ok"}
    
    async def _generate_server_data(self, family_id: str) -> Dict[str, Any]:
        """Generate server data for a family.
        
        Args:
            family_id: Family ID.
            
        Returns:
            Server data dictionary.
        """
        # Get family
        family = await self.state.get_family(family_id)
        if not family:
            return {}
        
        # Get users
        users = await self.state.get_users_by_family(family_id)
        users_dict = {u.get("id"): u for u in users}
        
        # Get devices
        devices = await self.state.get_devices_by_family(family_id)
        devices_dict = {d.get("deviceId"): d for d in devices}
        
        # Get categories
        categories = list(self.state._categories.values())
        
        # Get apps
        apps = []
        for device in devices:
            device_apps = await self.state.get_apps(device.get("deviceId"))
            if device_apps:
                apps.append({
                    "deviceId": device.get("deviceId"),
                    "version": "1",
                    "apps": device_apps,
                })
        
        # Build server data
        server_data = {
            "devices": {
                "v": "",
                "data": devices_dict,
            },
            "devices2": devices,
            "apps": apps,
            "rmCategories": [],
            "categoryBase": categories,
            "categoryApp": [],
            "usedTimes": [],
            "rules": [],
            "tasks": [],
            "users": {
                "v": "",
                "data": users_dict,
            },
            "krq": [],
            "kr": [],
            "pings": [],
            "dh": {
                "v": "1",
                "k": "",
            },
            "u2f": {
                "v": "1",
                "d": [],
            },
            "fullVersion": 0,
            "message": "",
            "apiLevel": 1,
        }
        
        return server_data


# Global auth service instance
auth_service = AuthService()