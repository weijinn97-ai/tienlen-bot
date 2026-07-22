# Replay 0.1.0 Acceptance Evidence

Status: `CANDIDATE`, not `LOCKED`.

Implemented:

- versioned deterministic JSON replay bundles;
- SHA-256 bundle checksum and per-event hash chain;
- frame, perception, state, legal move, decision, tap and verification event kinds;
- recursive secret redaction and rejection of raw frame/binary payloads;
- complete `TableState` contract round trip;
- deterministic offline decision reproduction;
- explicit validation codes for missing, corrupt, oversized and mismatched records;
- validator CLI and large replay artifact ignore rules.

The fixed fixture validates offline without MEmu. Runtime recording and locked live replay evidence remain required before `LOCKED`.
