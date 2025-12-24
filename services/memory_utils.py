# services/memory_utils.py
"""
Consolidated memory read/write utilities for Windows process memory operations.
Used by emulator services (PCSX2, DuckStation, etc.) for memory access.
"""

import ctypes
import ctypes.wintypes
from typing import Optional

# --- Windows API Definitions (Kernel32.dll) ---
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Define necessary Win32 types and constants
SIZE_T = ctypes.c_size_t
DWORD = ctypes.wintypes.DWORD
HANDLE = ctypes.wintypes.HANDLE
LPCVOID = ctypes.wintypes.LPCVOID
LPVOID = ctypes.wintypes.LPVOID

# Function Signatures for Process Memory Operations
ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    HANDLE,      # hProcess
    LPCVOID,     # lpBaseAddress
    LPVOID,      # lpBuffer
    SIZE_T,      # nSize
    ctypes.POINTER(SIZE_T)  # lpNumberOfBytesRead
]
ReadProcessMemory.restype = ctypes.wintypes.BOOL

WriteProcessMemory = kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [
    HANDLE,      # hProcess
    LPVOID,      # lpBaseAddress
    LPCVOID,     # lpBuffer
    SIZE_T,      # nSize
    ctypes.POINTER(SIZE_T)  # lpNumberOfBytesWritten
]
WriteProcessMemory.restype = ctypes.wintypes.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx


def read_process_memory(handle: HANDLE, address: int, size: int) -> Optional[bytes]:
    """
    Read memory from a target process using Windows ReadProcessMemory API.

    Args:
        handle: Process handle (from OpenProcess)
        address: Memory address to read from
        size: Number of bytes to read

    Returns:
        Raw bytes read from memory, or None if read fails
    """
    try:
        # Create a buffer of the required size
        buffer = ctypes.create_string_buffer(size)
        bytes_read = SIZE_T(0)

        # Call the Windows API function
        success = ReadProcessMemory(
            handle,
            LPCVOID(address),
            buffer,
            SIZE_T(size),
            ctypes.byref(bytes_read)
        )

        if success and bytes_read.value == size:
            return buffer.raw
        else:
            # Handle cases where memory read fails
            return None
    except Exception:
        return None


def write_process_memory(handle: int, address: int, data: bytes) -> bool:
    """
    Write data to process memory with proper error handling.

    Args:
        handle: Process handle (from OpenProcess)
        address: Memory address to write to
        data: Bytes to write

    Returns:
        True if write succeeded, False otherwise
    """
    size = len(data)

    # Query memory information to see if this region is valid
    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", ctypes.c_ulong),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.c_ulong),
            ("Protect", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
        ]

    mbi = MEMORY_BASIC_INFORMATION()
    result = VirtualQueryEx(
        handle,
        ctypes.c_void_p(address),
        ctypes.byref(mbi),
        ctypes.sizeof(mbi)
    )

    if result == 0:
        return False

    # Check if memory is committed
    MEM_COMMIT = 0x1000
    if mbi.State != MEM_COMMIT:
        return False

    # Create buffer from bytes
    buffer = (ctypes.c_char * size).from_buffer_copy(data)

    # Try direct write
    bytes_written = ctypes.c_size_t()
    write_result = WriteProcessMemory(
        handle,
        ctypes.c_void_p(address),
        buffer,
        size,
        ctypes.byref(bytes_written)
    )

    if write_result and bytes_written.value == size:
        return True

    # Write failed - check if it's due to read-only protection
    PAGE_READONLY = 0x02
    if mbi.Protect == PAGE_READONLY:
        print(f"   Memory write failed - likely due to read-only protection.")
        print(f"   If using an emulator with recompiler, try disabling it.")

    return False
