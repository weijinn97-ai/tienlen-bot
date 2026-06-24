from __future__ import annotations

from typing import Mapping

import requests

from configs.agent_config import FREE_API_CONFIG


class FreeAPIConfigurationError(RuntimeError):
    pass


class FreeAPIAgent:
    def __init__(self, config: Mapping[str, str] | None = None):
        resolved_config = dict(FREE_API_CONFIG if config is None else config)
        self.api_key = str(resolved_config.get("api_key", "")).strip()
        self.endpoint = str(resolved_config.get("endpoint", "")).strip()
        self.model = str(resolved_config.get("model", "gpt-nano-free")).strip() or "gpt-nano-free"

    def decide_action(self, game_state: dict) -> dict:
        """
        Decides the action to take based on the current game state using a free API.
        """
        self._validate_configuration()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "prompt": self._format_game_state_for_llm(game_state),
            "max_tokens": 100
        }
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            llm_response = response.json()
            # Parse LLM response to get the action
            action = self._parse_llm_response(llm_response)
            return action
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with Free API Agent: {e}")
            return {"action": "pass"} # Fallback action

    def _validate_configuration(self) -> None:
        missing_fields = []
        if not self.api_key:
            missing_fields.append("api_key")
        if not self.endpoint:
            missing_fields.append("endpoint")

        if missing_fields:
            joined_fields = ", ".join(missing_fields)
            raise FreeAPIConfigurationError(
                "Free API Agent is not configured. Missing "
                f"{joined_fields}. Set TIENLEN_FREE_API_KEY and "
                "TIENLEN_FREE_API_ENDPOINT or update FREE_API_CONFIG."
            )

    def _format_game_state_for_llm(self, game_state: dict) -> str:
        """
        Formats the game state into a prompt string for the LLM.
        """
        # Example formatting - this will need to be more sophisticated
        prompt = f"Current game state: {game_state}\nWhat cards should I play?"
        return prompt

    def _parse_llm_response(self, llm_response: dict) -> dict:
        """
        Parses the LLM's response to extract the action.
        """
        # Example parsing - this will depend on the LLM's output format
        # Assume LLM returns something like {"choices": [{"text": "play 3_spades, 4_hearts"}]}
        text_response = llm_response.get("choices", [{}])[0].get("text", "pass")
        if "play" in text_response:
            cards_to_play = text_response.replace("play ", "").split(", ")
            return {"action": "play", "cards": cards_to_play}
        return {"action": "pass"}
