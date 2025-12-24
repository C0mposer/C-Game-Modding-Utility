# services/emulator_pid_utils.py
"""
Generic emulator PID finding utilities.
Consolidates duplicate PID finding logic from individual emulator services.
"""

from typing import Optional
from services.pid_service import get_pid_by_prefix


def find_emulator_pid(process_prefix: str, emulator_name: str) -> Optional[int]:
    """
    Find the PID of an emulator process by name prefix.

    Args:
        process_prefix: Process name prefix to search for (e.g., "pcsx2", "duckstation")
        emulator_name: Human-readable emulator name for logging (e.g., "PCSX2", "DuckStation")

    Returns:
        Process ID if found, None otherwise
    """
    try:
        pid = get_pid_by_prefix(process_prefix)
        if pid:
            print(f"Found {emulator_name} process (PID: {pid})")
        else:
            print(f"{emulator_name} process not found.")
        return pid
    except OSError as e:
        print(f"Error while searching for {emulator_name} process: {e}")
        return None
