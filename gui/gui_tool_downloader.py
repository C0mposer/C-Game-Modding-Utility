import tkinter as tk
from tkinter import ttk
from gui import gui_messagebox as messagebox
import threading
from typing import Dict, List
from services.prereq_downloader_service import ToolManager


class ToolDownloaderDialog:

    def __init__(self, parent, tool_manager: ToolManager, required_platforms: List[str] = None):
        self.tool_manager = tool_manager
        self.required_platforms = required_platforms or tool_manager.get_all_platforms()
        self.selected_platforms = set()
        self.download_complete = False
        self.cancelled = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Platform Tools Setup")
        self.dialog.geometry("600x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()
        self._check_installed_platforms()

        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        # Header
        header_frame = tk.Frame(self.dialog, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title = tk.Label(
            header_frame,
            text="Welcome to Code Injection Toolchain",
            font=("Segoe UI", 14, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=10)

        subtitle = tk.Label(
            header_frame,
            text="Select platforms to download tools for:",
            font=("Segoe UI", 9),
            bg="#2c3e50",
            fg="#bdc3c7"
        )
        subtitle.pack()

        # Main content
        content_frame = tk.Frame(self.dialog, padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Platform selection
        self.platform_vars = {}
        self.platform_labels = {}

        for platform in self.required_platforms:
            info = self.tool_manager.get_platform_info(platform)
            if not info:
                continue

            frame = tk.Frame(content_frame, relief=tk.RIDGE, borderwidth=1, padx=10, pady=10)
            frame.pack(fill=tk.X, pady=5)

            var = tk.BooleanVar(value=True)
            self.platform_vars[platform] = var

            cb = tk.Checkbutton(
                frame,
                text=info.display_name,
                variable=var,
                font=("Segoe UI", 10, "bold"),
                command=self._update_selection
            )
            cb.pack(anchor=tk.W)

            size_label = tk.Label(
                frame,
                text=f"Download size: {info.size_mb:.1f} MB",
                font=("Segoe UI", 9),
                fg="#7f8c8d"
            )
            size_label.pack(anchor=tk.W, padx=20)

            status_label = tk.Label(
                frame,
                text="Not installed",
                font=("Segoe UI", 9),
                fg="#e74c3c"
            )
            status_label.pack(anchor=tk.W, padx=20)
            self.platform_labels[platform] = status_label

        # Total size
        self.total_frame = tk.Frame(content_frame, pady=10)
        self.total_frame.pack(fill=tk.X)

        self.total_label = tk.Label(
            self.total_frame,
            text="Total download: 0.0 MB",
            font=("Segoe UI", 10, "bold")
        )
        self.total_label.pack()

        # Progress section (hidden initially)
        self.progress_frame = tk.Frame(content_frame, pady=10)
        self.progress_label = tk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 9)
        )
        self.progress_label.pack()

        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(pady=5)

        # Buttons
        button_frame = tk.Frame(self.dialog, padx=20, pady=10)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_close,
            width=12
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

        self.download_btn = tk.Button(
            button_frame,
            text="Download",
            command=self._start_download,
            width=12,
            bg="#27ae60",
            fg="white",
            font=("Segoe UI", 9, "bold")
        )
        self.download_btn.pack(side=tk.RIGHT, padx=5)

        self.skip_btn = tk.Button(
            button_frame,
            text="Skip (Download Later)",
            command=self._skip_download,
            width=18
        )
        self.skip_btn.pack(side=tk.RIGHT, padx=5)

        # Initial update
        self._update_selection()

    def _check_installed_platforms(self):
        for platform, label in self.platform_labels.items():
            if self.tool_manager.is_platform_installed(platform):
                label.config(text="Already installed", fg="#27ae60")
                # Uncheck if already installed
                self.platform_vars[platform].set(False)

    def _update_selection(self):
        selected = [p for p, var in self.platform_vars.items() if var.get()]
        self.selected_platforms = set(selected)

        total_size = self.tool_manager.get_total_download_size(selected)
        self.total_label.config(text=f"Total download: {total_size:.1f} MB")

        # Enable/disable download button
        self.download_btn.config(state=tk.NORMAL if selected else tk.DISABLED)

    def _start_download(self):
        if not self.selected_platforms:
            return

        # Disable UI during download
        self.download_btn.config(state=tk.DISABLED)
        self.skip_btn.config(state=tk.DISABLED)
        for var in self.platform_vars.values():
            var.trace_remove("write", None)

        # Show progress
        self.progress_frame.pack(fill=tk.X, before=self.total_frame)

        # Start download in background thread
        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()

    def _download_worker(self):
        platforms = list(self.selected_platforms)
        total_platforms = len(platforms)

        for idx, platform in enumerate(platforms):
            if self.cancelled:
                break

            info = self.tool_manager.get_platform_info(platform)

            # Update UI
            self.dialog.after(0, self._update_download_status,
                            f"Downloading {info.display_name} ({idx + 1}/{total_platforms})...",
                            (idx / total_platforms) * 100)

            # Download
            def progress_callback(downloaded, total):
                if total > 0:
                    platform_progress = (downloaded / total) * (100 / total_platforms)
                    total_progress = ((idx / total_platforms) * 100) + platform_progress
                    self.dialog.after(0, self._update_download_status,
                                    f"Downloading {info.display_name}... {downloaded // 1024 // 1024:.1f} MB / {total // 1024 // 1024:.1f} MB",
                                    total_progress)

            success = self.tool_manager.download_platform_tools(platform, progress_callback)

            if not success:
                self.dialog.after(0, messagebox.showerror,
                                "Download Failed",
                                f"Failed to download {info.display_name} tools.\nPlease check your internet connection and try again.")
                self.dialog.after(0, self._download_failed)
                return

            # Update status
            self.dialog.after(0, self._update_platform_status, platform)

        # Download complete
        if not self.cancelled:
            self.dialog.after(0, self._download_finished)

    def _update_download_status(self, message: str, progress: float):
        self.progress_label.config(text=message)
        self.progress_bar['value'] = progress

    def _update_platform_status(self, platform: str):
        if platform in self.platform_labels:
            self.platform_labels[platform].config(
                text="Installed successfully",
                fg="#27ae60"
            )

    def _download_finished(self):
        self.download_complete = True
        self.progress_label.config(text="All platforms installed successfully!")
        self.progress_bar['value'] = 100

        messagebox.showinfo(
            "Download Complete",
            "Platform tools installed successfully!\n\nYou can now create projects and build ISOs."
        )

        self.dialog.destroy()

    def _download_failed(self):
        self.progress_frame.pack_forget()
        self.download_btn.config(state=tk.NORMAL)
        self.skip_btn.config(state=tk.NORMAL)

    def _skip_download(self):
        result = messagebox.askyesno(
            "Skip Download",
            "Are you sure you want to skip downloading platform tools?\n\n"
            "You can download them later from the Settings menu."
        )
        if result:
            self.dialog.destroy()

    def _on_close(self):
        if self.download_btn['state'] == tk.DISABLED:
            # Download in progress
            result = messagebox.askyesno(
                "Cancel Download",
                "Download is in progress. Are you sure you want to cancel?"
            )
            if result:
                self.cancelled = True
                self.dialog.destroy()
        else:
            self.dialog.destroy()

    def show(self) -> bool:
        self.dialog.wait_window()
        return self.download_complete


def check_and_prompt_missing_tools(parent, tool_dir: str, required_platforms: List[str] = None) -> bool:
    manager = ToolManager(tool_dir)

    # Determine which platforms to check
    platforms_to_check = required_platforms or ['common']  # At minimum need common tools

    missing = manager.get_missing_platforms(platforms_to_check)

    if missing:
        dialog = ToolDownloaderDialog(parent, manager, missing)
        return dialog.show()

    return True  # All required tools present
