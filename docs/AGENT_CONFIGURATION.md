# AI Agent Configuration and Usage Guide

This document provides instructions on how to configure and utilize the hybrid AI agent architecture within the Tiến Lên Bot project. The bot supports both a Free API Agent (leveraging external LLMs) and a Local Agent (rule-based or small ML model) for decision-making.

## 1. Agent Configuration (`configs/agent_config.py`)

The primary configuration for selecting and setting up the agents is located in `configs/agent_config.py`.

```python
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
```

### Key Configuration Parameters:

*   **`USE_LOCAL_AGENT`**: Set to `True` to activate the `LocalAgent`. Set to `False` to activate the `FreeAPIAgent`.
*   **`FREE_API_CONFIG`**: A dictionary containing parameters for the Free API Agent:
    *   `api_key`: Your API key for the chosen free LLM service. **Replace `"YOUR_FREE_API_KEY"` with your actual key.**
    *   `endpoint`: The API endpoint URL for the LLM service.
    *   `model`: The specific model name to be used (e.g., `gpt-nano-free`).
*   **`LOCAL_AGENT_CONFIG`**: A dictionary containing parameters for the Local Agent:
    *   `model_path`: Path to a pre-trained local machine learning model (e.g., a `.pt` file for a small neural network).
    *   `rules_config`: Path to a JSON file containing rules for a rule-based agent.
*   **`ENABLE_FALLBACK`**: If `True`, the `DecisionOrchestrator` will automatically switch to the `LocalAgent` if the `FreeAPIAgent` encounters an error or times out. This enhances the bot's stability and resilience.

## 2. Free API Agent Usage

To use the `FreeAPIAgent`:

1.  Set `USE_LOCAL_AGENT = False` in `configs/agent_config.py`.
2.  Update `FREE_API_CONFIG` with your actual API key, endpoint, and model details. You will need to sign up for a free-tier LLM service (e.g., some community-driven open-source LLM APIs, or free trial tiers of commercial services) and obtain the necessary credentials.
3.  Ensure your system has `requests` library installed (`pip install requests`).
4.  The `FreeAPIAgent` will format the game state into a prompt and send it to the configured LLM API. The LLM's response will then be parsed to determine the bot's action.

**Note:** The effectiveness and reliability of the `FreeAPIAgent` heavily depend on the chosen LLM service's performance, rate limits, and the quality of the prompt engineering.

## 3. Local Agent Usage

To use the `LocalAgent`:

1.  Set `USE_LOCAL_AGENT = True` in `configs/agent_config.py`.
2.  **For Rule-based Agent:**
    *   Create a `rules.json` file (or similar) in the `configs/` directory, defining the game-playing rules. Update `LOCAL_AGENT_CONFIG["rules_config"]` to point to this file.
    *   The `LocalAgent` (specifically, its `decide_action` method) will need to be implemented to interpret these rules and make decisions based on the `game_state`.
3.  **For Small ML Model Agent:**
    *   Train a small, efficient machine learning model (e.g., a simple neural network) on game data. Save its weights (e.g., `local_agent_model.pt`) in the `models/` directory.
    *   Update `LOCAL_AGENT_CONFIG["model_path"]` to point to your trained model.
    *   The `LocalAgent`'s `decide_action` method will need to load and run inference with this model.

**Advantages of Local Agent:**

*   **Cost-effective:** No external API calls, saving money.
*   **Low Latency:** Decisions are made locally, leading to faster response times.
*   **Reliability:** Not dependent on external services or internet connectivity.

**Disadvantages:**

*   **Complexity:** Requires more effort to develop and maintain the game logic or train a custom model.
*   **Performance:** May not achieve the same strategic depth as a sophisticated LLM.

## 4. Game State Adapter

The `GameStateAdapter` module (`bot/agent/game_state_adapter.py`) is crucial for both agents. It standardizes the raw game state (detected cards, OCR results) into a consistent format that both the `FreeAPIAgent` and `LocalAgent` can understand. This abstraction ensures that changes in the recognition layer do not directly impact the agent's logic.

## 5. Action Executor

The `ActionExecutor` module (`bot/agent/action_executor.py`) translates the agent's decision (e.g., "play 3_spades") into actual ADB commands to interact with the MEmu emulator. This involves mapping card names to screen coordinates and simulating taps or swipes. This module will be integrated with the screen capture and recognition components to perform actions effectively.
