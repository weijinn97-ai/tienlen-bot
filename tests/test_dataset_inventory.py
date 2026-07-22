import csv
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from tools.build_dataset_inventory import (
    build_annotation_review,
    build_groups,
    build_split,
    discover_inventory,
    hamming_distance,
    main,
    normalize_card_mention,
    phash64,
    run_pipeline,
    sha256_file,
    validate_no_leakage,
    validate_yolo_annotation,
)


class DatasetFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.batch = root / "data" / "submissions" / "session-a"
        self.raw = self.batch / "raw"
        self.raw.mkdir(parents=True)
        self.rows = []

    def add_image(
        self,
        name: str,
        value: int,
        *,
        room: str = "room-a",
        round_text: str = "1/32 10:00",
    ) -> Path:
        path = self.raw / name
        yy, xx = np.indices((48, 64))
        image = np.stack(
            (
                (xx * 3 + value) % 255,
                (yy * 5 + value) % 255,
                ((xx + yy) * 2 + value) % 255,
            ),
            axis=2,
        ).astype(np.uint8)
        self.assert_write(cv2.imwrite(str(path), image))
        self.rows.append(
            {
                "source_filename": name,
                "room_id": room,
                "round_text": round_text,
                "cards_visible": "3S;4C",
                "label_status": "hand_read",
            }
        )
        return path

    @staticmethod
    def assert_write(result: bool) -> None:
        if not result:
            raise RuntimeError("Failed to write test image.")

    def write_manifest(self) -> None:
        with (self.batch / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "source_filename",
                    "room_id",
                    "round_text",
                    "cards_visible",
                    "label_status",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(self.rows)


class DatasetInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = DatasetFixture(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sha256_and_phash_are_deterministic(self) -> None:
        path = self.fixture.add_image("one.png", 10)
        image = cv2.imread(str(path))
        self.assertEqual(sha256_file(path), sha256_file(path))
        self.assertEqual(phash64(image), phash64(image))
        self.assertEqual(len(phash64(image)), 16)

    def test_hamming_distance_is_symmetric(self) -> None:
        self.assertEqual(hamming_distance("0" * 16, "f" * 16), 64)
        self.assertEqual(hamming_distance("1234abcd00000000", "1234abcd00000001"), 1)

    def test_manifest_card_names_normalize_to_contract(self) -> None:
        self.assertEqual(normalize_card_mention("3_diamonds"), "3D")
        self.assertEqual(normalize_card_mention("10_hearts"), "10H")
        self.assertEqual(normalize_card_mention("AS"), "AS")
        self.assertEqual(normalize_card_mention("bad-card"), "UNKNOWN")

    def test_exact_duplicate_is_grouped(self) -> None:
        first = self.fixture.add_image("one.png", 20)
        second = self.fixture.raw / "two.png"
        second.write_bytes(first.read_bytes())
        self.fixture.rows.append(dict(self.fixture.rows[0], source_filename="two.png"))
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        groups, rows = build_groups(inventory, 0)
        self.assertEqual(groups[inventory[0]["asset_id"]], groups[inventory[1]["asset_id"]])
        self.assertEqual({row["duplicate_kind"] for row in rows}, {"EXACT"})

    def test_near_duplicate_respects_threshold(self) -> None:
        self.fixture.add_image("one.png", 20)
        self.fixture.add_image("two.png", 21)
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        distance = hamming_distance(inventory[0]["phash64"], inventory[1]["phash64"])
        groups, _ = build_groups(inventory, distance)
        self.assertEqual(groups[inventory[0]["asset_id"]], groups[inventory[1]["asset_id"]])

    def test_duplicate_assets_never_cross_split(self) -> None:
        first = self.fixture.add_image("one.png", 30)
        second = self.fixture.raw / "two.png"
        second.write_bytes(first.read_bytes())
        self.fixture.rows.append(dict(self.fixture.rows[0], source_filename="two.png"))
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        groups, _ = build_groups(inventory, 0)
        splits = build_split(inventory, groups, 17)
        self.assertEqual(len({row["split"] for row in splits}), 1)
        self.assertEqual(validate_no_leakage(inventory, splits, groups), [])

    def test_same_capture_boundary_never_crosses_split(self) -> None:
        self.fixture.add_image("one.png", 1, round_text="2/32 10:00")
        self.fixture.add_image("two.png", 100, round_text="2/32 10:05")
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        groups, _ = build_groups(inventory, 0)
        splits = build_split(inventory, groups, 17)
        self.assertEqual(len({row["split"] for row in splits}), 1)

    def test_missing_metadata_is_unknown(self) -> None:
        self.fixture.add_image("one.png", 10, round_text="")
        self.fixture.rows[0]["cards_visible"] = ""
        self.fixture.rows[0]["label_status"] = ""
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        self.assertEqual(inventory[0]["match_id"], "UNKNOWN")
        self.assertEqual(inventory[0]["round_id"], "UNKNOWN")
        self.assertEqual(inventory[0]["zone"], "UNKNOWN")

    def test_corrupt_image_is_reported_without_crashing(self) -> None:
        path = self.fixture.raw / "broken.png"
        path.write_bytes(b"not an image")
        self.fixture.rows.append(
            {
                "source_filename": "broken.png",
                "room_id": "",
                "round_text": "",
                "cards_visible": "",
                "label_status": "",
            }
        )
        self.fixture.write_manifest()
        coverage = run_pipeline(self.root, Path("reports"))
        self.assertEqual(coverage["corrupt_images"], 1)
        self.assertEqual(coverage["valid_images"], 0)

    def test_annotation_status_present_missing_and_invalid(self) -> None:
        self.fixture.add_image("valid.png", 10)
        self.fixture.add_image("missing.png", 20)
        self.fixture.add_image("invalid.png", 30)
        labels = self.fixture.batch / "labels"
        labels.mkdir()
        (labels / "valid.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        (labels / "invalid.txt").write_text("99 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        self.fixture.write_manifest()
        inventory, _ = discover_inventory(self.root)
        statuses = {Path(row["relative_path"]).name: row["annotation_status"] for row in inventory}
        self.assertEqual(statuses, {"invalid.png": "INVALID", "missing.png": "MISSING", "valid.png": "PRESENT"})
        self.assertIn("class_out_of_range", validate_yolo_annotation(labels / "invalid.txt"))

    def test_review_selects_all_val_test_and_twenty_percent_train(self) -> None:
        inventory = [
            {
                "asset_id": f"id-{index}",
                "relative_path": f"{index}.png",
                "annotation_status": "PRESENT",
            }
            for index in range(10)
        ]
        splits = [
            {
                "asset_id": f"id-{index}",
                "split": "train" if index < 5 else ("val" if index < 8 else "test"),
            }
            for index in range(10)
        ]
        review = build_annotation_review(inventory, splits, 17)
        required = [row for row in review if row["review_required"] == "true"]
        self.assertEqual(sum(row["split"] != "train" for row in required), 5)
        self.assertGreaterEqual(sum(row["split"] == "train" for row in required), 1)

    def test_repeated_runs_are_byte_deterministic(self) -> None:
        self.fixture.add_image("one.png", 10)
        self.fixture.add_image("two.png", 120)
        self.fixture.write_manifest()
        first = self.root / "first"
        second = self.root / "second"
        run_pipeline(self.root, first)
        run_pipeline(self.root, second)
        self.assertEqual(
            {path.name: path.read_bytes() for path in first.iterdir()},
            {path.name: path.read_bytes() for path in second.iterdir()},
        )

    def test_pipeline_does_not_modify_raw_inputs(self) -> None:
        path = self.fixture.add_image("one.png", 10)
        self.fixture.write_manifest()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        run_pipeline(self.root, Path("reports"))
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_cli_returns_nonzero_for_invalid_threshold(self) -> None:
        self.fixture.add_image("one.png", 10)
        self.fixture.write_manifest()
        with redirect_stdout(io.StringIO()):
            result = main(
                [
                    "--repo-root",
                    str(self.root),
                    "--output",
                    "reports",
                    "--phash-threshold",
                    "65",
                ]
            )
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
