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
process_name = "mednafen"


# Define addresses
MAIN_RAM = 0
MAIN_RAM_129 = 0x2003E80
MAIN_RAM_131 = 0x2034E80


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

def InjectIntoEmu(project_path, codecaves, hooks, version):
    if version == "1.29":
        MAIN_RAM = MAIN_RAM_129
    elif version == "1.31":
        MAIN_RAM = MAIN_RAM_131    

    # Open a handle to the process
    mod_file_path = project_path + "/.config/output/final_bins/"
    # List all files in the directory
    bin_files = os.listdir(mod_file_path)
    
    # Get the PID of the target process
    pcsx2_pid = get_pid(process_name)
    if pcsx2_pid is None:
        exit_message = colored("Could not find mednafen Process!", "red")
        print(exit_message)
        return "Could not find mednafen Process!"
        
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
        
        
    #Injecting
    for cave in codecaves:
        # Write the mod data to the process
        address_to_write_to = ctypes.c_ulonglong(MAIN_RAM + int(cave[1].removeprefix("0x80"), base=16))
        #print(hex(MAIN_RAM + int(cave[1], base=16)))
        change_memory_protection(pcsx2_handle, address_to_write_to, len(mod_data[cave[0]]), PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(pcsx2_handle, address_to_write_to, mod_data[cave[0]], len(mod_data[cave[0]])):
            print(colored(f"Successfully placed custom function code at: {hex(int(cave[1], base=16))}", "yellow"))
        else:
            error_code = ctypes.windll.kernel32.GetLastError()
            exit_message = colored(f"Failed to write to memory. Code: {error_code}", "red")
            print(exit_message)
            return exit_message
    for hook in hooks:
        address_to_write_to = ctypes.c_ulonglong(MAIN_RAM + int(hook[1].removeprefix("0x80"), base=16))
        change_memory_protection(pcsx2_handle, address_to_write_to, len(mod_data[hook[0]]), PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(pcsx2_handle, address_to_write_to, mod_data[hook[0]], len(mod_data[hook[0]])):
            print(colored(f"Successfully placed custom hook code at: {hex(int(hook[1], base=16))}", "yellow"))
        

    # Close the process handle
    ctypes.windll.kernel32.CloseHandle(pcsx2_handle)
    return f"Successfully injected mod into mednafen {version}!"

    
if __name__ == "__main__":
    project_path = "projects/SpyroAHT"
    code_caves = [('DebugText', '0x0048ADC0', '0x0', ['main.c'])]
    hooks = [('MainHook', '0x002b30ec', '0', ['main_hook.s'])]
    InjectIntoEmu(project_path, code_caves, hooks)