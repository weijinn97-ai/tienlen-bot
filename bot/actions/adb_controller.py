from __future__ import annotations

import subprocess


class ADBController:
    def __init__(
        self,
        adb_path: str = "adb",
        device_id: str | None = None,
        *,
        verify_connection: bool = True,
        runner=subprocess.run,
    ) -> None:
        self.adb_path = adb_path
        self.device_id = device_id
        self._runner = runner
        if verify_connection:
            self._check_adb_connection()

    def build_command(self, command: list[str]) -> list[str]:
        full_command = [self.adb_path]
        if self.device_id:
            full_command.extend(["-s", self.device_id])
        full_command.extend(command)
        return full_command

    def run(self, command: list[str], timeout: int = 10) -> str:
        full_command = self.build_command(command)
        try:
            result = self._runner(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(exc.stderr.strip() or str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"ADB command timed out: {' '.join(full_command)}") from exc
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"ADB executable not found at {self.adb_path}."
            ) from exc

    def _check_adb_connection(self) -> None:
        devices = self.run(["devices"])
        if self.device_id and self.device_id not in devices:
            raise RuntimeError(
                f"Device {self.device_id} not found. Available devices:\n{devices}"
            )
        if not self.device_id and "device" not in devices:
            raise RuntimeError(
                "No ADB devices found. Ensure MEmu is running and ADB debugging is enabled."
            )

    def tap(self, x: int, y: int, *, timeout: int = 10) -> str:
        return self.run(["shell", "input", "tap", str(x), str(y)], timeout=timeout)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        duration: int = 200,
        timeout: int = 10,
    ) -> str:
        return self.run(
            [
                "shell",
                "input",
                "swipe",
                str(x1),
                str(y1),
                str(x2),
                str(y2),
                str(duration),
            ],
            timeout=timeout,
        )

    def send_text(self, text: str, *, timeout: int = 10) -> str:
        return self.run(["shell", "input", "text", text], timeout=timeout)

    def health_check(self, *, timeout: int = 5) -> str:
        return self.run(["shell", "echo", "ping"], timeout=timeout)
