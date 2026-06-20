import subprocess
import time

class ADBController:
    def __init__(self, adb_path="adb", device_id=None):
        self.adb_path = adb_path
        self.device_id = device_id
        self._check_adb_connection()

    def _execute_adb_command(self, command, timeout=10):
        full_command = [self.adb_path]
        if self.device_id:
            full_command.extend(["-s", self.device_id])
        full_command.extend(command)

        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"ADB command failed: {e.cmd}")
            print(f"Stderr: {e.stderr.strip()}")
            raise
        except subprocess.TimeoutExpired as e:
            print(f"ADB command timed out: {e.cmd}")
            raise
        except FileNotFoundError:
            print(f"ADB executable not found at {self.adb_path}. Please ensure ADB is installed and in your PATH, or provide the correct path.")
            raise

    def _check_adb_connection(self):
        try:
            devices = self._execute_adb_command(["devices"])
            if self.device_id and self.device_id not in devices:
                raise Exception(f"Device {self.device_id} not found. Available devices:\n{devices}")
            elif not self.device_id and "device" not in devices:
                raise Exception(f"No ADB devices found. Please ensure MEmu is running and ADB debugging is enabled.\nAvailable devices:\n{devices}")
            print("ADB connection successful.")
        except Exception as e:
            print(f"ADB connection check failed: {e}")
            raise

    def tap(self, x, y):
        print(f"Tapping at: ({x}, {y})")
        self._execute_adb_command(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1, y1, x2, y2, duration=200):
        print(f"Swiping from ({x1}, {y1}) to ({x2}, {y2}) over {duration}ms")
        self._execute_adb_command(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    def send_text(self, text):
        print(f"Sending text: {text}")
        self._execute_adb_command(["shell", "input", "text", text])

    def get_screenshot(self, save_path="screen.png"):
        print(f"Taking screenshot and saving to {save_path}")
        self._execute_adb_command(["shell", "screencap", "-p", "/sdcard/screen.png"])
        self._execute_adb_command(["pull", "/sdcard/screen.png", save_path])
        self._execute_adb_command(["shell", "rm", "/sdcard/screen.png"])
        return save_path

# Example usage
if __name__ == "__main__":
    # Ensure ADB is in your system PATH or provide the full path to adb.exe
    # Example: adb_controller = ADBController(adb_path="C:\\platform-tools\\adb.exe")
    try:
        adb_controller = ADBController()
        print("ADBController initialized.")

        # Example: Take a screenshot
        # screenshot_file = adb_controller.get_screenshot("test_screenshot.png")
        # print(f"Screenshot saved to {screenshot_file}")

        # Example: Tap at coordinates (adjust for your emulator)
        # adb_controller.tap(500, 800)

        # Example: Swipe
        # adb_controller.swipe(500, 800, 500, 200)

    except Exception as e:
        print(f"Error during ADB operations: {e}")
