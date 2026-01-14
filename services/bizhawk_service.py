import ctypes
import ctypes.wintypes
import psutil
from typing import Optional
from functions.verbose_print import verbose_print

from services.emulator_pid_utils import find_emulator_pid
from services.memory_utils import read_process_memory

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

# Define Win32 types and constants
SIZE_T = ctypes.c_size_t
DWORD = ctypes.wintypes.DWORD
HANDLE = ctypes.wintypes.HANDLE
HMODULE = ctypes.wintypes.HMODULE
LPCVOID = ctypes.wintypes.LPCVOID
LPVOID = ctypes.wintypes.LPVOID

# Define Access Rights for OpenProcess
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)

MAX_PATH = 260

# Function Signatures for Process Handling
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, ctypes.wintypes.BOOL, DWORD]
OpenProcess.restype = HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = ctypes.wintypes.BOOL
# -----------------------------------------------

# First 16 bytes of PS1 main RAM. Hopefully this is enough for no false positives
PS1_RAM_SIGNATURE = bytes.fromhex("03000000800C5A270800400300000000")

def find_bizhawk_pid() -> Optional[int]:
    return find_emulator_pid("EmuHawk", "BizHawk")

def get_module_base_address(handle: HANDLE, module_name: str) -> Optional[int]:
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

def find_ram_base_by_pattern(handle: HANDLE, start_address: int, max_search_size: int = 0x1000000) -> Optional[int]:
    CHUNK_SIZE = 0x10000  # Read 64KB at a time
    pattern = PS1_RAM_SIGNATURE
    pattern_len = len(pattern)

    verbose_print(f" Searching for PS1 RAM pattern starting from 0x{start_address:X}...")

    current_address = start_address
    end_address = start_address + max_search_size

    while current_address < end_address:
        # Read a chunk of memory
        chunk_data = read_process_memory(handle, current_address, CHUNK_SIZE)

        if chunk_data is None:
            # If can't read skip to next chunk
            current_address += CHUNK_SIZE
            continue

        # Search for pattern in this chunk
        offset = chunk_data.find(pattern)

        if offset != -1:
            # Pattern found
            ram_address = current_address + offset
            verbose_print(f" Found PS1 RAM signature at: 0x{ram_address:X}")
            return ram_address

        # Move to next chunk, with overlap to catch patterns at chunk boundaries
        current_address += CHUNK_SIZE - pattern_len

    verbose_print(f" PS1 RAM signature not found within {max_search_size / (1024*1024):.1f} MB search range")
    return None

def get_ram_base_address_ctypes(pid: Optional[int] = None) -> int:
    ram_base_address = 0
    proc_handle = None

    # Get the BizHawk PID
    if pid is not None:
        bizhawk_pid = pid
    else:
        bizhawk_pid = find_bizhawk_pid()

    if not bizhawk_pid:
        verbose_print("Error: No BizHawk (EmuHawk) process found.")
        return 0

    try:
        bizhawk_proc = psutil.Process(bizhawk_pid)
        verbose_print(f"Found BizHawk process: {bizhawk_proc.name()} (PID: {bizhawk_pid})")
    except psutil.NoSuchProcess:
        verbose_print(f"Error: BizHawk process with PID {bizhawk_pid} no longer exists.")
        return 0
    except psutil.AccessDenied:
        verbose_print(f"Error: Access denied when creating psutil.Process for PID {bizhawk_pid}.")
        return 0

    try:
        # Open the process handle
        proc_handle = OpenProcess(PROCESS_ALL_ACCESS, False, bizhawk_pid)
        if not proc_handle:
            verbose_print(f"Error: Could not open process with ID {bizhawk_pid}. Try running as Administrator.")
            return 0

        # Find octoshock.dll base address
        octoshock_base = get_module_base_address(proc_handle, "octoshock.dll")

        if not octoshock_base:
            verbose_print("Error: Could not find octoshock.dll module in BizHawk process.")
            verbose_print("Make sure a PS1 game is loaded in BizHawk.")
            return 0

        print(f" Found octoshock.dll at: 0x{octoshock_base:X}")

        # Search for PS1 RAM signature starting from octoshock.dll
        ram_base_address = find_ram_base_by_pattern(proc_handle, octoshock_base)

        if ram_base_address == 0 or ram_base_address is None:
            verbose_print("Failed to find PS1 RAM base address via pattern matching.")
            return 0

        return ram_base_address

    finally:
        if proc_handle:
            CloseHandle(proc_handle)
