import requests
from configs.agent_config import FREE_API_CONFIG

class FreeAPIAgent:
    def __init__(self):
        self.api_key = FREE_API_CONFIG["api_key"]
        self.endpoint = FREE_API_CONFIG["endpoint"]
        self.model = FREE_API_CONFIG["model"]

    def decide_action(self, game_state: dict) -> dict:
        """
        Decides the action to take based on the current game state using a free API.
        """
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

