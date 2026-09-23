from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_LOCALES = frozenset({"en", "ar", "fr"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    database_url: str = "postgresql://localhost:5432/news_ai_helper"

    # Token MakinatyNews presents to us.
    inbound_api_token: str = "change-me"
    # Token we present to MakinatyNews.
    outbound_api_token: str = "change-me"

    makinaty_base_url: str = "http://localhost:3000"
    makinaty_timeout_seconds: float = 30.0

    # The model is chosen per locale so that a language which benchmarks badly
    # can be pointed elsewhere without touching the other two.
    models: dict[str, str] = {
        "en": "qwen-3-32b",
        "ar": "qwen-3-32b",
        "fr": "qwen-3-32b",
    }

    # Words each language uses for the same content, relative to English.
    # Measured as the median, over the 25 corpus articles, of that language's
    # word count divided by the English word count. Used to scale length
    # targets so a French or Arabic quick read is not held to English counts.
    language_factors: dict[str, float] = {"en": 1.0, "ar": 1.09, "fr": 1.28}

    # Languages whose prompt carries a human-written style example. Off until
    # the evaluation shows an example raises that language's pass rate.
    style_examples: list[str] = []

    provider_base_url: str = "https://api.oxlo.ai/v1"
    provider_api_key: str = ""
    # Sized above the longest call we have observed complete, which was 141.66
    # seconds on a congested free pool. Oxlo returns in single digits.
    provider_timeout_seconds: float = 180.0

    # At least one each: zero attempts would run no model and no check.
    max_transport_attempts: int = Field(default=3, ge=1)
    max_generation_attempts: int = Field(default=2, ge=1)

    # Hosting already takes $12 of the $20 total, so the inference headroom is
    # about $8. Enforcing this needs storage, which arrives with the API layer.
    monthly_spend_cap_usd: float = 5.0

    @field_validator("models")
    @classmethod
    def _one_model_per_supported_locale(cls, value: dict[str, str]) -> dict[str, str]:
        # Checked at startup. A map missing a language would otherwise boot,
        # pass /health, and fail only when that language's button is pressed.
        missing = SUPPORTED_LOCALES - value.keys()
        unknown = value.keys() - SUPPORTED_LOCALES
        if missing:
            raise ValueError(f"MODELS has no model for: {sorted(missing)}")
        if unknown:
            raise ValueError(f"MODELS names unsupported locales: {sorted(unknown)}")
        return value

    @field_validator("language_factors")
    @classmethod
    def _one_positive_factor_per_locale(cls, value: dict[str, float]) -> dict[str, float]:
        if set(value) != SUPPORTED_LOCALES:
            raise ValueError(f"LANGUAGE_FACTORS must cover exactly {sorted(SUPPORTED_LOCALES)}")
        if any(factor <= 0 for factor in value.values()):
            raise ValueError("LANGUAGE_FACTORS must all be positive")
        return value

    @field_validator("style_examples")
    @classmethod
    def _style_examples_for_supported_locales(cls, value: list[str]) -> list[str]:
        unknown = set(value) - SUPPORTED_LOCALES
        if unknown:
            raise ValueError(f"STYLE_EXAMPLES names unsupported locales: {sorted(unknown)}")
        return value

    def model_for(self, locale: str) -> str:
        return self.models[locale]


settings = Settings()
