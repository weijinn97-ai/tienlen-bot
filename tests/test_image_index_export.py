import csv
import tempfile
import unittest
from pathlib import Path

from tools.export_image_index_csv import collect_manifest_rows


class ImageIndexExportTests(unittest.TestCase):
    def test_collect_manifest_rows_reads_batch_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            submissions_dir = Path(temp_dir) / "submissions"
            batch_dir = submissions_dir / "batch_a"
            batch_dir.mkdir(parents=True)

            manifest_path = batch_dir / "manifest.csv"
            with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "image_id",
                        "batch_name",
                        "source_filename",
                        "repo_relative_path",
                        "original_source_path",
                        "file_size_bytes",
                        "captured_at",
                        "sha256",
                        "room_id",
                        "round_text",
                        "visibility_mode",
                        "cards_visible_count",
                        "cards_visible",
                        "label_status",
                        "split_status",
                        "notes",
                    ]
                )
                writer.writerow(
                    [
                        "001",
                        "batch_a",
                        "1.png",
                        "data/submissions/batch_a/raw/1.png",
                        r"C:\shots\1.png",
                        "123",
                        "2026-04-25T17:30:48",
                        "abc",
                        "294732",
                        "1/32 18:30 25/04",
                        "Mở",
                        "13",
                        "4_spades;5_spades",
                        "needs_bbox_label",
                        "hand_read",
                        "",
                    ]
                )

            rows = collect_manifest_rows(submissions_dir)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "001")
        self.assertEqual(rows[0][1], "batch_a")
        self.assertEqual(rows[0][8], "1/32 18:30 25/04")


if __name__ == "__main__":
    unittest.main()
