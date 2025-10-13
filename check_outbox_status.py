import sqlite3

# Connect to the database
conn = sqlite3.connect('data/brain.db')
cursor = conn.cursor()

# Check outbox messages
cursor.execute('SELECT id, task, status, retry_count, created_at FROM outbox ORDER BY created_at')
rows = cursor.fetchall()
print('Outbox messages:')
for row in rows:
    print(f'  ID: {row[0]}, Task: {row[1]}, Status: {row[2]}, Retry: {row[3]}, Created: {row[4]}')

conn.close()
