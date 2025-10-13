import requests
import json

# Test email endpoint
url = "http://localhost:8765/outbox/email"
data = {
    "user_id": 789,
    "subject": "Test Subject",
    "body": "Test Body"
}

response = requests.post(url, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
