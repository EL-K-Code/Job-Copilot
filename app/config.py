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


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_fallback_provider: str = os.getenv("LLM_FALLBACK_PROVIDER", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    google_client_secret_file: str = os.getenv(
        "GOOGLE_CLIENT_SECRET_FILE", "credentials.json"
    )
    google_token_dir: str = os.getenv("GOOGLE_TOKEN_DIR", "tokens")

    memory_index_dir: str = os.getenv("MEMORY_INDEX_DIR", "data/faiss_index")
    applications_file: str = os.getenv("APPLICATIONS_FILE", "data/applications.json")
    profile_memories_file: str = os.getenv(
        "PROFILE_MEMORIES_FILE",
        "data/profile_memories.atomic.json",
    )

    user_data_root: str = os.getenv("USER_DATA_ROOT", "data/users")
    beta_users_file: str = os.getenv("BETA_USERS_FILE", "data/beta_users.json")
    beta_auth_enabled: bool = _env_flag("BETA_AUTH_ENABLED", default=False)
    beta_daily_ai_limit: int = _env_int("BETA_DAILY_AI_LIMIT", 10, minimum=1)
    local_candidate_name: str = os.getenv("LOCAL_CANDIDATE_NAME", "").strip()

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
