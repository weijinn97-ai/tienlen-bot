class GameStateAdapter:
    def __init__(self):
        pass

    def adapt_state(self, raw_game_state: dict) -> dict:
        """
        Converts the raw recognized game state into a standardized format
        that can be consumed by AI agents.
        
        raw_game_state is expected to contain:
        - 'hand_cards': list of detected cards in player's hand (e.g., ['3_spades', '4_hearts'])
        - 'selected_cards': list of cards currently selected by player
        - 'played_cards': list of cards played by opponents (e.g., {'player1': ['A_spades'], 'player2': []})
        - 'current_turn_player': ID of the player whose turn it is
        - 'last_played_combo': The last combo played on the table
        - 'num_players': Total number of players in the game
        - 'room_id', 'bet_amount', etc. (from OCR)
        """
        # This is a simplified example. Real implementation will involve more complex parsing
        # and structuring based on the game rules and agent requirements.
        
        adapted_state = {
            "my_hand": raw_game_state.get("hand_cards", []),
            "my_selected_cards": raw_game_state.get("selected_cards", []),
            "last_played_cards": raw_game_state.get("last_played_combo", []),
            "current_player_turn": raw_game_state.get("current_turn_player", ""),
            "players_info": raw_game_state.get("players_info", {}), # e.g., {'player_id': {'cards_left': 5}}
            "num_players": raw_game_state.get("num_players", 4),
            # Add other relevant game state information
        }
        return adapted_state
