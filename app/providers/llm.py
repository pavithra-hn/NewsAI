"""Any OpenAI-compatible chat completions endpoint.

Oxlo today, for development against published articles. DeepInfra is the
intended production provider once the company account exists. Both speak the
same wire format, which is the point of going through one interface.
"""

import asyncio

import httpx

from app.config import settings
from app.providers.base import Completion, Pricing, ProviderError

# Published rates, per million tokens. Used to report what a call cost.
PRICES = {
    "qwen-3-32b": Pricing(0.08, 0.28),
    "qwen3-32b": Pricing(0.08, 0.28),
    "Qwen/Qwen3-32B": Pricing(0.08, 0.28),
    "Qwen/Qwen3-235B-A22B-Instruct-2507": Pricing(0.09, 0.55),
}

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}

BASE_BACKOFF_SECONDS = 1.0


class LLMProvider:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        max_attempts: int | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        # The base URL comes from configuration and is never taken from a
        # response, and redirects are not followed, so the api key cannot be
        # sent to a host we did not choose.
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.provider_base_url,
            timeout=timeout or settings.provider_timeout_seconds,
            headers={"Authorization": f"Bearer {api_key or settings.provider_api_key}"},
            follow_redirects=False,
        )
        self._max_attempts = max_attempts or settings.max_transport_attempts
        self._sleep = sleep

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 400,
    ) -> Completion:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self._post_with_retry(payload)
        return self._parse(response, model)

    async def _post_with_retry(self, payload) -> httpx.Response:
        last = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 400:
                    return response
                last = f"{response.status_code} from the provider"
                # A malformed request will not become well formed by repeating
                # it, so only the transient statuses are worth another attempt.
                if response.status_code not in RETRYABLE_STATUS:
                    raise ProviderError(last)

            if attempt < self._max_attempts:
                await self._sleep(BASE_BACKOFF_SECONDS * 2 ** (attempt - 1))

        raise ProviderError(f"gave up after {self._max_attempts} attempts: {last}")

    def _parse(self, response: httpx.Response, model: str) -> Completion:
        try:
            body = response.json()
            choice = body["choices"][0]
            text = choice["message"]["content"]
            usage = body.get("usage", {})
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"response was not a usable completion: {exc}") from exc

        if text is None:
            raise ProviderError("the completion carried no content")

        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        pricing = PRICES.get(model)

        return Completion(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=choice.get("finish_reason", "stop"),
            model=model,
            cost_usd=pricing.cost(input_tokens, output_tokens) if pricing else 0.0,
            cost_known=pricing is not None,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
