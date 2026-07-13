import unittest

import numpy as np

from bot.perception.ocr import TesseractOcr
from contracts.interfaces import Rect


class OcrTests(unittest.TestCase):
    def test_recognizes_only_requested_roi(self) -> None:
        seen = {}

        def engine(image, *, config):
            seen["shape"] = image.shape
            seen["config"] = config
            return " 13\n"

        result = TesseractOcr(engine).recognize(
            np.zeros((100, 200, 3), dtype=np.uint8),
            Rect(20, 10, 40, 30),
            whitelist="0123456789",
        )
        self.assertEqual(result.text, "13")
        self.assertEqual(seen["shape"], (60, 80))
        self.assertIn("tessedit_char_whitelist=0123456789", seen["config"])

    def test_rejects_roi_outside_frame(self) -> None:
        with self.assertRaises(ValueError):
            TesseractOcr(lambda image, config: "").recognize(
                np.zeros((10, 10, 3), dtype=np.uint8),
                Rect(9, 9, 2, 2),
            )


if __name__ == "__main__":
    unittest.main()
