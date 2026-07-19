# MOD-RULES-DECISION 0.2.0 Candidate Evidence

Source branch: `agent/rules-01`

Scope:

- Pure combo classification and comparison.
- Legal combo/move enumeration.
- Deterministic LocalAgent integration with a final legality guard.
- Candidate rules specification for owner review.

Results:

- Full suite: 79 tests passed.
- Rules tests: 11 passed.
- Generated-state invariant: 10,000 states, 0 invalid PLAY outputs.
- 13-card benchmark sample: 206 combos, mean 4.226 ms, worst batch mean 4.322 ms.

This evidence promotes the module to `CANDIDATE 0.2.0`, not `LOCKED`. The owner must
review `docs/rules/TIEN_LEN_RULES_V1_VI.md` and the unresolved decisions before locking.
