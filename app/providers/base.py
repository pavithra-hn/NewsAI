"""The single interface every model call goes through.

Everything behind this boundary is swappable by configuration. Changing
provider, or pointing one language at a different model, touches settings and
not pipeline code.

Swappable does not mean interchangeable. Providers differ in runtime,
quantisation, sampling defaults and model revision, and any of those can change
the text that comes back, so a provider change is revalidated rather than
assumed safe.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """The model call did not produce a usable completion."""


@dataclass(frozen=True)
class Pricing:
    input_per_million: float
    output_per_million: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_per_million
            + output_tokens / 1_000_000 * self.output_per_million
        )


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    model: str
    cost_usd: float = 0.0
    # False when we hold no published rate for the model. Reporting 0.00 as
    # though it were measured would put a false figure into the cost tracking.
    cost_known: bool = False


class Provider(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = ...,
        max_tokens: int = ...,
    ) -> Completion: ...
