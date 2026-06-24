import os


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


# Set to True to use the local agent, False to use the free API agent.
USE_LOCAL_AGENT = _env_flag("TIENLEN_USE_LOCAL_AGENT", True)

# Configuration for Free API Agent. Prefer environment variables for secrets.
FREE_API_CONFIG = {
    "api_key": os.getenv("TIENLEN_FREE_API_KEY", "").strip(),
    "endpoint": os.getenv("TIENLEN_FREE_API_ENDPOINT", "").strip(),
    "model": os.getenv("TIENLEN_FREE_API_MODEL", "gpt-nano-free").strip() or "gpt-nano-free",
}

# Configuration for Local Agent (e.g., path to local model, rule-based parameters)
LOCAL_AGENT_CONFIG = {
    "model_path": os.getenv("TIENLEN_LOCAL_MODEL_PATH", "models/local_agent_model.pt"),
    "rules_config": os.getenv("TIENLEN_LOCAL_RULES_CONFIG", "configs/local_agent_rules.json"),
}

# Fallback mechanism: If True, local agent will be used if free API agent fails or times out.
ENABLE_FALLBACK = _env_flag("TIENLEN_ENABLE_FALLBACK", True)
