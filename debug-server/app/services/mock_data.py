"""Mock data generation system for TimeLimit API.

This module provides a seed-based reproducible mock data generator
for testing the TimeLimit backend API.
"""

import hashlib
import json
import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.security import (
    calculate_hmac_sha256,
    generate_keypair,
    hash_password,
)

logger = logging.getLogger(__name__)


class MockDataGenerator:
    """Seed-based mock data generator for TimeLimit API.
    
    Generates reproducible mock data for families, users, devices,
    categories, apps, time limit rules, and crypto keys.
    """
    
    def __init__(self, seed: int = None):
        """Initialize the mock data generator.
        
        Args:
            seed: Random seed for reproducibility. Uses MOCK_DATA_SEED from config if not provided.
        """
        self.seed = seed or settings.MOCK_DATA_SEED
        self._random_state = self._init_random_state()
        self._generated_data: Dict[str, Any] = {}
        
    def _init_random_state(self) -> Dict[str, Any]:
        """Initialize deterministic random state from seed."""
        # Use seed to create deterministic random values
        seed_bytes = str(self.seed).encode()
        hash_obj = hashlib.sha256(seed_bytes)
        return {
            "hash": hash_obj.hexdigest(),
            "counter": 0,
        }
    
    def _random_string(self, length: int = 16) -> str:
        """Generate a deterministic random string."""
        self._random_state["counter"] += 1
        combined = f"{self._random_state['hash']}{self._random_state['counter']}"
        hash_obj = hashlib.sha256(combined.encode())
        chars = string.ascii_letters + string.digits
        return ''.join(chars[ord(hash_obj.hexdigest()[i]) % len(chars)] for i in range(length))
    
    def _random_uuid(self) -> str:
        """Generate a deterministic UUID-like string."""
        return self._random_string(8) + "-" + self._random_string(4) + "-" + self._random_string(4) + "-" + self._random_string(4) + "-" + self._random_string(12)
    
    def _random_int(self, min_val: int = 0, max_val: int = 1000) -> int:
        """Generate a deterministic random integer."""
        self._random_state["counter"] += 1
        combined = f"{self._random_state['hash']}{self._random_state['counter']}"
        hash_obj = hashlib.sha256(combined.encode())
        return min_val + (int(hash_obj.hexdigest(), 16) % (max_val - min_val + 1))
    
    def _random_choice(self, items: List[Any]) -> Any:
        """Make a deterministic random choice from a list."""
        if not items:
            return None
        self._random_state["counter"] += 1
        combined = f"{self._random_state['hash']}{self._random_state['counter']}"
        hash_obj = hashlib.sha256(combined.encode())
        index = int(hash_obj.hexdigest(), 16) % len(items)
        return items[index]
    
    def generate_family(self, family_id: str = None) -> Dict[str, Any]:
        """Generate a family with parent and child users.
        
        Args:
            family_id: Optional family ID. Generated if not provided.
            
        Returns:
            Family data dictionary.
        """
        family_id = family_id or self._random_uuid()
        parent_id = f"user_{self._random_string(8)}"
        child_ids = [f"user_{self._random_string(8)}" for _ in range(settings.MOCK_CHILD_COUNT)]
        
        # Generate parent password hash
        parent_password = "parent_password_123"
        parent_hash = hash_password(parent_password)
        parent_second_salt = self._random_string(16)
        parent_second_hash = hash_password(parent_password + parent_second_salt)
        
        family_data = {
            "family_id": family_id,
            "mail": f"parent_{self._random_string(6)}@example.com",
            "parent_id": parent_id,
            "child_ids": child_ids,
            "parent_password": {
                "hash": parent_hash,
                "secondHash": parent_second_hash,
                "secondSalt": parent_second_salt,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._generated_data[f"family_{family_id}"] = family_data
        logger.info("Generated family", extra={"family_id": family_id})
        return family_data
    
    def generate_user(self, user_id: str, family_id: str, user_type: str = "child") -> Dict[str, Any]:
        """Generate a user (parent or child).
        
        Args:
            user_id: User ID.
            family_id: Family ID.
            user_type: "parent" or "child".
            
        Returns:
            User data dictionary.
        """
        now = datetime.now(timezone.utc)
        
        user_data = {
            "id": user_id,
            "name": f"{user_type.capitalize()}_{self._random_string(6)}",
            "password": "",  # Empty for child users
            "secondPasswordSalt": self._random_string(16) if user_type == "parent" else "",
            "type": user_type,
            "timeZone": "Europe/Amsterdam",
            "disableLimitsUntil": 0,
            "mail": f"{user_id}@example.com" if user_type == "parent" else "",
            "currentDevice": "",
            "categoryForNotAssignedApps": f"cat_{self._random_string(8)}" if user_type == "child" else "",
            "relaxPrimaryDevice": True,
            "flags": 0,
            "limitLoginCategory": None,
            "preBlockDuration": 0,
            "family_id": family_id,
            "created_at": now.isoformat(),
        }
        
        self._generated_data[f"user_{user_id}"] = user_data
        logger.info("Generated user", extra={"user_id": user_id, "user_type": user_type})
        return user_data
    
    def generate_device(self, device_id: str, family_id: str, user_id: str = None) -> Dict[str, Any]:
        """Generate a device.
        
        Args:
            device_id: Device ID.
            family_id: Family ID.
            user_id: Current user ID on this device.
            
        Returns:
            Device data dictionary.
        """
        # Generate Curve25519 key pair
        public_key, private_key = generate_keypair()
        
        device_data = {
            "deviceId": device_id,
            "name": f"Device_{self._random_string(6)}",
            "model": self._random_choice(["Pixel 7", "Samsung Galaxy S23", "OnePlus 11", "Xiaomi 13"]),
            "addedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            "currentUserId": user_id or f"user_{self._random_string(8)}",
            "currentProtectionLevel": "none",
            "highestProtectionLevel": "none",
            "currentAppVersion": self._random_int(1, 100),
            "highestAppVersion": self._random_int(1, 100),
            "publicKey": public_key,
            "privateKey": private_key,
            "platformType": "android",
            "platformLevel": self._random_choice([29, 30, 31, 32, 33, 34]),
            "familyId": family_id,
        }
        
        self._generated_data[f"device_{device_id}"] = device_data
        logger.info("Generated device", extra={"device_id": device_id})
        return device_data
    
    def generate_category(self, category_id: str, child_id: str, parent_category_id: str = None) -> Dict[str, Any]:
        """Generate a category.
        
        Args:
            category_id: Category ID.
            child_id: Child user ID this category belongs to.
            parent_category_id: Optional parent category ID.
            
        Returns:
            Category data dictionary.
        """
        titles = ["Games", "Social Media", "Work", "Education", "Entertainment", "Shopping", "News", "Music"]
        
        category_data = {
            "categoryId": category_id,
            "childId": child_id,
            "title": self._random_choice(titles),
            "blockedTimes": "0",
            "extraTime": 0,
            "extraTimeDay": 0,
            "tempBlocked": False,
            "tempBlockTime": 0,
            "version": "1",
            "parentCategoryId": parent_category_id,
            "blockAllNotifications": False,
            "timeWarnings": 0,
            "sort": self._random_int(0, 100),
            "networks": [],
            "flags": 0,
            "blockNotificationDelay": 0,
            "atw": [0, 0, 0, 0, 0, 0, 0],
        }
        
        self._generated_data[f"category_{category_id}"] = category_data
        logger.info("Generated category", extra={"category_id": category_id})
        return category_data
    
    def generate_apps(self, device_id: str, count: int = None) -> List[str]:
        """Generate installed apps for a device.
        
        Args:
            device_id: Device ID.
            count: Number of apps to generate.
            
        Returns:
            List of app package names.
        """
        count = count or settings.MOCK_APP_COUNT
        app_categories = [
            "com.android.chrome",
            "com.facebook.katana",
            "com.google.android.youtube",
            "com.instagram.android",
            "com.twitter.android",
            "com.tiktok.android",
            "com.snapchat.android",
            "com.netflix.mediaclient",
            "com.amazon.amazonVideo.livingRoom",
            "com.hulu.plus",
            "com.disney.disneyplus",
            "com.google.android.apps.maps",
            "com.google.android.apps.photos",
            "com.spotify.music.android",
            "com.discord",
            "com.reddit.frontpage",
            "com.pinterest.client",
            "com.lyft.android",
            "com UberTechnologies.Uber",
            "com.grubhub",
            "com.netflix.mediaclient",
            "com.hulu.plus",
            "com.disney.disneyplus",
            "com.amazon.amazonVideo.livingRoom",
            "com.google.android.apps.docs",
            "com.google.android.apps.drive",
            "com.microsoft.office.outlook",
            "com.microsoft.android.teamviewer",
            "com.slack",
            "com.zoom.videomeetings",
            "com.dropbox.android",
            "com.canva.canva.editor",
            "com.adobe.reader",
            "com.google.android.apps.books",
            "com.google.android.apps.movies",
            "com.google.android.apps.tickets",
            "com.google.android.apps.transit",
            "com.google.android.apps.bard",
            "com.google.android.apps.photos",
        ]
        
        apps = [self._random_choice(app_categories) for _ in range(count)]
        # Remove duplicates while preserving order
        seen = set()
        unique_apps = []
        for app in apps:
            if app not in seen:
                seen.add(app)
                unique_apps.append(app)
        
        self._generated_data[f"apps_{device_id}"] = unique_apps
        return unique_apps
    
    def generate_time_limit_rule(self, category_id: str, day: int = None) -> Dict[str, Any]:
        """Generate a time limit rule.
        
        Args:
            category_id: Category ID.
            day: Day of week (0-6). Random if not provided.
            
        Returns:
            Time limit rule dictionary.
        """
        day = day if day is not None else self._random_int(0, 6)
        
        # Generate random start time (between 00:00 and 20:00)
        start_hour = self._random_int(0, 20)
        start_minute = self._random_int(0, 59)
        start_time = (start_hour * 3600 + start_minute * 60) * 1000  # in milliseconds
        
        # Generate random duration (1-4 hours)
        duration_hours = self._random_int(1, 4)
        end_time = start_time + (duration_hours * 3600 * 1000)
        
        rule = {
            "categoryId": category_id,
            "day": day,
            "startTime": start_time,
            "endTime": end_time,
            "maxTime": duration_hours * 3600 * 1000,
        }
        
        self._generated_data[f"rule_{category_id}_{day}"] = rule
        return rule
    
    def generate_used_time(self, category_id: str, date: str = None) -> Dict[str, Any]:
        """Generate used time item.
        
        Args:
            category_id: Category ID.
            date: Date string. Random if not provided.
            
        Returns:
            Used time dictionary.
        """
        if date is None:
            now = datetime.now(timezone.utc)
            date = now.strftime("%Y-%m-%d")
        
        # Generate random used time (0-8 hours)
        used_time = self._random_int(0, 8 * 3600 * 1000)
        
        used_time_data = {
            "categoryId": category_id,
            "usedTime": used_time,
            "date": date,
        }
        
        self._generated_data[f"used_time_{category_id}_{date}"] = used_time_data
        return used_time_data
    
    def generate_child_task(self, category_id: str, task_id: str = None) -> Dict[str, Any]:
        """Generate a child task.
        
        Args:
            category_id: Category ID.
            task_id: Task ID. Random if not provided.
            
        Returns:
            Child task dictionary.
        """
        task_id = task_id or f"task_{self._random_string(8)}"
        
        task_titles = [
            "Complete homework",
            "Read a book",
            "Practice piano",
            "Clean room",
            "Do chores",
            "Exercise",
            "Learn new skill",
            "Help with dinner",
        ]
        
        task = {
            "categoryId": category_id,
            "taskId": task_id,
            "title": self._random_choice(task_titles),
            "description": f"Task {task_id} for category {category_id}",
            "completed": self._random_choice([True, False]),
        }
        
        self._generated_data[f"task_{task_id}"] = task
        return task
    
    def generate_dh_key(self) -> Dict[str, str]:
        """Generate a DH key for password encryption.
        
        Returns:
            DH key dictionary with version and public key.
        """
        # Generate a simple DH key representation
        # In production, this would use actual ECDH
        key = {
            "v": "1",
            "k": self._random_string(32),  # Simulated public key
        }
        
        self._generated_data["dh_key"] = key
        return key
    
    def generate_u2f_data(self) -> Dict[str, Any]:
        """Generate U2F data for a device.
        
        Returns:
            U2F data dictionary.
        """
        u2f_data = {
            "v": "1",
            "d": [
                {
                    "deviceId": f"device_{self._random_string(8)}",
                    "keyHandle": self._random_string(64),
                    "publicKey": self._random_string(64),
                }
            ],
        }
        
        self._generated_data["u2f_data"] = u2f_data
        return u2f_data
    
    def generate_full_version(self) -> int:
        """Generate a full version (premium) expiration timestamp.
        
        Returns:
            Timestamp in milliseconds (1 year from now if premium, 0 if not).
        """
        # 50% chance of having full version
        if self._random_choice([True, False]):
            # 1 year from now
            expiry = int(datetime.now(timezone.utc).timestamp() * 1000) + (365 * 24 * 3600 * 1000)
            self._generated_data["full_version"] = expiry
            return expiry
        else:
            self._generated_data["full_version"] = 0
            return 0
    
    def generate_family_data(self) -> Dict[str, Any]:
        """Generate complete family data for ServerDataStatus.
        
        Returns:
            Complete family data dictionary.
        """
        # Define app categories list (used for category app assignments)
        app_categories = [
            "com.android.chrome",
            "com.facebook.katana",
            "com.google.android.youtube",
            "com.instagram.android",
            "com.twitter.android",
            "com.tiktok.android",
            "com.snapchat.android",
            "com.netflix.mediaclient",
            "com.amazon.amazonVideo.livingRoom",
            "com.hulu.plus",
            "com.disney.disneyplus",
            "com.google.android.apps.maps",
            "com.google.android.apps.photos",
            "com.spotify.music.android",
            "com.discord",
            "com.reddit.frontpage",
            "com.pinterest.client",
            "com.lyft.android",
            "com.UberTechnologies.Uber",
            "com.grubhub",
        ]
        
        # Generate family
        family = self.generate_family()
        family_id = family["family_id"]
        parent_id = family["parent_id"]
        child_ids = family["child_ids"]
        
        # Generate devices
        devices = []
        device_ids = []
        
        # Parent device
        parent_device_id = f"device_{self._random_string(8)}"
        device_ids.append(parent_device_id)
        parent_device = self.generate_device(parent_device_id, family_id, parent_id)
        devices.append(parent_device)
        
        # Child devices
        for child_id in child_ids:
            for _ in range(settings.MOCK_DEVICE_COUNT):
                device_id = f"device_{self._random_string(8)}"
                device_ids.append(device_id)
                device = self.generate_device(device_id, family_id, child_id)
                devices.append(device)
        
        # Generate users
        users = {}
        users[parent_id] = self.generate_user(parent_id, family_id, "parent")
        for child_id in child_ids:
            users[child_id] = self.generate_user(child_id, family_id, "child")
        
        # Generate categories
        categories = []
        category_ids = []
        for child_id in child_ids:
            for _ in range(settings.MOCK_CATEGORY_COUNT):
                category_id = f"cat_{self._random_string(8)}"
                category_ids.append(category_id)
                category = self.generate_category(category_id, child_id)
                categories.append(category)
        
        # Generate apps per device
        apps = []
        for device in devices:
            device_apps = self.generate_apps(device["deviceId"])
            apps.append({
                "deviceId": device["deviceId"],
                "version": "1",
                "apps": device_apps,
            })
        
        # Generate category app assignments
        category_apps = []
        for category_id in category_ids:
            assigned_apps = [self._random_choice(app_categories) for _ in range(self._random_int(1, 5))]
            category_apps.append({
                "categoryId": category_id,
                "apps": assigned_apps,
                "version": "1",
            })
        
        # Generate used times
        used_times = []
        for category_id in category_ids:
            used_times.append(self.generate_used_time(category_id))
        
        # Generate rules
        rules = []
        for category_id in category_ids:
            for day in range(7):
                if self._random_choice([True, False]):
                    rules.append(self.generate_time_limit_rule(category_id, day))
        
        # Generate tasks
        tasks = []
        for category_id in category_ids:
            for _ in range(self._random_int(1, 3)):
                tasks.append(self.generate_child_task(category_id))
        
        # Generate DH key and U2F data
        dh_key = self.generate_dh_key()
        u2f_data = self.generate_u2f_data()
        
        # Generate full version
        full_version = self.generate_full_version()
        
        # Build ServerDataStatus
        server_data = {
            "devices": {
                "v": "1",
                "data": {d["deviceId"]: d for d in devices},
            },
            "devices2": devices,
            "apps": apps,
            "rmCategories": [],
            "categoryBase": categories,
            "categoryApp": category_apps,
            "usedTimes": used_times,
            "rules": rules,
            "tasks": tasks,
            "users": {
                "v": "1",
                "data": users,
            },
            "krq": [],
            "kr": [],
            "pings": [],
            "dh": dh_key,
            "u2f": u2f_data,
            "fullVersion": full_version,
            "message": "",
            "apiLevel": 1,
        }
        
        return server_data
    
    # ========================================================================
    # ID Generation Methods (for tests)
    # ========================================================================
    
    def generate_device_id(self) -> str:
        """Generate a device ID string.
        
        Returns:
            Device ID string.
        """
        return f"device_{self._random_string(8)}"
    
    def generate_user_id(self) -> str:
        """Generate a user ID string.
        
        Returns:
            User ID string.
        """
        return f"user_{self._random_string(8)}"
    
    def generate_category_id(self) -> str:
        """Generate a category ID string.
        
        Returns:
            Category ID string.
        """
        return f"cat_{self._random_string(8)}"
    
    def generate_action_id(self) -> str:
        """Generate an action ID string.
        
        Returns:
            Action ID string.
        """
        return f"action_{self._random_string(8)}"
    
    # ========================================================================
    # Data Generation Methods (for tests)
    # ========================================================================
    
    def generate_device_data(self) -> Dict[str, Any]:
        """Generate device data dictionary.
        
        Returns:
            Device data dictionary with deviceId, deviceName, deviceModel.
        """
        device_id = self.generate_device_id()
        device_data = {
            "deviceId": device_id,
            "deviceName": f"Device_{self._random_string(6)}",
            "deviceModel": self._random_choice(["Pixel 7", "Samsung Galaxy S23", "OnePlus 11", "Xiaomi 13"]),
        }
        self._generated_data[f"device_data_{device_id}"] = device_data
        return device_data
    
    def generate_user_data(self) -> Dict[str, Any]:
        """Generate user data dictionary.
        
        Returns:
            User data dictionary with userId, userName.
        """
        user_id = self.generate_user_id()
        user_data = {
            "userId": user_id,
            "userName": f"User_{self._random_string(6)}",
        }
        self._generated_data[f"user_data_{user_id}"] = user_data
        return user_data
    
    def generate_category_data(self) -> Dict[str, Any]:
        """Generate category data dictionary.
        
        Returns:
            Category data dictionary with categoryId, title.
        """
        category_id = self.generate_category_id()
        category_data = {
            "categoryId": category_id,
            "title": self._random_choice(["Games", "Social Media", "Work", "Education", "Entertainment", "Shopping", "News", "Music"]),
        }
        self._generated_data[f"category_data_{category_id}"] = category_data
        return category_data
    
    def generate_app_data(self) -> Dict[str, Any]:
        """Generate app data dictionary.
        
        Returns:
            App data dictionary with packageName, appName.
        """
        package_names = [
            "com.android.chrome",
            "com.facebook.katana",
            "com.google.android.youtube",
            "com.instagram.android",
            "com.twitter.android",
            "com.tiktok.android",
            "com.snapchat.android",
            "com.netflix.mediaclient",
        ]
        package_name = self._random_choice(package_names)
        app_names = {
            "com.android.chrome": "Chrome",
            "com.facebook.katana": "Facebook",
            "com.google.android.youtube": "YouTube",
            "com.instagram.android": "Instagram",
            "com.twitter.android": "Twitter",
            "com.tiktok.android": "TikTok",
            "com.snapchat.android": "Snapchat",
            "com.netflix.mediaclient": "Netflix",
        }
        app_data = {
            "packageName": package_name,
            "appName": app_names.get(package_name, "Unknown App"),
        }
        self._generated_data[f"app_data_{package_name}"] = app_data
        return app_data
    
    def generate_sync_action(
        self,
        action_type: str = "AddCategoryAction",
        user_id: str = None,
        category_id: str = None,
        title: str = None,
        child_id: str = None
    ) -> Dict[str, Any]:
        """Generate a sync action.
        
        Args:
            action_type: Type of action to generate.
            user_id: User ID for the action. Generated if not provided.
            category_id: Category ID for the action. Generated if not provided.
            title: Title for the action (for AddCategoryAction).
            child_id: Child ID for the action (for AddCategoryAction).
            
        Returns:
            Sync action dictionary.
        """
        if user_id is None:
            user_id = self.generate_user_id()
        if category_id is None:
            category_id = self.generate_category_id()
        if title is None:
            title = self._random_choice(["Games", "Social Media", "Work", "Education", "Entertainment"])
        if child_id is None:
            child_id = self.generate_user_id()
        
        action = {
            "type": action_type,
            "sequenceNumber": self._random_int(1, 10000),
            "integrity": f"password:base64{self._random_string(16)}",
            "userId": user_id,
            "encodedAction": f'{{"categoryId":"{category_id}","title":"{title}","childId":"{child_id}"}}'
        }
        
        self._generated_data[f"action_{action_type}_{action['sequenceNumber']}"] = action
        return action
    
    def generate_actions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate multiple sync actions.
        
        Args:
            count: Number of actions to generate.
            
        Returns:
            List of sync action dictionaries.
        """
        actions = []
        for i in range(count):
            action = self.generate_sync_action(
                action_type=self._random_choice([
                    "AddCategoryAction",
                    "UpdateCategoryAction",
                    "DeleteCategoryAction",
                    "AddUsedTimeAction",
                    "AddRuleAction",
                    "DeleteRuleAction",
                    "SetAppsAction"
                ]),
                user_id=f"user_{self._random_string(8)}"
            )
            actions.append(action)
        return actions
    
    # ========================================================================
    # Token Data Generation Methods (for tests)
    # ========================================================================
    
    def generate_device_auth_token_data(self) -> Dict[str, Any]:
        """Generate device auth token data.
        
        Returns:
            Token data dictionary with token, familyId, deviceId.
        """
        token = f"device_token_{self._random_string(16)}"
        token_data = {
            "token": token,
            "familyId": f"family_{self._random_string(8)}",
            "deviceId": f"device_{self._random_string(8)}",
        }
        self._generated_data[f"device_auth_token_{token}"] = token_data
        return token_data
    
    def generate_add_device_token_data(self) -> Dict[str, Any]:
        """Generate add-device token data.
        
        Returns:
            Token data dictionary with token, deviceId, parentId.
        """
        token = f"add_device_token_{self._random_string(16)}"
        token_data = {
            "token": token,
            "deviceId": f"device_{self._random_string(8)}",
            "parentId": f"parent_{self._random_string(8)}",
        }
        self._generated_data[f"add_device_token_{token}"] = token_data
        return token_data
    
    def generate_mail_login_token_data(self) -> Dict[str, Any]:
        """Generate mail login token data.
        
        Returns:
            Token data dictionary with token, mail.
        """
        token = f"mail_login_token_{self._random_string(16)}"
        token_data = {
            "token": token,
            "mail": f"user_{self._random_string(6)}@example.com",
        }
        self._generated_data[f"mail_login_token_{token}"] = token_data
        return token_data
    
    def generate_mail_auth_token_data(self) -> Dict[str, Any]:
        """Generate mail auth token data.
        
        Returns:
            Token data dictionary with token, mailLoginToken.
        """
        token = f"mail_auth_token_{self._random_string(16)}"
        token_data = {
            "token": token,
            "mailLoginToken": f"mail_login_token_{self._random_string(16)}",
        }
        self._generated_data[f"mail_auth_token_{token}"] = token_data
        return token_data
    
    # ========================================================================
    # Sync Status Generation Methods (for tests)
    # ========================================================================
    
    def generate_sync_status(self) -> Dict[str, Any]:
        """Generate sync status dictionary.
        
        Returns:
            Sync status dictionary with clientLevel, devices, users, apps.
        """
        status = {
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
        self._generated_data["sync_status"] = status
        return status
    
    def generate_server_data_status(self) -> Dict[str, Any]:
        """Generate server data status dictionary.
        
        Returns:
            Server data status dictionary.
        """
        return self.generate_family_data()
    
    def get_generated_data(self) -> Dict[str, Any]:
        """Get all generated data.
        
        Returns:
            Dictionary of all generated data.
        """
        return self._generated_data.copy()
    
    def reset(self) -> None:
        """Reset the generator state."""
        self._random_state = self._init_random_state()
        self._generated_data.clear()
        logger.info("Mock data generator reset")


# Global mock data generator instance
mock_data_generator = MockDataGenerator()