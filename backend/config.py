"""Application settings and LLM factory."""

import os
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mongodb_uri: str = Field(validation_alias="MONGODB_URI")
    llm_provider: Literal["anthropic", "groq"] = Field(
        default="anthropic",
        validation_alias="LLM_PROVIDER",
    )
    anthropic_api_key: str = Field(validation_alias="ANTHROPIC_API_KEY")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    serpapi_key: str = Field(validation_alias="SERPAPI_KEY")
    google_places_api_key: str = Field(validation_alias="GOOGLE_PLACES_API_KEY")
    google_routes_api_key: str = Field(validation_alias="GOOGLE_ROUTES_API_KEY")

    langchain_api_key: str | None = Field(default=None, validation_alias="LANGCHAIN_API_KEY")
    langchain_tracing_v2: str = Field(default="false", validation_alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field(default="squadplanner", validation_alias="LANGCHAIN_PROJECT")

    serpapi_monthly_hard_limit: int = Field(
        default=200,
        ge=0,
        validation_alias="SERPAPI_MONTHLY_HARD_LIMIT",
    )


settings = Settings()


def configure_langsmith() -> None:
    """Configure LangSmith environment variables when tracing is enabled."""
    if settings.langchain_tracing_v2.lower() != "true":
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


def get_llm() -> Any:
    """Return a chat model for the configured provider (lazy-imports providers)."""
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-haiku-4-5",
            api_key=settings.anthropic_api_key,
        )
    if settings.llm_provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as err:
            raise ImportError(
                "LLM_PROVIDER=groq requires the langchain-groq package "
                "(pip install langchain-groq)."
            ) from err

        return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=settings.groq_api_key,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
