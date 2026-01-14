from typing import Optional
from services.pid_service import get_pid_by_prefix


def find_emulator_pid(process_prefix: str, emulator_name: str) -> Optional[int]:
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
