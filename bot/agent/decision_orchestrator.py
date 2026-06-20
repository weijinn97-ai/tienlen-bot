from bot.agent.free_api_agent import FreeAPIAgent
from bot.agent.local_agent import LocalAgent
from bot.agent.game_state_adapter import GameStateAdapter
from configs.agent_config import USE_LOCAL_AGENT, ENABLE_FALLBACK

class DecisionOrchestrator:
    def __init__(self):
        self.game_state_adapter = GameStateAdapter()
        self.local_agent = LocalAgent()
        self.free_api_agent = FreeAPIAgent()

    def decide_action(self, raw_game_state: dict) -> dict:
        """
        Orchestrates the decision-making process, choosing between local and API agents.
        """
        adapted_game_state = self.game_state_adapter.adapt_state(raw_game_state)

        if USE_LOCAL_AGENT:
            print("Using Local Agent for decision.")
            action = self.local_agent.decide_action(adapted_game_state)
            return action
        else:
            print("Using Free API Agent for decision.")
            try:
                action = self.free_api_agent.decide_action(adapted_game_state)
                return action
            except Exception as e:
                print(f"Free API Agent failed: {e}")
                if ENABLE_FALLBACK:
                    print("Falling back to Local Agent.")
                    action = self.local_agent.decide_action(adapted_game_state)
                    return action
                else:
                    return {"action": "pass", "reason": "API Agent failed and fallback disabled"}
