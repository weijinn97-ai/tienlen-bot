import tempfile
import unittest
from pathlib import Path

from tools.seed_google_sheet_public import load_seed_sheets, rows_to_tsv


class GoogleSheetSeedToolTests(unittest.TestCase):
    def test_rows_to_tsv_preserves_grid_shape(self) -> None:
        tsv = rows_to_tsv([["A", "B"], ["1", "2"]])

        self.assertEqual(tsv, "A\tB\n1\t2")

    def test_load_seed_sheets_sorts_csv_files_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            seed_dir = Path(temp_dir)
            (seed_dir / "02_Agent_Notes.csv").write_text(
                "Header1,Header2\nb,2\n",
                encoding="utf-8-sig",
            )
            (seed_dir / "01_Task_Board.csv").write_text(
                "Header1,Header2\na,1\n",
                encoding="utf-8-sig",
            )

            sheets = load_seed_sheets(seed_dir)

        self.assertEqual(
            [sheet.tab_name for sheet in sheets],
            ["01_Task_Board", "02_Agent_Notes"],
        )
        self.assertEqual(sheets[0].rows[1], ["a", "1"])


if __name__ == "__main__":
    unittest.main()
