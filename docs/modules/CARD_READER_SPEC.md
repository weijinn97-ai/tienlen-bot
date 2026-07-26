# Card Reader Module — Interface Specification

Status: `IMPLEMENTED — table zone usable, hand zone precision-only`
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

**Both zones are read, with different pipelines.** Table cards are flat and
axis-aligned. Hand cards render ~1.6x larger, are rotated into a fan (measured
-8.8 to +2.9 degrees across 13 cards) and are clipped by the bottom of the
screen, so their box height is not the card height. Each hand card is deskewed by
the angle of its own top edge, then matched against a separate template bank -
reusing the flat table templates on hand glyphs scores 0/13.

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

## 6. Accuracy

### Implementation

`bot/perception/card_reader.py` matches the corner index against a template bank
of 13 rank and 4 suit glyphs shipped as `card_templates.npz` (6 KB). The game
renders cards as fixed sprites, so a template built from real examples matches
later occurrences exactly. There is no model and no training.

Templates are built differently per glyph type, for a measured reason:

- **Ranks: medoid.** Averaging several examples blurred the glyphs badly - the
  `9` template was 47.5% ambiguous pixels and was consistently misread as `Q`.
  Taking the single most representative example dropped that to 12.1%.
- **Suits: mean.** Suit glyphs vary more within a class (hearts spread 0.156
  against ~0.09 elsewhere), so a single example rejected correct reads.

Suits are decided by colour first, which removes red/black confusion entirely
(51/51 correct on the labelled set), then by margin between the two remaining
candidates rather than absolute distance.

### Measured, on 51 hand-transcribed table cards

| Metric | Value |
|---|---|
| Precision | **100.0%** (41 correct, 0 wrong) |
| Recall | 80.4% (10 refused) |

### Label-free check over all 221 staged frames

| Metric | Value |
|---|---|
| Frames with table cards | 110 |
| Cards read | 427 |
| **Frames containing a duplicate card** | **0 (0.0%)** |

A frame that reports the same physical card twice is provably wrong without
needing ground truth, so this is an error lower bound measured on the whole
corpus rather than a sample. It was 26.16% before thresholding and is now zero.

### Hand zone, measured

| Metric | Value |
|---|---|
| Precision (37 transcribed hand cards) | **100.0%** (12 correct, 0 wrong) |
| Recall | **32.4%** |

Label-free check, using the fact that the game displays a hand sorted by Tien Len
strength — any hand returned out of order is provably wrong:

| Metric | Value |
|---|---|
| Frames with hand cards | 147 |
| **Hands returned out of sort order** | **0 (0.0%)** |
| Frames with a duplicate hand card | 0 |

The hand zone uses a stricter suit margin than the table (0.09 vs 0.015). At the
table's value the hand reads 91.7% precision with 6.2% of hands out of order;
0.09 is the first value reaching 100% precision and zero order violations, at the
cost of recall falling from 59.5% to 32.4%.

**Hand recall is not good enough to drive play.** At 32.4% the bot sees roughly 2
of its 13 cards. It cannot choose a move from that. Raising hand recall while
holding precision is the next piece of work, and it needs better hand suit
templates rather than more frames.

### Gates not yet met

`docs/TRAINING_PLAN_FINAL.md` requires precision/recall >= 0.98 and exact combo
>= 97% for the table. Precision is met; **recall at 80.4% is not**, and exact-set
accuracy is unmeasured. This reader is not qualified for production play.

The 51-card labelled set is also small and was used to pick thresholds, so the
precision figure is in-sample. An owner-locked evaluation set is still required
before any production claim.

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
