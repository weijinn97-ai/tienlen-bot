from __future__ import annotations

try:
    import psutil
except ImportError:  # pragma: no cover - environment dependent
    psutil = None


class SystemMonitor:
    def __init__(self, interval: float = 1) -> None:
        self.interval = interval

    def get_system_metrics(self) -> dict[str, float]:
        if psutil is None:
            return {"cpu_percent": 0.0, "ram_percent": 0.0}

        cpu_percent = psutil.cpu_percent(interval=self.interval)
        ram_percent = psutil.virtual_memory().percent
        return {
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent,
        }

    def get_process_metrics(
        self,
        process_name: str | None = None,
        *,
        pid: int | None = None,
    ) -> dict[str, float | int | str] | None:
        if psutil is None:
            return None

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            info = proc.info
            if pid is not None and info["pid"] == pid:
                return {
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": info["cpu_percent"],
                    "memory_percent": info["memory_percent"],
                }
            if process_name and process_name.lower() in info["name"].lower():
                return {
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": info["cpu_percent"],
                    "memory_percent": info["memory_percent"],
                }
        return None
