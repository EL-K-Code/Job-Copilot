from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable using common truthy values."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    """Read a bounded integer environment variable with a clear startup error."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


def _env_choice(
    name: str,
    default: str,
    *,
    allowed: set[str],
) -> str:
    """Read a normalized enum-like environment value and fail fast on typos."""
    value = os.getenv(name, default).strip().lower() or default
    if value not in allowed:
        supported = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {supported}.")
    return value


def _hosted_recruiter_demo_default() -> bool:
    """Fail closed for authenticated Supabase deployments unless explicitly overridden."""
    return (
        os.getenv("PERSISTENCE_BACKEND", "auto").strip().lower() == "supabase"
        and _env_flag("BETA_AUTH_ENABLED", default=False)
    )


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_fallback_provider: str = os.getenv("LLM_FALLBACK_PROVIDER", "")

    # Phase 4: deterministic routing policy. `single` preserves the legacy one-tier behavior.
    llm_routing_mode: str = _env_choice(
        "LLM_ROUTING_MODE",
        "adaptive",
        allowed={"adaptive", "single"},
    )
    llm_routing_complex_job_chars: int = _env_int(
        "LLM_ROUTING_COMPLEX_JOB_CHARS",
        6000,
        minimum=500,
    )
    # Pricing is intentionally explicit/configurable so stale provider prices are never hidden
    # in application code. JSON keys use `provider:model` and rates are USD / 1M tokens.
    llm_pricing_version: str = os.getenv("LLM_PRICING_VERSION", "unconfigured").strip()
    llm_pricing_json: str = os.getenv("LLM_PRICING_JSON", "").strip()

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_profile_model: str = os.getenv(
        "OPENAI_PROFILE_MODEL",
        "gpt-4.1-nano",
    )
    openai_economy_model: str = os.getenv(
        "OPENAI_ECONOMY_MODEL",
        os.getenv("OPENAI_PROFILE_MODEL", "gpt-4.1-nano"),
    ).strip()
    openai_strong_model: str = os.getenv(
        "OPENAI_STRONG_MODEL",
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    ).strip()

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    anthropic_profile_model: str = os.getenv(
        "ANTHROPIC_PROFILE_MODEL",
        os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    )
    anthropic_economy_model: str = os.getenv(
        "ANTHROPIC_ECONOMY_MODEL",
        os.getenv("ANTHROPIC_PROFILE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")),
    ).strip()
    anthropic_strong_model: str = os.getenv(
        "ANTHROPIC_STRONG_MODEL",
        os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    ).strip()

    # Local Google OAuth remains filesystem-backed for local development.
    google_client_secret_file: str = os.getenv(
        "GOOGLE_CLIENT_SECRET_FILE", "credentials.json"
    )
    google_token_dir: str = os.getenv("GOOGLE_TOKEN_DIR", "tokens")

    # Hosted OAuth uses a Google Web client and encrypted Supabase token persistence.
    hosted_google_oauth_enabled: bool = _env_flag(
        "HOSTED_GOOGLE_OAUTH_ENABLED",
        default=False,
    )
    google_oauth_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    google_oauth_client_secret: str = os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRET", ""
    ).strip()
    google_oauth_redirect_uri: str = os.getenv(
        "GOOGLE_OAUTH_REDIRECT_URI", ""
    ).strip()
    google_token_encryption_key: str = os.getenv(
        "GOOGLE_TOKEN_ENCRYPTION_KEY", ""
    ).strip()

    memory_index_dir: str = os.getenv("MEMORY_INDEX_DIR", "data/faiss_index")
    applications_file: str = os.getenv("APPLICATIONS_FILE", "data/applications.json")
    profile_memories_file: str = os.getenv(
        "PROFILE_MEMORIES_FILE",
        "data/profile_memories.atomic.json",
    )

    # Premium evidence retrieval. Dense FAISS remains available as an explicit baseline.
    retrieval_strategy: str = _env_choice(
        "RETRIEVAL_STRATEGY",
        "hybrid",
        allowed={"dense", "hybrid"},
    )
    retrieval_candidate_k: int = _env_int(
        "RETRIEVAL_CANDIDATE_K",
        16,
        minimum=1,
    )
    retrieval_rrf_k: int = _env_int("RETRIEVAL_RRF_K", 60, minimum=1)
    retrieval_rerank_k: int = _env_int("RETRIEVAL_RERANK_K", 12, minimum=1)
    retrieval_reranker_enabled: bool = _env_flag(
        "RETRIEVAL_RERANKER_ENABLED",
        default=True,
    )
    retrieval_reranker_model: str = os.getenv(
        "RETRIEVAL_RERANKER_MODEL",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ).strip()

    user_data_root: str = os.getenv("USER_DATA_ROOT", "data/users")
    beta_users_file: str = os.getenv("BETA_USERS_FILE", "data/beta_users.json")
    beta_auth_enabled: bool = _env_flag("BETA_AUTH_ENABLED", default=False)
    beta_daily_ai_limit: int = _env_int("BETA_DAILY_AI_LIMIT", 10, minimum=1)
    local_candidate_name: str = os.getenv("LOCAL_CANDIDATE_NAME", "").strip()

    # Authenticated Supabase deployments fail closed into this boundary. Hosted Google
    # actions are separately opt-in and require a complete web-OAuth configuration.
    hosted_recruiter_demo: bool = _env_flag(
        "HOSTED_RECRUITER_DEMO",
        default=_hosted_recruiter_demo_default(),
    )

    # Deployment persistence. Prefer Supabase's current sb_secret_* server key.
    # SUPABASE_SERVICE_ROLE_KEY remains supported for legacy projects until migration.
    persistence_backend: str = os.getenv("PERSISTENCE_BACKEND", "auto")
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_secret_key: str = os.getenv(
        "SUPABASE_SECRET_KEY",
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    ).strip()
    supabase_timeout_seconds: int = _env_int(
        "SUPABASE_TIMEOUT_SECONDS", 12, minimum=1
    )

    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Paris")
    allow_trusted_faiss_deserialization: bool = _env_flag(
        "ALLOW_TRUSTED_FAISS_DESERIALIZATION",
        default=False,
    )

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def google_client_secret_path(self) -> Path:
        return self.project_root / self.google_client_secret_file

    @property
    def google_token_path(self) -> Path:
        return self.project_root / self.google_token_dir / "google_token.json"

    @property
    def memory_index_path(self) -> Path:
        return self.project_root / self.memory_index_dir

    @property
    def applications_path(self) -> Path:
        return self.project_root / self.applications_file

    @property
    def profile_memories_path(self) -> Path:
        return self.project_root / self.profile_memories_file

    @property
    def user_data_root_path(self) -> Path:
        return self.project_root / self.user_data_root

    @property
    def beta_users_path(self) -> Path:
        return self.project_root / self.beta_users_file

    def require_openai_api_key(self) -> str:
        """Return the configured OpenAI API key or fail without exposing it."""
        if not self.openai_api_key.strip():
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Add it to a local .env file or "
                "to the deployment secret store."
            )
        return self.openai_api_key

    def require_anthropic_api_key(self) -> str:
        """Return the configured Anthropic API key or fail without exposing it."""
        if not self.anthropic_api_key.strip():
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. Add it to a local .env file "
                "or to the deployment secret store."
            )
        return self.anthropic_api_key


settings = Settings()
