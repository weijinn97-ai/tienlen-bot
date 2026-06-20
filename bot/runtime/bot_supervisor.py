from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Process
from typing import Callable

from bot.runtime.schemas import BotBinding
from bot.stability.system_monitor import SystemMonitor


@dataclass(frozen=True)
class ResourceLimits:
    max_active_bots: int
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 85.0


@dataclass
class ManagedBot:
    binding: BotBinding
    process: Process | None = None


class BotSupervisor:
    def __init__(
        self,
        *,
        resource_limits: ResourceLimits | None = None,
        system_monitor: SystemMonitor | None = None,
    ) -> None:
        self.resource_limits = resource_limits or ResourceLimits(max_active_bots=1)
        self.system_monitor = system_monitor or SystemMonitor(interval=0)
        self._registry: dict[str, ManagedBot] = {}

    def register_binding(self, binding: BotBinding) -> None:
        self._ensure_unique_binding(binding)
        self._registry[binding.bot_id] = ManagedBot(binding=binding)

    def bindings(self) -> list[BotBinding]:
        return [managed.binding for managed in self._registry.values()]

    def can_start_new_bot(self) -> bool:
        active_count = sum(
            1
            for managed in self._registry.values()
            if managed.process is not None and managed.process.is_alive()
        )
        if active_count >= self.resource_limits.max_active_bots:
            return False

        metrics = self.system_monitor.get_system_metrics()
        return (
            metrics["cpu_percent"] <= self.resource_limits.max_cpu_percent
            and metrics["ram_percent"] <= self.resource_limits.max_ram_percent
        )

    def start_bot(
        self,
        bot_id: str,
        *,
        target: Callable[..., None],
        args: tuple = (),
    ) -> Process:
        if bot_id not in self._registry:
            raise KeyError(f"Unknown bot_id: {bot_id}")
        if not self.can_start_new_bot():
            raise RuntimeError("Admission control denied starting another bot.")

        managed = self._registry[bot_id]
        if managed.process is not None and managed.process.is_alive():
            raise RuntimeError(f"Bot {bot_id} is already running.")

        process = Process(
            target=target,
            args=(managed.binding, *args),
            name=f"bot-worker-{bot_id}",
        )
        process.start()
        managed.process = process
        return process

    def pause_bot(self, bot_id: str) -> None:
        managed = self._registry[bot_id]
        if managed.process is not None and managed.process.is_alive():
            managed.process.terminate()
            managed.process.join(timeout=2)
            managed.process = None

    def restart_bot(
        self,
        bot_id: str,
        *,
        target: Callable[..., None],
        args: tuple = (),
    ) -> Process:
        self.pause_bot(bot_id)
        return self.start_bot(bot_id, target=target, args=args)

    def identity_recheck(self, bot_id: str, observed_fingerprint: str | None) -> bool:
        managed = self._registry[bot_id]
        expected = managed.binding.identity_fingerprint
        if expected is None or observed_fingerprint is None:
            return True
        return expected == observed_fingerprint

    def _ensure_unique_binding(self, candidate: BotBinding) -> None:
        if candidate.bot_id in self._registry:
            raise ValueError(f"Duplicate bot_id: {candidate.bot_id}")

        for managed in self._registry.values():
            binding = managed.binding
            if binding.hwnd == candidate.hwnd:
                raise ValueError(f"HWND already bound to bot {binding.bot_id}")
            if binding.adb_serial == candidate.adb_serial:
                raise ValueError(f"ADB serial already bound to bot {binding.bot_id}")
            if binding.pid == candidate.pid:
                raise ValueError(f"PID already bound to bot {binding.bot_id}")
