import psutil
import time

class SystemMonitor:
    def __init__(self, interval=1):
        self.interval = interval

    def get_system_metrics(self):
        cpu_percent = psutil.cpu_percent(interval=self.interval)
        ram_percent = psutil.virtual_memory().percent
        return {
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent
        }

    def get_process_metrics(self, process_name):
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            if process_name.lower() in proc.info["name"].lower():
                return {
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "cpu_percent": proc.info["cpu_percent"],
                    "memory_percent": proc.info["memory_percent"]
                }
        return None

# Example usage
if __name__ == "__main__":
    monitor = SystemMonitor()
    print("Monitoring system resources...")
    try:
        while True:
            system_metrics = monitor.get_system_metrics()
            print(f"System: CPU: {system_metrics["cpu_percent"]}% | RAM: {system_metrics["ram_percent"]}% ")

            # Replace "MEmu.exe" with the actual process name of your MEmu emulator
            memu_metrics = monitor.get_process_metrics("MEmu.exe")
            if memu_metrics:
                print(f"MEmu: PID: {memu_metrics["pid"]} | CPU: {memu_metrics["cpu_percent"]}% | RAM: {memu_metrics["memory_percent"]}% ")
            else:
                print("MEmu process not found.")

            time.sleep(5)
    except KeyboardInterrupt:
        print("Monitoring stopped.")
