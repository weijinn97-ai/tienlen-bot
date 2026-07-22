# GEMINI-CONTRACT-01 Final Report (Lock-grade Audit PR #26)

## Task

Stabilize serialization, strict wire-boundary validation (both deserialization and serialization), duplicate JSON key rejection, and source-object validation for contracts used across process boundaries and replay.

## Status: AUDITED & COMPLETE

## Branch + Commit

- Branch: `agent/gemini-contract-01`
- Baseline: `gemini-contract-01-baseline` (`2b1fe57`)

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `contracts/serialization.py` | MODIFIED | Canonical JSON serialization with duplicate key rejection, bidirectional strict validation, and lock-grade source-object validation for all 10 contract types |
| `contracts/__init__.py` | MODIFIED | Export `CONTRACT_SCHEMA_VERSION`, `contract_to_dict`, `contract_from_dict`, `contract_to_json`, `contract_from_json` |
| `tests/test_contract_serialization.py` | MODIFIED | 70 tests covering round-trip, determinism, fixtures, strict wire validation, duplicate key rejection, serialization validation, error handling, consumers |
| `tests/fixtures/contracts_v1/perception_snapshot_full.json` | NEW | Full PerceptionSnapshot v1 fixture |
| `tests/fixtures/contracts_v1/table_state_full.json` | NEW | Full TableState v1 fixture |
| `tests/fixtures/contracts_v1/action_plan_play.json` | NEW | ActionPlan PLAY with VerifySpec fixture |
| `tests/fixtures/contracts_v1/action_plan_wait.json` | NEW | ActionPlan WAIT minimal fixture |
| `docs/acceptance/contracts/0.2.0/README.md` | MODIFIED | Acceptance evidence |
| `docs/acceptance/contracts/0.2.0/commands.txt` | MODIFIED | Verification commands and LF SHA-256 calculation method |
| `docs/acceptance/contracts/0.2.0/metrics.json` | MODIFIED | Machine-readable metrics (180 tests total) |
| `docs/acceptance/contracts/0.2.0/artifacts.sha256` | MODIFIED | LF-normalized SHA-256 checksums |
| `docs/acceptance/contracts/0.2.0/failures.md` | MODIFIED | Strict wire validation behavior & audit documentation |

## Completed Audit Requirements

- [x] **Duplicate JSON Key Rejection**: Implemented `_reject_duplicate_json_keys` callback in `contract_from_json` via `json.loads(..., object_pairs_hook=...)`. Duplicate keys in envelope, payload, ROI, counts raise `ValueError`.
- [x] **Strict Serialization Boundary**:
  - Removed `str(...)` fallback from `_button_state_to_payload` and `_action_plan_to_payload`. Only accepts exact `str`, `ButtonId`, or `None`.
  - In `contract_to_dict`, generated payload is validated with matching deserializer before returning, preventing invalid contract instances (`Rect(True, ...)`, non-finite confidence) from producing valid JSON/dict output.
  - Rejects non-string keys in dict payloads with clear `TypeError` before formatting.
- [x] **Lock-grade Source Validation**:
  - Exact type requirements applied in serializers (`type(value) is expected_type`) for Enums, `Rect`, `DetectedCard`, tuples, and mapping counts. Prevents silently converting fake dicts, inherited classes, or duck-typed lists into valid payload data.
- [x] **Mandatory Audit Regression Tests**: Added `AdversarialAuditTests` in `tests/test_contract_serialization.py`:
  - `test_duplicate_schema_version_json_key_rejected`
  - `test_duplicate_nested_counts_json_key_rejected`
  - `test_serialization_rejects_invalid_button_id_types`
  - `test_serialization_rejects_non_finite_confidence`
  - `test_serialization_rejects_bool_in_integer_fields`
  - `test_direct_dict_non_string_keys_rejected`
  - `test_serialization_rejects_fake_enum_types`
  - `test_serialization_rejects_duck_typed_objects`
  - `test_serialization_rejects_source_list_for_tuples`
  - `test_serialization_rejects_mutated_wrong_optional`
- [x] **Evidence & Checksums**: Updated all evidence files, metrics (180 tests total), and recalculated LF-normalized SHA-256 checksums.

## Tests Run + Exact Result

```
py -3 -m unittest discover -s tests -p "test_contract_serialization.py" -v
Ran 70 tests in 0.019s
OK

py -3 -m unittest discover -s tests -v
Ran 180 tests in 3.321s
OK

powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
Gemini scope check passed. Task=GEMINI-CONTRACT-01; branch=agent/gemini-contract-01; changed=13

py -3 tools/check_module_governance.py
Module governance checks passed.

py -3 -m compileall -q bot contracts tools
(no output = success)

git diff --check
(no output = clean)
```

## Proposed Next Step

Owner reviews updated PR #26 and decides on promoting `MOD-CONTRACTS` to `0.2.0 CANDIDATE` or `LOCKED`.
