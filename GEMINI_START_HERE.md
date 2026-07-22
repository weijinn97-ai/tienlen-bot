# Google Gemini: Start Here

This is the only link the project owner needs to send to Google Antigravity/Gemini.

Repository: `https://github.com/weijinn97-ai/tienlen-bot`

## Your instruction

Work autonomously on the task currently authorized by this repository. Do not ask the owner to copy files or explain the project again.

1. Clone the repository into a new folder named `tienlen-bot-gemini`.
2. Read `AGENTS.md`.
3. Read `docs/MASTER_EXECUTION_PLAN_VI.md`.
4. Read `.github/module-registry.json`.
5. Read `gemini_handoff_bundle/README.md`.
6. Read `gemini_handoff_bundle/ACTIVE_TASK.json`.
7. Read the `instruction_file` named by `ACTIVE_TASK.json`.
8. Checkout the exact `baseline_ref` and create the exact `required_branch` from `ACTIVE_TASK.json`.
9. Run the baseline tests and `gemini_handoff_bundle/guard_scope.ps1` before editing.
10. Implement the entire active task, including code, tests, fixtures, evidence and final report.
11. Run the scope guard, full tests, compile, governance and diff checks before commit and push.
12. Push only the required branch and open a draft pull request to `main`.
13. Do not merge the pull request. Return only the draft PR link and a short summary to the owner.

## Mandatory safety rules

- Only the task with `status: ACTIVE` is authorized.
- The scope in `ACTIVE_TASK.json` is deny-by-default.
- Do not edit any file outside `allowed_new_paths` and `allowed_existing_file_modifications`.
- Never edit `ACTIVE_TASK.json`, `guard_scope.ps1`, existing tests, module registry or locked/forbidden modules.
- Never use `git reset --hard`, `git clean`, force-push, push to `main`, merge a PR or delete/rename files.
- Never change contract semantics, card encoding or module status unless the active policy explicitly allows it.
- If the scope guard fails or work requires a forbidden path, stop and create `BLOCKERS.md` in the authorized output directory.

## Current active assignment

The machine-readable source of truth is always:

`gemini_handoff_bundle/ACTIVE_TASK.json`

Do not rely on task details copied into chat because they can become stale. Read the repository files directly.

Begin now and continue until the active task is fully implemented or an explicit blocker is recorded.
