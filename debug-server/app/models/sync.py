"""Sync request and response models for TimeLimit API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Action Upload Models
# ============================================================================

class ActionUploadItem(BaseModel):
    """Model for a single sync action item.
    
    An action uploaded to the server via POST /sync/push-actions.
    Actions are serialized as JSON and contain all the information
    needed to apply a change to the local state.
    """
    
    encodedAction: str = Field(..., description="JSON string of the action")
    sequenceNumber: int = Field(..., description="Unique sequence number (prevents duplicates)")
    integrity: str = Field(..., description="Integrity hash (HMAC-SHA256: 'password:' + base64(hmac))")
    type: str = Field(..., description="Action type string (e.g., 'AddCategoryAppAction')")
    userId: str = Field(..., description="User ID associated with the action")


class ActionUploadRequest(BaseModel):
    """Request model for push-actions endpoint."""
    
    deviceAuthToken: str = Field(..., description="Device authentication token")
    actions: List[ActionUploadItem] = Field(..., description="List of actions to push (batch of 25)")


class ActionUploadResponse(BaseModel):
    """Response model for push-actions endpoint.
    
    Response to POST /sync/push-actions.
    """
    
    status: str = Field(default="ok", description="Status of the operation")
    shouldDoFullSync: bool = Field(..., description="If true, client should wipe version numbers and do a full sync")


# ============================================================================
# Client Data Status Models
# ============================================================================

class ClientDataStatus(BaseModel):
    """Model for client sync status.
    
    The client's sync state sent to the server in POST /sync/pull-status.
    Contains version numbers for each entity type, allowing the server
    to return only changed data.
    """
    
    clientLevel: int = Field(default=7, description="Client protocol version (current: 7)")
    devices: str = Field(default="", description="Device list version")
    users: str = Field(default="", description="User list version")
    apps: Dict[str, str] = Field(default_factory=dict, description="Per-device installed apps version")
    devicesDetail: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="Per-device app base/diff versions")
    categories: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="Per-category version numbers")
    kri: int = Field(default=0, description="Last processed key request server sequence")
    kr: int = Field(default=0, description="Last processed key response server sequence")
    dh: str = Field(default="", description="DH key version")
    u2f: str = Field(default="", description="U2F data version")


# ============================================================================
# Server Data Status Models
# ============================================================================

class ServerDeviceData(BaseModel):
    """Device data within ServerDataStatus.devices.data[]."""
    
    deviceId: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Human-readable device name")
    model: str = Field(..., description="Device model")
    addedAt: int = Field(..., description="Timestamp when device was added")
    currentUserId: str = Field(..., description="ID of current user on this device")
    currentProtectionLevel: str = Field(..., description="Current protection level")
    highestProtectionLevel: str = Field(..., description="Highest achieved protection level")
    currentAppVersion: int = Field(..., description="Current app version code")
    highestAppVersion: int = Field(..., description="Highest app version code")
    publicKey: Optional[str] = Field(None, description="Curve25519 public key (base64)")
    platformType: Optional[str] = Field(None, description="Platform type (e.g., 'android')")
    platformLevel: Optional[int] = Field(None, description="Platform API level")


class ServerUserData(BaseModel):
    """User data within ServerDataStatus.users.data[]."""
    
    id: str = Field(..., description="UUID (client-generated)")
    name: str = Field(..., description="Display name")
    password: str = Field(..., description="bcrypt hash (empty if not set)")
    secondPasswordSalt: str = Field(..., description="Salt for second password hash")
    type: str = Field(..., description="'parent' or 'child'")
    timeZone: str = Field(..., description="IANA timezone ID")
    disableLimitsUntil: int = Field(default=0, description="Timestamp (0 = limits enabled)")
    mail: str = Field(..., description="Email address (for parent accounts)")
    currentDevice: str = Field(..., description="ID of current/primary device")
    categoryForNotAssignedApps: Optional[str] = Field(None, description="Category for apps not assigned to any category")
    relaxPrimaryDevice: bool = Field(default=True, description="If true, limits relaxed when connected and premium")
    flags: int = Field(default=0, description="Bitmask")
    limitLoginCategory: Optional[str] = Field(None, description="Category ID for login limits")
    preBlockDuration: int = Field(default=0, description="Pre-block duration in milliseconds")


class ServerUpdatedCategoryBaseData(BaseModel):
    """Category base data within ServerDataStatus.categoryBase[]."""
    
    categoryId: str = Field(..., description="Unique category identifier")
    childId: str = Field(..., description="User ID this category belongs to")
    title: str = Field(..., description="Category title")
    blockedTimes: str = Field(default="0", description="Bitmask string for blocked times")
    extraTime: int = Field(default=0, description="Extra time in milliseconds")
    extraTimeDay: int = Field(default=0, description="Extra time day")
    tempBlocked: bool = Field(default=False, description="If category is temporarily blocked")
    tempBlockTime: int = Field(default=0, description="Temporary block expiration timestamp")
    version: str = Field(default="1", description="Base data version")
    parentCategoryId: Optional[str] = Field(None, description="Parent category ID")
    blockAllNotifications: bool = Field(default=False, description="If true, block all notifications")
    timeWarnings: int = Field(default=0, description="Time warning settings")
    sort: int = Field(default=0, description="Sort order")
    networks: List[str] = Field(default_factory=list, description="Network restrictions")
    flags: int = Field(default=0, description="Category flags bitmask")
    blockNotificationDelay: int = Field(default=0, description="Notification block delay")
    atw: List[int] = Field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0], description="Allowed time windows (7-element array)")


class ServerUpdatedCategoryAssignedApps(BaseModel):
    """Category app assignments within ServerDataStatus.categoryApp[]."""
    
    categoryId: str = Field(..., description="Category identifier")
    apps: List[str] = Field(default_factory=list, description="List of app package names assigned to this category")
    version: str = Field(default="1", description="Assigned apps version")


class ServerUpdatedCategoryUsedTimes(BaseModel):
    """Used time items within ServerDataStatus.usedTimes[]."""
    
    categoryId: str = Field(..., description="Category identifier")
    usedTime: int = Field(..., description="Used time in milliseconds")
    date: str = Field(..., description="Date string (e.g., '2024-01-15')")


class ServerUpdatedTimeLimitRules(BaseModel):
    """Time limit rules within ServerDataStatus.rules[]."""
    
    categoryId: str = Field(..., description="Category identifier")
    day: int = Field(..., description="Day of week (0-6, 0=Sunday)")
    startTime: int = Field(..., description="Start time in milliseconds")
    endTime: int = Field(..., description="End time in milliseconds")
    maxTime: int = Field(..., description="Maximum allowed time in milliseconds")


class ServerUpdatedCategoryTasks(BaseModel):
    """Child tasks within ServerDataStatus.tasks[]."""
    
    categoryId: str = Field(..., description="Category identifier")
    taskId: str = Field(..., description="Task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    completed: bool = Field(default=False, description="If task is completed")


class ServerInstalledAppsData(BaseModel):
    """Installed apps per device within ServerDataStatus.apps[]."""
    
    deviceId: str = Field(..., description="Device identifier")
    version: str = Field(..., description="Installed apps version")
    apps: List[str] = Field(default_factory=list, description="List of installed app package names")


class ServerCryptContainer(BaseModel):
    """Encrypted data container for app lists."""
    
    version: str = Field(..., description="Crypt container version")
    data: str = Field(..., description="Base64 encoded encrypted data")


class ServerDhKey(BaseModel):
    """DH key for password encryption within ServerDataStatus.dh."""
    
    v: str = Field(..., description="Key version string")
    k: str = Field(..., description="Base64 encoded EC public key (secp256r1)")


class ServerU2fDataEntry(BaseModel):
    """U2F data entry within ServerDataStatus.u2f.d[]."""
    
    deviceId: str = Field(..., description="Device identifier")
    keyHandle: str = Field(..., description="U2F key handle")
    publicKey: str = Field(..., description="U2F public key")


class ServerU2fData(BaseModel):
    """U2F data within ServerDataStatus.u2f."""
    
    v: str = Field(..., description="U2F data version")
    d: List[ServerU2fDataEntry] = Field(default_factory=list, description="List of U2F key handles and public keys")


class Ping(BaseModel):
    """Ping/pong messages for primary device borrowing within ServerDataStatus.pings[]."""
    
    deviceId: str = Field(..., description="Device that sent the ping")
    token: str = Field(..., description="Ping token")
    timestamp: int = Field(..., description="Ping timestamp")


class KeyRequest(BaseModel):
    """Pending key requests within ServerDataStatus.krq[]."""
    
    deviceId: str = Field(..., description="Requesting device ID")
    tempKey: str = Field(..., description="Temporary Curve25519 key")
    signature: str = Field(..., description="Signature of the request")
    categoryId: str = Field(..., description="Category ID for the key request")
    type: str = Field(..., description="Key request type")
    sequenceNumber: int = Field(..., description="Server sequence number")


class KeyResponse(BaseModel):
    """Key responses within ServerDataStatus.kr[]."""
    
    deviceId: str = Field(..., description="Responding device ID")
    tempKey: str = Field(..., description="Temporary Curve25519 key")
    encryptedKey: str = Field(..., description="Encrypted generation key")
    signature: str = Field(..., description="Signature of the response")
    sequenceNumber: int = Field(..., description="Server sequence number")


class ServerDataStatus(BaseModel):
    """Server's response to POST /sync/pull-status.
    
    Contains the complete family state that the client needs to synchronize.
    """
    
    devices: Dict[str, Any] = Field(..., description="Full device list with version")
    devices2: List[Dict[str, Any]] = Field(default_factory=list, description="Extended device data")
    apps: List[Dict[str, Any]] = Field(default_factory=list, description="Installed apps per device")
    rmCategories: List[str] = Field(default_factory=list, description="List of removed category IDs")
    categoryBase: List[Dict[str, Any]] = Field(default_factory=list, description="Category base data")
    categoryApp: List[Dict[str, Any]] = Field(default_factory=list, description="Category app assignments")
    usedTimes: List[Dict[str, Any]] = Field(default_factory=list, description="Used time items per category")
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="Time limit rules per category")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Child tasks per category")
    users: Dict[str, Any] = Field(..., description="Full user list with version")
    krq: List[Dict[str, Any]] = Field(default_factory=list, description="Pending key requests")
    kr: List[Dict[str, Any]] = Field(default_factory=list, description="Key responses")
    pings: List[Dict[str, Any]] = Field(default_factory=list, description="Ping/pong messages")
    dh: Dict[str, str] = Field(default_factory=lambda: {"v": "1", "k": ""}, description="DH key for password encryption")
    u2f: Dict[str, Any] = Field(default_factory=lambda: {"v": "1", "d": []}, description="U2F data")
    fullVersion: int = Field(default=0, description="Premium expiration timestamp")
    message: str = Field(default="", description="Server message")
    apiLevel: int = Field(default=1, description="Server API level")


# ============================================================================
# Pull Status Request/Response
# ============================================================================

class PullStatusRequest(BaseModel):
    """Request model for pull-status endpoint."""
    
    deviceAuthToken: str = Field(..., description="Device authentication token")
    status: ClientDataStatus = Field(..., description="Client's current sync status")


class PullStatusResponse(BaseModel):
    """Response model for pull-status endpoint."""
    
    status: str = Field(default="ok", description="Status of the operation")
    data: Dict[str, Any] = Field(..., description="Server data status (ServerDataStatus)")


# ============================================================================
# Report Removed Request/Response
# ============================================================================

class ReportRemovedRequest(BaseModel):
    """Request model for report-removed endpoint."""
    
    deviceAuthToken: str = Field(..., description="Device authentication token")


class ReportRemovedResponse(BaseModel):
    """Response model for report-removed endpoint."""
    
    status: str = Field(default="ok", description="Status of the operation")


# ============================================================================
# Is Device Removed Request/Response
# ============================================================================

class IsDeviceRemovedRequest(BaseModel):
    """Request model for is-device-removed endpoint."""
    
    deviceAuthToken: str = Field(..., description="Device authentication token")


class IsDeviceRemovedResponse(BaseModel):
    """Response model for is-device-removed endpoint."""
    
    status: str = Field(default="ok", description="Status of the operation")
    isDeviceRemoved: bool = Field(..., description="If device was removed")