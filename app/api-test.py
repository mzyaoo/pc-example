import requests

url = "http://localhost:8000/health/stream"

payload = {
    "user_id": "1111",
    "task_id": '2222',
    "mode": '3333'
}

headers = {"Content-Type": "application/json"}

with requests.post(url, json=payload, stream=True, headers=headers, timeout=60) as r:
    r.raise_for_status()

    for line in r.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')

            if not decoded_line.strip():
                continue

            print(f"原始数据: {decoded_line}")
