# Time Limit Rule Category - Free Format String Implementation Plan

## Problem Statement

The user wants to specify a category name as a free-format string when creating a time limit rule, rather than selecting from a dropdown of existing categories.

## Analysis of Official Server Source Code

### TimelimitRule Model (`src/model/timelimitrule.ts`)
- `categoryId`: string (6-character alphanumeric ID, validated within family)
- `maxTimeInMillis`: number
- `dayMask`: number (bitmask for days of week)
- `applyToExtraTimeUsage`: boolean
- `start`: number (minutes of day)
- `end`: number (minutes of day)
- `sessionDurationMilliseconds`: number
- `sessionPauseMilliseconds`: number
- `perDay`: boolean
- `expiresAt`: optional number

### Category Model (`src/database/category.ts`)
- `id`: string (primary key, 6-character alphanumeric)
- `title`: string (free-format TEXT field - `labelColumn` type)
- `childId`: string
- `blockedTimes`: string
- `extraTime`: number
- `extraTimeDay`: number
- `tempBlocked`: boolean
- `tempBlockTime`: string
- `version`: string
- `parentCategoryId`: string
- `blockAllNotifications`: boolean
- `timeWarnings`: number
- `sortOrder`: number
- `flags`: string
- `blockNotificationDelay`: string

### CreateCategoryAction (`src/action/createcategory.ts`)
- `categoryId`: string (6-character alphanumeric)
- `childId`: string
- `title`: string (free-format category name)

### CreateTimeLimitRuleAction (`src/action/createtimelimitrule.ts`)
- `rule`: TimelimitRule object

## Current Dashboard Implementation Issues

1. **HTML Template** (`dashboardV2.html` lines 1367-1377):
   - Uses `<select id="rule-category">` dropdown for category selection
   - Categories are populated from `/api/dashboard/categories`

2. **JavaScript** (`dashboardV2.js`):
   - `populateCategoryDropdown()`: Fetches categories and populates dropdown
   - `submitRuleForm()`: Sends `categoryId` from dropdown selection
   - No mechanism to create a new category with a free-format name

3. **API Endpoint** (`app.py` lines 3393-3602):
   - Expects `categoryId` as a string
   - No support for category name input

## Solution Design

### Approach: Create Category First, Then Create Rule

When a user enters a category name:
1. Check if a category with that name already exists
2. If not, create a new category with the given name
3. Use the category's ID in the time limit rule

### Implementation Steps

1. **Update HTML Template** (`dashboardV2.html`):
   - Replace `<select>` dropdown with `<input type="text">` for category name
   - Add a "Create Category" button or auto-create on form submit
   - Keep a hidden field or data attribute to store the categoryId

2. **Update JavaScript** (`dashboardV2.js`):
   - Modify `populateCategoryDropdown()` to `populateCategoryInput()`
   - Add `createCategoryWithName()` function to create category via API
   - Update `submitRuleForm()` to:
     - Get category name from input
     - Find or create category with that name
     - Get the categoryId
     - Submit the rule with the categoryId

3. **Add API Endpoint** (`app.py`):
   - Add `POST /api/dashboard/categories` endpoint to create a category
   - Accept `title` (category name) and optional `childId`
   - Return the created category with its `id`

4. **Update Documentation**:
   - Update `docs/time-limit-rules-user-guide.md`
   - Update `docs/api/internal-api.md`
   - Update `docs/dashboardV2-implementation.md`

## API Changes Required

### New Endpoint: Create Category

**Endpoint**: `POST /api/dashboard/categories`

**Request Body**:
```json
{
    "title": "Games",
    "childId": "user_123"  // optional, defaults to first child
}
```

**Response**:
```json
{
    "status": "ok",
    "category": {
        "id": "cat_abc123",
        "title": "Games",
        "childId": "user_123"
    }
}
```

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Change category input from dropdown to text field
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Update JavaScript logic
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Add category creation endpoint
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Add `create_category()` function
5. `timelimit-ui/docs/time-limit-rules-user-guide.md` - Update documentation
6. `timelimit-ui/docs/api/internal-api.md` - Update API documentation

## Testing Considerations

- Test creating a new category with a unique name
- Test using an existing category name (should find and use existing category)
- Test edge cases: empty name, very long name, special characters
- Test that the rule is properly synced to the server