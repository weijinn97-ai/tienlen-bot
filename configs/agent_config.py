# Agent Configuration

# Set to True to use the local agent, False to use the free API agent.
USE_LOCAL_AGENT = True

# Configuration for Free API Agent (e.g., LLM API key, endpoint)
FREE_API_CONFIG = {
    "api_key": "YOUR_FREE_API_KEY",
    "endpoint": "https://api.example.com/free-llm",
    "model": "gpt-nano-free" # Example free model
}

# Configuration for Local Agent (e.g., path to local model, rule-based parameters)
LOCAL_AGENT_CONFIG = {
    "model_path": "models/local_agent_model.pt", # Path to a small local ML model
    "rules_config": "configs/local_agent_rules.json" # Path to rule-based configuration
}

# Fallback mechanism: If True, local agent will be used if free API agent fails or times out.
ENABLE_FALLBACK = True
