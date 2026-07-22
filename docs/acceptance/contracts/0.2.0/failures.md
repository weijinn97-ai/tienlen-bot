# Known Failures and Limitations

## Status: No blocking failures

All 161 tests pass. No known regressions or limitations at this time.

## Accepted limitations

- Serialization format uses compact JSON (no pretty-print). This is intentional for determinism and replay compatibility.
- `ButtonState.button_id` and `ActionPlan.target_button` accept both `ButtonId` enum members and plain strings. Non-enum strings are passed through as-is during deserialization.

## Out of scope

- No changes to `contracts/interfaces.py` semantics.
- No changes to module registry or status.
- No new external dependencies added.
