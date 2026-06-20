from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Semaphore, Thread
from typing import Callable

from bot.actions.adb_controller import ADBController


@dataclass(frozen=True)
class AdbRequest:
    command: list[str]
    timeout: int = 10


class AdbBroker:
    def __init__(
        self,
        *,
        adb_path: str = "adb",
        per_serial_queue_size: int = 8,
        global_concurrent_limit: int = 2,
        controller_factory: Callable[[str], ADBController] | None = None,
    ) -> None:
        if per_serial_queue_size < 1:
            raise ValueError("per_serial_queue_size must be positive.")
        if global_concurrent_limit < 1:
            raise ValueError("global_concurrent_limit must be positive.")

        self.adb_path = adb_path
        self.per_serial_queue_size = per_serial_queue_size
        self._controller_factory = controller_factory or self._default_controller_factory
        self._global_gate = Semaphore(global_concurrent_limit)
        self._stop_event = Event()
        self._queues: dict[str, Queue[tuple[AdbRequest, Future]]] = {}
        self._threads: dict[str, Thread] = {}
        self._controllers: dict[str, ADBController] = {}

    def register_serial(self, adb_serial: str) -> None:
        if adb_serial in self._queues:
            return

        self._controllers[adb_serial] = self._controller_factory(adb_serial)
        queue: Queue[tuple[AdbRequest, Future]] = Queue(maxsize=self.per_serial_queue_size)
        self._queues[adb_serial] = queue
        thread = Thread(
            target=self._serial_worker,
            args=(adb_serial, queue),
            name=f"adb-{adb_serial}",
            daemon=True,
        )
        self._threads[adb_serial] = thread
        thread.start()

    def submit(
        self,
        adb_serial: str,
        command: list[str],
        *,
        timeout: int = 10,
        enqueue_timeout: float | None = None,
    ) -> Future:
        self.register_serial(adb_serial)
        future: Future = Future()
        request = AdbRequest(command=command, timeout=timeout)

        try:
            self._queues[adb_serial].put((request, future), timeout=enqueue_timeout)
        except Full as exc:
            raise RuntimeError(f"ADB queue for {adb_serial} is full.") from exc

        return future

    def tap(self, adb_serial: str, x: int, y: int, *, timeout: int = 10) -> Future:
        return self.submit(
            adb_serial,
            ["shell", "input", "tap", str(x), str(y)],
            timeout=timeout,
        )

    def swipe(
        self,
        adb_serial: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        duration: int = 200,
        timeout: int = 10,
    ) -> Future:
        return self.submit(
            adb_serial,
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

    def send_text(self, adb_serial: str, text: str, *, timeout: int = 10) -> Future:
        return self.submit(
            adb_serial,
            ["shell", "input", "text", text],
            timeout=timeout,
        )

    def health_check(self, adb_serial: str, *, timeout: int = 5) -> Future:
        return self.submit(adb_serial, ["shell", "echo", "ping"], timeout=timeout)

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads.values():
            thread.join(timeout=1)

    def _default_controller_factory(self, adb_serial: str) -> ADBController:
        return ADBController(
            adb_path=self.adb_path,
            device_id=adb_serial,
            verify_connection=False,
        )

    def _serial_worker(
        self,
        adb_serial: str,
        work_queue: Queue[tuple[AdbRequest, Future]],
    ) -> None:
        controller = self._controllers[adb_serial]
        while not self._stop_event.is_set():
            try:
                request, future = work_queue.get(timeout=0.1)
            except Empty:
                continue

            if future.cancelled():
                work_queue.task_done()
                continue

            try:
                with self._global_gate:
                    output = controller.run(request.command, timeout=request.timeout)
                future.set_result(output)
            except Exception as exc:  # pragma: no cover - defensive path
                future.set_exception(exc)
            finally:
                work_queue.task_done()
