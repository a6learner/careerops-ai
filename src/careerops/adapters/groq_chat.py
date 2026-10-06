import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum

import httpx


class GroqRequestFailureReason(StrEnum):
    REQUEST_FAILED = "request_failed"
    MISCONFIGURED = "misconfigured"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


class GroqRequestError(Exception):
    def __init__(
        self,
        reason: GroqRequestFailureReason,
        *,
        attempts: int,
        status_code: int | None = None,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.attempts = attempts
        self.status_code = status_code


class GroqChatTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_attempts: int,
        retry_base_delay_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Groq API key is required.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._transport = transport
        self._sleep = sleep
        self._request_attempt_count = 0

    @property
    def request_attempt_count(self) -> int:
        return self._request_attempt_count

    async def post_chat_completion(self, payload: dict[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            for attempt in range(1, self._max_attempts + 1):
                self._request_attempt_count += 1
                try:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    if attempt == self._max_attempts:
                        raise GroqRequestError(
                            GroqRequestFailureReason.TIMEOUT,
                            attempts=attempt,
                        ) from exc
                    await self._sleep(self._retry_delay(attempt, None))
                    continue
                except httpx.TransportError as exc:
                    if attempt == self._max_attempts:
                        raise GroqRequestError(
                            GroqRequestFailureReason.REQUEST_FAILED,
                            attempts=attempt,
                        ) from exc
                    await self._sleep(self._retry_delay(attempt, None))
                    continue

                if response.status_code < 400:
                    return response
                reason = classify_groq_status(response.status_code)
                if not is_retryable_groq_failure(reason) or attempt == self._max_attempts:
                    raise GroqRequestError(
                        reason,
                        attempts=attempt,
                        status_code=response.status_code,
                    )
                await self._sleep(
                    self._retry_delay(attempt, response.headers.get("Retry-After"))
                )
        raise AssertionError("Groq request loop exited unexpectedly.")

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), 5.0)
            except ValueError:
                pass
        return min(self._retry_base_delay_seconds * (2.0 ** (attempt - 1)), 5.0)


def classify_groq_status(status_code: int) -> GroqRequestFailureReason:
    if status_code in {401, 403}:
        return GroqRequestFailureReason.MISCONFIGURED
    if status_code == 408:
        return GroqRequestFailureReason.TIMEOUT
    if status_code == 429:
        return GroqRequestFailureReason.RATE_LIMITED
    if status_code in {498, 500, 502, 503, 504}:
        return GroqRequestFailureReason.UNAVAILABLE
    return GroqRequestFailureReason.REQUEST_FAILED


def is_retryable_groq_failure(reason: GroqRequestFailureReason) -> bool:
    return reason in {
        GroqRequestFailureReason.TIMEOUT,
        GroqRequestFailureReason.RATE_LIMITED,
        GroqRequestFailureReason.UNAVAILABLE,
    }
