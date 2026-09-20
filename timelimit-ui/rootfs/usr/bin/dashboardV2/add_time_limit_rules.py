#!/usr/bin/env python3
"""Script to add time_limit_rules table and functions to database.py"""

import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
db_file = os.path.join(script_dir, 'database.py')

# Read the file
with open(db_file, 'r') as f:
    lines = f.readlines()

# Find the line numbers where we need to make changes
init_db_end = None
drop_tables_start = None
clear_tables_start = None
migration_end = None
factory_start = None

for i, line in enumerate(lines):
    if 'CREATE TABLE IF NOT EXISTS connected_devices' in line:
        # Find the end of this CREATE TABLE statement
        for j in range(i, min(i + 20, len(lines))):
            if "''')" in lines[j]:
                init_db_end = j
                break
    
    if "cursor.execute('DROP TABLE IF EXISTS connected_devices')" in line:
        drop_tables_start = i
    
    if "tables = [" in line and drop_tables_start is not None:
        clear_tables_start = i
    
    if 'logger.warning(\n            "Could not drop device_auth_token column"' in lines[i:i+3] or \
       ('logger.warning(' in line and 'Could not drop device_auth_token column' in ''.join(lines[i:i+5])):
        # Find the end of this warning block
        for j in range(i, min(i + 10, len(lines))):
            if 'error=str(e)' in lines[j]:
                migration_end = j
                break
    
    if '# Database Factory' in line:
        factory_start = i
        break

print(f"Found positions: init_db_end={init_db_end}, drop_tables_start={drop_tables_start}, clear_tables_start={clear_tables_start}, migration_end={migration_end}, factory_start={factory_start}")

# Build the new content
new_lines = []

# 1. Add time_limit_rules table to init_db()
for i, line in enumerate(lines):
    new_lines.append(line)
    if i == init_db_end:
        new_lines.append('''
            # Create time_limit_rules table
            cursor.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS time_limit_rules (
                    id TEXT PRIMARY KEY,
                    device_auth_token TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    rule_type INTEGER DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    days INTEGER DEFAULT 127,
                    limit_minutes INTEGER DEFAULT 0,
                    version TEXT,
                    created_at TEXT NOT NULL,
                    last_updated INTEGER,
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            \'\'\')
''')

# 2. Add time_limit_rules to drop_tables()
for i, line in enumerate(lines):
    if i == drop_tables_start:
        new_lines.insert(len(new_lines) - 1, "            cursor.execute('DROP TABLE IF EXISTS time_limit_rules')\n")
    new_lines.append(line)

# 3. Add time_limit_rules to clear_all_tables()
for i, line in enumerate(lines):
    if i == clear_tables_start:
        new_lines.insert(len(new_lines) - 1, "                'time_limit_rules',\n")
    new_lines.append(line)

# 4. Add migration for time_limit_rules
# This is more complex, so we'll do it differently

# 5. Add time limit rules functions before Database Factory
# Find the factory_start in the new_lines
factory_pos = None
for i, line in enumerate(new_lines):
    if '# Database Factory' in line:
        factory_pos = i
        break

if factory_pos:
    time_limit_rules_functions = '''# ============================================================================
# Time Limit Rules Operations
# ============================================================================

def save_time_limit_rule(
    db: Database,
    rule_id: str,
    device_auth_token: str,
    user_id: str,
    category_id: str,
    rule_type: int = 0,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    days: int = 127,
    limit_minutes: int = 0,
    version: Optional[str] = None
) -> None:
    """Save a time limit rule to the database.
    
    Args:
        db: Database instance.
        rule_id: Unique rule ID (primary key).
        device_auth_token: Device auth token this rule belongs to.
        user_id: User ID this rule applies to.
        category_id: Category ID for the rule.
        rule_type: Type of rule (0=TIME_LIMIT, 1=TIME_LIMIT_EXCEPTIONS).
        start_time: Start time in HH:MM format.
        end_time: End time in HH:MM format.
        days: Days bitmask (0-127).
        limit_minutes: Time limit in minutes.
        version: Rule version string.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp() * 1000)
        
        sql = """INSERT OR REPLACE INTO time_limit_rules
            (id, device_auth_token, user_id, category_id, rule_type, start_time, end_time,
             days, limit_minutes, version, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        
        cursor.execute(sql, (
            rule_id,
            device_auth_token,
            user_id,
            category_id,
            rule_type,
            start_time,
            end_time,
            days,
            limit_minutes,
            version,
            datetime.now(timezone.utc).isoformat(),
            current_time
        ))
        
        conn.commit()
        logger.info(
            "Time limit rule saved",
            component="database",
            db_path=db.db_path,
            table_name="time_limit_rules",
            rule_id=rule_id
        )


def get_time_limit_rules_by_device_auth_token(
    db: Database,
    device_auth_token: str
) -> List[Dict[str, Any]]:
    """Get all time limit rules for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        List of time limit rule records.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM time_limit_rules WHERE device_auth_token = ?",
            (device_auth_token,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_time_limit_rule_by_id(
    db: Database,
    rule_id: str
) -> Optional[Dict[str, Any]]:
    """Get a single time limit rule by ID.
    
    Args:
        db: Database instance.
        rule_id: The rule ID to look up.
        
    Returns:
        Rule record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM time_limit_rules WHERE id = ?", (rule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_time_limit_rule(
    db: Database,
    rule_id: str,
    updates: Dict[str, Any]
) -> bool:
    """Update a time limit rule.
    
    Args:
        db: Database instance.
        rule_id: The rule ID to update.
        updates: Dictionary of fields to update.
        
    Returns:
        True if updated, False if rule not found.
    """
    if not updates:
        return False
    
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [rule_id]
        
        sql = f"UPDATE time_limit_rules SET {set_clause} WHERE id = ?"
        cursor.execute(sql, values)
        
        conn.commit()
        return cursor.rowcount > 0


def delete_time_limit_rule(
    db: Database,
    rule_id: str
) -> bool:
    """Delete a time limit rule.
    
    Args:
        db: Database instance.
        rule_id: The rule ID to delete.
        
    Returns:
        True if deleted, False if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM time_limit_rules WHERE id = ?", (rule_id,))
        conn.commit()
        
        return cursor.rowcount > 0


'''
    
    # Insert the functions before the Database Factory section
    new_lines = new_lines[:factory_pos] + [time_limit_rules_functions] + new_lines[factory_pos:]

# Write the file
with open(db_file, 'w') as f:
    f.writelines(new_lines)

print("File updated successfully")