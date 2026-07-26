# Turn loop

Status: **IMPLEMENTED — decides, does not tap**

`bot/runtime/turn_loop.py`

## 1. Why it exists

Every part of this chain already existed and none of it was connected:

| Stage | Module | State before |
|---|---|---|
| frame → cards | `bot/perception/card_reader.py` | built, unwired |
| frame → buttons | `bot/perception/buttons.py` | built, unwired |
| → typed snapshot | `bot/perception/pipeline.py` | built, constructed only in tests |
| → table state | `bot/perception/table_state.py` | built, unwired |
| → decision | `bot/agent/local_agent.py`, `bot/rules/tien_len.py` | built, unwired |
| → tap plan | `bot/actions/action_pipeline.py` | built, unwired |

`PerceptionPipeline` was never constructed outside the test suite, and
`tools/run_bot_session.py` only watched ADB and window health. The repository
could read a frame, and could plan a tap, and could not get from one to the
other. This module is that join and nothing else.

## 2. Contract

```python
loop = TurnLoop(PerceptionPipeline(PerceptionAdapters(cards=CardReader(), buttons=...)))
outcome = loop.step(frame)          # frame: FrameEnvelope
```

`TurnOutcome` carries every stage plus where it stopped:

| Field | Meaning |
|---|---|
| `snapshot` | typed perception, `None` if the frame was rejected |
| `state` | `TableState` handed to the rules engine |
| `decision` | `{"action": play\|pass\|wait, ...}` — always has a `reason` |
| `plan` | `ActionPlan` ready for `ActionTapExecutor`, or `None` |
| `recovery` | a button that must be pressed before anything else means anything |
| `failures` | per-component adapter failures from the pipeline |

**It never taps.** Execution stays with `ActionTapExecutor`, which is what lets a
turn be replayed against recorded frames with no emulator attached.

## 3. The turn gate

Acting off-turn is worse than not acting, so ownership needs two signals.

The repository's `HybridTurnOwnerDetector` confirms the avatar highlight against
a card-count delta, which needs the opponents' counts read off the screen — the
bot does not read them yet. The action buttons are a better witness and are
already detected. Measured over 221 frames:

| | ring picks SELF | ring picks another seat | ring undecided |
|---|---|---|---|
| an action button is visible (111) | **107** | 1 | 3 |
| no action button (110) | 4 | 94 | 12 |

Requiring both removes the 4 frames where the ring alone would have acted
off-turn. A ring on another seat is reported as-is and never triggers an action,
so a second witness there would buy nothing.

## 4. Auto-play recovery

When a turn times out the game plays the hand itself and shows a **"Hủy tự
động"** button. While it is up, any decision made from the frame would be acted
on by nobody, so `step` returns early with `recovery` set and no plan. The caller
must tap it.

The button is drawn low and centred, over the fan, not in the action band — a
search window aimed at the action band misses it entirely. It has its own
`NormalizedRect(0.31, 0.75, 0.40, 0.23)`.

Separation is wide: on the 221 staged frames, which contain no auto-play, the
highest template score is **0.288**; on frames that do contain it the score is
**≥ 0.998**. The gate is 0.82.

Verified live: detected at (640, 620) with confidence 1.000, tapped, and the
button was gone on the next frame — the turn was taken back.

## 5. Measured

436 frames — 221 staged, 65 live, 150 captured during one live round:

| | |
|---|---|
| Frames judged to be the bot's turn | 107 (24.5%) |
| Frames in auto-play, recovery offered | 76 |
| Complete tap plans built and executed against a recording controller | 46 |
| Taps per plan | 1.70 mean, 5 max |
| **Plans naming a card the hand does not hold** | **0** |
| Latency p50 / p95 | 52.3 ms / 69.3 ms (0.58% of the 12 s turn budget) |

Where frames stop:

| Reason | Frames |
|---|---|
| `not_my_turn` | 253 |
| `auto_play_engaged` | 76 |
| `lead_single` (acted) | 42 |
| `invalid_target_combo` | 34 |
| `no_legal_response` (passed) | 17 |
| `unplannable` | 8 |
| `respond_single` / `respond_four_of_a_kind` (acted) | 6 |

## 6. Known limits

- **`invalid_target_combo`, 34 frames.** The table cards that were read do not
  form a legal Tien Len combo, so the bot cannot judge what it must beat and
  waits. This is downstream of table recall (80.4%), not a rules bug: a partial
  read of a five-card straight is not a combo.
- **19 frames needed a re-read before the final tap.** `ActionPlanBuilder`
  accepts a disabled "Đánh" button because selecting cards is what enables it,
  while `ActionTapExecutor` insists it be enabled. On a live bot the
  `refresh_snapshot` hook closes that gap; offline there is no second frame, so
  the executor refuses. Any runtime built on this loop must wire
  `refresh_snapshot`.
- **Confidence excludes the turn signals.** The gate decides whether to act; it
  is not evidence about how well the cards were read, so it is deliberately not
  folded into `snapshot.confidence`.
- **No consensus across frames.** `HybridTurnOwnerConsensus` and
  `TableStateConsensus` exist and are not used here. One frame, one decision.
