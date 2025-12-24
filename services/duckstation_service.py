import ctypes
import ctypes.wintypes
import psutil
import struct
import time
import os
import pefile
from functions.verbose_print import *

# Import consolidated utilities
from services.emulator_pid_utils import find_emulator_pid
from services.memory_utils import read_process_memory
from functions.PE import find_export_rva

# --- Windows API Definitions (Kernel32.dll) ---
# Load kernel32 library
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Define necessary Win32 types and constants
SIZE_T = ctypes.c_size_t
DWORD = ctypes.wintypes.DWORD
HANDLE = ctypes.wintypes.HANDLE
LPCVOID = ctypes.wintypes.LPCVOID
LPVOID = ctypes.wintypes.LPVOID

# Define Access Rights for OpenProcess 
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)

# Function Signatures for Process Handling
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, ctypes.wintypes.BOOL, DWORD]
OpenProcess.restype = HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = ctypes.wintypes.BOOL

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    HANDLE,      # hProcess
    LPCVOID,     # lpBaseAddress
    LPVOID,      # lpBuffer
    SIZE_T,      # nSize
    ctypes.POINTER(SIZE_T)  # lpNumberOfBytesRead
]
ReadProcessMemory.restype = ctypes.wintypes.BOOL

# Functions for Symbol Lookup
LoadLibrary = kernel32.LoadLibraryW
GetProcAddress = kernel32.GetProcAddress
GetProcAddress.restype = ctypes.c_ulonglong  # Use c_ulonglong for 64-bit RVA
FreeLibrary = kernel32.FreeLibrary
# -----------------------------------------------

def find_duckstation_pid() -> int | None:
    """Find DuckStation process PID"""
    return find_emulator_pid("duckstation", "DuckStation")

def get_ram_base_address_ctypes(pid: int = None) -> int:
    """
    Finds the base address of the PlayStation RAM in the DuckStation process
    using ctypes and a low-level PID lookup.

    Args:
        pid: Optional process ID. If provided, skips process scanning.
    """
    ram_base_address = 0
    proc_handle = None

    # 1. Resolve the DuckStation PID
    if pid is not None:
        duckstation_pid = pid
    else:
        duckstation_pid = find_duckstation_pid()

    if not duckstation_pid:
        print("Error: No DuckStation process found.")
        return 0

    # 2. Create a psutil.Process object only AFTER we know the PID
    try:
        duckstation_proc = psutil.Process(duckstation_pid)
        print(f"Found DuckStation process: {duckstation_proc.name()} (PID: {duckstation_pid})")
    except psutil.NoSuchProcess:
        print(f"Error: DuckStation process with PID {duckstation_pid} no longer exists.")
        return 0
    except psutil.AccessDenied:
        print(f"Error: Access denied when creating psutil.Process for PID {duckstation_pid}.")
        return 0

    try:
        # 3. Open the process handle
        proc_handle = OpenProcess(PROCESS_ALL_ACCESS, False, duckstation_pid)
        if not proc_handle:
            print(f"Error: Could not open process with ID {duckstation_pid}. Try running as Administrator.")
            return 0

        # Get the main module executable path
        try:
            main_module_path = duckstation_proc.exe()  # Full path to the EXE
        except psutil.AccessDenied:
            print("Error: Access denied when reading process info.")
            return 0

        # --- Strategy 1: Parse PE Export Table ---
        symbol_rva = find_export_rva(main_module_path, "RAM")
        
        if symbol_rva:
            # Find the actual base address of the running executable module
            main_map = next(
                (m for m in duckstation_proc.memory_maps(grouped=False) 
                 if m.path.lower() == main_module_path.lower()),
                None
            )
            
            if main_map:
                # Convert the hex address string to an integer
                exe_base_addr = int(main_map.addr.split('-')[0], 16)
                
                # Absolute address = Base Address + RVA
                symbol_address = exe_base_addr + symbol_rva 
                
                # Read the *value* at the symbol's address (8 bytes/ulong pointer)
                raw_data = read_process_memory(proc_handle, symbol_address, 8)
                
                if raw_data is not None and len(raw_data) == 8:
                    # Unpack as an 8-byte unsigned integer (Q) little-endian (<)
                    ram_base_address = struct.unpack('<Q', raw_data)[0]
                    print(f"Found RAM Base Address via 'RAM' export: 0x{ram_base_address:X}")
                    return ram_base_address
                else:
                    print("Export found, but failed to read the value at its memory address.")
            else:
                print("Could not find main module's memory map.")

        if ram_base_address == 0:
            print("Failed to find RAM Base Address using both methods.")
        
        return ram_base_address

    finally:
        if proc_handle:
            CloseHandle(proc_handle)