# Known Failures and Limitations

## Status: No blocking failures

All 182 unit and integration tests pass cleanly.

## Known Risks and Wire Validation Behavior

- **Strict Owner Audit Verification**:
  - **Duplicate JSON key rejection**: `json.loads` uses `object_pairs_hook=_reject_duplicate_json_keys` to reject duplicate keys in envelope, payload, ROI, or card counts (e.g. `{"schema_version": 99, "schema_version": 1}` or `{"0": 3, "0": 12}`).
  - **Strict Serialization**: `contract_to_dict` generates payload and validates it using `_FROM_PAYLOAD[type_name]`, preventing `contract_to_dict` or `contract_to_json` from emitting invalid fields (`Rect(True, 0, 1, 1)`, non-finite confidence, invalid button_id, etc.). `_button_state_to_payload` and `_action_plan_to_payload` enforce exact `ButtonId`, `str`, or `None` types without `str(...)` fallback.
  - **Non-string keys**: Envelope and payload dict keys are checked for `type(k) is str` before processing or sorting to prevent type errors during formatting.
- **Lock-grade Audit Verification**:
  - **Source Object Validation**: Serializers enforce exact Python object types (`type(value) is expected_type`) for Enums, `Rect`, `DetectedCard`, tuples, and mappings prior to data conversion, ensuring no silent duck-type coercion.

## Accepted Limitations

- Serialization format uses compact JSON (no pretty-print). This is intentional for determinism and replay compatibility.
- Unknown string values for `button_id` and `target_button` are preserved as string rather than raising an error, allowing forward compatibility for custom buttons.

## Out of Scope

- No changes to `contracts/interfaces.py` semantics.
- No changes to module registry or status (`MOD-CONTRACTS` remains `CANDIDATE`).
- No new external dependencies added.
