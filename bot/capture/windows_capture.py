import numpy as np
import cv2
import mss
import win32gui
import win32ui
import win32con

class WindowsCapture:
    def __init__(self, window_name=None):
        self.window_name = window_name
        self.sct = mss.mss()
        self.hwnd = None
        if self.window_name:
            self.hwnd = win32gui.FindWindow(None, self.window_name)
            if not self.hwnd:
                raise Exception(f'Window not found: {self.window_name}')

    def get_screenshot(self):
        if self.hwnd:
            # Get window dimensions
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            width = right - left
            height = bot - top

            # Adjust for window borders and title bar if necessary
            # This might need fine-tuning depending on the emulator window style
            # For simplicity, we'll capture the whole window for now.

            # Capture the window
            wincap = {
                'left': left,
                'top': top,
                'width': width,
                'height': height
            }
            sct_img = self.sct.grab(wincap)
            return np.array(sct_img)
        else:
            # Capture primary monitor if no window name is provided
            sct_img = self.sct.grab(self.sct.monitors[1]) # monitors[0] is all screens, monitors[1] is primary
            return np.array(sct_img)

    def get_window_info(self):
        if self.hwnd:
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            return {'left': left, 'top': top, 'right': right, 'bottom': bot}
        return None

# Example usage (for testing purposes)
if __name__ == '__main__':
    # Replace 'MEmu' with the actual window title of your MEmu emulator
    # You might need to use a tool like 'Window Spy' to get the exact title
    window_title = 'MEmu'
    try:
        wincap = WindowsCapture(window_title)
        print(f"Found window: {window_title}")
        while True:
            screenshot = wincap.get_screenshot()
            cv2.imshow('Bot View', screenshot)

            if cv2.waitKey(1) == ord('q'):
                cv2.destroyAllWindows()
                break
    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure MEmu is running and the window title is correct.")
        print("If you don't know the window title, try running without specifying it to capture the primary screen.")
        try:
            wincap = WindowsCapture()
            print("Capturing primary screen.")
            while True:
                screenshot = wincap.get_screenshot()
                cv2.imshow('Bot View (Primary Screen)', screenshot)
                if cv2.waitKey(1) == ord('q'):
                    cv2.destroyAllWindows()
                    break
        except Exception as e_fallback:
            print(f"Fallback capture failed: {e_fallback}")

