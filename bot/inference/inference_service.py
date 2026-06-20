from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from threading import Event, Thread
import time
from typing import Any, Mapping, Protocol

from bot.runtime.schemas import FrameEnvelope


@dataclass(frozen=True)
class InferenceJob:
    frame: FrameEnvelope
    metadata: Mapping[str, Any] = field(default_factory=dict)
    submitted_ns: int = field(default_factory=time.monotonic_ns)


@dataclass(frozen=True)
class InferenceResult:
    bot_id: str
    frame_id: str
    sequence: int
    output: Mapping[str, Any]
    latency_ms: float


class InferenceBackend(Protocol):
    def infer(self, image: Any, metadata: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class NullInferenceBackend:
    def infer(self, image: Any, metadata: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "noop", "metadata": dict(metadata)}


class InferenceService:
    def __init__(
        self,
        backend: InferenceBackend | None = None,
        *,
        max_queue_size: int = 16,
        worker_count: int = 1,
    ) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive.")
        if worker_count < 1:
            raise ValueError("worker_count must be positive.")

        self.backend = backend or NullInferenceBackend()
        self._jobs: Queue[tuple[InferenceJob, Future]] = Queue(maxsize=max_queue_size)
        self._stop_event = Event()
        self._workers = [
            Thread(target=self._worker_loop, name=f"inference-{index}", daemon=True)
            for index in range(worker_count)
        ]
        for worker in self._workers:
            worker.start()

    def submit(
        self,
        frame: FrameEnvelope,
        *,
        metadata: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Future:
        future: Future = Future()
        job = InferenceJob(frame=frame, metadata=metadata or {})
        try:
            self._jobs.put((job, future), timeout=timeout)
        except Full as exc:
            raise RuntimeError("Inference queue is full.") from exc
        return future

    def stop(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=1)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job, future = self._jobs.get(timeout=0.1)
            except Empty:
                continue

            if future.cancelled():
                self._jobs.task_done()
                continue

            started_ns = time.monotonic_ns()
            try:
                output = self.backend.infer(job.frame.image, job.metadata)
                latency_ms = (time.monotonic_ns() - started_ns) / 1_000_000
                future.set_result(
                    InferenceResult(
                        bot_id=job.frame.bot_id,
                        frame_id=job.frame.frame_id,
                        sequence=job.frame.sequence,
                        output=output,
                        latency_ms=latency_ms,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive path
                future.set_exception(exc)
            finally:
                self._jobs.task_done()
