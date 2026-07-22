# Known Failures and Limitations

## Status: No blocking failures

All 170 unit and integration tests pass cleanly.

## Known Risks and Wire Validation Behavior

- **Strict Wire Validation**:
  - JSON non-finite constants (`NaN`, `Infinity`, `-Infinity`) are strictly rejected via `parse_constant` callback.
  - Direct Python dict values `float("nan")`, `float("inf")`, `float("-inf")` in confidence fields raise `ValueError`.
  - `schema_version=True` (boolean `True`) raises `TypeError` because `type(True)` is `bool`.
  - `player_card_counts` requires key `in {"0", "1", "2", "3"}`; keys like `"00"`, `"4"`, `"SELF"` raise `ValueError`. Count values must be `int` (`0 <= count <= 13`); boolean `True` raises `TypeError`.
  - `ButtonState.button_id` must be string; `ActionPlan.target_button` must be string or `None`. Objects/lists/numerics/booleans raise `TypeError`.
  - Integer fields (e.g., `frame_ts`, `x`, `y`, `width`, `height`, `timeout_ms`, `max_retries`) enforce `type(val) is int` to strictly reject booleans.

## Accepted Limitations

- Serialization format uses compact JSON (no pretty-print). This is intentional for determinism and replay compatibility.
- Unknown string values for `button_id` and `target_button` are preserved as string rather than raising an error, allowing forward compatibility for custom buttons.

## Out of Scope

- No changes to `contracts/interfaces.py` semantics.
- No changes to module registry or status (`MOD-CONTRACTS` remains `CANDIDATE`).
- No new external dependencies added.
