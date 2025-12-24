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
GetProcAddress.restype = ctypes.c_ulonglong # Use c_ulonglong for 64-bit RVA
FreeLibrary = kernel32.FreeLibrary
# -----------------------------------------------

def find_pcsx2_pid() -> int | None:
    """Find PCSX2 process PID"""
    return find_emulator_pid("pcsx2", "PCSX2")

def set_ee_base_address_ctypes() -> int:
    """
    Finds the base address of the Emotion Engine (EE) memory in the PCSX2 process
    using ctypes and a low-level PID lookup.
    """
    ee_base_address = 0
    proc_handle = None

    # 1. Find the process PID using low-level approach
    pcsx2_pid = find_pcsx2_pid()
    if not pcsx2_pid:
        print("Error: PCSX2 process not found.")
        return 0

    # 2. Create a psutil.Process object only AFTER we know the PID
    #    (this is cheap; no full process iteration)
    try:
        pcsx2_proc = psutil.Process(pcsx2_pid)
    except psutil.NoSuchProcess:
        print("Error: PCSX2 process vanished before we could attach.")
        return 0
    except psutil.AccessDenied:
        print("Error: Access denied when creating psutil.Process for PCSX2.")
        return 0

    try:
        # 3. Open the process handle
        proc_handle = OpenProcess(PROCESS_ALL_ACCESS, False, pcsx2_pid)
        if not proc_handle:
            print(f"Error: Could not open process with ID {pcsx2_pid}. Try running as Administrator.")
            return 0

        # Get the main module executable path
        try:
            main_module_path = pcsx2_proc.exe()  # Full path to the EXE
        except psutil.AccessDenied:
            print("Error: Access denied when reading process exe path.")
            return 0

        # --- Strategy 1: Parse PE Export Table ---
        symbol_rva = find_export_rva(main_module_path, "EEmem")
        
        if symbol_rva:
            # Find the actual base address of the running executable module
            main_map = next(
                (m for m in pcsx2_proc.memory_maps(grouped=False) 
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
                    ee_base_address = struct.unpack('<Q', raw_data)[0]
                    print(f"Found EE Base Address via 'EEmem' export: 0x{ee_base_address:X}")
                    return ee_base_address
                else:
                    print("Export found, but failed to read the value at its memory address.")
            else:
                print("Could not find main module's memory map.")

        # --- Strategy 2: Fallback Brute-Force Search ---
        print("'EEmem' export not found or failed. Starting fallback search...")
        
        main_module_map = next(
            (m for m in pcsx2_proc.memory_maps(grouped=False) 
             if m.path.lower() == main_module_path.lower()),
            None
        )
        
        if not main_module_map:
            print("Error: Could not find main module's memory map for fallback.")
            return 0

        base_address = int(main_module_map.addr.split('-')[0], 16)
        
        alignment = 0x10000000
        SIGNATURE = 0x3C1A8001
        
        current = ((base_address + alignment - 1) // alignment) * alignment
        
        for i in range(10): 
            raw_data = read_process_memory(proc_handle, current, 4)
            
            if raw_data is not None and len(raw_data) == 4:
                read_value = struct.unpack('<I', raw_data)[0]
                
                if read_value == SIGNATURE:
                    ee_base_address = current
                    print(f"Found EE Base Address via fallback search at offset {i}: 0x{ee_base_address:X}")
                    return ee_base_address
            
            current += alignment 

        print("Failed to find EE Base Address using both methods within 10 checks.")
        return 0

    finally:
        if proc_handle:
            CloseHandle(proc_handle)
