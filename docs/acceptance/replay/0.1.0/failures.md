# Remaining Replay Gates

- Runtime workers do not yet emit replay events automatically.
- No locked replay captured from a complete live MEmu round exists.
- Frame/video artifacts still require external storage and a retention policy.
- Replay schema migration from v1 has not been exercised because no older schema exists.

These are lock blockers, not reasons to bypass checksum, redaction or validation failures.
