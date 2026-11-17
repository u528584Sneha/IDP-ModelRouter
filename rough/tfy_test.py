"""
Quick connectivity test for the TrueFoundry-hosted gpt-5.6-sol model.

Setup:
    pip install openai
    export TFY_API_KEY="your-truefoundry-api-key"   # Windows: set TFY_API_KEY=...

Run:
    python tfy_test.py
"""
import os
from openai import OpenAI

api_key = os.environ.get("TFY_API_KEY")
if not api_key:
    raise SystemExit("Set the TFY_API_KEY environment variable before running this script.")

client = OpenAI(
    api_key=api_key,
    base_url="https://tfy.wns.com/api/llm",  # your org's self-hosted TrueFoundry gateway
)

response = client.chat.completions.create(
    model="openai-idp/gpt-5.6-sol",
    messages=[
        {"role": "user", "content": "Hello from my local machine!"}
    ],
)

print(response.choices[0].message.content)
