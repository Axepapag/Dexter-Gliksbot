import requests
import json

# Test adding a message to outbox
url = "http://localhost:8765/outbox/add"
data = {
    "task_name": "test_email",
    "payload": {
        "user_id": 456,
        "subject": "Hello",
        "body": "Test message"
    }
}

response = requests.post(url, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
