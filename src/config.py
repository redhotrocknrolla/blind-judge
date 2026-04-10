"""
Blind Judge — Config
Читает ~/.blind-judge/config.yaml или переменные окружения.
"""

import os
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "llm": {
        "base_url": "https://api.anthropic.com",
        "api_key": None,
        "model": "claude-haiku-4-5",
        "max_tokens": 4096,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 8080,
    },
    "parser": {
        "max_retries": 2,
        "double_check": False,
    }
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm"] = DEFAULT_CONFIG["llm"].copy()
    config["server"] = DEFAULT_CONFIG["server"].copy()
    config["parser"] = DEFAULT_CONFIG["parser"].copy()

    # Читаем файл если есть
    config_path = Path.home() / ".blind-judge" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            file_cfg = yaml.safe_load(f) or {}
        for section in ("llm", "server", "parser"):
            if section in file_cfg:
                config[section].update(file_cfg[section])

    # Переменные окружения перекрывают файл
    if os.environ.get("BLIND_JUDGE_LLM_BASE_URL"):
        config["llm"]["base_url"] = os.environ["BLIND_JUDGE_LLM_BASE_URL"]
    if os.environ.get("BLIND_JUDGE_LLM_API_KEY"):
        config["llm"]["api_key"] = os.environ["BLIND_JUDGE_LLM_API_KEY"]
    if os.environ.get("BLIND_JUDGE_LLM_MODEL"):
        config["llm"]["model"] = os.environ["BLIND_JUDGE_LLM_MODEL"]
    if os.environ.get("BLIND_JUDGE_PORT"):
        config["server"]["port"] = int(os.environ["BLIND_JUDGE_PORT"])

    # Fallback на стандартные ключи
    if not config["llm"]["api_key"]:
        config["llm"]["api_key"] = os.environ.get("ANTHROPIC_API_KEY") or \
                                    os.environ.get("OPENAI_API_KEY") or ""

    return config
