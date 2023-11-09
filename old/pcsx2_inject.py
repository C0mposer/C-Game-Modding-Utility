import ctypes
import os
import psutil
from termcolor import colored

# Define constants
PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40
PROCESS_VM_OPERATION = 0x8
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20

# Define process and file-related constants
process_name = "pcsx2.exe"


# Define addresses
EE_RAM = 0x20000000


# Function to get process ID by a string. It doesn't have to be full, it can just be the start
def get_pid(process_name):
    process_name_lower = process_name.lower()
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        #print(proc.info['name'])
        if proc.info['name'].lower().startswith(process_name_lower):
            return proc.info['pid']
    print(colored("Could not find PID for proccess starting with " + process_name, "red"))
    return None

# Function to write data to process memory
def write_to_process_memory(handle, address, data, size):
    buffer = (ctypes.c_char * size).from_buffer_copy(data)
    bytes_written = ctypes.c_size_t()
    result = ctypes.windll.kernel32.WriteProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_written))
    return result != 0

# Function to change memory protection
def change_memory_protection(handle, address, size, protection):
    old_protection = ctypes.c_ulong()
    ctypes.windll.kernel32.VirtualProtectEx(handle, address, size, protection, ctypes.byref(old_protection))
    return old_protection

def InjectIntoPCSX2(project_path, codecaves, hooks):
    # Open a handle to the process
    mod_file_path = project_path + "/.config/output/final_bins/"
    # List all files in the directory
    bin_files = os.listdir(mod_file_path)
    
    # Get the PID of the target process
    pcsx2_pid = get_pid(process_name)
    if pcsx2_pid is None:
        exit_message = colored("Could not find PCSX2 1.6.0 Process!", "red")
        print(exit_message)
        return "Could not find PCSX2 1.6.0 Process!"
        
    pcsx2_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pcsx2_pid)

    mod_data = {}
    bin_files = os.listdir(mod_file_path)
    for i, mod_file in enumerate(bin_files):
        # Open and read the mod file
        mod_file_path_included = mod_file_path + mod_file
        try:
            with open(mod_file_path_included, 'rb') as mod_file:
                current_mod_file_name =  str(mod_file.name).split("/")[-1].split(".")[0]    #Getting just the filename, because I NEED ITTT lol
                mod_data[current_mod_file_name] = mod_file.read()
                #print("Reading file", current_mod_file_name)
                #print("current mod_data", mod_data)
        except IOError:
            exit_message = colored(f"Failed to open or read {mod_file}", "red")
            print(exit_message)
            return exit_message
        
    for cave in codecaves:
        # Write the mod data to the process
        if write_to_process_memory(pcsx2_handle, (EE_RAM + int(cave[1], base=16)), mod_data[cave[0]], len(mod_data[cave[0]])):
            print(colored(f"Successfully placed custom function code at: {hex(int(cave[1], base=16))}", "yellow"))
    for hook in hooks:
        if write_to_process_memory(pcsx2_handle, (EE_RAM + int(hook[1], base=16)), mod_data[hook[0]], len(mod_data[hook[0]])):
            print(colored(f"Successfully placed custom hook code at: {hex(int(hook[1], base=16))}", "yellow"))
        

    # Close the process handle
    ctypes.windll.kernel32.CloseHandle(pcsx2_handle)
    return "Successfully injected mod into PCSX2!"

    
if __name__ == "__main__":
    project_path = "projects/SpyroAHT"
    code_caves = [('DebugText', '0x0048ADC0', '0x0', ['main.c'])]
    hooks = [('MainHook', '0x002b30ec', '0', ['main_hook.s'])]
    InjectIntoPCSX2(project_path, code_caves, hooks)