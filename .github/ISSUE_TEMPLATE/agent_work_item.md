---
name: Agent work item
about: Create an epic or child issue with explicit scope, contract touchpoints, and acceptance criteria.
title: "[lane] short title"
labels: []
assignees: ""
---

## Summary

One short paragraph that states the problem and the intended outcome.

## Issue Type

- [ ] Epic
- [ ] Child task
- [ ] Bug
- [ ] Chore
- [ ] Module lock candidate
- [ ] Locked module change

## Module Claim

- Module ID from `.github/module-registry.json`:
- Current status:
- Owner / agent:
- Branch name:
- Files allowed to change:
- Public API that must remain compatible:

## Parent / Related Epic

- Parent epic:
- Related contracts:
- Related docs:

## Problem Statement

What is broken, missing, or risky today?

## Why Now

Why should we do this now instead of later?

## In Scope

- 
- 
- 

## Out of Scope

- 
- 

## Inputs

- Existing files/modules:
- Runtime assumptions:
- Data/sample inputs:

## Deliverables

- [ ] Code or docs change
- [ ] Tests or validation
- [ ] Tracker/doc update if needed

## Contract Touchpoints

List the exact symbols or files touched, for example:

- `contracts/interfaces.py::TableState`
- `contracts/interfaces.py::VerifySpec`
- `bot/agent/game_state_adapter.py`

## Acceptance Criteria

- [ ] The output matches the agreed contract exactly.
- [ ] Naming is consistent with the current epic and contract docs.
- [ ] The change includes the minimum realistic validation.
- [ ] Failure modes are explicit and operator-safe.
- [ ] No unrelated refactor is bundled into this issue.
- [ ] Module registry and evidence are updated if status/version changes.
- [ ] No `LOCKED` path is changed without owner approval and required PR label.

Add issue-specific acceptance criteria below:

- [ ] 
- [ ] 
- [ ] 

## Verification

Commands or manual checks:

```bash
# put validation commands here
```

## Dependencies

- Blocking issues:
- Follow-up issues:

## Handoff Notes

Anything the next agent must know before continuing.

- Last commit SHA:
- Exact tests and results:
- Completed / not completed:
- Known risks:
- Exact next command or action:
