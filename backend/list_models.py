import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GROQ_API_KEY")
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

res = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
print("Status:", res.status_code)
if res.status_code == 200:
    models = res.json().get("data", [])
    for m in models:
        print("Model ID:", m.get("id"))
else:
    print(res.text)
