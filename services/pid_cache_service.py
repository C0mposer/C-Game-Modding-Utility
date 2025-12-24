import os
import json
import psutil
from typing import Optional, Dict

#! Technically, cacheing is not as needed anymore since we made PID scanning faster, but oh well
class PIDCacheService:
    def __init__(self, project_folder: str):
        self.project_folder = project_folder
        self.cache_dir = os.path.join(project_folder, ".config")
        self.cache_file = os.path.join(self.cache_dir, "emulator_pid_cache.json")
        self.cache: Dict[str, int] = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def _save_cache(self):
        try:
            # Ensure .config directory exists
            os.makedirs(self.cache_dir, exist_ok=True)

            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            pass

    def get_cached_pid(self, emulator_name: str, expected_process_name: str) -> Optional[int]:
        if emulator_name not in self.cache:
            return None

        cached_pid = self.cache[emulator_name]

        # Validate that PID still exists and matches expected process
        if self._validate_pid(cached_pid, expected_process_name):
            return cached_pid

        # PID is stale, remove from cache
        del self.cache[emulator_name]
        self._save_cache()
        return None

    def cache_pid(self, emulator_name: str, pid: int):
        self.cache[emulator_name] = pid
        self._save_cache()

    def invalidate_cache(self, emulator_name: Optional[str] = None):
        if emulator_name is None:
            self.cache = {}
        elif emulator_name in self.cache:
            del self.cache[emulator_name]

        self._save_cache()

    def _validate_pid(self, pid: int, expected_process_name: str) -> bool:
        try:
            proc = psutil.Process(pid)
            # Check if process name matches (case-insensitive prefix match)
            actual_name = proc.name().lower()
            expected_name = expected_process_name.lower()
            return actual_name.startswith(expected_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
