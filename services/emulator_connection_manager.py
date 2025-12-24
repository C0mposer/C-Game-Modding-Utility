"""
Centralized Emulator Connection Manager
Manages emulator scanning and connections across the entire application
"""

import threading
from typing import Optional, List, Callable, Dict
from services.emulator_service import EmulatorService, EMULATOR_CONFIGS
from functions.verbose_print import verbose_print
import ctypes
import psutil


class EmulatorConnection:
    """Cached emulator connection state"""
    def __init__(self):
        self.emulator_name: Optional[str] = None
        self.main_ram: Optional[int] = None
        self.handle: Optional[int] = None
        self.kernel32 = None
        self.emu_info = None
        self.is_valid = False

    def reset(self):
        """Reset connection state"""
        if self.handle and self.kernel32:
            try:
                self.kernel32.CloseHandle(self.handle)
            except:
                pass
        self.emulator_name = None
        self.main_ram = None
        self.handle = None
        self.emu_info = None
        self.is_valid = False

    def validate(self) -> bool:
        """Check if connection is still valid"""
        if not self.handle or not self.kernel32:
            return False

        exit_code = ctypes.c_ulong()
        if self.kernel32.GetExitCodeProcess(self.handle, ctypes.byref(exit_code)):
            STILL_ACTIVE = 259
            if exit_code.value == STILL_ACTIVE:
                return True

        # Handle is no longer valid
        try:
            self.kernel32.CloseHandle(self.handle)
        except:
            pass
        self.handle = None
        self.is_valid = False
        return False


class EmulatorConnectionManager:
    """Singleton manager for all emulator connections across the application"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.connection = EmulatorConnection()
            self.available_emulators: List[str] = []
            self.last_scan_result: List[str] = []
            self.cached_pids: Dict[str, int] = {}  # emulator_name -> PID mapping

            # Callbacks for UI updates
            self.on_emulators_scanned: List[Callable[[List[str]], None]] = []
            self.on_connection_changed: List[Callable[[bool, Optional[str]], None]] = []

            # Current project data (needed for EmulatorService)
            self.current_project_data = None

    def set_project_data(self, project_data):
        """Set the current project data (required for EmulatorService)"""
        self.current_project_data = project_data

    def reset_for_project_close(self):
        """Reset connection when project is closed or changed"""
        self.connection.reset()
        self.available_emulators = []
        self.last_scan_result = []
        self._notify_connection_changed(False, None)

    def register_scan_callback(self, callback: Callable[[List[str]], None]):
        """Register a callback to be notified when emulators are scanned"""
        if callback not in self.on_emulators_scanned:
            self.on_emulators_scanned.append(callback)
            verbose_print(f"[EmulatorManager] Registered scan callback: {callback} (total: {len(self.on_emulators_scanned)})")

    def register_connection_callback(self, callback: Callable[[bool, Optional[str]], None]):
        """Register a callback to be notified when connection status changes"""
        if callback not in self.on_connection_changed:
            self.on_connection_changed.append(callback)

    def unregister_scan_callback(self, callback: Callable[[List[str]], None]):
        """Unregister a scan callback"""
        if callback in self.on_emulators_scanned:
            self.on_emulators_scanned.remove(callback)

    def unregister_connection_callback(self, callback: Callable[[bool, Optional[str]], None]):
        """Unregister a connection callback"""
        if callback in self.on_connection_changed:
            self.on_connection_changed.remove(callback)

    def scan_emulators(self) -> List[str]:
        """Scan for available emulators and notify all listeners"""
        if not self.current_project_data:
            return []

        emu_service = EmulatorService(self.current_project_data)
        available = emu_service.get_available_emulators()

        self.available_emulators = available
        self.last_scan_result = available

        # Cache PIDs for each found emulator
        for emu_name in available:
            if emu_name in EMULATOR_CONFIGS:
                emu_info = EMULATOR_CONFIGS[emu_name]
                pid = emu_service._get_pid(emu_info.process_name)
                if pid:
                    self.cached_pids[emu_name] = pid
                    verbose_print(f"[EmulatorManager] Cached PID {pid} for {emu_name}")

        # Print user-friendly summary
        if available:
            emulator_list = ", ".join(available)
            print(f"Found {len(available)} running emulator(s): {emulator_list}")
        else:
            verbose_print("[EmulatorManager] No emulators found")

        verbose_print(f"[EmulatorManager] Registered callbacks: {len(self.on_emulators_scanned)}")

        # Notify all registered callbacks
        for callback in self.on_emulators_scanned:
            try:
                verbose_print(f"[EmulatorManager] Calling callback: {callback}")
                callback(available)
            except Exception as e:
                print(f"Error in scan callback: {e}")
                import traceback
                traceback.print_exc()

        return available

    def get_or_establish_connection(self, emulator_name: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Get or establish emulator connection. Returns (handle, main_ram, kernel32).
        Caches connection for instant reuse and notifies listeners.
        """
        if not self.current_project_data:
            return (None, None, None)

        # Check if we can reuse existing connection
        if (self.connection.is_valid and
            self.connection.emulator_name == emulator_name and
            self.connection.validate()):
            # Reusing cached connection
            return (self.connection.handle,
                    self.connection.main_ram,
                    self.connection.kernel32)

        # Need to establish new connection
        if emulator_name not in EMULATOR_CONFIGS:
            return (None, None, None)

        emu_info = EMULATOR_CONFIGS[emulator_name]
        emu_service = EmulatorService(self.current_project_data)

        # Setup kernel32
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # Get process handle
        PROCESS_VM_OPERATION = 0x8
        PROCESS_VM_READ = 0x10
        PROCESS_VM_WRITE = 0x20
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_ACCESS = PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION

        # Try to use cached PID first
        pid = None
        if emulator_name in self.cached_pids:
            cached_pid = self.cached_pids[emulator_name]
            # Validate that PID still exists and has the correct process name
            if self._validate_pid(cached_pid, emu_info.process_name):
                pid = cached_pid
                verbose_print(f"[EmulatorManager] Using cached PID {pid} for {emulator_name}")
            else:
                verbose_print(f"[EmulatorManager] Cached PID {cached_pid} invalid, re-scanning...")
                # PID is invalid/reused, remove from cache
                del self.cached_pids[emulator_name]

        # If no valid cached PID, search for it
        if pid is None:
            pid = emu_service._get_pid(emu_info.process_name)
            if pid is None:
                return (None, None, None)
            # Cache the new PID
            self.cached_pids[emulator_name] = pid
            verbose_print(f"[EmulatorManager] Cached new PID {pid} for {emulator_name}")

        handle = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
        if not handle:
            return (None, None, None)

        # Get main RAM address
        main_ram = None
        if emu_info.name == "Dolphin":
            main_ram = emu_service._get_dolphin_base_address()
        elif emu_info.name == "PCSX2":
            from services.pcsx2_service import set_ee_base_address_ctypes
            main_ram = set_ee_base_address_ctypes()
        elif emu_info.name == "Duckstation":
            from services.duckstation_service import get_ram_base_address_ctypes
            main_ram = get_ram_base_address_ctypes(pid)  # Pass cached PID to avoid slow process scan
        else:
            main_ram = emu_service._get_main_ram_address(handle, emu_info)

        if main_ram is None or main_ram == 0:
            kernel32.CloseHandle(handle)
            return (None, None, None)

        # Cache the connection
        self.connection.emulator_name = emulator_name
        self.connection.main_ram = main_ram
        self.connection.handle = handle
        self.connection.kernel32 = kernel32
        self.connection.emu_info = emu_info
        self.connection.is_valid = True

        # Notify listeners of successful connection
        self._notify_connection_changed(True, emulator_name)

        return (handle, main_ram, kernel32)

    def get_current_connection(self) -> Optional[EmulatorConnection]:
        """Get the current connection if valid, otherwise None"""
        if self.connection.is_valid and self.connection.validate():
            return self.connection
        return None

    def disconnect(self):
        """Disconnect from current emulator"""
        was_connected = self.connection.is_valid
        emulator_name = self.connection.emulator_name
        self.connection.reset()

        if was_connected:
            self._notify_connection_changed(False, emulator_name)

    def _validate_pid(self, pid: int, expected_process_name: str) -> bool:
        """
        Validate that a PID is still valid and matches the expected process name.
        Returns True if valid, False if PID doesn't exist or process name doesn't match.
        """
        try:
            proc = psutil.Process(pid)
            # Check if process name matches (case-insensitive prefix match)
            actual_name = proc.name().lower()
            expected_name = expected_process_name.lower()
            return actual_name.startswith(expected_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _notify_connection_changed(self, is_connected: bool, emulator_name: Optional[str]):
        """Notify all listeners of connection status change"""
        for callback in self.on_connection_changed:
            try:
                callback(is_connected, emulator_name)
            except Exception as e:
                print(f"Error in connection callback: {e}")


# Global singleton instance
_manager = None

def get_emulator_manager() -> EmulatorConnectionManager:
    """Get the global emulator connection manager instance"""
    global _manager
    if _manager is None:
        _manager = EmulatorConnectionManager()
    return _manager
