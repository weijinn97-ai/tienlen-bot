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

**The action buttons decide. The gold ring may only veto.**

The game shows "Đánh" or "Bỏ Lượt" only on the player's own turn, which makes
them the strongest signal available. The repository's `HybridTurnOwnerDetector`
instead confirms the avatar highlight against a card-count delta, which needs the
opponents' counts read off the screen — the bot does not read them yet.

Measured over 582 frames (221 staged, 361 live):

| gate | frames judged to be our turn |
|---|---|
| ring says SELF **and** a button is visible | 107 |
| a button is visible | 165 |
| **a button is visible, unless the ring names another seat** | **164** |

| | count | consequence |
|---|---|---|
| button visible, ring undecided | **57** | requiring the ring forfeits these |
| button visible, ring names another seat | 1 | the veto, and its whole value |
| ring says SELF, no button | 5 | not our turn; all three gates block |

### Correction

The first version of this module required both signals. That was measured on the
221 staged frames alone, where the ring is reliable; across the live corpus it is
undecided on **57 of the 165 frames that show an action button**, so the
conjunctive gate forfeited about **35% of the bot's turns**. A forfeited turn is
auto-played — the exact failure this loop exists to prevent. The defect was found
by running the loop live: it sat still on a frame where both "Đánh" and "Bỏ Lượt"
were visible and enabled.

The ring's remaining job is the veto, worth 1 frame in 582. It is kept because it
costs nothing and guards against a stale or transitional button.

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
| Frames judged to be the bot's turn | 164 (37.6%) |
| Frames in auto-play, recovery offered | 76 |
| Complete tap plans built and executed against a recording controller | 62 |
| Taps per plan | 1.97 mean, 5 max |
| **Plans naming a card the hand does not hold** | **0** |
| Latency p50 / p95 | 50.7 ms / 68.9 ms (0.57% of the 12 s turn budget) |

Where frames stop:

| Reason | Frames |
|---|---|
| `not_my_turn` | 218 |
| `auto_play_engaged` | 76 |
| `lead_single` (acted) | 69 |
| `invalid_target_combo` | 41 |
| `no_legal_response` (passed) | 17 |
| `unplannable` | 8 |
| `respond_single` / `respond_straight` / `respond_four_of_a_kind` (acted) | 13 |

## 6. Running it against a live emulator

```
py -3 tools/run_turn_loop.py --serial 127.0.0.1:23523            # dry run
py -3 tools/run_turn_loop.py --serial 127.0.0.1:23523 --act      # plays
```

Dry run reads the screen, decides, prints the decision and taps nothing. `--act`
lets it play and wires `refresh_snapshot`, which is what closes the disabled-
button gap in §6.

**Auto-play recovery follows `--act`, deliberately.** Taking the turn back and
then not playing it just lets the clock run out and auto-play re-engage, one
round poorer. Cancelling is only an improvement if something is going to play the
turn, so a dry run reports the state and leaves it alone.

Capture is `adb exec-out screencap`, which the architecture rules bar from the
production hot path. This is an operator tool; the runtime capture path stays
Windows-side and HWND-bound.

## 7. Known limits

- **`invalid_target_combo`, 41 frames.** The table cards that were read do not
  form a legal Tien Len combo, so the bot cannot judge what it must beat and
  waits. This is downstream of table recall (80.4%), not a rules bug: a partial
  read of a five-card straight is not a combo.
- **20 frames needed a re-read before the final tap.** `ActionPlanBuilder`
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
