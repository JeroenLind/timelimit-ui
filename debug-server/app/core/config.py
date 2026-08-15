from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )

    # Project settings
    PROJECT_NAME: str = "Debug Server"
    API_V1_STR: str = ""

    # Server settings
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080

    # JWT / Authentication settings
    SECRET_KEY: str  # Required, no default
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Security settings
    BCRYPT_COST: int = 12
    ENABLE_HTTPS: bool = False

    # Mock data settings
    MOCK_DATA_SEED: int = 42
    MOCK_FAMILY_COUNT: int = 1
    MOCK_CHILD_COUNT: int = 2
    MOCK_DEVICE_COUNT: int = 3
    MOCK_CATEGORY_COUNT: int = 3
    MOCK_APP_COUNT: int = 10

    # WebSocket settings
    ENABLE_WEBSOCKET: bool = True
    LONGPOLL_TIMEOUT_SECONDS: int = 25

    # Rate limiting settings
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    # Test mode settings
    TEST_MODE: bool = False

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/debug-server.log"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5
    LOG_FORMAT: str = "json"
    
    # Log retention settings
    MAX_LOG_FILES: int = 10  # Maximum number of log files to retain on startup

    # Message logging settings (for outgoing message logging)
    MESSAGE_LOGGING_ENABLED: bool = True
    MESSAGE_LOGGING_ASYNC: bool = True
    MESSAGE_LOGGING_LEVEL: str = "INFO"
    MESSAGE_LOGGING_MAX_BUFFER_SIZE: int = 1000
    MESSAGE_LOGGING_SANITIZE: bool = True


settings = Settings()