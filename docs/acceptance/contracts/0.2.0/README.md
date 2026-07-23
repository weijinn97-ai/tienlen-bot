# Acceptance Evidence – contracts 0.2.0 CANDIDATE (Lock-grade Audit)

## Environment

- OS: Windows (MEmu host)
- Python: 3.14
- Repository: `weijinn97-ai/tienlen-bot`
- Baseline: `gemini-contract-01-baseline` (commit `2b1fe57`)
- Branch: `agent/gemini-contract-01`

## Scope

Added stable serialization, strict wire-boundary validation (duplicate key rejection, payload validation on serialization), lock-grade source-object validation (exact type checking for Enums, classes, and containers), and compatibility fixtures for contracts module.
No changes to `contracts/interfaces.py`, card encoding, or existing contract semantics.

## Files Changed

| File | Action |
|------|--------|
| `contracts/serialization.py` | MODIFIED (Duplicate key rejection, strict source-object validation) |
| `contracts/__init__.py` | MODIFIED (Export public serialization API) |
| `tests/test_contract_serialization.py` | MODIFIED (72 serialization & audit tests) |
| `tests/fixtures/contracts_v1/perception_snapshot_full.json` | NEW |
| `tests/fixtures/contracts_v1/table_state_full.json` | NEW |
| `tests/fixtures/contracts_v1/action_plan_play.json` | NEW |
| `tests/fixtures/contracts_v1/action_plan_wait.json` | NEW |

## Test Results

- **Baseline tests**: 110/110 OK
- **Serialization & Audit tests**: 72/72 OK
- **Total tests**: 182/182 OK
- **Compile check**: `py -3 -m compileall -q bot contracts tools` – clean
- **Governance check**: `py -3 tools/check_module_governance.py` – passed
- **Scope guard**: `gemini_handoff_bundle/guard_scope.ps1` – passed
- **Whitespace**: `git diff --check` – clean

## Checksums Method

Checksums in `artifacts.sha256` are calculated from normalized LF line-endings (`open(f, 'rb').read().replace(b'\r\n', b'\n')`) to eliminate OS-dependent checkout differences.

## Conclusion

Module `MOD-CONTRACTS` is proposed as **0.2.0 CANDIDATE** for owner review.
Agent does not set `LOCKED` or modify registry.
