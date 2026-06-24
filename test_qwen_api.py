# pip install openai
from openai import OpenAI

client = OpenAI(
    base_url="https://mango-backend-ai.mangolabx.io/v1",
    api_key="e2685415f59ae8e6a90b7ef26a9e9e95cdc17f1e50f1bfc1",
)
resp = client.chat.completions.create(
    model="qwen3.6-35b-a3b",    
    messages=[{"role": "user", "content": "กินไรยัง"}],
    max_tokens=1024,
)
print(resp.choices[0].message.content)

