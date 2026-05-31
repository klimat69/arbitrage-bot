from dotenv import load_dotenv
import os

from typing import Optional

load_dotenv()  # tự động load từ .env vào os.environ

def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)
