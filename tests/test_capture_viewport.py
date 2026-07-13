import unittest

from bot.capture.windows_capture import ViewportSpec


class ViewportSpecTests(unittest.TestCase):
    def test_bottom_left_viewport_removes_memu_chrome(self) -> None:
        window_rect = {
            "left": 318,
            "top": 63,
            "right": 1639,
            "bottom": 816,
            "width": 1321,
            "height": 753,
        }
        result = ViewportSpec(1280, 720).resolve(window_rect)
        self.assertEqual(
            result,
            {
                "left": 318,
                "top": 96,
                "right": 1598,
                "bottom": 816,
                "width": 1280,
                "height": 720,
            },
        )

    def test_rejects_viewport_larger_than_window(self) -> None:
        with self.assertRaises(RuntimeError):
            ViewportSpec(1920, 1080).resolve(
                {
                    "left": 0,
                    "top": 0,
                    "right": 1280,
                    "bottom": 720,
                    "width": 1280,
                    "height": 720,
                }
            )


if __name__ == "__main__":
    unittest.main()
