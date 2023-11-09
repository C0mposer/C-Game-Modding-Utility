import ctypes
import os
import psutil
import cProfile
from termcolor import colored

# Define constants
PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40
PROCESS_VM_OPERATION = 0x8
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20

# Define some data types
DWORD = ctypes.c_uint
HANDLE = ctypes.wintypes.HANDLE
HMODULE = ctypes.wintypes.HMODULE
LPSTR = ctypes.c_char_p
MAX_PATH = 260  # Maximum path length

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

# Define process and file-related constants
process_name = "duckstation"


# Define addresses
MAIN_RAM_PTR_OFFSET = 0x87E6B0


# Function to get process ID by a string. It doesn't have to be full, it can just be the start
def get_pid(process_name):
    process_name_lower = process_name.lower()
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        #print(proc.info['name'])
        if proc.info['name'].lower().startswith(process_name_lower):
            return proc.info['pid']
    print(colored("Could not find PID for proccess starting with " + process_name, "red"))
    return None

def GetBaseAddressFromEXE(process_handle, process_name):
    base_address = None
    
    # Define an array to hold module handles
    module_handles = (HMODULE * 1024)()
    cb_needed = DWORD()

    if psapi.EnumProcessModules(process_handle, module_handles, ctypes.sizeof(module_handles), ctypes.byref(cb_needed)):
        for i in range(cb_needed.value // ctypes.sizeof(HMODULE)):
            module_name = (ctypes.c_char * MAX_PATH)()
            if psapi.GetModuleBaseNameA(process_handle, ctypes.c_ulonglong(module_handles[i]), module_name, MAX_PATH) > 0:
                module_name_str = module_name.value.decode('utf-8')
                if module_name_str.lower() == process_name.lower():
                    base_address = module_handles[i]
                    print(colored(f"Base address of {process_name}: {base_address:X}", "blue"))
                    break
    
    return base_address

# Function to write data to process memory
def write_to_process_memory(handle, address, data, size):
    buffer = (ctypes.c_char * size).from_buffer_copy(data)
    bytes_written = ctypes.c_size_t()
    result = ctypes.windll.kernel32.WriteProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_written))
    return result != 0

def read_process_memory(handle, address, size):
    buffer = (ctypes.c_char * size)()
    bytes_read = ctypes.c_size_t()
    
    result = ctypes.windll.kernel32.ReadProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_read))
    
    if result == 0:
        error_code = ctypes.windll.kernel32.GetLastError()
        print(colored(f"ReadProcessMemory failed with error code: {error_code}", "red"))
        return None
    
    return buffer.raw[:bytes_read.value]

# Function to change memory protection
def change_memory_protection(handle, address, size, protection):
    old_protection = ctypes.c_ulong()
    ctypes.windll.kernel32.VirtualProtectEx(handle, address, size, protection, ctypes.byref(old_protection))
    return old_protection

def Log(project_path, codecaves, hooks):
    cProfile.run("InjectIntoDuckstation()", sort="cumtime")
    

def InjectIntoDuckstation(project_path, codecaves, hooks):
    # Open a handle to the process
    mod_file_path = project_path + "/.config/output/final_bins/"
    # List all files in the directory
    bin_files = os.listdir(mod_file_path)
    
    # Get the PID of the target process
    duckstation_pid = get_pid(process_name)
    if duckstation_pid is None:
        exit_message = colored("Could not find Duckstation Process!", "red")
        print(exit_message)
        return "Could not find Duckstation Process!"
        
    duckstation_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, duckstation_pid)
    
    base_address = GetBaseAddressFromEXE(duckstation_handle, "duckstation-qt-x64-ReleaseLTCG.exe")

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
        
        
    #Get duckstation base address from pointer
    ptr_address = read_process_memory(duckstation_handle, ctypes.c_ulonglong(base_address + MAIN_RAM_PTR_OFFSET), 8)
    try:
        pointer_value = int.from_bytes(ptr_address, byteorder='little', signed=False)  
    except:
        exit_message = colored(f"Failed to read pointer to main ram at value {ptr_address}", "red")
        print(exit_message)
        return f"Failed to read pointer to main ram at value {ptr_address}"
    
    MAIN_RAM = pointer_value    
    print(colored(f"Duckstation base RAM value: {hex(MAIN_RAM)}", "blue"))   
    
    
    #Injecting
    for cave in codecaves:
        # Write the mod data to the process
        address_to_write_to = ctypes.c_ulonglong(MAIN_RAM + int(cave[1].removeprefix("0x80"), base=16))
        #print(MAIN_RAM + int(cave[1], base=16))
        change_memory_protection(duckstation_handle, address_to_write_to, len(mod_data[cave[0]]), PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(duckstation_handle, address_to_write_to, mod_data[cave[0]], len(mod_data[cave[0]])):
            print(colored(f"Successfully placed custom function code at: {hex(int(cave[1], base=16))}", "green"))
        else:
            error_code = ctypes.windll.kernel32.GetLastError()
            print(colored(f"failed to write to memory {error_code}", "red"))
    for hook in hooks:
        address_to_write_to = ctypes.c_ulonglong(MAIN_RAM + int(hook[1].removeprefix("0x80"), base=16))
        change_memory_protection(duckstation_handle, address_to_write_to, len(mod_data[hook[0]]), PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(duckstation_handle, address_to_write_to, mod_data[hook[0]], len(mod_data[hook[0]])):
            print(colored(f"Successfully placed custom hook code at: {hex(int(hook[1], base=16))}", "green"))
        

    # Close the process handle
    ctypes.windll.kernel32.CloseHandle(duckstation_handle)
    
    print(colored(f"Successfully injected mod into duckstation!", "yellow"))
    return "Successfully injected mod into duckstation!"

def Log(project_path, codecaves, hooks):
    cProfile.runctx('InjectIntoDuckstation(project_path, codecaves, hooks)', {'project_path': project_path, 'codecaves': codecaves, 'hooks': hooks, "InjectIntoDuckstation": InjectIntoDuckstation}, {})
    
if __name__ == "__main__":
    project_path = "projects/SpyroAHT"
    code_caves = [('DebugText', '0x0048ADC0', '0x0', ['main.c'])]
    hooks = [('MainHook', '0x002b30ec', '0', ['main_hook.s'])]
    InjectIntoDuckstation(project_path, code_caves, hooks)