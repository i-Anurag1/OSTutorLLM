from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "ostutor-local-development-secret-change-in-production"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ostutor:ostutor@db:5432/ostutor"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_exp_minutes: int = 720
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen3:14b"
    llm_num_predict: int = 900
    llm_num_ctx: int = 4096
    llm_timeout: int = 300
    llm_temperature: float = 0.2
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    rag_dense_k: int = 24
    rag_sparse_k: int = 24
    rag_rerank_k: int = 12
    rag_final_k: int = 6
    cache_ttl_seconds: int = 900
    cors_origins: str = "http://localhost:3000"
    max_code_seconds: int = 3
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
