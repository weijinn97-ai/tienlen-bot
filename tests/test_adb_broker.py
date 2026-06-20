import unittest

from bot.actions.adb_broker import AdbBroker


class FakeController:
    def __init__(self, adb_serial: str, recorder: list[tuple[str, list[str]]]) -> None:
        self.adb_serial = adb_serial
        self.recorder = recorder

    def run(self, command: list[str], timeout: int = 10) -> str:
        self.recorder.append((self.adb_serial, command))
        return "ok"


class AdbBrokerTests(unittest.TestCase):
    def test_broker_routes_commands_by_serial(self) -> None:
        recorder: list[tuple[str, list[str]]] = []

        def factory(adb_serial: str) -> FakeController:
            return FakeController(adb_serial, recorder)

        broker = AdbBroker(controller_factory=factory)
        try:
            first = broker.tap("127.0.0.1:7555", 10, 20)
            second = broker.send_text("127.0.0.1:7556", "hello")

            self.assertEqual(first.result(timeout=1), "ok")
            self.assertEqual(second.result(timeout=1), "ok")
        finally:
            broker.stop()

        self.assertEqual(
            recorder,
            [
                ("127.0.0.1:7555", ["shell", "input", "tap", "10", "20"]),
                ("127.0.0.1:7556", ["shell", "input", "text", "hello"]),
            ],
        )


if __name__ == "__main__":
    unittest.main()
