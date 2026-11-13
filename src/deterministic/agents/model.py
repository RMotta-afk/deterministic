"""Small, validated client for an OpenAI-compatible chat completion endpoint."""

import json
import os
import time
import urllib.error
import urllib.request

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    base_url: str = "https://api.openai.com/v1"
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    timeout_seconds: int = Field(default=120, gt=0, le=600)
    max_completion_tokens: int = Field(default=6000, gt=0)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)
    embedding_usd_per_million: float | None = Field(default=None, ge=0)

    @classmethod
    def from_environment(cls) -> "ModelSettings":
        key = os.getenv("MIGRATION_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("MIGRATION_MODEL")
        if not key or not model:
            raise ValueError("Set MIGRATION_MODEL and MIGRATION_API_KEY (or OPENAI_API_KEY)")
        return cls(
            base_url=os.getenv("MIGRATION_BASE_URL", "https://api.openai.com/v1"),
            model=model,
            api_key=key,
            timeout_seconds=int(os.getenv("MIGRATION_TIMEOUT_SECONDS", "120")),
            max_completion_tokens=int(os.getenv("MIGRATION_MAX_COMPLETION_TOKENS", "6000")),
            input_usd_per_million=(
                float(os.environ["MIGRATION_INPUT_USD_PER_MILLION"])
                if os.getenv("MIGRATION_INPUT_USD_PER_MILLION")
                else None
            ),
            output_usd_per_million=(
                float(os.environ["MIGRATION_OUTPUT_USD_PER_MILLION"])
                if os.getenv("MIGRATION_OUTPUT_USD_PER_MILLION")
                else None
            ),
            embedding_usd_per_million=(
                float(os.environ["MIGRATION_EMBEDDING_USD_PER_MILLION"])
                if os.getenv("MIGRATION_EMBEDDING_USD_PER_MILLION")
                else None
            ),
        )


class ModelResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str
    model: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    vector: list[float]
    model: str
    prompt_tokens: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class _ProviderBoundary(BaseModel):
    # Compatible providers may add fields outside the subset we consume.
    model_config = ConfigDict(extra="ignore", strict=True)


class _ChatUsage(_ProviderBoundary):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class _ChatMessage(_ProviderBoundary):
    content: str


class _ChatChoice(_ProviderBoundary):
    message: _ChatMessage


class _ChatResponse(_ProviderBoundary):
    model: str
    choices: list[_ChatChoice] = Field(min_length=1)
    usage: _ChatUsage


class _EmbeddingUsage(_ProviderBoundary):
    prompt_tokens: int = Field(ge=0)


class _EmbeddingPoint(_ProviderBoundary):
    embedding: list[float] = Field(min_length=1)


class _EmbeddingResponse(_ProviderBoundary):
    model: str
    data: list[_EmbeddingPoint] = Field(min_length=1)
    usage: _EmbeddingUsage


class ChatModel:
    def __init__(self, settings: ModelSettings):
        self.settings = settings

    def complete(
        self, system: str, user: str, max_completion_tokens: int | None = None
    ) -> ModelResult:
        body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_completion_tokens": max_completion_tokens or self.settings.max_completion_tokens,
        }
        if "MIGRATION_TEMPERATURE" in os.environ:
            body["temperature"] = float(os.environ["MIGRATION_TEMPERATURE"])
        request = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                payload = _ChatResponse.model_validate_json(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Model endpoint returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Model endpoint is unavailable") from exc
        except ValidationError as exc:
            raise RuntimeError("Model endpoint response is invalid") from exc
        try:
            content = payload.choices[0].message.content
            usage = payload.usage
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty model response")
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            cost = (
                (
                    prompt_tokens * self.settings.input_usd_per_million
                    + completion_tokens * self.settings.output_usd_per_million
                )
                / 1_000_000
                if self.settings.input_usd_per_million is not None
                and self.settings.output_usd_per_million is not None
                else None
            )
            return ModelResult(
                text=content,
                model=payload.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=(time.perf_counter() - started) * 1000,
                cost_usd=cost,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Model response lacks text or token usage") from exc

    def embed(self, text: str, model: str) -> EmbeddingResult:
        request = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/embeddings",
            data=json.dumps({"model": model, "input": text}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                payload = _EmbeddingResponse.model_validate_json(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Embedding endpoint returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Embedding endpoint is unavailable") from exc
        except ValidationError as exc:
            raise RuntimeError("Embedding endpoint response is invalid") from exc
        try:
            vector = payload.data[0].embedding
            if not vector:
                raise ValueError("empty embedding")
            tokens = payload.usage.prompt_tokens
            rate = self.settings.embedding_usd_per_million
            return EmbeddingResult(
                vector=vector,
                model=payload.model,
                prompt_tokens=tokens,
                duration_ms=(time.perf_counter() - started) * 1000,
                cost_usd=tokens * rate / 1_000_000 if rate is not None else None,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Embedding response lacks a vector or token usage") from exc
