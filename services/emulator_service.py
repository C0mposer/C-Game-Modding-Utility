import ctypes
import ctypes.wintypes
import psutil
from services.pid_service import iter_processes
import os
import requests
from typing import List, Tuple, Optional, Dict, Any
from classes.project_data.project_data import ProjectData
from services.pcsx2_service import set_ee_base_address_ctypes
from services.duckstation_service import *
from path_helper import get_application_directory

# Import consolidated memory operations
from services.memory_utils import read_process_memory, write_process_memory

# Windows API constants
PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40
PROCESS_VM_OPERATION = 0x8
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20
PROCESS_QUERY_INFORMATION = 0x0400

DWORD = ctypes.c_uint
HANDLE = ctypes.wintypes.HANDLE
HMODULE = ctypes.wintypes.HMODULE
LPSTR = ctypes.c_char_p
MAX_PATH = 260

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)


class EmulatorInfo:
    """Configuration for different emulators"""
    def __init__(self, name: str, process_name: str, platform: str,
                 base: bool = False, base_exe_dll_name: str = "",
                 ptr: bool = False, double_ptr: bool = False,
                 main_ram_offset: int = 0, address: int = 0):
        self.name = name
        self.process_name = process_name  # Process name to search for
        self.platform = platform
        self.base = base  # Whether to get base address from module
        self.base_exe_dll_name = base_exe_dll_name  # Name of module to get base from
        self.ptr = ptr  # Whether main RAM is accessed via pointer
        self.double_ptr = double_ptr  # Whether it's a pointer to a pointer
        self.main_ram_offset = main_ram_offset  # Offset from base to RAM pointer
        self.address = address  # Direct address (if not using base/ptr)


# Emulator configurations
EMULATOR_CONFIGS = {
    # PS1 Emulators
    "DuckStation": EmulatorInfo(
        name="Duckstation",
        process_name="duckstation",
        platform="PS1",
        base=False,
        ptr=False,
        address=0  # Will be dynamically found
    ),
    "BizHawk": EmulatorInfo(
        name="BizHawk",
        process_name="EmuHawk",
        platform="PS1",
        base=True,
        base_exe_dll_name="octoshock.dll",
        ptr=False,
        main_ram_offset=0x310f80 
    ),
    "Mednafen 1.29": EmulatorInfo(
        name="Mednafen 1.29",
        process_name="mednafen",
        platform="PS1",
        base=False,
        ptr=False,
        address=0x2003E80  #  ACTUAL ADDRESS
    ),
    "Mednafen 1.31": EmulatorInfo(
        name="Mednafen 1.31",
        process_name="mednafen",
        platform="PS1",
        base=False,
        ptr=False,
        address=0x2034E80  #  ACTUAL ADDRESS
    ),
    "PCSX-Redux": EmulatorInfo(
        name="PCSX-Redux",
        process_name="pcsx-redux",
        platform="PS1",
        base=False,
        ptr=False,
        address=0x0  # Uses HTTP API instead
    ),
    
    # PS2 Emulators
    "PCSX2": EmulatorInfo(
        name="PCSX2",
        process_name="pcsx2",  # Will match both pcsx2.exe and pcsx2-qt.exe
        platform="PS2",
        base=False,
        ptr=False,
        address=0  # Will be dynamically found
    ),
    
    # GameCube/Wii Emulators
    "Dolphin": EmulatorInfo(
            name="Dolphin",
            process_name="Dolphin",
            platform="Gamecube",  # Also works for Wii
            base=False,  # We'll use the memory engine instead
            ptr=False,
            double_ptr=False,
            address=0  # Will be filled by GetDolphinBaseAddress()
        ),
    
    # N64 Emulators
    "Project64": EmulatorInfo(
        name="Project64",
        process_name="Project64",
        platform="N64",
        base=True,
        base_exe_dll_name="Project64.exe",
        ptr=True,
        main_ram_offset=0x0  #  Needs to be found
    ),
}


class InjectionResult:
    """Result of an injection operation"""
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


class EmulatorService:
    """Handles injection of compiled code into running emulators"""
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        
    def get_available_emulators(self) -> List[str]:
        """Get list of currently running emulators that match the project's platform"""
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        available: List[str] = []

        # Scan all processes ONCE using the fast Toolhelp32Snapshot-based iterator
        running_processes: dict[str, int] = {}
        try:
            for pid, name in iter_processes():
                if not name:
                    continue
                name_lower = name.lower()
                running_processes[name_lower] = pid
        except OSError as e:
            # Fallback to psutil if the Win32 snapshot fails for some reason
            print(f"Warning: Error scanning processes via Toolhelp32Snapshot: {e}")
            try:
                for proc in psutil.process_iter(attrs=['pid', 'name']):
                    pname = proc.info.get('name')
                    if pname:
                        running_processes[pname.lower()] = proc.info['pid']
            except Exception as e2:
                print(f"Warning: Error scanning processes with psutil: {e2}")
                running_processes = {}

        # Now check each emulator against the cached process list
        for emu_name, emu_info in EMULATOR_CONFIGS.items():
            # Check if emulator matches platform (or is multi-platform like Dolphin)
            if emu_info.platform == platform or (platform == "Wii" and emu_info.platform == "Gamecube"):
                process_name_lower = emu_info.process_name.lower()

                # Check if any running process name starts with the emulator's process name
                for running_proc_name in running_processes.keys():
                    if running_proc_name.startswith(process_name_lower):
                        available.append(emu_name)
                        break

        return available
    
    def inject_into_emulator(self, emulator_name: str) -> InjectionResult:
        """
        Main injection function - injects compiled code into running emulator
        Uses centralized connection manager for cached PIDs and connections.
        """
        if emulator_name not in EMULATOR_CONFIGS:
            return InjectionResult(False, f"Unknown emulator: {emulator_name}")

        emu_info = EMULATOR_CONFIGS[emulator_name]

        # Special case for PCSX-Redux (uses HTTP API)
        if emulator_name == "PCSX-Redux":
            return self._inject_into_redux(emu_info)

        # Special case for PCSX2 - try PINE protocol first
        if emulator_name == "PCSX2":
            print(f" Checking for PINE protocol support...")
            pine_result = self._perform_pine_injection()

            # If PINE succeeded, return the result
            if pine_result is not None:
                return pine_result

            # PINE failed or unavailable, fallback to standard memory write
            print(f" Falling back to standard memory write injection...")

        # Use centralized connection manager for cached connection
        from services.emulator_connection_manager import get_emulator_manager
        manager = get_emulator_manager()
        manager.set_project_data(self.project_data)

        # Get or establish connection (uses cached PID if available)
        handle, main_ram, kernel32 = manager.get_or_establish_connection(emulator_name)

        if not handle or not main_ram:
            return InjectionResult(False,
                f"Could not connect to {emulator_name}.\n\n"
                "Make sure:\n"
                "• Emulator is running\n"
                "• A game is loaded\n"
                "• Run as Administrator if needed")

        try:
            # Perform injection using cached connection
            result = self._perform_injection(handle, main_ram, emu_info.name)

            # If injection succeeded and this is Dolphin, try to trigger auto JIT cache clear
            if result.success and emulator_name == "Dolphin":
                pid = manager.cached_pids.get(emulator_name)
                if pid:
                    self._try_auto_jit_cache_clear(handle, pid)

            return result
        finally:
            # Don't close handle - manager caches it for reuse
            pass
    
   # services/emulator_service.py - REPLACE the _inject_via_memory method
   
    def _change_memory_protection(handle, address, size, protection):
        old_protection = ctypes.c_ulong()
        ctypes.windll.kernel32.VirtualProtectEx(handle, address, size, protection, ctypes.byref(old_protection))
        return old_protection

    def _inject_via_memory(self, emu_info: EmulatorInfo) -> InjectionResult:
        """Inject code via direct memory manipulation"""
        try:
            # Special handling for PCSX2 - use dynamic address detection
            if emu_info.name == "PCSX2":
                # Try pcsx2-qt.exe first, then pcsx2.exe
                main_ram = None
                print(f" Attempting to find PCSX2 EE memory...")
                main_ram = set_ee_base_address_ctypes()
                if main_ram != 0:
                    print(f" Found PCSX2 EE Base Address: 0x{main_ram:X}")

                if main_ram is None or main_ram == 0:
                    return InjectionResult(False,
                        "Could not locate PCSX2 EE memory address.\n\n"
                        "Make sure:\n"
                        "• PCSX2 is running\n"
                        "• A game is loaded and running\n"
                        "• You're running this tool as Administrator")

                # Get the actual process handle for injection
                pid = None
                pid = self._get_pid("pcsx2")

                if pid is None:
                    return InjectionResult(False, "Could not find PCSX2 process")

                # Use specific access rights for memory operations
                PROCESS_ACCESS = (PROCESS_VM_OPERATION | PROCESS_VM_READ |
                                 PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION)
                handle = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
                if not handle:
                    error_code = ctypes.windll.kernel32.GetLastError()
                    return InjectionResult(False,
                        f"Could not open PCSX2 process (error {error_code}). "
                        "Try running as Administrator.")

                try:
                    return self._perform_injection(handle, main_ram, emu_info.name)
                finally:
                    kernel32.CloseHandle(handle)
                    
            if emu_info.name == "Duckstation":
                main_ram = None
                print(f" Attempting to find Duckstation memory...")
                main_ram = get_ram_base_address_ctypes()
                if main_ram != 0:
                    print(f" Found Duckstation Base Address: 0x{main_ram:X}")
                
                if main_ram is None or main_ram == 0:
                    return InjectionResult(False)
                
                # Get the actual process handle for injection
                pid = None
                pid = self._get_pid("duckstation")
                
                if pid is None:
                    return InjectionResult(False, "Could not find Duckstation process")
                
                # Use specific access rights for memory operations
                PROCESS_ACCESS = (PROCESS_VM_OPERATION | PROCESS_VM_READ | 
                                 PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION)
                handle = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
                if not handle:
                    error_code = ctypes.windll.kernel32.GetLastError()
                    return InjectionResult(False, 
                        f"Could not open Duckstation process (error {error_code}). "
                        "Try running as Administrator.")
                
                try:
                    return self._perform_injection(handle, main_ram, emu_info.name)
                finally:
                    kernel32.CloseHandle(handle)
            
            # Special handling for Dolphin - use memory engine
            elif emu_info.name == "Dolphin":
                main_ram = self._get_dolphin_base_address()
                
                if main_ram is None:
                    return InjectionResult(False, 
                        "Could not locate Dolphin MEM1 address.\n\n"
                        "Make sure:\n"
                        "• Dolphin is running\n"
                        "• A game is loaded (not just at menu)\n"
                        "• DolphinMemoryEngine tool is in prereq/DolphinMemoryEngine/")
                
                print(f" Found Dolphin MEM1 at: 0x{main_ram:X}")
                
                # For Dolphin, we inject directly to MEM1 without needing process handle
                # Actually, we still need the handle to write, so let's get it
                pid = self._get_pid(emu_info.process_name)
                if pid is None:
                    return InjectionResult(False, f"Could not find {emu_info.name} process")
                
                handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
                if not handle:
                    return InjectionResult(False, f"Could not open {emu_info.name} process")
                
                try:
                    # Continue with standard injection using main_ram
                    result = self._perform_injection(handle, main_ram, emu_info.name)

                    # If injection succeeded, try to trigger auto JIT cache clear
                    if result.success:
                        self._try_auto_jit_cache_clear(handle, pid)

                    return result
                finally:
                    kernel32.CloseHandle(handle)
            
            else:
                # Standard process for other emulators
                # Get process ID
                pid = self._get_pid(emu_info.process_name)
                if pid is None:
                    return InjectionResult(False, f"Could not find {emu_info.name} process")
                
                # Open process handle
                handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
                if not handle:
                    return InjectionResult(False, f"Could not open {emu_info.name} process")
                
                try:
                    # Get main RAM address
                    main_ram = self._get_main_ram_address(handle, emu_info)
                    if main_ram is None:
                        return InjectionResult(False, "Could not locate main RAM in emulator")
                    
                    print(f" Found main RAM at: 0x{main_ram:X}")
                    
                    # Perform injection
                    return self._perform_injection(handle, main_ram, emu_info.name)
                    
                finally:
                    kernel32.CloseHandle(handle)
        
        except Exception as e:
            import traceback
            return InjectionResult(False, f"Injection error: {str(e)}\n{traceback.format_exc()}")


    def _perform_injection(self, handle: int, main_ram: int, emulator_name: str) -> InjectionResult:
        """
        Perform the actual injection (separated for reuse).
        This is the common injection logic used by all emulators.
        """
        # Load compiled binaries
        bin_data = self._load_compiled_binaries()
        if not bin_data:
            return InjectionResult(False, "No compiled binaries found. Compile project first.")
        
        print(f" Loaded {len(bin_data)} binary file(s)")
        
        injection_count = 0
        failed_count = 0

        # Inject codecaves
        for codecave in self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves():
            if codecave.GetName() not in bin_data:
                print(f" Warning: No binary found for codecave '{codecave.GetName()}'")
                continue
            
            memory_addr = codecave.GetMemoryAddress()
            if not memory_addr:
                print(f" Warning: No memory address set for codecave '{codecave.GetName()}'")
                continue
            
            # Convert "80123456" to actual offset
            offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
            target_address = main_ram + offset
            
            success = self._write_memory(
                handle, 
                target_address, 
                bin_data[codecave.GetName()]
            )
            
            if success:
                print(f" Injected codecave '{codecave.GetName()}' at 0x{memory_addr}")
                injection_count += 1
            else:
                print(f" Failed to inject codecave '{codecave.GetName()}'")
                failed_count += 1

        # Inject hooks
        for hook in self.project_data.GetCurrentBuildVersion().GetEnabledHooks():
            if hook.GetName() not in bin_data:
                print(f" Warning: No binary found for hook '{hook.GetName()}'")
                continue
            
            memory_addr = hook.GetMemoryAddress()
            if not memory_addr:
                print(f" Warning: No memory address set for hook '{hook.GetName()}'")
                continue
            
            offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
            target_address = main_ram + offset
            
            success = self._write_memory(
                handle,
                target_address,
                bin_data[hook.GetName()]
            )
            
            if success:
                print(f" Injected hook '{hook.GetName()}' at 0x{memory_addr}")
                injection_count += 1
            else:
                print(f" Failed to inject hook '{hook.GetName()}'")
                failed_count += 1

        # Inject binary patches
        for patch in self.project_data.GetCurrentBuildVersion().GetEnabledBinaryPatches():
            if patch.GetName() not in bin_data:
                print(f" Warning: No binary found for patch '{patch.GetName()}'")
                continue
            
            memory_addr = patch.GetMemoryAddress()
            if not memory_addr:
                print(f" Warning: No memory address set for patch '{patch.GetName()}'")
                continue
            
            offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
            target_address = main_ram + offset
            
            success = self._write_memory(
                handle,
                target_address,
                bin_data[patch.GetName()]
            )
            
            if success:
                print(f" Injected patch '{patch.GetName()}' at 0x{memory_addr}")
                injection_count += 1
            else:
                print(f" Failed to inject patch '{patch.GetName()}'")
                failed_count += 1
        
        if failed_count > 0:
            return InjectionResult(False, f"Injection completed with {failed_count} failure(s)")

        return InjectionResult(True, f"Successfully injected {injection_count} item(s) into {emulator_name}!")


    def _perform_pine_injection(self, verbose: bool = False) -> InjectionResult:
        """
        Perform injection using PINE protocol for PCSX2.
        This refreshes the recompiler cache for full-speed execution.
        Falls back to standard memory write if PINE fails.

        Args:
            verbose: If True, print detailed debug information
        """
        try:
            print("\n====== Starting PINE injection attempt ======")

            # Import PINE wrapper
            import sys
            pine_path = os.path.join(get_application_directory(), 'prereq', 'pine')

            if verbose:
                print(f"[PINE DEBUG] Calculated PINE path: {pine_path}")
                print(f"[PINE DEBUG] PINE path exists: {os.path.exists(pine_path)}")

            if pine_path not in sys.path:
                sys.path.insert(0, pine_path)
                if verbose:
                    print(f"[PINE DEBUG] Added PINE path to sys.path")

            if verbose:
                print(f"[PINE DEBUG] Attempting to import pcsx2_ipc module...")

            import prereq.pine.pcsx2_ipc as pcsx2_ipc

            if verbose:
                print(f"[PINE DEBUG] Successfully imported pcsx2_ipc module")

            # Initialize PINE IPC
            if verbose:
                print("[PINE DEBUG] Calling pcsx2_ipc.init()...")

            init_result = pcsx2_ipc.init()

            if verbose:
                print(f"[PINE DEBUG] pcsx2_ipc.init() returned: {init_result}")

            if not init_result:
                error_code = pcsx2_ipc.get_last_error()
                error_names = {0: "NoError", 1: "ErrorNotConnected", 2: "ErrorTimeout"}
                error_name = error_names.get(error_code, f"Unknown({error_code})")

                if verbose:
                    print(f"[PINE DEBUG] PINE initialization failed with error code: {error_code} ({error_name})")

                print(f"PCSX2 PINE Injection Failed: {error_name}")
                return None  # Signal fallback

            if verbose:
                print("[PINE DEBUG] PINE initialization successful!")

            try:
                # Load compiled binaries
                if verbose:
                    print("[PINE DEBUG] Loading compiled binaries...")

                bin_data = self._load_compiled_binaries()

                if verbose:
                    print(f"[PINE DEBUG] Loaded {len(bin_data)} binary files")
                    print(f"[PINE DEBUG] Binary files loaded: {list(bin_data.keys())}")
                    for name, data in bin_data.items():
                        print(f"[PINE DEBUG]   {name}: {len(data)} bytes")

                if not bin_data:
                    if verbose:
                        print("[PINE DEBUG] No compiled binaries found, shutting down PINE")
                    pcsx2_ipc.shutdown()
                    return InjectionResult(False, "No compiled binaries found. Compile project first.")

                injection_count = 0
                failed_count = 0

                # Inject codecaves
                codecaves = self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves()

                if verbose:
                    print(f"[PINE DEBUG] Processing {len(codecaves)} codecaves...")

                for codecave in codecaves:
                    codecave_name = codecave.GetName()

                    if verbose:
                        print(f"[PINE DEBUG] Processing codecave: {codecave_name}")

                    if codecave_name not in bin_data:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no binary found for '{codecave_name}'")
                        continue

                    memory_addr = codecave.GetMemoryAddress()
                    if not memory_addr:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no memory address set for '{codecave_name}'")
                        continue

                    # Convert "80123456" to PS2 address (remove 0x80 prefix)
                    ps2_address = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                    data_size = len(bin_data[codecave_name])

                    if verbose:
                        print(f"[PINE DEBUG]   Memory address: {memory_addr} -> PS2 address: 0x{ps2_address:X}")
                        print(f"[PINE DEBUG]   Data size: {data_size} bytes")
                        print(f"[PINE DEBUG]   Calling pcsx2_ipc.write_bytes(0x{ps2_address:X}, {data_size} bytes)...")

                    # Write via PINE
                    success = pcsx2_ipc.write_bytes(ps2_address, bin_data[codecave_name])

                    if verbose:
                        print(f"[PINE DEBUG]   write_bytes returned: {success}")

                    if success:
                        print(f"Injecting codecave '{codecave_name}' at 0x{memory_addr} size {data_size} bytes")
                        injection_count += 1
                    else:
                        error_code = pcsx2_ipc.get_last_error()
                        if verbose:
                            print(f"[PINE DEBUG]   Injection failed! Error code: {error_code}")
                        print(f"Failed to inject codecave '{codecave_name}'")
                        failed_count += 1

                # Inject hooks
                hooks = self.project_data.GetCurrentBuildVersion().GetEnabledHooks()

                if verbose:
                    print(f"[PINE DEBUG] Processing {len(hooks)} hooks...")

                for hook in hooks:
                    hook_name = hook.GetName()

                    if verbose:
                        print(f"[PINE DEBUG] Processing hook: {hook_name}")

                    if hook_name not in bin_data:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no binary found for '{hook_name}'")
                        continue

                    memory_addr = hook.GetMemoryAddress()
                    if not memory_addr:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no memory address set for '{hook_name}'")
                        continue

                    ps2_address = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                    data_size = len(bin_data[hook_name])

                    if verbose:
                        print(f"[PINE DEBUG]   Memory address: {memory_addr} -> PS2 address: 0x{ps2_address:X}")
                        print(f"[PINE DEBUG]   Data size: {data_size} bytes")
                        print(f"[PINE DEBUG]   Calling pcsx2_ipc.write_bytes(0x{ps2_address:X}, {data_size} bytes)...")

                    success = pcsx2_ipc.write_bytes(ps2_address, bin_data[hook_name])

                    if verbose:
                        print(f"[PINE DEBUG]   write_bytes returned: {success}")

                    if success:
                        print(f"Injecting hook '{hook_name}' at 0x{memory_addr} size {data_size} bytes")
                        injection_count += 1
                    else:
                        error_code = pcsx2_ipc.get_last_error()
                        if verbose:
                            print(f"[PINE DEBUG]   Injection failed! Error code: {error_code}")
                        print(f"Failed to inject hook '{hook_name}'")
                        failed_count += 1

                # Inject binary patches
                patches = self.project_data.GetCurrentBuildVersion().GetEnabledBinaryPatches()

                if verbose:
                    print(f"[PINE DEBUG] Processing {len(patches)} patches...")

                for patch in patches:
                    patch_name = patch.GetName()

                    if verbose:
                        print(f"[PINE DEBUG] Processing patch: {patch_name}")

                    if patch_name not in bin_data:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no binary found for '{patch_name}'")
                        continue

                    memory_addr = patch.GetMemoryAddress()
                    if not memory_addr:
                        if verbose:
                            print(f"[PINE DEBUG]   Skipping - no memory address set for '{patch_name}'")
                        continue

                    ps2_address = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                    data_size = len(bin_data[patch_name])

                    if verbose:
                        print(f"[PINE DEBUG]   Memory address: {memory_addr} -> PS2 address: 0x{ps2_address:X}")
                        print(f"[PINE DEBUG]   Data size: {data_size} bytes")
                        print(f"[PINE DEBUG]   Calling pcsx2_ipc.write_bytes(0x{ps2_address:X}, {data_size} bytes)...")

                    success = pcsx2_ipc.write_bytes(ps2_address, bin_data[patch_name])

                    if verbose:
                        print(f"[PINE DEBUG]   write_bytes returned: {success}")

                    if success:
                        print(f"Injecting patch '{patch_name}' at 0x{memory_addr} size {data_size} bytes")
                        injection_count += 1
                    else:
                        error_code = pcsx2_ipc.get_last_error()
                        if verbose:
                            print(f"[PINE DEBUG]   Injection failed! Error code: {error_code}")
                        print(f"Failed to inject patch '{patch_name}'")
                        failed_count += 1

                # Cleanup
                if verbose:
                    print(f"[PINE DEBUG] Injection complete. Success: {injection_count}, Failed: {failed_count}")
                    print("[PINE DEBUG] Calling pcsx2_ipc.shutdown()...")

                pcsx2_ipc.shutdown()

                if verbose:
                    print("[PINE DEBUG] PINE shutdown complete")

                if failed_count > 0:
                    if verbose:
                        print(f"[PINE DEBUG] Returning failure result (had {failed_count} failures)")
                    print(f"\nPCSX2 PINE Injection Failed: {failed_count} item(s) failed to inject")
                    return InjectionResult(False, f"PINE injection completed with {failed_count} failure(s)")

                if verbose:
                    print(f"[PINE DEBUG] Returning success result ({injection_count} items injected)")

                print(f"\nPCSX2 PINE Injection Successful! {injection_count} item(s) injected")
                return InjectionResult(True, f"Successfully injected {injection_count} item(s) via PINE protocol!")

            except Exception as e:
                if verbose:
                    print(f"[PINE DEBUG] Exception during PINE injection: {e}")
                    print(f"[PINE DEBUG] Exception type: {type(e).__name__}")
                    import traceback
                    print(f"[PINE DEBUG] Traceback:\n{traceback.format_exc()}")
                    print("[PINE DEBUG] Shutting down PINE after exception...")

                pcsx2_ipc.shutdown()
                print(f"PCSX2 PINE Injection Failed: {e}")
                return None  # Signal fallback

        except ImportError as e:
            if verbose:
                print(f"[PINE DEBUG] ImportError while importing PINE module: {e}")
                print(f"[PINE DEBUG] Exception type: {type(e).__name__}")
                import traceback
                print(f"[PINE DEBUG] Traceback:\n{traceback.format_exc()}")

            print(f"PCSX2 PINE Injection Failed: PINE module not available ({e})")
            return None  # Signal fallback
        except Exception as e:
            if verbose:
                print(f"[PINE DEBUG] Exception during PINE initialization: {e}")
                print(f"[PINE DEBUG] Exception type: {type(e).__name__}")
                import traceback
                print(f"[PINE DEBUG] Traceback:\n{traceback.format_exc()}")

            print(f"PCSX2 PINE Injection Failed: Initialization error ({e})")
            return None  # Signal fallback



    def _upload_redux_symbols(self):
        """Upload symbol map to PCSX-Redux"""
        try:
            project_folder = self.project_data.GetProjectFolder()
            map_path = os.path.join(project_folder, '.config', 'memory_map', 'MyMod.map')
            
            if not os.path.exists(map_path):
                return
            
            url = "http://127.0.0.1:8080"
            
            # Reset existing symbols
            requests.post(url + "/api/v1/assembly/symbols?function=reset")
            
            # Upload new symbols
            with open(map_path, 'rb') as f:
                response = requests.post(
                    url + "/api/v1/assembly/symbols?function=upload",
                    files={"file": f}
                )
                
                if response.status_code == 200:
                    print(" Uploaded symbols to PCSX-Redux")
        
        except Exception as e:
            print(f" Could not upload symbols: {e}")
    
    def _inject_into_redux(self, emu_info: EmulatorInfo) -> InjectionResult:
        """Special injection for PCSX-Redux via HTTP API"""
        try:
            url = "http://127.0.0.1:8080"
            api_url = url + "/api/v1/cpu/ram/raw"
            
            # Load compiled binaries
            bin_data = self._load_compiled_binaries()
            if not bin_data:
                return InjectionResult(False, "No compiled binaries found. Compile project first.")

            # Inject codecaves
            for codecave in self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves():
                if codecave.GetName() not in bin_data:
                    continue
                
                memory_addr = codecave.GetMemoryAddress()
                if not memory_addr:
                    continue
                
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                data = bin_data[codecave.GetName()]
                
                response = requests.post(
                    api_url + f"?offset={offset}&size={len(data)}",
                    files={"file": data}
                )
                
                if response.status_code == 200:
                    print(f" Injected codecave '{codecave.GetName()}' at 0x{memory_addr}")
                else:
                    print(f" Failed to inject codecave '{codecave.GetName()}'")

            # Inject hooks
            for hook in self.project_data.GetCurrentBuildVersion().GetEnabledHooks():
                if hook.GetName() not in bin_data:
                    continue
                
                memory_addr = hook.GetMemoryAddress()
                if not memory_addr:
                    continue
                
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                data = bin_data[hook.GetName()]
                
                response = requests.post(
                    api_url + f"?offset={offset}&size={len(data)}",
                    files={"file": data}
                )
                
                if response.status_code == 200:
                    print(f" Injected hook '{hook.GetName()}' at 0x{memory_addr}")
                else:
                    print(f" Failed to inject hook '{hook.GetName()}'")

            # Inject binary patches
            for patch in self.project_data.GetCurrentBuildVersion().GetEnabledBinaryPatches():
                if patch.GetName() not in bin_data:
                    continue
                
                memory_addr = patch.GetMemoryAddress()
                if not memory_addr:
                    continue
                
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                data = bin_data[patch.GetName()]
                
                response = requests.post(
                    api_url + f"?offset={offset}&size={len(data)}",
                    files={"file": data}
                )
                
                if response.status_code == 200:
                    print(f" Injected patch '{patch.GetName()}' at 0x{memory_addr}")
                else:
                    print(f" Failed to inject patch '{patch.GetName()}'")
            
            # Upload symbol map
            self._upload_redux_symbols()
            
            return InjectionResult(True, "Successfully injected into PCSX-Redux!")
        
        except Exception as e:
            return InjectionResult(False, f"Redux injection error: {str(e)}")
    
    def _get_main_ram_address(self, handle: int, emu_info: EmulatorInfo) -> Optional[int]:
        # Get base address if needed
        base_address = None
        if emu_info.base:
            base_address = self._get_base_address_from_exe(handle, emu_info.base_exe_dll_name)
            if base_address is None:
                print(f" Could not find base address for {emu_info.base_exe_dll_name}")
                return None
        
        # Pointer to pointer (e.g., Dolphin)
        if emu_info.double_ptr:
            ptr_ptr_addr = base_address + emu_info.main_ram_offset
            ptr_ptr_data = self._read_memory(handle, ptr_ptr_addr, 8)
            if not ptr_ptr_data:
                return None
            
            ptr_addr = int.from_bytes(ptr_ptr_data, byteorder='little', signed=False)
            ptr_data = self._read_memory(handle, ptr_addr, 8)
            if not ptr_data:
                return None
            
            return int.from_bytes(ptr_data, byteorder='little', signed=False)
        
        # Single pointer (e.g., DuckStation, PCSX2)
        elif emu_info.ptr:
            ptr_addr = base_address + emu_info.main_ram_offset
            ptr_data = self._read_memory(handle, ptr_addr, 8)
            if not ptr_data:
                return None
            
            return int.from_bytes(ptr_data, byteorder='little', signed=False)
        
        # Base + offset (e.g., BizHawk)
        elif emu_info.base and not emu_info.ptr:
            return base_address + emu_info.main_ram_offset
        
        # Direct address (e.g., Mednafen, old PCSX2)
        else:
            return emu_info.address
    
    def _get_base_address_from_exe(self, handle: int, module_name: str) -> Optional[int]:
        module_handles = (HMODULE * 1024)()
        cb_needed = DWORD()
        
        if not psapi.EnumProcessModules(handle, module_handles, 
                                       ctypes.sizeof(module_handles), 
                                       ctypes.byref(cb_needed)):
            return None
        
        for i in range(cb_needed.value // ctypes.sizeof(HMODULE)):
            module_name_buffer = (ctypes.c_char * MAX_PATH)()
            if psapi.GetModuleBaseNameA(handle, 
                                       ctypes.c_ulonglong(module_handles[i]), 
                                       module_name_buffer, 
                                       MAX_PATH) > 0:
                current_module = module_name_buffer.value.decode('utf-8')
                if current_module.lower() == module_name.lower():
                    return module_handles[i]
        
        return None
    
    # services/emulator_service.py - UPDATE _read_memory

    def _read_memory(self, handle: int, address: int, size: int) -> Optional[bytes]:
        """Read memory from process - delegates to consolidated memory_utils"""
        return read_process_memory(handle, address, size)
        
    # services/emulator_service.py - UPDATE _write_memory to add test read

    def _write_memory(self, handle: int, address: int, data: bytes) -> bool:
        """Write data to process memory - delegates to consolidated memory_utils"""
        return write_process_memory(handle, address, data)
    
    def _load_compiled_binaries(self) -> Dict[str, bytes]:
        """Load all compiled .bin files from output directory"""
        project_folder = self.project_data.GetProjectFolder()
        bin_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        if not os.path.exists(bin_dir):
            return {}
        
        bin_data = {}
        for filename in os.listdir(bin_dir):
            if filename.endswith('.bin'):
                name = os.path.splitext(filename)[0]
                with open(os.path.join(bin_dir, filename), 'rb') as f:
                    bin_data[name] = f.read()
        
        return bin_data

    
    def _get_pid(self, process_name: str) -> Optional[int]:
        """Get process ID by name (case-insensitive prefix match)"""
        from services.pid_service import get_pid_by_prefix
        return get_pid_by_prefix(process_name)
    
    # def _is_process_running(self, process_name: str) -> bool:
    #     """Check if a process is currently running"""
    #     return self._get_pid(process_name) is not None

    # Cache for auto JIT cache clear support detection
    _dolphin_jit_cache = {}  # exe_path -> (symbol_rva, base_address) or None

    def _try_auto_jit_cache_clear(self, handle: int, pid: int) -> None:
        """
        Try to trigger automatic JIT cache clear on custom Dolphin builds.
        Checks if the Dolphin executable has the exported symbol 'g_dolphin_request_jit_cache_clear',
        and if so, writes 0x1 to it to trigger the JIT cache refresh.

        Args:
            handle: Process handle
            pid: Process ID
        """
        from functions.PE import find_export_rva
        from functions.verbose_print import verbose_print

        try:
            # Get the Dolphin executable path using psutil
            proc = psutil.Process(pid)
            exe_path = proc.exe()

            # Check cache first to avoid slow PE parsing on every injection
            if exe_path not in self._dolphin_jit_cache:
                verbose_print(f"  Checking for auto JIT cache clear support in: {exe_path}")

                # Check if the custom symbol exists (slow operation, only done once)
                symbol_rva = find_export_rva(exe_path, "g_dolphin_request_jit_cache_clear")

                if symbol_rva == 0:
                    verbose_print("  Custom Dolphin build not detected (no g_dolphin_request_jit_cache_clear export)")
                    # Cache the negative result
                    self._dolphin_jit_cache[exe_path] = None
                    return

                # Get the base address of the Dolphin executable module
                base_address = self._get_base_address_from_exe(handle, os.path.basename(exe_path))

                if base_address is None:
                    print(" Warning: Could not get Dolphin base address for auto JIT cache clear")
                    self._dolphin_jit_cache[exe_path] = None
                    return

                # Cache the positive result
                self._dolphin_jit_cache[exe_path] = (symbol_rva, base_address)

                verbose_print(f"  Found g_dolphin_request_jit_cache_clear at RVA 0x{symbol_rva:X}")
                verbose_print(f"  Dolphin base address: 0x{base_address:X}")
                print(f" Custom Dolphin build detected - auto JIT cache clear enabled")

            # Use cached result
            cache_result = self._dolphin_jit_cache[exe_path]
            if cache_result is None:
                return  # Not a custom build

            symbol_rva, base_address = cache_result
            symbol_address = base_address + symbol_rva

            verbose_print(f"  Writing to JIT cache clear symbol at 0x{symbol_address:X}")

            # Write 0x1 to trigger the JIT cache clear
            trigger_value = (1).to_bytes(4, byteorder='little')

            if self._write_memory(handle, symbol_address, trigger_value):
                verbose_print("  Triggered automatic JIT cache clear")
            else:
                print(" Warning: Failed to write to JIT cache clear symbol")

        except psutil.NoSuchProcess:
            print(" Warning: Dolphin process no longer exists")
        except Exception as e:
            print(f" Warning: Could not trigger auto JIT cache clear: {e}")
            import traceback
            verbose_print(traceback.format_exc())

# services/emulator_service.py - ADD this test method

    def test_memory_access(self, handle: int, address: int) -> bool:
        """Test if we can read from an address (to verify it's valid)"""
        try:
            # Try to read 4 bytes
            test_data = self._read_memory(handle, address, 4)
            if test_data:
                print(f"   Test read successful: {' '.join(f'{b:02X}' for b in test_data)}")
                return True
            else:
                print(f"   Test read failed")
                return False
        except:
            print(f"   Test read exception")
            return False
        
    def _get_dolphin_base_address(self) -> Optional[int]:
        """
        Get Dolphin's MEM1 base address using DolphinMemoryEngine.
        Returns the base address as an integer, or None if not found.
        """
        import subprocess
        
        tool_dir = os.getcwd()
        dolphin_mem_tool = os.path.join(tool_dir, "prereq", "DolphinMemoryEngine", "PrintDolphinBaseAddress.exe")
        
        if not os.path.exists(dolphin_mem_tool):
            print(f" Warning: DolphinMemoryEngine not found at {dolphin_mem_tool}")
            return None
        
        try:
            result = subprocess.run(
                [dolphin_mem_tool],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=5
            )
            
            # Parse output
            base_address_str = result.stdout.strip()
            
            if not base_address_str:
                print(" Warning: DolphinMemoryEngine returned empty output")
                return None
            
            # Convert to int
            base_address_int = int(base_address_str, base=16)
            
            if base_address_int == 0x0:
                print(" Warning: Could not find Dolphin MEM1 address (returned 0x0)")
                return None
            
            print(f" Dolphin MEM1 Address: 0x{base_address_int:X}")
            return base_address_int
            
        except subprocess.TimeoutExpired:
            print(" Warning: DolphinMemoryEngine timed out")
            return None
        except ValueError:
            print(f" Warning: Could not parse Dolphin address: {result.stdout}")
            return None
        except Exception as e:
            print(f" Warning: Failed to get Dolphin base address: {e}")
            return None