import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize",           wintypes.DWORD),
        ("cntUsage",         wintypes.DWORD),
        ("th32ProcessID",    wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID",     wintypes.DWORD),
        ("cntThreads",       wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase",   ctypes.c_long),
        ("dwFlags",          wintypes.DWORD),
        ("szExeFile",        wintypes.WCHAR * MAX_PATH),
    ]

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype  = wintypes.HANDLE

Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32FirstW.restype  = wintypes.BOOL

Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32NextW.restype  = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype  = wintypes.BOOL


def iter_processes():
    """Yield (pid, exe_name) for all processes using Toolhelp32Snapshot."""
    h_snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h_snapshot == wintypes.HANDLE(-1).value:
        raise OSError("CreateToolhelp32Snapshot failed")

    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

        success = Process32FirstW(h_snapshot, ctypes.byref(entry))
        if not success:
            raise OSError("Process32FirstW failed")

        while success:
            pid = entry.th32ProcessID
            name = entry.szExeFile
            yield pid, name
            success = Process32NextW(h_snapshot, ctypes.byref(entry))
    finally:
        CloseHandle(h_snapshot)


def get_pid_by_prefix(prefix: str):
    prefix = prefix.lower()
    for pid, name in iter_processes():
        if name and name.lower().startswith(prefix):
            # print(name, pid)  # debug
            return pid
    return None