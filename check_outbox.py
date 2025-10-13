import sqlite3

# Connect to the database
conn = sqlite3.connect('data/brain.db')
cursor = conn.cursor()

# Check outbox table structure
cursor.execute("PRAGMA table_info(outbox)")
columns = cursor.fetchall()
print("Outbox table structure:")
for column in columns:
    print(f"  {column[1]} ({column[2]}) - Not Null: {bool(column[3])} - Default: {column[4]} - PK: {bool(column[5])}")

# Check indexes
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='outbox'")
indexes = cursor.fetchall()
print("\nOutbox indexes:")
for index in indexes:
    print(f"  {index[0]}")

# Check some sample data
try:
    cursor.execute("SELECT COUNT(*) FROM outbox")
    count = cursor.fetchone()[0]
    print(f"\nTotal outbox messages: {count}")
    
    if count > 0:
        cursor.execute("SELECT * FROM outbox LIMIT 3")
        rows = cursor.fetchall()
        print("\nSample outbox messages:")
        for row in rows:
            print(f"  {row}")
except Exception as e:
    print(f"\nError checking outbox data: {e}")

conn.close()
