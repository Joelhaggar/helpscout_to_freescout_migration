"""
Configuration module for Help Scout to FreeScout migration.
Loads environment variables and provides configuration settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)


class Config:
    """Configuration settings for the migration tool."""

    # Help Scout Configuration
    HELPSCOUT_CLIENT_ID = os.getenv('Helpscout_client_id')
    HELPSCOUT_CLIENT_SECRET = os.getenv('Helpscout_client_secret')
    HELPSCOUT_API_BASE = 'https://api.helpscout.net/v2'
    HELPSCOUT_TOKEN_URL = 'https://api.helpscout.net/v2/oauth2/token'

    # FreeScout Configuration
    FREESCOUT_API_KEY = os.getenv('Freescout_APIKey')
    FREESCOUT_URL = os.getenv('Freescout_URL', 'http://localhost:8000')

    # Add protocol if missing
    if not FREESCOUT_URL.startswith('http'):
        FREESCOUT_URL = f'http://{FREESCOUT_URL}'

    # Rate Limiting
    RATE_LIMIT_DELAY = 0.5  # seconds between API calls (Help Scout)
    HELPSCOUT_RATE_LIMIT = 0.5  # Help Scout: 12 req/5sec, 200 req/min
    FREESCOUT_RATE_LIMIT = 0.0  # FreeScout: local, no rate limit needed

    # Logging
    LOG_DIR = project_root / 'logs'
    LOG_FILE = LOG_DIR / 'migration.log'
    ERROR_LOG_FILE = LOG_DIR / 'errors.log'

    # Output
    OUTPUT_DIR = project_root / 'output'
    CUSTOMER_ID_MAP_FILE = OUTPUT_DIR / 'customer_id_map.json'
    CONVERSATION_ID_MAP_FILE = OUTPUT_DIR / 'conversation_id_map.json'

    # Mapping files
    USER_MAPPING_FILE = project_root / 'config' / 'user_mapping.json'
    MAILBOX_MAPPING_FILE = project_root / 'config' / 'mailbox_mapping.json'

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []

        if not cls.HELPSCOUT_CLIENT_ID:
            errors.append("Helpscout_client_id not found in .env")

        if not cls.HELPSCOUT_CLIENT_SECRET:
            errors.append("Helpscout_client_secret not found in .env")

        if not cls.FREESCOUT_API_KEY:
            errors.append("Freescout_APIKey not found in .env")

        if not cls.FREESCOUT_URL:
            errors.append("Freescout_URL not found in .env")

        if errors:
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return True

    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        cls.LOG_DIR.mkdir(exist_ok=True)
        cls.OUTPUT_DIR.mkdir(exist_ok=True)


# Validate configuration on import
try:
    Config.validate()
    Config.ensure_directories()
except ValueError as e:
    print(f"Configuration Error: {e}")
    raise
