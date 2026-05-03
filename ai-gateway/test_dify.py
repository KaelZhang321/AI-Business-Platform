import requests

DIFY_URL = "https://dify.kaibol.net/v1/chat-messages"
DIFY_API_KEY = "app-7qe85nmTmehuST9egNnotsOa"   # 👈 用你新的key

headers = {
    "Authorization": f"Bearer {DIFY_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "inputs": {},
    "query": "你好，测试一下",
    "response_mode": "blocking",
    "user": "test-user-001",
}

resp = requests.post(DIFY_URL, json=payload, headers=headers)

print("STATUS:", resp.status_code)
print("RESPONSE:", resp.text)