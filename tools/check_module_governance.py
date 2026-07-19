from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Iterable


VALID_STATUSES = {"PLANNED", "IN_PROGRESS", "CANDIDATE", "LOCKED", "DEPRECATED"}


def load_registry(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict):
        raise ValueError("Module registry root must be an object.")
    return registry


def validate_registry(registry: dict[str, object]) -> list[str]:
    errors: list[str] = []
    modules = registry.get("modules")
    if not isinstance(modules, list):
        return ["registry.modules must be a list"]

    ids: set[str] = set()
    for index, item in enumerate(modules):
        prefix = f"modules[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue

        module_id = item.get("id")
        if not isinstance(module_id, str) or not module_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif module_id in ids:
            errors.append(f"duplicate module id: {module_id}")
        else:
            ids.add(module_id)

        status = item.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{prefix}.status is invalid: {status!r}")

        paths = item.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(value, str) and value for value in paths):
            errors.append(f"{prefix}.paths must contain at least one glob")

        if status == "LOCKED":
            version = item.get("version")
            evidence = item.get("evidence")
            tests = item.get("tests")
            if not isinstance(version, str) or version.startswith("0."):
                errors.append(f"{prefix}: LOCKED module requires a stable version")
            if not isinstance(evidence, str) or not evidence:
                errors.append(f"{prefix}: LOCKED module requires evidence")
            if not isinstance(tests, list) or not tests:
                errors.append(f"{prefix}: LOCKED module requires tests")

    for index, item in enumerate(modules):
        if not isinstance(item, dict):
            continue
        for dependency in item.get("blocked_by", []):
            if dependency not in ids:
                errors.append(f"modules[{index}] references unknown dependency {dependency!r}")
    return errors


def locked_changes(registry: dict[str, object], changed_files: Iterable[str]) -> dict[str, list[str]]:
    changed = [path.replace("\\", "/") for path in changed_files if path.strip()]
    violations: dict[str, list[str]] = {}
    modules = registry.get("modules", [])
    if not isinstance(modules, list):
        return violations

    for item in modules:
        if not isinstance(item, dict) or item.get("status") != "LOCKED":
            continue
        module_id = str(item.get("id"))
        patterns = item.get("paths", [])
        matches = sorted(
            path
            for path in changed
            if any(fnmatch.fnmatchcase(path, str(pattern)) for pattern in patterns)
        )
        if matches:
            violations[module_id] = matches
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate module governance and lock rules.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(".github/module-registry.json"),
    )
    parser.add_argument("--changed-files", type=Path)
    parser.add_argument("--allow-locked-changes", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = load_registry(args.registry)
    errors = validate_registry(registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.changed_files:
        changed_files = args.changed_files.read_text(encoding="utf-8").splitlines()
        violations = locked_changes(registry, changed_files)
        if violations and not args.allow_locked_changes:
            for module_id, paths in violations.items():
                print(f"ERROR: {module_id} is LOCKED; unauthorized changes: {', '.join(paths)}")
            print("Owner approval and the locked-change-approved PR label are required.")
            return 1

    print("Module governance checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
