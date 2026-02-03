from __future__ import annotations


def _openai_chat_sync(
    api_key: str,
    api_base: str | None,
    model: str | None,
    system_prompt: str,
    user_prompt: str,
    timeout: int,
    max_tokens: int,
    temperature: float,
    openai_available: bool,
    openai_class,
) -> str:
    if not openai_available or openai_class is None:
        raise RuntimeError("OpenAI library not available")
    client = openai_class(api_key=api_key, base_url=api_base, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()
