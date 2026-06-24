import importlib
import os
import unittest
from unittest import mock

import configs.agent_config as agent_config
from bot.agent.decision_orchestrator import DecisionOrchestrator
from bot.agent.free_api_agent import FreeAPIAgent, FreeAPIConfigurationError


class AgentConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in (
            "TIENLEN_USE_LOCAL_AGENT",
            "TIENLEN_ENABLE_FALLBACK",
            "TIENLEN_FREE_API_KEY",
            "TIENLEN_FREE_API_ENDPOINT",
            "TIENLEN_FREE_API_MODEL",
        ):
            os.environ.pop(name, None)
        importlib.reload(agent_config)

    def test_config_reads_environment_overrides(self) -> None:
        os.environ["TIENLEN_USE_LOCAL_AGENT"] = "false"
        os.environ["TIENLEN_ENABLE_FALLBACK"] = "0"
        os.environ["TIENLEN_FREE_API_KEY"] = "test-key"
        os.environ["TIENLEN_FREE_API_ENDPOINT"] = "https://example.test/free-llm"
        os.environ["TIENLEN_FREE_API_MODEL"] = "mini-model"

        reloaded = importlib.reload(agent_config)

        self.assertFalse(reloaded.USE_LOCAL_AGENT)
        self.assertFalse(reloaded.ENABLE_FALLBACK)
        self.assertEqual(reloaded.FREE_API_CONFIG["api_key"], "test-key")
        self.assertEqual(reloaded.FREE_API_CONFIG["endpoint"], "https://example.test/free-llm")
        self.assertEqual(reloaded.FREE_API_CONFIG["model"], "mini-model")


class FreeAPIAgentTests(unittest.TestCase):
    def test_decide_action_raises_clear_error_when_config_missing(self) -> None:
        agent = FreeAPIAgent(config={"api_key": "", "endpoint": "", "model": "mini-model"})

        with self.assertRaises(FreeAPIConfigurationError) as context:
            agent.decide_action({"my_hand": ["3_spades"]})

        self.assertIn("Missing api_key, endpoint", str(context.exception))

    def test_local_mode_does_not_create_free_api_agent(self) -> None:
        with mock.patch("bot.agent.decision_orchestrator.USE_LOCAL_AGENT", True):
            orchestrator = DecisionOrchestrator()
            orchestrator.game_state_adapter = mock.Mock(adapt_state=lambda state: state)
            orchestrator.local_agent = mock.Mock(decide_action=mock.Mock(return_value={"action": "pass"}))

            result = orchestrator.decide_action({})

        self.assertEqual(result, {"action": "pass"})
        self.assertIsNone(orchestrator.free_api_agent)

    def test_api_failure_falls_back_to_local_agent(self) -> None:
        with mock.patch("bot.agent.decision_orchestrator.USE_LOCAL_AGENT", False), mock.patch(
            "bot.agent.decision_orchestrator.ENABLE_FALLBACK", True
        ):
            orchestrator = DecisionOrchestrator()
            orchestrator.game_state_adapter = mock.Mock(adapt_state=lambda state: state)
            orchestrator.free_api_agent = mock.Mock(decide_action=mock.Mock(side_effect=RuntimeError("missing config")))
            orchestrator.local_agent = mock.Mock(
                decide_action=mock.Mock(return_value={"action": "play", "cards": ["3_spades"]})
            )

            result = orchestrator.decide_action({"my_hand": ["3_spades"]})

        self.assertEqual(result, {"action": "play", "cards": ["3_spades"]})
        orchestrator.local_agent.decide_action.assert_called_once_with({"my_hand": ["3_spades"]})
