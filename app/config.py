from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    google_client_secret_file: str = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "credentials.json")
    google_token_dir: str = os.getenv("GOOGLE_TOKEN_DIR", "tokens")

    memory_index_dir: str = os.getenv("MEMORY_INDEX_DIR", "data/faiss_index")
    applications_file: str = os.getenv("APPLICATIONS_FILE", "data/applications.json")
    profile_memories_file: str = os.getenv("PROFILE_MEMORIES_FILE", "data/profile_memories.json")

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


settings = Settings()