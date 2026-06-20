from configs.agent_config import LOCAL_AGENT_CONFIG

class LocalAgent:
    def __init__(self):
        self.model_path = LOCAL_AGENT_CONFIG["model_path"]
        self.rules_config = LOCAL_AGENT_CONFIG["rules_config"]
        # Load local model or rules here
        print(f"Local Agent initialized with model: {self.model_path} and rules: {self.rules_config}")

    def decide_action(self, game_state: dict) -> dict:
        """
        Decides the action to take based on the current game state using local logic.
        This can be a rule-based system or a small, pre-trained ML model.
        """
        # Example: Simple rule-based logic
        cards_in_hand = game_state.get("my_hand", [])
        last_played_cards = game_state.get("last_played_cards", [])

        if not cards_in_hand:
            return {"action": "pass"}

        # Simple logic: play the smallest single card if possible, otherwise pass
        if not last_played_cards:
            # If it's the first turn or after a pass, play the smallest card
            if cards_in_hand:
                smallest_card = sorted(cards_in_hand, key=self._card_value)[0]
                return {"action": "play", "cards": [smallest_card]}
        else:
            # Try to beat the last played cards with a single card
            if len(last_played_cards) == 1:
                last_card_value = self._card_value(last_played_cards[0])
                playable_cards = [c for c in cards_in_hand if self._card_value(c) > last_card_value]
                if playable_cards:
                    smallest_playable = sorted(playable_cards, key=self._card_value)[0]
                    return {"action": "play", "cards": [smallest_playable]}

        return {"action": "pass"}

    def _card_value(self, card_str: str) -> int:
        """
        Helper to get a numerical value for a card for comparison.
        (This is a simplified example and needs proper implementation for Tien Len rules)
        """
        rank_map = {
            "3": 0, "4": 1, "5": 2, "6": 3, "7": 4, "8": 5, "9": 6, "10": 7,
            "J": 8, "Q": 9, "K": 10, "A": 11, "2": 12
        }
        suit_map = {"clubs": 0, "diamonds": 1, "hearts": 2, "spades": 3}

        rank_char = card_str.split("_")[0]
        suit_char = card_str.split("_")[1]

        rank_val = rank_map.get(rank_char, -1)
        suit_val = suit_map.get(suit_char, -1)

        return rank_val * 4 + suit_val # Combine rank and suit for unique value
