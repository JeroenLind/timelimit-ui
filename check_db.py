import sqlite3
import os

db_path = 'timelimit-ui/rootfs/usr/bin/dashboardV2/dashboardV2.db'
print('Database exists:', os.path.exists(db_path))
if os.path.exists(db_path):
    print('Database size:', os.path.getsize(db_path), 'bytes')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])

# Check auth_tokens
cursor.execute('SELECT COUNT(*) FROM auth_tokens')
count = cursor.fetchone()[0]
print('Auth tokens count:', count)

# Check families
cursor.execute('SELECT COUNT(*) FROM families')
count = cursor.fetchone()[0]
print('Families count:', count)

# Check devices
cursor.execute('SELECT COUNT(*) FROM devices')
count = cursor.fetchone()[0]
print('Devices count:', count)

conn.close()