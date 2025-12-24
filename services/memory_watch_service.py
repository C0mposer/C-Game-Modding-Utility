import time
import threading
import os
from typing import List, Optional, Callable, Tuple
from enum import Enum
from functions.verbose_print import verbose_print

class DataType(Enum):
    """Memory data types"""
    BYTE_SIGNED = "s8"
    BYTE_UNSIGNED = "u8"
    SHORT_SIGNED = "s16"
    SHORT_UNSIGNED = "u16"
    INT_SIGNED = "s32"
    INT_UNSIGNED = "u32"
    FLOAT = "float"  # 4 bytes: IEEE 754 single precision
    RGB = "rgb"    # 3 bytes: R, G, B
    RGBA = "rgba"  # 4 bytes: R, G, B, A
    BGR = "bgr"    # 3 bytes: B, G, R
    BGRA = "bgra"  # 4 bytes: B, G, R, A

    @property
    def size(self) -> int:
        """Size in bytes"""
        if self == DataType.RGB or self == DataType.BGR:
            return 3
        if self in (DataType.RGBA, DataType.BGRA):
            return 4
        if self in (DataType.BYTE_SIGNED, DataType.BYTE_UNSIGNED):
            return 1
        if self in (DataType.SHORT_SIGNED, DataType.SHORT_UNSIGNED):
            return 2
        if self in (DataType.INT_SIGNED, DataType.INT_UNSIGNED, DataType.FLOAT):
            return 4
        return 4

    @property
    def is_signed(self) -> bool:
        """Check if signed type"""
        return self.value.startswith("s")

    @property
    def is_color(self) -> bool:
        """Check if this is a color type"""
        return self in (DataType.RGB, DataType.RGBA, DataType.BGR, DataType.BGRA)

    @property
    def has_alpha(self) -> bool:
        """Check if this color type has an alpha channel"""
        return self in (DataType.RGBA, DataType.BGRA)


class WatchEntry:
    """Represents a single memory watch entry"""

    def __init__(self, address: int, data_type: DataType, name: str = ""):
        self.address = address
        self.data_type = data_type
        self.name = name or f"0x{address:X}"
        self.current_value: Optional[int] = None
        self.previous_value: Optional[int] = None
        self.last_updated = 0.0
        self.has_changed = False

        # For color types (RGB/RGBA/BGR/BGRA)
        self.rgb_value: Optional[Tuple[int, int, int]] = None
        self.rgba_value: Optional[Tuple[int, int, int, int]] = None
        self.previous_rgb_value: Optional[Tuple[int, int, int]] = None
        self.previous_rgba_value: Optional[Tuple[int, int, int, int]] = None

    def update_value(self, new_value: int):
        """Update with new value"""
        if self.current_value is not None:
            self.previous_value = self.current_value

        self.current_value = new_value
        self.last_updated = time.time()

        if self.previous_value is not None:
            self.has_changed = (self.current_value != self.previous_value)
        else:
            self.has_changed = False

    def update_rgb_value(self, r: int, g: int, b: int):
        """Update RGB value (3 components)"""
        if self.rgb_value is not None:
            self.previous_rgb_value = self.rgb_value

        self.rgb_value = (r, g, b)
        self.last_updated = time.time()

        if self.previous_rgb_value is not None:
            self.has_changed = (self.rgb_value != self.previous_rgb_value)
        else:
            self.has_changed = False

    def update_rgba_value(self, r: int, g: int, b: int, a: int):
        """Update RGBA value (4 components)"""
        if self.rgba_value is not None:
            self.previous_rgba_value = self.rgba_value

        self.rgba_value = (r, g, b, a)
        self.last_updated = time.time()

        if self.previous_rgba_value is not None:
            self.has_changed = (self.rgba_value != self.previous_rgba_value)
        else:
            self.has_changed = False

    def format_value(self) -> str:
        """Format current value as string"""
        # Handle RGB/BGR (3 bytes)
        if self.data_type in (DataType.RGB, DataType.BGR):
            if self.rgb_value is None:
                return "---"
            r, g, b = self.rgb_value
            return f"R:{r} G:{g} B:{b}"

        # Handle RGBA/BGRA (4 bytes)
        if self.data_type in (DataType.RGBA, DataType.BGRA):
            if self.rgba_value is None:
                return "---"
            r, g, b, a = self.rgba_value
            return f"R:{r} G:{g} B:{b} A:{a}"

        if self.current_value is None:
            return "---"

        # Handle float
        if self.data_type == DataType.FLOAT:
            import struct
            try:
                float_val = struct.unpack('f', self.current_value.to_bytes(4, byteorder='little'))[0]
                return f"{float_val:.6f}"
            except:
                return "---"

        if self.data_type.is_signed:
            max_val = 1 << (self.data_type.size * 8)
            if self.current_value >= max_val // 2:
                return str(self.current_value - max_val)

        return str(self.current_value)

    def format_hex(self) -> str:
        """Format current value as hex"""
        # Handle RGB/BGR (3 bytes)
        if self.data_type in (DataType.RGB, DataType.BGR):
            if self.rgb_value is None:
                return "---"
            r, g, b = self.rgb_value
            return f"{r:02X}{g:02X}{b:02X}"

        # Handle RGBA/BGRA (4 bytes)
        if self.data_type in (DataType.RGBA, DataType.BGRA):
            if self.rgba_value is None:
                return "---"
            r, g, b, a = self.rgba_value
            return f"{r:02X}{g:02X}{b:02X}{a:02X}"

        if self.current_value is None:
            return "---"

        width = self.data_type.size * 2
        return f"0x{self.current_value:0{width}X}"


class MemoryWatchService:
    """Service for watching memory addresses in real-time"""

    def __init__(self):
        self.watch_entries: List[WatchEntry] = []
        self.is_running = False
        self.poll_interval = 0.1  # 100ms
        self.poll_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Callbacks
        self.on_update: Optional[Callable[[List[WatchEntry]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Emulator connection
        self.emulator_service = None
        self.emulator_name: Optional[str] = None
        self.main_ram_address: Optional[int] = None

        # Cached for fast I/O
        self._emu_info = None
        self._kernel32 = None
        self._process_handle = None
        
        # Connection validity flag
        self._connection_valid = False

    # ---------- Setup / teardown ----------

    def reset_connection(self):
        """Reset all connection state - call this only when changing projects"""
        print("Resetting memory watch connection state...")
        
        # Stop polling if running
        if self.is_running:
            self.stop()
        
        # Close existing handle
        if self._process_handle and self._kernel32:
            try:
                self._kernel32.CloseHandle(self._process_handle)
                print("Closed previous process handle")
            except Exception as e:
                print(f"Error closing handle: {e}")
        
        # Clear all cached state
        self._process_handle = None
        self.main_ram_address = None
        self.emulator_name = None
        self._emu_info = None
        self._connection_valid = False
        
        # Clear watches
        self.watch_entries.clear()
        
        print("Connection state reset complete")

    def set_emulator_connection(self, emulator_service, emulator_name: str):
        """
        Set the emulator connection for reading memory.
        Uses centralized connection manager for cached PIDs and connections.
        """
        # Only reset if we're connecting to a different emulator or don't have a valid connection
        if self._connection_valid and self.emulator_name == emulator_name and self.main_ram_address:
            print(f"Reusing existing connection to {emulator_name}")
            # Validate the handle is still good
            if self._validate_existing_connection():
                return True
            else:
                print("Existing connection no longer valid, reconnecting...")

        # Use centralized connection manager for cached connection
        from services.emulator_connection_manager import get_emulator_manager
        from services.emulator_service import EMULATOR_CONFIGS

        manager = get_emulator_manager()
        if hasattr(emulator_service, 'project_data'):
            manager.set_project_data(emulator_service.project_data)

        self._emu_info = EMULATOR_CONFIGS.get(emulator_name)
        if not self._emu_info:
            print(f"Unknown emulator: {emulator_name}")
            self._connection_valid = False
            return False

        # Get or establish connection (uses cached PID if available)
        handle, main_ram, kernel32 = manager.get_or_establish_connection(emulator_name)

        if not handle or not main_ram:
            print(f"Could not connect to {emulator_name}")
            self._connection_valid = False
            return False

        # Store connection info
        self.emulator_service = emulator_service
        self.emulator_name = emulator_name
        self.main_ram_address = main_ram
        self._process_handle = handle
        self._kernel32 = kernel32
        self._connection_valid = True

        print(f"Memory watch connected to {emulator_name} at 0x{self.main_ram_address:X}")
        return True
    
    def _validate_existing_connection(self) -> bool:
        """Check if the existing connection is still valid"""
        if not self._process_handle or not self._kernel32:
            return False
        
        import ctypes
        exit_code = ctypes.c_ulong()
        if self._kernel32.GetExitCodeProcess(self._process_handle, ctypes.byref(exit_code)):
            STILL_ACTIVE = 259
            if exit_code.value == STILL_ACTIVE:
                return True
        
        # Handle is no longer valid
        try:
            self._kernel32.CloseHandle(self._process_handle)
        except Exception:
            pass
        self._process_handle = None
        self._connection_valid = False
        return False

    def _get_main_ram_address(self) -> Optional[int]:
        """Resolve the main RAM base address once."""
        if not self.emulator_service or not self._emu_info:
            return None

        emu_info = self._emu_info

        try:
            # PCSX2: use pcsx2_service
            if emu_info.name == "PCSX2":
                from services.pcsx2_service import set_ee_base_address_ctypes
                
                base = None
                base = set_ee_base_address_ctypes()
                if base != 0:
                    print(f"Memory watch found PCSX2 EE Base at: 0x{base:X}")
                    return base
                
                print("Memory watch could not locate PCSX2 EE memory address")
                return None
            
            if emu_info.name == "Duckstation":
                from services.duckstation_service import get_ram_base_address_ctypes
                
                base = None
                base = get_ram_base_address_ctypes()
                if base != 0:
                    print(f"Memory watch found Duckstation memory at: 0x{base:X}")
                    return base
                
                print("Memory watch could not locate Duckstation memory address")
                return None
            
            # Dolphin: use its helper
            if emu_info.name == "Dolphin":
                base = self.emulator_service._get_dolphin_base_address()
                if base:
                    print(f"Memory watch found Dolphin MEM1 at: 0x{base:X}")
                    return base
                print("Memory watch could not locate Dolphin MEM1 address")
                return None

            # Others: open once, query, close
            k32 = self._ensure_kernel32()
            pid = self.emulator_service._get_pid(emu_info.process_name)
            if not pid:
                return None

            PROCESS_ALL_ACCESS = 0x1F0FFF
            handle = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not handle:
                return None

            try:
                return self.emulator_service._get_main_ram_address(handle, emu_info)
            finally:
                k32.CloseHandle(handle)

        except Exception as e:
            print(f"Error getting RAM address: {e}")
            return None

    def _ensure_kernel32(self):
        if self._kernel32 is None:
            import ctypes
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return self._kernel32

    def _ensure_process_handle(self) -> Optional[int]:
        """Use a cached OpenProcess handle; reopen if needed."""
        if not self.emulator_service or not self._emu_info:
            return None

        import ctypes
        k32 = self._ensure_kernel32()

        # Validate existing handle
        if self._process_handle:
            exit_code = ctypes.c_ulong()
            if k32.GetExitCodeProcess(self._process_handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                if exit_code.value == STILL_ACTIVE:
                    return self._process_handle
            # Handle is invalid - close it
            try:
                k32.CloseHandle(self._process_handle)
            except Exception:
                pass
            self._process_handle = None

        # Open new handle
        pid = self.emulator_service._get_pid(self._emu_info.process_name)
        if not pid:
            print(f"Could not find process: {self._emu_info.process_name}")
            return None

        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            print(f"Could not open process (error {error})")
            return None

        self._process_handle = handle
        print(f"Opened new process handle: {handle}")
        return handle

    # ---------- Watch management ----------

    def add_watch(self, address: int, data_type: DataType, name: str = "") -> WatchEntry:
        with self.lock:
            entry = WatchEntry(address, data_type, name)
            self.watch_entries.append(entry)
            verbose_print(f"Added watch: {entry.name} ({data_type.value})")
            return entry

    def remove_watch(self, entry: WatchEntry):
        with self.lock:
            if entry in self.watch_entries:
                self.watch_entries.remove(entry)
                print(f"Removed watch: {entry.name}")

    def clear_watches(self):
        with self.lock:
            self.watch_entries.clear()
            print("Cleared all watches")

    # ---------- Poll loop ----------

    def start(self):
        if self.is_running:
            print("Memory watch already running")
            return

        if not self.main_ram_address or not self._connection_valid:
            print("Cannot start: no valid emulator connection")
            if self.on_error:
                self.on_error("No emulator connection")
            return

        # Ensure we have a valid handle before starting
        if not self._ensure_process_handle():
            print("Cannot start: failed to get process handle")
            if self.on_error:
                self.on_error("Failed to connect to emulator process")
            return

        self.is_running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        print("Memory watch started")

    def stop(self):
        if not self.is_running:
            return
            
        self.is_running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=1.0)

        # Don't close the handle - keep it cached for when window reopens
        print("Memory watch stopped (keeping connection alive)")

    def _poll_loop(self):
        while self.is_running:
            try:
                self._update_all_watches()
                if self.on_update:
                    with self.lock:
                        entries_copy = list(self.watch_entries)
                    self.on_update(entries_copy)
            except Exception as e:
                print(f"Poll error: {e}")
                if self.on_error:
                    self.on_error(str(e))
            time.sleep(self.poll_interval)

    def _update_all_watches(self):
        if not self.main_ram_address or not self.emulator_service or not self._emu_info:
            return

        handle = self._ensure_process_handle()
        if not handle:
            if self.on_error:
                self.on_error("Emulator not running")
            self.stop()
            return

        with self.lock:
            for entry in self.watch_entries:
                if entry.data_type.is_color:
                    color = self._read_color_value(handle, entry.address, entry.data_type)
                    if color is not None:
                        if entry.data_type.has_alpha:
                            entry.update_rgba_value(*color)
                        else:
                            entry.update_rgb_value(*color)
                else:
                    value = self._read_value(handle, entry.address, entry.data_type)
                    if value is not None:
                        entry.update_value(value)

    # ---------- Low-level IO helpers ----------

    def _normalize_offset(self, address: int) -> int:
        addr_str = f"{address:X}"
        if addr_str.startswith("80"):
            return int(addr_str[2:], 16)
        return address

    def _is_big_endian_platform(self) -> bool:
        """Check if the emulator platform uses big-endian byte order"""
        if not self._emu_info:
            return False
        return self._emu_info.platform in ["Gamecube", "Wii"]

    def _is_ps2(self) -> bool:
        """Check if currently connected to PS2/PCSX2"""
        return self._emu_info and self._emu_info.name == "PCSX2"

    def _get_pine_ipc(self):
        """Get PINE IPC module (cached)"""
        if not hasattr(self, '_pine_ipc'):
            import sys
            from path_helper import get_application_directory
            pine_path = os.path.join(get_application_directory(), 'prereq', 'pine')
            if pine_path not in sys.path:
                sys.path.insert(0, pine_path)
            import prereq.pine.pcsx2_ipc as pcsx2_ipc
            self._pine_ipc = pcsx2_ipc
        return self._pine_ipc

    def _read_memory_pine(self, ps2_address: int, size: int) -> Optional[bytes]:
        """Read memory using PINE protocol for PS2"""
        try:
            pine = self._get_pine_ipc()

            # Initialize PINE if not already
            if not hasattr(self, '_pine_initialized') or not self._pine_initialized:
                if not pine.init():
                    print(f"PINE initialization failed")
                    return None
                self._pine_initialized = True

            # Read bytes via PINE
            data = pine.read_bytes(ps2_address, size)
            if data:
                return bytes(data)
            return None

        except Exception as e:
            print(f"PINE read error: {e}")
            return None

    def _write_memory_pine(self, ps2_address: int, data: bytes) -> bool:
        """Write memory using PINE protocol for PS2"""
        try:
            pine = self._get_pine_ipc()

            # Initialize PINE if not already
            if not hasattr(self, '_pine_initialized') or not self._pine_initialized:
                if not pine.init():
                    print(f"PINE initialization failed")
                    return False
                self._pine_initialized = True

            # Write bytes via PINE
            success = pine.write_bytes(ps2_address, data)
            return bool(success)

        except Exception as e:
            print(f"PINE write error: {e}")
            return False

    def _read_value(self, handle: int, address: int, data_type: DataType) -> Optional[int]:
        if not self.main_ram_address:
            return None

        offset = self._normalize_offset(address)

        # Use PINE for PS2
        if self._is_ps2():
            data = self._read_memory_pine(offset, data_type.size)
        else:
            target_address = self.main_ram_address + offset
            data = self.emulator_service._read_memory(handle, target_address, data_type.size)

        if not data:
            return None

        if self._is_big_endian_platform():
            value = int.from_bytes(data, byteorder="big", signed=False)
        else:
            value = int.from_bytes(data, byteorder="little", signed=False)

        return value

    def _read_color_value(self, handle: int, address: int, data_type: DataType):
        """Read color value from memory - handles RGB, RGBA, BGR, BGRA"""
        if not self.main_ram_address:
            return None

        offset = self._normalize_offset(address)
        num_bytes = data_type.size

        # Use PINE for PS2
        if self._is_ps2():
            data = self._read_memory_pine(offset, num_bytes)
        else:
            target_address = self.main_ram_address + offset
            data = self.emulator_service._read_memory(handle, target_address, num_bytes)

        if not data or len(data) != num_bytes:
            return None

        # Parse based on color format
        if data_type == DataType.RGB:
            # RGB: R, G, B
            r, g, b = data[0], data[1], data[2]
            return r, g, b
        elif data_type == DataType.RGBA:
            # RGBA: R, G, B, A
            r, g, b, a = data[0], data[1], data[2], data[3]
            return r, g, b, a
        elif data_type == DataType.BGR:
            # BGR: B, G, R
            b, g, r = data[0], data[1], data[2]
            return r, g, b
        elif data_type == DataType.BGRA:
            # BGRA: B, G, R, A
            b, g, r, a = data[0], data[1], data[2], data[3]
            return r, g, b, a

        return None

    def write_value(self, address: int, value: int, data_type: DataType) -> bool:
        """Write scalar value using cached handle (Cheat Engine style) or PINE for PS2."""
        if not self.main_ram_address or not self.emulator_service or not self._emu_info:
            return False

        try:
            offset = self._normalize_offset(address)

            if value < 0:
                max_val = 1 << (data_type.size * 8)
                value = max_val + value

            if self._is_big_endian_platform():
                data = value.to_bytes(data_type.size, "big", signed=False)
            else:
                data = value.to_bytes(data_type.size, "little", signed=False)

            # Use PINE for PS2
            if self._is_ps2():
                success = self._write_memory_pine(offset, data)
            else:
                handle = self._ensure_process_handle()
                if not handle:
                    return False
                target_address = self.main_ram_address + offset
                success = self.emulator_service._write_memory(handle, target_address, data)

            return bool(success)

        except Exception as e:
            print(f"Error writing value: {e}")
            return False

    def write_color_value(self, address: int, data_type: DataType, r: int, g: int, b: int, a: int = 255) -> bool:
        """Write color value (RGB/RGBA/BGR/BGRA) using cached handle or PINE for PS2"""
        if not self.main_ram_address or not self.emulator_service or not self._emu_info:
            return False

        try:
            offset = self._normalize_offset(address)

            # Clamp values to 0-255
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            a = max(0, min(255, a))

            # Write bytes based on format
            if data_type == DataType.RGB:
                data = bytes([r, g, b])
            elif data_type == DataType.RGBA:
                data = bytes([r, g, b, a])
            elif data_type == DataType.BGR:
                data = bytes([b, g, r])
            elif data_type == DataType.BGRA:
                data = bytes([b, g, r, a])
            else:
                return False

            # Use PINE for PS2
            if self._is_ps2():
                success = self._write_memory_pine(offset, data)
            else:
                handle = self._ensure_process_handle()
                if not handle:
                    return False
                target_address = self.main_ram_address + offset
                success = self.emulator_service._write_memory(handle, target_address, data)

            if success:
                if data_type.has_alpha:
                    print(f"Wrote {data_type.value.upper()} to 0x{address:X}: R={r}, G={g}, B={b}, A={a}")
                else:
                    print(f"Wrote {data_type.value.upper()} to 0x{address:X}: R={r}, G={g}, B={b}")

            return bool(success)

        except Exception as e:
            print(f"Error writing color value: {e}")
            return False
        
    def write_float_value(self, address: int, float_value: float) -> bool:
        if not self.main_ram_address or not self.emulator_service or not self._emu_info:
            return False

        try:
            import struct
            offset = self._normalize_offset(address)

            # Convert float to bytes
            if self._is_big_endian_platform():
                data = struct.pack('>f', float_value)  # Big-endian
            else:
                data = struct.pack('<f', float_value)  # Little-endian

            # Use PINE for PS2
            if self._is_ps2():
                success = self._write_memory_pine(offset, data)
            else:
                handle = self._ensure_process_handle()
                if not handle:
                    return False
                target_address = self.main_ram_address + offset
                success = self.emulator_service._write_memory(handle, target_address, data)

            if success:
                print(f"Wrote float to 0x{address:X}: {float_value}")

            return bool(success)

        except Exception as e:
            print(f"Error writing float value: {e}")
            return False