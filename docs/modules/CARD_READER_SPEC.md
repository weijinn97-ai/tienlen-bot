# Card Reader Module — Interface Specification

Status: `DRAFT — pending owner approval`
Owner-authorised: CUDA torch install, GTX 1650 reference device, per-machine device selection.

This document is the contract other agents work against. It defines the module
boundary only. It does not authorise training, and it does not claim accuracy
numbers that have not been measured.

## 1. Purpose

Read playing cards from a 1280x720 game frame and return typed detections. It is
the single source of card identity for the bot. Nothing downstream re-reads
pixels.

## 2. Module boundary

Path: `bot/perception/card_reader.py`

The module plugs into the existing `PerceptionPipeline` as its card adapter. The
pipeline already defines the required shape:

```python
cards = _validate_cards(self.adapters.cards.detect(image.copy()))
```

Therefore the public surface is exactly one method:

```python
class CardReader:
    def detect(self, image: np.ndarray) -> Sequence[DetectedCard]: ...
```

### Inputs

| Item | Type | Constraint |
|---|---|---|
| `image` | `np.ndarray` | BGR, shape `(720, 1280, 3)`, `uint8` |

The pipeline passes a defensive copy. The module MUST NOT mutate the array.

### Outputs

`Sequence[DetectedCard]` using the existing contract in `contracts/interfaces.py`:

```python
DetectedCard(code: str, roi: Rect, zone: CardZone, confidence: float, seat: SeatPosition | None)
```

- `code` — validated by `validate_card_code`; the 52-card taxonomy, e.g. `"3S"`, `"AH"`, `"10D"`.
- `roi` — `Rect(x, y, width, height)`, non-negative origin, positive size.
- `zone` — `CardZone.MY_HAND` / `CardZone.TABLE` / `CardZone.SELECTED`.
- `confidence` — `float` in `[0.0, 1.0]`.

The module MUST NOT return duplicate `(code, zone)` pairs for the same physical
card, and MUST NOT return more than 13 cards in `MY_HAND`.

## 3. Failure policy

The pipeline treats the adapter boundary as untrusted and already fails safe:

```python
except Exception as exc:  # adapter boundary must fail safe
    failures.append(PipelineFailure(FailureComponent.CARDS, type(exc).__name__))
```

Rules for this module:

- Return an empty sequence rather than a guess when the frame is unreadable.
- Never raise for ordinary low-confidence cases; drop the detection instead.
- Never block. No network calls, no disk writes on the hot path.
- Reject a frame whose shape is not `(720, 1280, 3)` by raising `ValueError`;
  the pipeline records it as a `CARDS` failure.

A dropped card is recoverable — the next frame retries. A wrong card is not:
it produces an illegal or losing play. Silence is preferred over confidence.

## 4. Device selection

Device is resolved **per machine**, not hardcoded:

1. Use CUDA when `torch.cuda.is_available()` and a device is present.
2. Otherwise fall back to CPU.
3. The resolved device MUST be logged once at construction and recorded in
   latency evidence.

Reference device for acceptance thresholds: **NVIDIA GeForce GTX 1650, 4 GB
VRAM, compute capability 7.5**, CUDA build `cu126`, driver 592.27.

### VRAM contention — known risk

The emulator shares the same GPU. `nvidia-smi` shows `MEmuHeadless.exe` resident
on device 0. Total VRAM is 4096 MiB for both the emulator and inference. Any
multi-bot deployment MUST measure VRAM headroom before scaling; this is not yet
measured and MUST NOT be assumed.

## 5. Latency budget

One turn allows 12 000 ms before the game auto-plays. Card reading is one step
inside that budget, alongside capture, decision, ADB tap and verification.

Measured values are recorded in `latency.json` and quoted in section 8. Evidence
MUST report warm-up, p50, p95 and p99 separately, per the training plan. Warm-up
is excluded from steady-state percentiles but MUST be reported, because the first
inference after process start is materially slower and would otherwise hide a
cold-start stall.

## 6. Accuracy thresholds

Inherited from `docs/TRAINING_PLAN_FINAL.md`. These are acceptance gates, not
current status:

| Zone | Precision / Recall | Exact-set |
|---|---|---|
| `MY_HAND` | >= 0.99 | exact hand >= 98% |
| `TABLE` | >= 0.98 | exact combo >= 97% |

No accuracy claim may be published without an owner-locked evaluation set. The
current dataset has **0 annotated images**, so no accuracy figure exists yet.

## 7. Test requirements

The module ships with tests covering, at minimum:

- happy path for each zone
- input array is not mutated
- wrong frame shape rejected
- low-confidence detection dropped, not guessed
- no duplicate `(code, zone)` output
- `MY_HAND` capped at 13
- deterministic ordering across repeated runs on the same frame
- device resolution falls back to CPU when CUDA is absent

Ordering must be stable so downstream diffing and replay stay reproducible; the
pipeline already sorts by zone, position and code.

## 8. Measured latency

Measured on 60 real 1280x720 frames, `imgsz=1280`, YOLO11n backbone. Raw output
in `card_reader_latency.json`. Reproduce with:

```
py -3 tools/bench_card_reader_latency.py --frames-dir <frames> --count 60
```

`<frames>` is a directory of raw capture frames, which live outside Git per the
training plan. The tool resolves the device itself, so the same command produces
CPU-only numbers on a machine without a GPU.

| Device | warm-up | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| `cuda:0` GTX 1650 | 2384.0 ms | 25.9 ms | 27.6 ms | **28.2 ms** | 33.5 ms |
| `cpu` (12 cores) | 184.5 ms | 132.2 ms | 142.3 ms | **144.8 ms** | 164.1 ms |

GPU is 5.2x faster than CPU at p95. Against the 12 000 ms turn budget:

- GPU p99 = 28.2 ms = **0.24%** of budget
- CPU p99 = 144.8 ms = **1.21%** of budget

Steady-state inference is not a bottleneck on either device. The CPU path is a
viable fallback, so a machine without a GPU is still supportable.

### Warm-up is the real latency risk

GPU warm-up costs **2384 ms — 19.9% of an entire turn** — while steady state
costs 28 ms. A cold first inference during live play burns a fifth of the
budget for that turn.

Therefore the module MUST expose an explicit warm-up performed before gameplay
starts, and MUST NOT lazily initialise on first `detect()`. Warm-up completion
is a precondition of the runtime's ready state, not a detail of the hot path.

Note the inversion: GPU warm-up (2384 ms) is 13x more expensive than CPU
warm-up (184 ms), so the faster device carries the larger cold-start penalty.

## 9. Out of scope

- Training and weight production — governed by `TRAINING_PLAN_FINAL.md`, still `BLOCKED_ON_DATA`.
- Combo classification — belongs to the rules layer, not perception.
- Turn ownership, buttons and OCR — separate adapters already exist.
- Any ADB action.
