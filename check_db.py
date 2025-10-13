import sqlite3

# Connect to the database
conn = sqlite3.connect('data/brain.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in database:")
for table in tables:
    print(f"  {table[0]}")

# Check migrations table
try:
    cursor.execute("SELECT version, applied_at, description FROM migrations")
    migrations = cursor.fetchall()
    print("\nApplied migrations:")
    for migration in migrations:
        print(f"  {migration[0]}: {migration[2]} (applied at {migration[1]})")
except:
    print("\nNo migrations table found")

conn.close()
