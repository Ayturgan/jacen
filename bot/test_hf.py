"""Тест доступных моделей на HuggingFace Serverless Inference"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from huggingface_hub import InferenceClient

HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient(token=HF_TOKEN)

models_to_test = [
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen3-32B",
    "Qwen/Qwen3-14B",
    "Qwen/Qwen3-4B",
    "mistralai/Mistral-Small-24B-Instruct-2501",
    "microsoft/Phi-3-mini-4k-instruct",
    "google/gemma-3-27b-it",
]

for model_id in models_to_test:
    print(f"\n🔹 {model_id}...", end=" ", flush=True)
    try:
        result = client.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": "Say one word."}],
            max_tokens=10,
        )
        print(f"✅ {result.choices[0].message.content.strip()}")
    except Exception as e:
        err = str(e)[:80]
        print(f"❌ {err}")
