import requests
import json

# Test Dexter endpoint
url = "http://127.0.0.1:8765/dexter/chat"
data = {
    "message": "Hello Dexter, are you there?"
}

response = requests.post(url, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
