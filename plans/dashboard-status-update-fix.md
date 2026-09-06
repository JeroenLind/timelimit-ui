# Dashboard Status Update Fix Plan

## Problem Analysis

### Issue
The dashboard fails to update its status (app version) to the server due to a missing database column `next_sequence_number` in the `sync_state` table.

### Root Cause
- The `sync_state` table schema in `database.py` includes `next_sequence_number INTEGER DEFAULT 0` (line 196)
- The `get_next_sequence_number()` function queries this column
- The `increment_sequence_number()` function also uses this column
- The `_push_app_version_action()` method in `sync_manager.py` calls `get_next_sequence_number()` which fails
- When the database already exists, `CREATE TABLE IF NOT EXISTS` doesn't update the schema
- The existing database was created with an older schema that doesn't have this column

### Log Evidence
From `dashboardV2-2026-08-22_20-37-02-3f2c507a.log`:
- Line 206: `"error": "no such column: next_sequence_number"`
- Line 226: Same error during second sync
- Line 215: `"event": "Updated own device app version after sync"` - Local update succeeds but server push fails

## Solution

Add a database migration to add the missing `next_sequence_number` column if it doesn't exist.

### Implementation Steps

1. **Add migration function in `database.py`**
   - Create a `migrate_database()` function that checks for and adds missing columns
   - Call this function in `init_db()` after table creation

2. **Migration logic**
   - Check if `next_sequence_number` column exists in `sync_state` table
   - If not, add it with `ALTER TABLE sync_state ADD COLUMN next_sequence_number INTEGER DEFAULT 0`

3. **Test the fix**
   - Verify the migration runs correctly
   - Verify app version is pushed to server after migration

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`
   - Add `migrate_database()` function
   - Call migration in `init_db()`

## Technical Details

### Migration SQL
```sql
ALTER TABLE sync_state ADD COLUMN next_sequence_number INTEGER DEFAULT 0
```

### Migration Function
```python
def migrate_database(db: Database) -> None:
    """Run database migrations for schema updates.
    
    This function checks for and adds missing columns to existing tables.
    It should be called after init_db() to ensure the database schema
    is up to date.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Check if next_sequence_number column exists in sync_state table
        cursor.execute("PRAGMA table_info(sync_state)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'next_sequence_number' not in columns:
            logger.info(
                "Migrating database: adding next_sequence_number column",
                component="database",
                db_path=db.db_path
            )
            cursor.execute('''
                ALTER TABLE sync_state 
                ADD COLUMN next_sequence_number INTEGER DEFAULT 0
            ''')
            conn.commit()
            logger.info(
                "Database migration completed",
                component="database",
                db_path=db.db_path
            )
```

## Expected Outcome

After the fix:
1. Database migration runs on startup
2. `next_sequence_number` column is added if missing
3. `_push_app_version_action()` succeeds
4. App version is correctly reported to the server
5. Server shows correct `currentAppVersion` and `highestAppVersion` for the dashboard device