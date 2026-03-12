from __future__ import annotations

import aiohttp


class GroqClient:
    def __init__(self, api_url: str, api_key: str, model_name: str, timeout_seconds: int = 45):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def chat_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    details = await response.text()
                    raise RuntimeError(f"Groq error status={response.status}: {details[:800]}")

                data = await response.json()

        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return answer
