import unittest

import numpy as np

from bot.ui.preview import frame_to_ppm


class PreviewTests(unittest.TestCase):
    def test_bgr_frame_is_encoded_as_rgb_ppm(self):
        frame = np.array([[[1, 2, 3], [10, 20, 30]]], dtype=np.uint8)
        encoded = frame_to_ppm(frame)
        self.assertTrue(encoded.startswith(b"P6\n2 1\n255\n"))
        self.assertEqual(encoded.split(b"\n", 3)[3], bytes([3, 2, 1, 30, 20, 10]))

    def test_rejects_wrong_dtype_and_shape(self):
        with self.assertRaises(ValueError):
            frame_to_ppm(np.zeros((2, 2, 3), dtype=np.int32))
        with self.assertRaises(ValueError):
            frame_to_ppm(np.zeros((2, 2), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
