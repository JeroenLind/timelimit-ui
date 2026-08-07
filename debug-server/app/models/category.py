"""Category data models for TimeLimit API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CategoryBaseData(BaseModel):
    """Category base data model for TimeLimit API.
    
    Represents the base configuration for a time limit category.
    """
    
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
    atw: List[int] = Field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0], description="Allowed time windows (7-element array, 0=Sunday)")


class CategoryAppAssignment(BaseModel):
    """Category app assignment model.
    
    Represents apps assigned to a category.
    """
    
    categoryId: str = Field(..., description="Category identifier")
    apps: List[str] = Field(default_factory=list, description="List of app package names assigned to this category")
    version: str = Field(default="1", description="Assigned apps version")


class CategoryUsedTime(BaseModel):
    """Used time item model.
    
    Represents time usage for a category on a specific date.
    """
    
    categoryId: str = Field(..., description="Category identifier")
    usedTime: int = Field(..., description="Used time in milliseconds")
    date: str = Field(..., description="Date string (e.g., '2024-01-15')")


class TimeLimitRule(BaseModel):
    """Time limit rule model.
    
    Represents a time limit rule for a category.
    """
    
    categoryId: str = Field(..., description="Category identifier")
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6, 0=Sunday)")
    startTime: int = Field(..., description="Start time in milliseconds from midnight")
    endTime: int = Field(..., description="End time in milliseconds from midnight")
    maxTime: int = Field(..., description="Maximum allowed time in milliseconds")


class CategoryTask(BaseModel):
    """Child task model.
    
    Represents a task for a category.
    """
    
    categoryId: str = Field(..., description="Category identifier")
    taskId: str = Field(..., description="Task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    completed: bool = Field(default=False, description="If task is completed")


class CategoryCreate(BaseModel):
    """Model for creating a new category."""
    
    title: str = Field(..., description="Category title")
    childId: str = Field(..., description="User ID this category belongs to")
    parentCategoryId: Optional[str] = Field(None, description="Parent category ID")


class CategoryUpdate(BaseModel):
    """Model for updating a category."""
    
    title: Optional[str] = Field(None, description="Updated category title")
    tempBlocked: Optional[bool] = Field(None, description="Updated temp blocked status")
    tempBlockTime: Optional[int] = Field(None, description="Updated temp block time")