import tkinter as tk
from tkinter import ttk
import threading
import dearpygui.dearpygui as dpg
from services.prereq_downloader_service import ToolManager
from gui import gui_messagebox as messagebox


class PrereqDownloadPrompt:
    def __init__(self, tool_manager: ToolManager, platform_key: str, platform_display_name: str):

        self.tool_manager = tool_manager
        self.platform_key = platform_key
        self.platform_display_name = platform_display_name
        self.download_complete = False
        self.cancelled = False

        # Create dialog
        self.dialog = tk.Tk()
        self.dialog.title("Download Prerequisites")

        dialog_width = 550
        dialog_height = 280

        # Place over main window
        viewport_pos = dpg.get_viewport_pos()
        viewport_width = dpg.get_viewport_client_width()
        viewport_height = dpg.get_viewport_client_height()

        center_x = viewport_pos[0] + (viewport_width - dialog_width) // 2
        center_y = viewport_pos[1] + (viewport_height - dialog_height) // 2

        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{center_x}+{center_y}")
        self.dialog.resizable(False, False)

        self.dialog.attributes('-topmost', True)
        self.dialog.lift()
        self.dialog.focus_force()

        self._create_widgets()

        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        header_frame = tk.Frame(self.dialog, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title = tk.Label(
            header_frame,
            text="Missing Prerequisites",
            font=("Segoe UI", 14, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=15)

        content_frame = tk.Frame(self.dialog, padx=30, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        package_info = self.tool_manager.get_platform_info(self.platform_key)
        message = f"{self.platform_display_name} prerequisites are not installed.\n\n" \
                  f"Download size: {package_info.size_mb:.1f} MB"

        msg_label = tk.Label(
            content_frame,
            text=message,
            font=("Segoe UI", 10),
            justify=tk.LEFT
        )
        msg_label.pack(pady=10)

        # Progress section (hidden initially)
        self.progress_frame = tk.Frame(content_frame)

        self.progress_label = tk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 9)
        )
        self.progress_label.pack()

        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            length=450
        )
        self.progress_bar.pack(pady=5)

        # Buttons
        button_frame = tk.Frame(self.dialog, padx=20, pady=15)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_close,
            width=12
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

        self.download_all_btn = tk.Button(
            button_frame,
            text="Download All Platform Tools",
            command=self._download_all,
            width=25,
            bg="#3498db",
            fg="white",
            font=("Segoe UI", 9, "bold")
        )
        self.download_all_btn.pack(side=tk.RIGHT, padx=5)

        self.download_btn = tk.Button(
            button_frame,
            text=f"Download {package_info.display_name} Tools",
            command=self._download_platform,
            width=32,
            bg="#27ae60",
            fg="white",
            font=("Segoe UI", 9, "bold")
        )
        self.download_btn.pack(side=tk.RIGHT, padx=5)

    def _download_platform(self):
        self._start_download(platforms=[self.platform_key])

    def _download_all(self):
        all_platforms = self.tool_manager.get_all_platforms()
        self._start_download(platforms=all_platforms)

    def _start_download(self, platforms):
        # Disable UI during download
        self.download_btn.config(state=tk.DISABLED)
        self.download_all_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)

        # Show progress
        self.progress_frame.pack(fill=tk.X, pady=10)

        # Start download in background thread
        thread = threading.Thread(target=self._download_worker, args=(platforms,), daemon=True)
        thread.start()

    def _download_worker(self, platforms):
        total_platforms = len(platforms)

        for idx, platform in enumerate(platforms):
            if self.cancelled:
                break

            info = self.tool_manager.get_platform_info(platform)

            self.dialog.after(0, self._update_progress,
                            f"Downloading {info.display_name} tools... ({idx + 1}/{total_platforms})",
                            (idx / total_platforms) * 100)

            def progress_callback(downloaded, total):
                if total > 0:
                    platform_progress = (downloaded / total) * (100 / total_platforms)
                    total_progress = ((idx / total_platforms) * 100) + platform_progress
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    self.dialog.after(0, self._update_progress,
                                    f"Downloading {info.display_name} tools... {mb_downloaded:.1f} / {mb_total:.1f} MB",
                                    total_progress)

            success = self.tool_manager.download_platform_tools(platform, progress_callback)

            if not success:
                self.dialog.after(0, self._download_failed, info.display_name)
                return

        # Download complete
        if not self.cancelled:
            self.dialog.after(0, self._download_finished)

    def _update_progress(self, message: str, progress: float):
        self.progress_label.config(text=message)
        self.progress_bar['value'] = progress

    def _download_failed(self, platform_name: str):
        messagebox.showerror(
            "Download Failed",
            f"Failed to download {platform_name} prerequisites.\n\n",
            parent=self.dialog
        )
        self.dialog.destroy()

    def _download_finished(self):
        self.download_complete = True
        messagebox.showinfo(
            "Download Complete",
            "Prerequisites installed successfully.",
            parent=self.dialog
        )
        self.dialog.destroy()

    def _on_close(self):
        if self.download_btn['state'] == tk.DISABLED:
            # Download in progress
            result = messagebox.askyesno(
                "Cancel Download",
                "Download is in progress. Are you sure you want to cancel?",
                parent=self.dialog
            )
            if result:
                self.cancelled = True
                self.dialog.destroy()
        else:
            self.cancelled = True
            self.dialog.destroy()

    def show(self) -> bool:
        self.dialog.mainloop()
        return self.download_complete


def check_and_prompt_prereqs(tool_dir: str, platform_name: str, parent_window=None) -> bool:
    tool_manager = ToolManager(tool_dir)

    # Check if already installed
    if tool_manager.check_platform_prereqs(platform_name):
        return True

    # Get platform key
    platform_key = tool_manager.PLATFORM_MAP.get(platform_name)
    if not platform_key:
        return True  # Unknown platform, let it continue

    prompt = PrereqDownloadPrompt(tool_manager, platform_key, platform_name)
    return prompt.show()
