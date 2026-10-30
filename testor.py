import asyncio
import hashlib
import httpx
from pathlib import Path
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent

async def main():
    env = dotenv_values(PROJECT_ROOT / ".env")
    api_key = env["OPENROUTER_API_KEY"]
    model = env["OPENROUTER_MODEL"]

    print("Model:", repr(model))
    print("Key fingerprint:", hashlib.sha256(api_key.encode()).hexdigest()[:12])

    async with httpx.AsyncClient(
        trust_env=False,
        timeout=30,
    ) as client:
        # Test authentication
        response = await client.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        print("Key endpoint:", response.status_code)

        # Test model
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Say OK"}
                ],
            },
        )

        print("Completion endpoint:", response.status_code)
        print("Response:", response.text[:500])


if __name__ == "__main__":
    asyncio.run(main())
