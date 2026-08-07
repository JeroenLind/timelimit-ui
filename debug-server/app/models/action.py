"""Action data models for TimeLimit sync protocol."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActionType:
    """Action type constants for sync protocol."""
    
    ADD_CATEGORY = "AddCategoryAction"
    UPDATE_CATEGORY = "UpdateCategoryAction"
    DELETE_CATEGORY = "DeleteCategoryAction"
    ADD_CATEGORY_APP = "AddCategoryAppAction"
    REMOVE_CATEGORY_APP = "RemoveCategoryAppAction"
    ADD_USED_TIME = "AddUsedTimeAction"
    UPDATE_USED_TIME = "UpdateUsedTimeAction"
    ADD_RULE = "AddRuleAction"
    UPDATE_RULE = "UpdateRuleAction"
    DELETE_RULE = "DeleteRuleAction"
    ADD_TASK = "AddTaskAction"
    UPDATE_TASK = "UpdateTaskAction"
    DELETE_TASK = "DeleteTaskAction"
    ADD_DEVICE = "AddDeviceAction"
    UPDATE_DEVICE = "UpdateDeviceAction"
    DELETE_DEVICE = "DeleteDeviceAction"
    ADD_USER = "AddUserAction"
    UPDATE_USER = "UpdateUserAction"
    DELETE_USER = "DeleteUserAction"
    SET_APPS = "SetAppsAction"
    ADD_PING = "AddPingAction"
    REMOVE_PING = "RemovePingAction"
    ADD_KEY_REQUEST = "AddKeyRequestAction"
    ADD_KEY_RESPONSE = "AddKeyResponseAction"
    SET_FULL_VERSION = "SetFullVersionAction"


class SyncAction(BaseModel):
    """Base sync action model.
    
    Represents a single action in the sync protocol.
    Actions are serialized as JSON and contain all the information
    needed to apply a change to the local state.
    """
    
    type: str = Field(..., description="Action type string")
    sequenceNumber: int = Field(..., description="Unique sequence number (prevents duplicates)")
    integrity: str = Field(..., description="Integrity hash (HMAC-SHA256: 'password:' + base64(hmac))")
    userId: str = Field(..., description="User ID associated with the action")
    encodedAction: str = Field(..., description="JSON string of the action data")


class AddCategoryAction(BaseModel):
    """Action to add a new category."""
    
    categoryId: str = Field(..., description="Category ID")
    title: str = Field(..., description="Category title")
    childId: str = Field(..., description="Child user ID")
    parentCategoryId: Optional[str] = Field(None, description="Parent category ID")


class UpdateCategoryAction(BaseModel):
    """Action to update an existing category."""
    
    categoryId: str = Field(..., description="Category ID")
    title: Optional[str] = Field(None, description="Updated title")
    tempBlocked: Optional[bool] = Field(None, description="Updated temp blocked status")
    tempBlockTime: Optional[int] = Field(None, description="Updated temp block time")


class DeleteCategoryAction(BaseModel):
    """Action to delete a category."""
    
    categoryId: str = Field(..., description="Category ID to delete")


class AddCategoryAppAction(BaseModel):
    """Action to add apps to a category."""
    
    categoryId: str = Field(..., description="Category ID")
    apps: list = Field(..., description="List of app package names to add")


class RemoveCategoryAppAction(BaseModel):
    """Action to remove apps from a category."""
    
    categoryId: str = Field(..., description="Category ID")
    apps: list = Field(..., description="List of app package names to remove")


class AddUsedTimeAction(BaseModel):
    """Action to add used time for a category."""
    
    categoryId: str = Field(..., description="Category ID")
    usedTime: int = Field(..., description="Used time in milliseconds")
    date: str = Field(..., description="Date string (e.g., '2024-01-15')")


class AddRuleAction(BaseModel):
    """Action to add a time limit rule."""
    
    categoryId: str = Field(..., description="Category ID")
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6)")
    startTime: int = Field(..., description="Start time in milliseconds")
    endTime: int = Field(..., description="End time in milliseconds")
    maxTime: int = Field(..., description="Maximum time in milliseconds")


class DeleteRuleAction(BaseModel):
    """Action to delete a time limit rule."""
    
    categoryId: str = Field(..., description="Category ID")
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6)")


class TimeLimitRule(BaseModel):
    """Time limit rule model.
    
    Represents a time limit rule for a category.
    """
    
    categoryId: str = Field(..., description="Category identifier")
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6, 0=Sunday)")
    startTime: int = Field(..., description="Start time in milliseconds")
    endTime: int = Field(..., description="End time in milliseconds")
    maxTime: int = Field(..., description="Maximum allowed time in milliseconds")


class AddTaskAction(BaseModel):
    """Action to add a child task."""
    
    categoryId: str = Field(..., description="Category ID")
    taskId: str = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    completed: bool = Field(default=False, description="Completed status")


class DeleteTaskAction(BaseModel):
    """Action to delete a child task."""
    
    categoryId: str = Field(..., description="Category ID")
    taskId: str = Field(..., description="Task ID to delete")


class SetAppsAction(BaseModel):
    """Action to set installed apps for a device."""
    
    deviceId: str = Field(..., description="Device ID")
    apps: list = Field(..., description="List of app package names")


class AddPingAction(BaseModel):
    """Action to add a ping for primary device borrowing."""
    
    deviceId: str = Field(..., description="Device ID that sent the ping")
    token: str = Field(..., description="Ping token")
    timestamp: int = Field(..., description="Ping timestamp")


class DeletePingAction(BaseModel):
    """Action to remove a ping."""
    
    deviceId: str = Field(..., description="Device ID")
    token: str = Field(..., description="Ping token to remove")


class AddKeyRequestAction(BaseModel):
    """Action to add a key request for encrypted app lists."""
    
    deviceId: str = Field(..., description="Requesting device ID")
    tempKey: str = Field(..., description="Temporary Curve25519 key (base64)")
    signature: str = Field(..., description="Signature of the request")
    categoryId: str = Field(..., description="Category ID for the key request")
    type: str = Field(..., description="Key request type")
    sequenceNumber: int = Field(..., description="Server sequence number")


class AddKeyResponseAction(BaseModel):
    """Action to add a key response for encrypted app lists."""
    
    deviceId: str = Field(..., description="Responding device ID")
    tempKey: str = Field(..., description="Temporary Curve25519 key (base64)")
    encryptedKey: str = Field(..., description="Encrypted generation key")
    signature: str = Field(..., description="Signature of the response")
    sequenceNumber: int = Field(..., description="Server sequence number")


class SetFullVersionAction(BaseModel):
    """Action to set full version (premium) expiration."""
    
    fullVersionUntil: int = Field(..., description="Timestamp when full version expires")