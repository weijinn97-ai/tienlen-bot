import unittest

from bot.runtime.bot_supervisor import BotSupervisor, ResourceLimits
from bot.runtime.schemas import BotBinding


class StubMonitor:
    def get_system_metrics(self) -> dict[str, float]:
        return {"cpu_percent": 10.0, "ram_percent": 20.0}


class BotSupervisorTests(unittest.TestCase):
    def test_duplicate_hwnd_is_rejected(self) -> None:
        supervisor = BotSupervisor(
            resource_limits=ResourceLimits(max_active_bots=2),
            system_monitor=StubMonitor(),
        )
        supervisor.register_binding(
            BotBinding(
                bot_id="bot-1",
                hwnd=100,
                adb_serial="127.0.0.1:7555",
                pid=500,
            )
        )

        with self.assertRaises(ValueError):
            supervisor.register_binding(
                BotBinding(
                    bot_id="bot-2",
                    hwnd=100,
                    adb_serial="127.0.0.1:7556",
                    pid=501,
                )
            )

    def test_admission_control_uses_limits(self) -> None:
        supervisor = BotSupervisor(
            resource_limits=ResourceLimits(max_active_bots=1),
            system_monitor=StubMonitor(),
        )
        supervisor.register_binding(
            BotBinding(
                bot_id="bot-1",
                hwnd=100,
                adb_serial="127.0.0.1:7555",
                pid=500,
            )
        )

        self.assertTrue(supervisor.can_start_new_bot())


if __name__ == "__main__":
    unittest.main()
