import sqlite3

conn = sqlite3.connect('users.db')  # Or your actual DB file
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        page TEXT,
        time_spent INTEGER
    )
''')

conn.commit()
conn.close()

print("✅ user_activity_log table created.")
