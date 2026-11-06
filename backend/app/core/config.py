"""Environment-driven application configuration.

All secrets, paths and model settings come from environment variables —
never hardcoded. See .env.example for the full list.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BackendDir = Path(__file__).resolve().parents[2]  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BackendDir / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "LectureLens"
    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Database ---
    database_url: str = "postgresql+psycopg2://lecturelens:lecturelens@localhost:5432/lecturelens"

    # --- Redis / RQ ---
    redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "lecturelens"
    # When true the pipeline runs inline in-process (used by tests / demo
    # without Redis). Never use in production.
    inline_jobs: bool = False

    # --- Storage ---
    storage_root: Path = BackendDir / "storage"
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MB
    max_audio_duration_seconds: float = 3600.0
    min_audio_duration_seconds: float = 2.0
    allowed_audio_extensions: str = ".wav,.mp3,.m4a,.flac,.ogg,.aac,.webm"

    # --- Audio processing ---
    target_sample_rate: int = 16000
    target_channels: int = 1
    chunk_duration_seconds: float = 30.0
    chunk_overlap_seconds: float = 2.0
    vad_energy_threshold_db: float = -35.0
    vad_min_speech_seconds: float = 0.35
    vad_max_silence_for_split_seconds: float = 0.6

    # --- Providers (mock | real names) ---
    asr_provider: Literal["mock", "indicconformer"] = "mock"
    llm_provider: Literal["mock", "param1"] = "mock"
    translation_provider: Literal["mock", "indictrans2"] = "mock"

    # --- Model configuration (real providers) ---
    model_device: Literal["auto", "cpu", "cuda"] = "auto"
    indicconformer_checkpoint: str = ""  # path to .nemo file
    indicconformer_multilingual: bool = True
    param1_model_id: str = "bharatgenai/Param-1-2.9B-Instruct"
    param1_max_input_tokens: int = 3072
    param1_max_new_tokens_notes: int = 1600
    param1_max_new_tokens_quiz: int = 1400
    param1_temperature: float = 0.2
    indictrans_en_indic_model: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    indictrans_indic_en_model: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    indictrans_indic_indic_model: str = "ai4bharat/indictrans2-indic-indic-dist-320M"
    translation_chunk_chars: int = 800

    # Optional remote GPU inference endpoints (http). When set, real providers
    # call this URL instead of loading weights locally.
    asr_remote_url: str = ""
    llm_remote_url: str = ""
    translation_remote_url: str = ""

    # --- LLM generation ---
    generation_language: Literal["en"] = "en"  # Param-1 canonical output language
    quiz_retry_attempts: int = 2
    job_timeout_seconds: int = 1800

    # --- Misc ---
    log_level: str = "INFO"

    @field_validator("storage_root", mode="after")
    @classmethod
    def _abs_storage(cls, v: Path) -> Path:
        return Path(v).expanduser().resolve()

    @property
    def uploads_dir(self) -> Path:
        return self.storage_root / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.storage_root / "processed"

    @property
    def exports_dir(self) -> Path:
        return self.storage_root / "exports"

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_audio_extensions.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
