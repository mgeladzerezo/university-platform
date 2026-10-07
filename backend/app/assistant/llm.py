import logging
from collections.abc import Iterator
from typing import Protocol

import anthropic

logger = logging.getLogger(__name__)


class LlmUnavailable(Exception):
    """The model could not produce an answer (API error, rate limit, refusal)."""


class LlmClient(Protocol):
    model: str

    def stream(self, system: str, user: str) -> Iterator[str]: ...

    def complete(self, system: str, user: str) -> str: ...


class AnthropicLlm:
    def __init__(self, model: str, client: anthropic.Anthropic | None = None):
        self.model = model
        # Credentials come from ANTHROPIC_API_KEY in the environment.
        self._client = client or anthropic.Anthropic()

    def stream(self, system: str, user: str) -> Iterator[str]:
        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": user}],
            ) as stream:
                yield from stream.text_stream
                if stream.get_final_message().stop_reason == "refusal":
                    raise LlmUnavailable("The model declined to answer")
        except anthropic.APIError as exc:
            raise self._unavailable(exc) from exc

    def complete(self, system: str, user: str) -> str:
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                output_config={"effort": "medium"},
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:
            raise self._unavailable(exc) from exc
        if message.stop_reason == "refusal":
            raise LlmUnavailable("The model declined to answer")
        return "".join(block.text for block in message.content if block.type == "text")

    @staticmethod
    def _unavailable(exc: anthropic.APIError) -> LlmUnavailable:
        # The SDK has already retried 429 and 5xx responses; whatever reaches
        # this point is reported to the user as a temporary failure.
        if isinstance(exc, anthropic.RateLimitError):
            logger.warning("Anthropic rate limit reached")
        elif isinstance(exc, anthropic.APIStatusError):
            logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        else:
            logger.error("Anthropic connection error: %s", exc)
        return LlmUnavailable("The assistant is temporarily unavailable")
