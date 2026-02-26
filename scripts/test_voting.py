import os
import sys
from datetime import datetime, timezone, timedelta
import jwt
from dotenv import load_dotenv
import httpx
import sqlite3

# Load env
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
import sys
sys.path.append(backend_dir)
from config import get_settings

JWT_SECRET = get_settings().jwt_secret

# Generate mock user token
expires_delta = timedelta(days=30)
expire = datetime.now(timezone.utc) + expires_delta

to_encode = {
    "sub": "mock_spotify_user_999",
    "role": "public_user",
    "exp": expire
}
encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

# Check if we have any scandals
db_path = os.path.join(backend_dir, 'skandal_tracker.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT id FROM scandals LIMIT 1")
row = cur.fetchone()
if not row:
    print("No scandals in database to vote on.")
    sys.exit(0)

scandal_id = row[0]

# Make request to backend
print(f"Testing vote for scandal {scandal_id}...")
headers = {
    "Authorization": f"Bearer {encoded_jwt}",
    "Content-Type": "application/json"
}

response = httpx.post(
    f"http://127.0.0.1:8001/api/scandals/{scandal_id}/vote",
    headers=headers,
    json={"vote": 8}
)

print(f"Status Code: {response.status_code}")
print(f"Response Body: {response.text}")
