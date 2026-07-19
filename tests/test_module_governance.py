import unittest

from tools.check_module_governance import locked_changes, validate_registry


def module(*, status: str = "CANDIDATE", version: str = "0.1.0") -> dict[str, object]:
    return {
        "id": "MOD-ONE",
        "status": status,
        "version": version,
        "paths": ["contracts/**"],
        "tests": ["tests/test_contract.py"],
        "evidence": "docs/evidence.md",
        "blocked_by": [],
    }


class ModuleGovernanceTests(unittest.TestCase):
    def test_valid_candidate_registry_passes(self) -> None:
        self.assertEqual(validate_registry({"modules": [module()]}), [])

    def test_locked_module_requires_stable_version(self) -> None:
        errors = validate_registry({"modules": [module(status="LOCKED")]})
        self.assertTrue(any("stable version" in error for error in errors))

    def test_detects_changes_inside_locked_module(self) -> None:
        registry = {"modules": [module(status="LOCKED", version="1.0.0")]}
        self.assertEqual(
            locked_changes(registry, ["README.md", "contracts/interfaces.py"]),
            {"MOD-ONE": ["contracts/interfaces.py"]},
        )

    def test_candidate_module_does_not_block_changes(self) -> None:
        registry = {"modules": [module()]}
        self.assertEqual(locked_changes(registry, ["contracts/interfaces.py"]), {})


if __name__ == "__main__":
    unittest.main()
