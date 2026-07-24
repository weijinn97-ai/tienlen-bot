import signal
import unittest
from unittest.mock import Mock, patch

from bot.ui.process_control import creation_flags, force_stop, request_graceful_stop


class ProcessControlTests(unittest.TestCase):
    def test_windows_uses_new_process_group(self):
        with patch("bot.ui.process_control.os.name", "nt"), patch(
            "bot.ui.process_control.subprocess.CREATE_NEW_PROCESS_GROUP", 0x200, create=True
        ):
            self.assertEqual(creation_flags(), 0x200)

    def test_non_windows_has_no_creation_flags(self):
        with patch("bot.ui.process_control.os.name", "posix"):
            self.assertEqual(creation_flags(), 0)

    def test_running_windows_process_receives_ctrl_break(self):
        process = Mock()
        process.poll.return_value = None
        with patch("bot.ui.process_control.os.name", "nt"):
            self.assertEqual(request_graceful_stop(process), "signal_sent")
        process.send_signal.assert_called_once_with(
            getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM)
        )
        process.terminate.assert_not_called()

    def test_running_posix_process_receives_sigterm(self):
        process = Mock()
        process.poll.return_value = None
        with patch("bot.ui.process_control.os.name", "posix"):
            self.assertEqual(request_graceful_stop(process), "signal_sent")
        process.send_signal.assert_called_once_with(signal.SIGTERM)

    def test_signal_failure_falls_back_to_terminate(self):
        process = Mock()
        process.poll.return_value = None
        process.send_signal.side_effect = OSError("not supported")
        with patch("bot.ui.process_control.os.name", "posix"):
            self.assertEqual(request_graceful_stop(process), "terminate_sent")
        process.terminate.assert_called_once_with()

    def test_already_stopped_process_is_not_touched(self):
        process = Mock()
        process.poll.return_value = 0
        self.assertEqual(request_graceful_stop(process), "already_stopped")
        process.send_signal.assert_not_called()
        process.terminate.assert_not_called()

    def test_force_stop_only_kills_running_process(self):
        stopped = Mock()
        stopped.poll.return_value = 0
        self.assertFalse(force_stop(stopped))
        stopped.kill.assert_not_called()

        running = Mock()
        running.poll.return_value = None
        self.assertTrue(force_stop(running))
        running.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
