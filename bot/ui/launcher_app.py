from __future__ import annotations

import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

from bot.discovery.adb_discovery import BindingCandidate, scan_memu_adb_bindings


ROOT = Path(__file__).resolve().parents[2]
RUN_SESSION_SCRIPT = ROOT / "tools" / "run_bot_session.py"


class BotLauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TienLen Bot Launcher")
        self.root.geometry("1220x760")
        self.root.minsize(1000, 620)

        self._icon_image = _build_icon_image()
        self.root.iconphoto(True, self._icon_image)

        self.log_queue: Queue[str] = Queue()
        self.candidates: list[BindingCandidate] = []
        self.process: subprocess.Popen[str] | None = None
        self.process_reader: Thread | None = None
        self.selected_vm_index: int | None = None

        self.status_var = tk.StringVar(value="Ready")
        self.selected_var = tk.StringVar(value="No emulator selected")

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_log_queue)
        self.refresh_instances()

    def _build_layout(self) -> None:
        self.root.configure(bg="#f4efe4")

        container = ttk.Frame(self.root, padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 15))
        style.configure("Muted.TLabel", font=("Segoe UI", 10))

        header = ttk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 12))

        icon_label = tk.Label(header, image=self._icon_image, bg="#f4efe4")
        icon_label.pack(side=tk.LEFT, padx=(0, 12))

        title_frame = ttk.Frame(header)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(title_frame, text="TienLen Bot Launcher", style="Header.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            title_frame,
            text="Scan emulator ADB endpoints, choose the exact instance, then run and inspect detailed logs.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        action_bar = ttk.Frame(container)
        action_bar.pack(fill=tk.X, pady=(0, 12))

        ttk.Button(action_bar, text="Refresh Instances", command=self.refresh_instances).pack(
            side=tk.LEFT
        )
        ttk.Button(action_bar, text="Run Bot", command=self.start_selected_bot).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_bar, text="Stop Bot", command=self.stop_bot).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(
            action_bar,
            text="Copy Binding Stub",
            command=self.copy_selected_binding,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(action_bar, textvariable=self.selected_var).pack(
            side=tk.RIGHT, padx=(12, 0)
        )

        content = ttk.Panedwindow(container, orient=tk.VERTICAL)
        content.pack(fill=tk.BOTH, expand=True)

        top_panel = ttk.Frame(content)
        bottom_panel = ttk.Frame(content)
        content.add(top_panel, weight=3)
        content.add(bottom_panel, weight=2)

        self.tree = ttk.Treeview(
            top_panel,
            columns=(
                "vm_index",
                "name",
                "adb_serial",
                "android_serial",
                "window_title",
                "pid",
                "hwnd",
                "model",
                "state",
            ),
            show="headings",
            selectmode="browse",
        )
        headings = {
            "vm_index": ("VM", 60),
            "name": ("Instance Name", 220),
            "adb_serial": ("ADB Serial", 140),
            "android_serial": ("Android Serial", 110),
            "window_title": ("Window Title", 220),
            "pid": ("PID", 80),
            "hwnd": ("HWND", 100),
            "model": ("Model", 120),
            "state": ("State", 90),
        }
        for key, (text, width) in headings.items():
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=tk.W)

        tree_scroll = ttk.Scrollbar(top_panel, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        log_header = ttk.Frame(bottom_panel)
        log_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(log_header, text="Detailed Bot Log", style="Header.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Button(log_header, text="Clear Log", command=self.clear_log).pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            bottom_panel,
            wrap=tk.WORD,
            bg="#111418",
            fg="#e7f2ec",
            insertbackground="#e7f2ec",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        log_scroll = ttk.Scrollbar(bottom_panel, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side=tk.LEFT)

    def refresh_instances(self) -> None:
        self._append_log("INFO", "Scanning running MEmu instances and ADB endpoints...")
        try:
            candidates = scan_memu_adb_bindings()
        except Exception as exc:
            self._append_log("ERROR", f"Scan failed: {exc}")
            messagebox.showerror("Scan failed", str(exc))
            return

        self.candidates = candidates
        self.tree.delete(*self.tree.get_children())
        for candidate in candidates:
            self.tree.insert(
                "",
                tk.END,
                iid=str(candidate.vm_index),
                values=(
                    candidate.vm_index,
                    candidate.vm_name,
                    candidate.adb_serial or "-",
                    candidate.android_serial or "-",
                    candidate.window_title or "-",
                    candidate.process_id,
                    hex(candidate.hwnd) if candidate.hwnd is not None else "-",
                    candidate.model or "-",
                    candidate.adb_state or "-",
                ),
            )

        self.status_var.set(f"Found {len(candidates)} running emulator instance(s)")
        if candidates:
            self._append_log(
                "INFO",
                f"Scan complete. Found {len(candidates)} running instance(s).",
            )
        else:
            self._append_log("WARN", "No running MEmu instances were found.")

    def start_selected_bot(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            messagebox.showwarning("No selection", "Choose one emulator instance first.")
            return

        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo("Bot already running", "Stop the current bot session first.")
            return

        command = [
            "py",
            "-3",
            str(RUN_SESSION_SCRIPT),
            "--vm-index",
            str(candidate.vm_index),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        self._append_log(
            "INFO",
            (
                "Starting bot session | "
                f"title='{self._candidate_title(candidate)}' | "
                f"vm={candidate.vm_index} | "
                f"pid={candidate.process_id} | "
                f"hwnd={hex(candidate.hwnd) if candidate.hwnd else '-'} | "
                f"adb_serial={candidate.adb_serial or '-'}"
            ),
        )
        self.status_var.set(
            f"Running: {self._candidate_title(candidate)} (VM {candidate.vm_index})"
        )

        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            creationflags=creationflags,
            env=env,
        )

        self.process_reader = Thread(target=self._read_process_output, daemon=True)
        self.process_reader.start()

    def stop_bot(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self._append_log("INFO", "No running bot session to stop.")
            return

        self._append_log("INFO", "Stopping bot session...")
        self.process.terminate()
        self.root.after(1500, self._kill_if_still_running)

    def copy_selected_binding(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            messagebox.showwarning("No selection", "Choose one emulator instance first.")
            return
        try:
            stub = candidate.as_binding_stub()
        except ValueError as exc:
            messagebox.showerror("Binding unavailable", str(exc))
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(stub)
        self._append_log(
            "INFO",
            f"Copied BotBinding stub for '{self._candidate_title(candidate)}'.",
        )

    def clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _selected_candidate(self) -> BindingCandidate | None:
        selection = self.tree.selection()
        if not selection:
            return None
        vm_index = int(selection[0])
        for candidate in self.candidates:
            if candidate.vm_index == vm_index:
                return candidate
        return None

    def _on_tree_select(self, _event: object) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            self.selected_vm_index = None
            self.selected_var.set("No emulator selected")
            return

        if self.selected_vm_index == candidate.vm_index:
            self.selected_var.set(
                f"Selected: {self._candidate_title(candidate)} | VM {candidate.vm_index}"
            )
            return

        self.selected_vm_index = candidate.vm_index
        self.selected_var.set(
            f"Selected: {self._candidate_title(candidate)} | VM {candidate.vm_index}"
        )
        self._append_log(
            "INFO",
            (
                "Selected emulator | "
                f"title='{self._candidate_title(candidate)}' | "
                f"vm={candidate.vm_index} | "
                f"pid={candidate.process_id} | "
                f"adb_serial={candidate.adb_serial or '-'}"
            ),
        )

    def _read_process_output(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None

        for line in self.process.stdout:
            self.log_queue.put(line.rstrip())

        exit_code = self.process.wait()
        self.log_queue.put(f"[SYSTEM] Bot session exited with code {exit_code}")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                if message.startswith("[SYSTEM]"):
                    self.status_var.set(message)
        except Empty:
            pass
        finally:
            self.root.after(100, self._drain_log_queue)

    def _append_log(self, level: str, message: str) -> None:
        self.log_queue.put(f"[{level}] {message}")

    def _kill_if_still_running(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self.status_var.set("Bot session stopped")
            return
        self.process.kill()
        self._append_log("WARN", "Bot session required force kill after terminate timeout.")
        self.status_var.set("Bot session force-stopped")

    def _on_close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            if not messagebox.askyesno(
                "Exit launcher",
                "A bot session is still running. Stop it and exit?",
            ):
                return
            self.stop_bot()
        self.root.destroy()

    @staticmethod
    def _candidate_title(candidate: BindingCandidate) -> str:
        return candidate.window_title or candidate.vm_name or f"VM {candidate.vm_index}"


def _build_icon_image() -> tk.PhotoImage:
    size = 32
    image = tk.PhotoImage(width=size, height=size)
    for y in range(size):
        row: list[str] = []
        for x in range(size):
            if x < 3 or y < 3 or x >= size - 3 or y >= size - 3:
                color = "#22483a"
            elif 8 <= x <= 23 and 5 <= y <= 26:
                if x in (8, 23) or y in (5, 26):
                    color = "#f5ddb3"
                else:
                    color = "#fcf8f0"
            elif 12 <= x <= 19 and 9 <= y <= 16:
                color = "#d6472f"
            elif (x - 22) ** 2 + (y - 22) ** 2 <= 22:
                color = "#d6a83a"
            else:
                color = "#428468"
            row.append(color)
        image.put("{" + " ".join(row) + "}", to=(0, y))
    return image


def main() -> int:
    root = tk.Tk()
    BotLauncherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
